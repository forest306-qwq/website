#!/usr/bin/env bash
# Add a server-enforced nickname entrance and private visitor list to nwuc.cn.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Use sudo bash install-server-visitors.sh"; exit 1; }
ref="${1:-main}"
[[ "$ref" == main || "$ref" =~ ^[0-9a-f]{40}$ ]] || exit 1
target=/etc/nginx/sites-available/default
[[ -f "$target" && ! -L "$target" ]] || { echo "Expected the default Nginx site configuration."; exit 1; }
nginx -t
nginx -V 2>&1 | grep -q -- --with-http_auth_request_module || { echo "Nginx needs the auth_request module."; exit 1; }
apt-get update
apt-get install -y gunicorn python3 curl ca-certificates
work="$(mktemp -d /tmp/forest306-visitors.XXXXXXXX)"
changed=0
installed=0
configs=("$target" /etc/nginx/snippets/forest306-visitors.conf /etc/nginx/conf.d/forest306-visitors-limit.conf /etc/nginx/snippets/forest306-counter.conf)
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
    echo "Visitor setup failed; previous Nginx configuration restored." >&2
  fi
  if [[ "$work" == /tmp/forest306-visitors.* && -d "$work" && ! -L "$work" ]]; then
    rm -rf -- "$work"
  fi
}
trap finish EXIT
base="https://raw.githubusercontent.com/forest306-qwq/website/$ref/server"
mkdir -p "$work/visitor"
for file in visitor_service.py configure_visitor_nginx.py check_visitor_ready.py test_visitors.py visitor-nginx.conf; do
  curl --fail --location --retry 2 --connect-timeout 15 --max-time 90 "$base/$file" -o "$work/$file"
done
for file in welcome.html login.html admin.html visitor.js style.css; do
  curl --fail --location --retry 2 --connect-timeout 15 --max-time 90 "$base/visitor/$file" -o "$work/visitor/$file"
done
python3 -m unittest discover -s "$work" -p test_visitors.py
if ! id forestvisitor >/dev/null 2>&1; then
  useradd --system --user-group --home-dir /var/lib/forest306-visitors --no-create-home --shell /usr/sbin/nologin forestvisitor
fi
install -d -m 0755 /opt/forest306-visitors /opt/forest306-visitors/visitor
install -m 0644 "$work/visitor_service.py" /opt/forest306-visitors/visitor_service.py
for file in welcome.html login.html admin.html visitor.js style.css; do
  install -m 0644 "$work/visitor/$file" "/opt/forest306-visitors/visitor/$file"
done
install -d -o forestvisitor -g forestvisitor -m 0700 /var/lib/forest306-visitors
cat > /usr/local/bin/forest306-visitor-password <<'PASSWORD'
#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Use sudo forest306-visitor-password"; exit 1; }
python3 /opt/forest306-visitors/visitor_service.py --set-password
chown forestvisitor:forestvisitor /var/lib/forest306-visitors/admin.json
chmod 0600 /var/lib/forest306-visitors/admin.json
PASSWORD
chmod 0755 /usr/local/bin/forest306-visitor-password
if [[ ! -f /var/lib/forest306-visitors/admin.json ]]; then
  echo "Create your PRIVATE visitor admin password. Do not send it in chat."
  /usr/local/bin/forest306-visitor-password
fi
cat > /etc/systemd/system/forest306-visitors.service <<'SERVICE'
[Unit]
Description=Forest306 nickname entrance and private visitor list
After=network.target

[Service]
User=forestvisitor
Group=forestvisitor
WorkingDirectory=/opt/forest306-visitors
StateDirectory=forest306-visitors
StateDirectoryMode=0700
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/gunicorn --bind 127.0.0.1:8794 --workers 2 --threads 2 --timeout 15 --error-logfile - visitor_service:application
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
systemctl enable forest306-visitors.service
systemctl restart forest306-visitors.service
python3 "$work/check_visitor_ready.py" --backend
mkdir -p "$work/backup" /etc/nginx/snippets
for file in "${configs[@]}"; do
  if [[ -e "$file" ]]; then
    cp -a --parents -- "$file" "$work/backup"
  fi
done
cp -a "$target" "$target.before-visitors-$(date +%Y%m%d%H%M%S)"
changed=1
install -m 0644 "$work/visitor-nginx.conf" /etc/nginx/snippets/forest306-visitors.conf
cat > /etc/nginx/conf.d/forest306-visitors-limit.conf <<'LIMIT'
limit_req_zone $binary_remote_addr zone=forest306_admin_login:1m rate=2r/m;
limit_req_zone $binary_remote_addr zone=forest306_visitor_enter:1m rate=10r/m;
LIMIT
# Aggregate counter reads are public; keep existing counter installer checks working.
python3 - <<'COUNTER'
from pathlib import Path
path = Path('/etc/nginx/snippets/forest306-counter.conf')
if path.is_file():
    text = path.read_text()
    if 'auth_request off;' not in text:
        expected = 'location = /api/site-counter {'
        if text.count(expected) != 1:
            raise SystemExit('Unexpected counter snippet; not changing it automatically.')
        path.write_text(text.replace(expected, expected + '\n    auth_request off;', 1))
COUNTER
python3 "$work/configure_visitor_nginx.py" "$target"
nginx -t
nginx -T > "$work/nginx-active.txt" 2>/dev/null
grep -Fq '# configuration file /etc/nginx/snippets/forest306-visitors.conf:' "$work/nginx-active.txt" || {
  echo "Visitor snippet is not loaded by the active Nginx configuration." >&2
  exit 1
}
systemctl reload nginx
python3 "$work/check_visitor_ready.py"
installed=1
echo "Visitor entrance installed successfully."
echo "Admin: https://nwuc.cn/visitor-admin"
echo "Data: /var/lib/forest306-visitors/visitors.sqlite3"
echo "Reset password: sudo forest306-visitor-password"
