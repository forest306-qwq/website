"""Same-origin site totals. Run behind Nginx using Gunicorn on loopback."""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
import uuid
from functools import lru_cache
from contextlib import closing
from http.cookies import SimpleCookie
from pathlib import Path

HOSTS = {'nwuc.cn', 'www.nwuc.cn'}
COOKIE = 'forest306_visitor'


def create_app(database, secret):
    database = str(database)
    if len(secret) < 32:
        raise ValueError('Counter signing key must contain at least 32 bytes')
    with closing(sqlite3.connect(database, timeout=10)) as db, db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript("""
            CREATE TABLE IF NOT EXISTS totals (id INTEGER PRIMARY KEY CHECK(id=1), pv INTEGER NOT NULL, uv INTEGER NOT NULL);
            INSERT OR IGNORE INTO totals VALUES (1, 0, 0);
            CREATE TABLE IF NOT EXISTS visitors (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, visitor TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS events_created ON events(created);
        """)

    def signature(value):
        return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()

    def decode_cookie(header):
        try:
            cookies = SimpleCookie()
            cookies.load(header)
            token = cookies[COOKIE].value
            value, signed = token.split('.')
            if re.fullmatch(r'[0-9a-f]{32}', value) and hmac.compare_digest(signed, signature(value)):
                return value
        except (KeyError, ValueError):
            pass
        return None

    def app(environ, start_response):
        headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store'),
                   ('X-Content-Type-Options', 'nosniff')]

        def respond(status, data):
            payload = json.dumps(data, separators=(',', ':')).encode()
            start_response(status, headers + [('Content-Length', str(len(payload)))])
            return [payload]

        host = environ.get('HTTP_HOST', '').lower()
        if host not in HOSTS:
            return respond('403 Forbidden', {'success': False})
        if environ.get('PATH_INFO') != '/api/site-counter':
            return respond('404 Not Found', {'success': False})
        method = environ.get('REQUEST_METHOD')
        if method not in ('GET', 'POST'):
            headers.append(('Allow', 'GET, POST'))
            return respond('405 Method Not Allowed', {'success': False})
        event = None
        if method == 'POST':
            if (environ.get('HTTP_ORIGIN') != 'https://' + host
                    or environ.get('HTTP_X_COUNTER_REQUEST') != '1'):
                return respond('403 Forbidden', {'success': False})
            try:
                length = int(environ.get('CONTENT_LENGTH', '0'))
                if not 0 < length <= 512 or environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                    raise ValueError()
                payload = json.loads(environ['wsgi.input'].read(length))
                event = str(uuid.UUID(payload['event']))
                if event != payload['event']:
                    raise ValueError()
            except (ValueError, KeyError, TypeError, AttributeError):
                return respond('400 Bad Request', {'success': False})
        try:
            with closing(sqlite3.connect(database, timeout=10)) as db, db:
                if method == 'POST':
                    db.execute('BEGIN IMMEDIATE')
                    existing = db.execute('SELECT visitor FROM events WHERE id=?', (event,)).fetchone()
                    if existing:
                        visitor = existing[0]
                    else:
                        visitor = decode_cookie(environ.get('HTTP_COOKIE', '')) or uuid.uuid4().hex
                        fingerprint = hashlib.sha256(visitor.encode()).hexdigest()
                        inserted = db.execute('INSERT OR IGNORE INTO visitors VALUES (?)', (fingerprint,)).rowcount
                        db.execute('INSERT INTO events VALUES (?, ?, ?)', (event, visitor, int(time.time())))
                        db.execute('UPDATE totals SET pv=pv+1, uv=uv+? WHERE id=1', (inserted,))
                    db.execute('DELETE FROM events WHERE created < ?', (int(time.time()) - 7 * 86400,))
                    headers.append(('Set-Cookie', COOKIE + '=' + visitor + '.' + signature(visitor)
                                    + '; Domain=nwuc.cn; Path=/; Max-Age=31536000; Secure; HttpOnly; SameSite=Lax'))
                pv, uv = db.execute('SELECT pv, uv FROM totals WHERE id=1').fetchone()
            return respond('200 OK', {'success': True, 'data': {'site_pv': pv, 'site_uv': uv}})
        except sqlite3.Error:
            return respond('503 Service Unavailable', {'success': False})
    return app


@lru_cache(maxsize=1)
def production_app():
    state = Path(os.environ.get('COUNTER_STATE', '/var/lib/forest306-counter'))
    return create_app(state / 'counter.sqlite3', (state / 'secret.key').read_bytes())


def application(environ, start_response):
    return production_app()(environ, start_response)
