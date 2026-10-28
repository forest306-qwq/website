"""Nickname entrance and private visitor list for nwuc.cn. No IP addresses are stored."""
import argparse
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import parse_qs

HOSTS = {'nwuc.cn', 'www.nwuc.cn'}
GUEST_COOKIE = '__Secure-forest306_guest'
ADMIN_COOKIE = '__Secure-forest306_admin'
MONTH = 30 * 86400
ADMIN_LIFETIME = 12 * 3600
CHINA = timezone(timedelta(hours=8))
SCHEMA = '''
CREATE TABLE IF NOT EXISTS visitors (
 id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
 nickname TEXT NOT NULL, joined INTEGER NOT NULL,
 last_seen INTEGER NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS admin_sessions (
 token_hash TEXT PRIMARY KEY, expires INTEGER NOT NULL, version TEXT NOT NULL);
'''


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def set_password(state, password):
    if len(password) < 12 or len(password) > 200:
        raise ValueError('Please use a password of 12 to 200 characters.')
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    value = json.dumps({'salt': salt.hex(), 'hash': hashed})
    target = state / 'admin.json'
    temporary = state / ('admin.' + secrets.token_hex(8) + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as file:
            file.write(value)
        temporary.chmod(0o600)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def clean_name(value):
    if not isinstance(value, str):
        raise ValueError('请填写昵称。')
    value = unicodedata.normalize('NFC', value).strip()
    if not 1 <= len(value) <= 24 or not any(c.isalnum() or unicodedata.category(c)[0] in 'PS' for c in value):
        raise ValueError('昵称请填写 1–24 个字符。')
    if any(unicodedata.category(c) in {'Cc', 'Cs'} or
           unicodedata.bidirectional(c) in {'LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'LRI', 'RLI', 'FSI', 'PDI'}
           for c in value):
        raise ValueError('昵称不能含有换行或控制字符。')
    return value


def cookie_token(environ, name):
    jar = SimpleCookie()
    try:
        jar.load(environ.get('HTTP_COOKIE', ''))
        token = jar[name].value if name in jar else ''
        return token if len(token) == 64 and all(c in '0123456789abcdef' for c in token) else ''
    except CookieError:
        return ''


def cookie(name, value, lifetime):
    return (name + '=' + value + '; Path=/; Domain=nwuc.cn; Max-Age=' + str(lifetime) +
            '; Secure; HttpOnly; SameSite=Lax')


class VisitorApp:
    def __init__(self, state, assets=None, clock=time.time):
        self.state = Path(state)
        self.state.mkdir(parents=True, exist_ok=True)
        self.database = self.state / 'visitors.sqlite3'
        self.assets = Path(assets or Path(__file__).parent / 'visitor')
        self.clock = clock
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)

    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def credentials(self):
        raw = (self.state / 'admin.json').read_bytes()
        return json.loads(raw), hashlib.sha256(raw).hexdigest()

    def guest(self, environ):
        token = cookie_token(environ, GUEST_COOKIE)
        if not token:
            return None
        now = int(self.clock())
        with closing(self.connect()) as db, db:
            visitor = db.execute('SELECT * FROM visitors WHERE token_hash=? AND expires>?',
                                 (digest(token), now)).fetchone()
            if visitor and now - visitor['last_seen'] >= 300:
                db.execute('UPDATE visitors SET last_seen=? WHERE id=?', (now, visitor['id']))
            return visitor

    def admin(self, environ):
        token = cookie_token(environ, ADMIN_COOKIE)
        if not token:
            return False
        _, version = self.credentials()
        with closing(self.connect()) as db:
            return db.execute('SELECT 1 FROM admin_sessions WHERE token_hash=? AND expires>? AND version=?',
                              (digest(token), int(self.clock()), version)).fetchone() is not None

    def page(self, filename, **values):
        text = (self.assets / filename).read_text(encoding='utf-8')
        return re.sub(r'\{\{(\w+)\}\}', lambda match: values.get(match[1], match[0]), text)

    def dashboard(self, query):
        try:
            page = max(1, min(1000000, int(parse_qs(query).get('page', ['1'])[0])))
        except (ValueError, TypeError):
            page = 1
        now = datetime.fromtimestamp(self.clock(), CHINA)
        today = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        with closing(self.connect()) as db:
            total = db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0]
            new = db.execute('SELECT COUNT(*) FROM visitors WHERE joined>=?', (today,)).fetchone()[0]
            pages = max(1, (total + 49) // 50)
            page = min(page, pages)
            visitors = db.execute('SELECT nickname,joined,last_seen FROM visitors ORDER BY joined DESC,id DESC LIMIT 50 OFFSET ?',
                                  ((page - 1) * 50,)).fetchall()
        def stamp(value):
            return datetime.fromtimestamp(value, CHINA).strftime('%Y-%m-%d %H:%M')
        rows = ''.join('<tr><td class="nickname">' + html.escape(row['nickname']) + '</td><td>' +
                       stamp(row['joined']) + '</td><td>' + stamp(row['last_seen']) + '</td></tr>' for row in visitors)
        if not rows:
            rows = '<tr><td colspan="3" class="empty">还没有访客填写昵称。</td></tr>'
        navigation = (('<a href="?page=' + str(page - 1) + '">上一页</a>' if page > 1 else '') +
                      '<span>第 ' + str(page) + ' / ' + str(pages) + ' 页</span>' +
                      ('<a href="?page=' + str(page + 1) + '">下一页</a>' if page < pages else ''))
        return self.page('admin.html', rows=rows, total=str(total), today=str(new), navigation=navigation)

    def __call__(self, environ, start_response):
        def respond(status, body=b'', content_type='application/json; charset=utf-8', extra=()):
            if isinstance(body, dict):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            elif isinstance(body, str):
                body = body.encode('utf-8')
            headers = [('Content-Type', content_type), ('Content-Length', str(len(body))),
                       ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                       ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'same-origin'),
                       ('X-Robots-Tag', 'noindex, nofollow'), ('Vary', 'Cookie'),
                       ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; "
                        "img-src 'self'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")]
            start_response(status, headers + list(extra))
            return [b'' if environ.get('REQUEST_METHOD') == 'HEAD' else body]

        path = environ.get('PATH_INFO', '')
        method = environ.get('REQUEST_METHOD', 'GET')
        if environ.get('HTTP_HOST', '').lower() not in HOSTS:
            return respond('400 Bad Request', {'error': '域名不正确。'})
        try:
            if path == '/_visitor/health' and method in {'GET', 'HEAD'}:
                with closing(self.connect()) as db:
                    db.execute('SELECT 1 FROM visitors LIMIT 1')
                self.credentials()
                return respond('200 OK', {'ready': True})
            if path in {'/_visitor/check', '/_visitor/session'} and method in {'GET', 'HEAD'}:
                allowed = self.guest(environ) is not None or self.admin(environ)
                return respond('204 No Content' if allowed else '401 Unauthorized')
            if path == '/_visitor/welcome' and method in {'GET', 'HEAD'}:
                return respond('200 OK', self.page('welcome.html'), 'text/html; charset=utf-8')
            if path in {'/_visitor/style.css', '/_visitor/visitor.js'} and method in {'GET', 'HEAD'}:
                name = path.rsplit('/', 1)[1]
                return respond('200 OK', (self.assets / name).read_bytes(),
                               'text/css; charset=utf-8' if name.endswith('.css') else 'text/javascript; charset=utf-8')
            if path == '/visitor-admin' and method in {'GET', 'HEAD'}:
                content = self.dashboard(environ.get('QUERY_STRING', '')) if self.admin(environ) else self.page('login.html')
                return respond('200 OK', content, 'text/html; charset=utf-8')
            if path not in {'/_visitor/enter', '/_visitor/admin-login', '/_visitor/admin-logout'}:
                return respond('404 Not Found', {'error': '页面不存在。'})
            if method != 'POST':
                return respond('405 Method Not Allowed', {'error': '请使用页面中的表单。'}, extra=[('Allow', 'POST')])
            if (environ.get('HTTP_ORIGIN') != 'https://' + environ['HTTP_HOST'].lower() or
                    environ.get('HTTP_X_VISITOR_REQUEST') != '1'):
                return respond('403 Forbidden', {'error': '请从本站页面提交。'})
            if environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                return respond('400 Bad Request', {'error': '提交格式不正确。'})
            length = int(environ.get('CONTENT_LENGTH') or '0')
            if not 0 < length <= 1024:
                return respond('413 Content Too Large', {'error': '填写的内容过长。'})
            try:
                data = json.loads(environ['wsgi.input'].read(length))
            except (ValueError, UnicodeError):
                return respond('400 Bad Request', {'error': '提交格式不正确。'})
            if not isinstance(data, dict):
                return respond('400 Bad Request', {'error': '提交格式不正确。'})
            now = int(self.clock())
            if path == '/_visitor/enter':
                if self.guest(environ):
                    return respond('200 OK', {'ok': True})
                try:
                    nickname = clean_name(data.get('nickname'))
                except ValueError as error:
                    return respond('400 Bad Request', {'error': str(error)})
                token = secrets.token_hex(32)
                with closing(self.connect()) as db, db:
                    db.execute('INSERT INTO visitors(token_hash,nickname,joined,last_seen,expires) VALUES(?,?,?,?,?)',
                               (digest(token), nickname, now, now, now + MONTH))
                return respond('200 OK', {'ok': True}, extra=[('Set-Cookie', cookie(GUEST_COOKIE, token, MONTH))])
            if path == '/_visitor/admin-login':
                password = data.get('password')
                if not isinstance(password, str) or not 1 <= len(password) <= 200:
                    return respond('400 Bad Request', {'error': '请输入后台密码。'})
                credentials, version = self.credentials()
                actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(credentials['salt']), n=16384, r=8, p=1).hex()
                if not hmac.compare_digest(actual, credentials['hash']):
                    return respond('401 Unauthorized', {'error': '密码不正确。'})
                token = secrets.token_hex(32)
                with closing(self.connect()) as db, db:
                    db.execute('DELETE FROM admin_sessions WHERE expires<=? OR version<>?', (now, version))
                    db.execute('INSERT INTO admin_sessions VALUES(?,?,?)', (digest(token), now + ADMIN_LIFETIME, version))
                return respond('200 OK', {'ok': True}, extra=[('Set-Cookie', cookie(ADMIN_COOKIE, token, ADMIN_LIFETIME))])
            if not self.admin(environ):
                return respond('403 Forbidden', {'error': '请先登录后台。'})
            with closing(self.connect()) as db, db:
                db.execute('DELETE FROM admin_sessions WHERE token_hash=?', (digest(cookie_token(environ, ADMIN_COOKIE)),))
            return respond('200 OK', {'ok': True}, extra=[('Set-Cookie', cookie(ADMIN_COOKIE, '', 0))])
        except (sqlite3.Error, OSError, ValueError, KeyError):
            return respond('503 Service Unavailable', {'error': '服务暂时不可用，请稍后重试。'})


_app = None


def application(environ, start_response):
    global _app
    if _app is None:
        _app = VisitorApp(os.environ.get('FOREST_VISITOR_STATE', '/var/lib/forest306-visitors'))
    return _app(environ, start_response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--set-password', action='store_true')
    parser.add_argument('--state', default='/var/lib/forest306-visitors')
    args = parser.parse_args()
    if args.set_password:
        from getpass import getpass
        first = getpass('Set visitor admin password (12+ characters): ')
        second = getpass('Repeat password: ')
        if first != second:
            raise SystemExit('Passwords differ. Nothing changed.')
        try:
            set_password(args.state, first)
        except ValueError as error:
            raise SystemExit(str(error))
        print('Admin password saved. Previous admin sessions are now invalid.')
