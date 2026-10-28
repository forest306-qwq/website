#!/usr/bin/env bash
# Install the nwuc.cn counter, preserving Nginx HTTPS and durable counter data.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Use sudo bash install-server-counter.sh"; exit 1; }
ref="${1:-main}"
[[ "$ref" == main || "$ref" =~ ^[0-9a-f]{40}$ ]] || exit 1
target=/etc/nginx/sites-available/default
[[ -f "$target" && ! -L "$target" ]] || { echo "Expected the default Nginx site configuration."; exit 1; }
nginx -t
apt-get update
apt-get install -y gunicorn python3 curl ca-certificates
work="$(mktemp -d /tmp/forest306-counter.XXXXXXXX)"
changed=0
installed=0
configs=("$target" /etc/nginx/snippets/forest306-counter.conf /etc/nginx/conf.d/forest306-counter-limit.conf)
finish() {
  if [[ "$changed" == 1 && "$installed" != 1 ]]; then
    for file in "${configs[@]}"; do
      if [[ -e "$work/backup$file" ]]; then
        cp -a -- "$work/backup$file" "$file"
      else
        rm -f -- "$file"
      fi
    done
    nginx -t && systemctl reload nginx || true
    echo "Counter setup failed; previous Nginx configuration restored." >&2
  fi
  if [[ "$work" == /tmp/forest306-counter.* && -d "$work" && ! -L "$work" ]]; then
    rm -rf -- "$work"
  fi
}
trap finish EXIT
base="https://raw.githubusercontent.com/forest306-qwq/website/$ref/server"
for file in counter_service.py configure_counter_nginx.py check_counter_ready.py test_counter.py test_counter_ready.py; do
  curl --fail --location --retry 2 --connect-timeout 15 --max-time 90 "$base/$file" -o "$work/$file"
done
python3 -m unittest discover -s "$work" -p 'test_counter*.py'
if ! id forestcounter >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /var/lib/forest306-counter --no-create-home --shell /usr/sbin/nologin forestcounter
fi
install -d -m 0755 /opt/forest306-counter
install -m 0644 "$work/counter_service.py" /opt/forest306-counter/counter_service.py
install -d -o forestcounter -g forestcounter -m 0700 /var/lib/forest306-counter
python3 - <<'SECRET'
import os
from pathlib import Path
p = Path('/var/lib/forest306-counter/secret.key')
try:
    with p.open('xb') as f:
        f.write(os.urandom(32))
except FileExistsError:
    if len(p.read_bytes()) != 32:
        raise SystemExit('Existing signing key is invalid; not replacing it.')
p.chmod(0o600)
SECRET
chown forestcounter:forestcounter /var/lib/forest306-counter/secret.key
cat > /etc/systemd/system/forest306-counter.service <<'SERVICE'
[Unit]
Description=Forest306 private site counter
After=network.target

[Service]
User=forestcounter
Group=forestcounter
WorkingDirectory=/opt/forest306-counter
StateDirectory=forest306-counter
StateDirectoryMode=0700
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/gunicorn --bind 127.0.0.1:8793 --workers 2 --threads 2 --timeout 15 --error-logfile - counter_service:application
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable forest306-counter.service
systemctl restart forest306-counter.service
python3 "$work/check_counter_ready.py" --backend
mkdir -p "$work/backup" /etc/nginx/snippets
for file in "${configs[@]}"; do
  if [[ -e "$file" ]]; then
    cp -a --parents -- "$file" "$work/backup"
  fi
done
# Save a persistent copy of the site config outside sites-enabled.
cp -a "$target" "$target.before-counter-$(date +%Y%m%d%H%M%S)"
changed=1
cat > /etc/nginx/conf.d/forest306-counter-limit.conf <<'LIMIT'
limit_req_zone $binary_remote_addr zone=forest306_counter:1m rate=5r/s;
LIMIT
cat > /etc/nginx/snippets/forest306-counter.conf <<'LOCATION'
location = /api/site-counter {
    # Public aggregate counts remain compatible with the optional nickname entrance.
    auth_request off;
    limit_req zone=forest306_counter burst=10 nodelay;
    limit_req_status 429;
    client_max_body_size 1k;
    proxy_pass http://127.0.0.1:8793;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 3s;
    proxy_read_timeout 15s;
    proxy_cache off;
    access_log off;
}
LOCATION
python3 "$work/configure_counter_nginx.py" "$target"
nginx -t
nginx -T > "$work/nginx-active.txt" 2>/dev/null
if ! grep -Fq '# configuration file /etc/nginx/snippets/forest306-counter.conf:' "$work/nginx-active.txt"; then
  echo "Counter snippet is not loaded by the active Nginx configuration; site config needs review." >&2
  exit 1
fi
systemctl reload nginx
python3 "$work/check_counter_ready.py"
installed=1
echo "Counter installed successfully."
echo "Data: /var/lib/forest306-counter/counter.sqlite3"
echo "Automatic website deployment will load the new footer script within about 5 minutes."
