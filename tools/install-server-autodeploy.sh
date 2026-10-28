#!/usr/bin/env bash
# Install polling deployment for forest306-qwq/website on Ubuntu + Nginx.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo bash install-server-autodeploy.sh" >&2
  exit 1
fi
deploy_user="${SUDO_USER:-admin}"
if [[ "$deploy_user" == root ]] || ! id "$deploy_user" >/dev/null 2>&1; then
  echo "Run this installer through sudo from the admin account." >&2
  exit 1
fi
webroot=/var/www/html
if [[ -L "$webroot" ]]; then
  echo "/var/www/html is a symlink; review its deployment configuration first." >&2
  exit 1
fi
nginx -t
apt-get update
apt-get install -y git python3 rsync ca-certificates
install -d -m 0755 "$webroot"
# The deploy service runs as the existing admin user, never as root.
chown -R -- "$deploy_user":www-data "$webroot"

cat > /usr/local/bin/forest306-deploy <<'DEPLOY_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
umask 022
state=/var/lib/forest306-deploy
webroot=/var/www/html
repository=https://github.com/forest306-qwq/website.git
cache="$state/repository.git"
exec 9>"$state/deploy.lock"
flock -n 9 || exit 0
if [[ ! -d "$cache" ]]; then
  git init --bare "$cache"
fi
timeout 120 git --git-dir="$cache" fetch --depth=1 --no-tags "$repository" refs/heads/main
revision="$(git --git-dir="$cache" rev-parse --verify 'FETCH_HEAD^{commit}')"
previous="$(cat "$state/deployed-revision" 2>/dev/null || true)"
if [[ "$revision" == "$previous" && -s "$webroot/index.html" && "${1:-}" != --force ]]; then
  echo "Already deployed: $revision"
  exit 0
fi
work="$(mktemp -d "$state/build.XXXXXXXX")"
cleanup() {
  if [[ "$work" == "$state"/build.* && -d "$work" && ! -L "$work" ]]; then
    rm -rf -- "$work"
  fi
}
trap cleanup EXIT
git --git-dir="$cache" archive "$revision" | tar -x -C "$work"
# Fresh snapshots prevent dirty working trees and _site-already-exists errors.
PAGES_BASE_PATH= timeout 120 python3 "$work/tools/build_pages.py"
test -s "$work/_site/index.html"
test -d "$work/_site/assets"
test -d "$work/_site/columns"
# Keep previous replaced files; preserve server-only files and ACME paths.
# Delayed updates reduce partial updates; this is not an atomic directory switch.
rsync -rlt --delay-updates --backup --backup-dir="$state/previous" \
  --chmod=D755,F644 --exclude='/.well-known/' "$work/_site/" "$webroot/"
printf '%s\n' "$revision" > "$state/deployed-revision.next"
mv -- "$state/deployed-revision.next" "$state/deployed-revision"
echo "Deployed successfully: $revision"
DEPLOY_SCRIPT
chmod 0755 /usr/local/bin/forest306-deploy
chown root:root /usr/local/bin/forest306-deploy

cat > /etc/systemd/system/forest306-deploy.service <<SERVICE
[Unit]
Description=Deploy Forest306 website from GitHub
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$deploy_user
Group=www-data
StateDirectory=forest306-deploy
StateDirectoryMode=0750
WorkingDirectory=/var/lib/forest306-deploy
Environment=GIT_TERMINAL_PROMPT=0
Environment=GIT_CONFIG_GLOBAL=/dev/null
Environment=GIT_CONFIG_NOSYSTEM=1
ExecStart=/usr/local/bin/forest306-deploy
TimeoutStartSec=300
UMask=0022
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/www/html
SERVICE
cat > /etc/systemd/system/forest306-deploy.timer <<'TIMER'
[Unit]
Description=Check Forest306 GitHub updates every five minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
AccuracySec=10s
Unit=forest306-deploy.service

[Install]
WantedBy=timers.target
TIMER
systemctl daemon-reload
if ! systemctl start forest306-deploy.service; then
  journalctl -u forest306-deploy.service -n 35 --no-pager
  echo "Initial deployment failed. Resolve the error, then rerun this installer." >&2
  exit 1
fi
systemctl enable --now forest306-deploy.timer
echo "Automatic deployment is enabled. GitHub is checked about every 5 minutes."
echo "The GitHub daily-song schedule remains responsible for choosing songs."
echo "View logs: sudo journalctl -u forest306-deploy.service -n 30 --no-pager"
