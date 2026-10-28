import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from visitor_service import VisitorApp, set_password, GUEST_COOKIE, ADMIN_COOKIE, MONTH
from configure_visitor_nginx import configure


class VisitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        self.now = 1800000000
        set_password(self.state, 'test-only-password-123')
        self.app = VisitorApp(self.state, clock=lambda: self.now)

    def request(self, path, method='GET', data=None, cookies='', host='nwuc.cn', origin=None, app=None):
        payload = json.dumps(data).encode() if data is not None else b''
        env = {'PATH_INFO': path, 'REQUEST_METHOD': method, 'HTTP_HOST': host,
               'QUERY_STRING': '', 'HTTP_COOKIE': cookies, 'wsgi.input': io.BytesIO(payload),
               'CONTENT_LENGTH': str(len(payload)), 'CONTENT_TYPE': 'application/json',
               'HTTP_ORIGIN': origin or 'https://' + host, 'HTTP_X_VISITOR_REQUEST': '1'}
        result = {}
        body = b''.join((app or self.app)(env, lambda status, headers: result.update(status=status, headers=dict(headers))))
        result['body'] = body.decode()
        return result

    def register(self, nickname='小森林'):
        result = self.request('/_visitor/enter', 'POST', {'nickname': nickname})
        self.assertEqual(result['status'], '200 OK')
        return result['headers']['Set-Cookie'].split(';')[0]

    def login(self):
        result = self.request('/_visitor/admin-login', 'POST', {'password': 'test-only-password-123'})
        self.assertEqual(result['status'], '200 OK')
        return result['headers']['Set-Cookie'].split(';')[0]

    def test_gate_persistence_cross_domain_expiry(self):
        self.assertEqual(self.request('/_visitor/check')['status'], '401 Unauthorized')
        cookie = self.register()
        for host in ('nwuc.cn', 'www.nwuc.cn'):
            self.assertEqual(self.request('/_visitor/check', cookies=cookie, host=host)['status'], '204 No Content')
        restarted = VisitorApp(self.state, clock=lambda: self.now)
        self.assertEqual(self.request('/_visitor/session', cookies=cookie, app=restarted)['status'], '204 No Content')
        self.now += MONTH + 1
        self.assertEqual(self.request('/_visitor/check', cookies=cookie)['status'], '401 Unauthorized')

    def test_validation_tampering_origin_and_no_duplicate_when_registered(self):
        for value in ('', '  ', 'a' * 25, 'abc\nxyz', '\u202eabc', None, '\u200b'):
            self.assertEqual(self.request('/_visitor/enter', 'POST', {'nickname': value})['status'], '400 Bad Request')
        self.assertEqual(self.request('/_visitor/enter', 'POST', {'nickname': 'test'}, origin='https://evil.test')['status'], '403 Forbidden')
        self.assertEqual(self.request('/_visitor/enter')['status'], '405 Method Not Allowed')
        cookie = self.register('朋友🌲')
        self.request('/_visitor/enter', 'POST', {'nickname': '重试'}, cookies=cookie)
        with closing(self.app.connect()) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT nickname FROM visitors').fetchone()[0], '朋友🌲')
        self.assertEqual(self.request('/_visitor/check', cookies=cookie[:-1] + 'x')['status'], '401 Unauthorized')

    def test_private_admin_logout_password_change_and_xss(self):
        self.register('<svg onload=alert(1)>')
        public = self.request('/visitor-admin')
        self.assertNotIn('alert(1)', public['body'])
        self.assertEqual(self.request('/_visitor/admin-login', 'POST', {'password': 'wrong'})['status'], '401 Unauthorized')
        cookie = self.login()
        private = self.request('/visitor-admin', cookies=cookie)
        self.assertIn('&lt;svg onload=alert(1)&gt;', private['body'])
        self.assertNotIn('<svg onload=alert(1)>', private['body'])
        self.assertEqual(self.request('/_visitor/check', cookies=cookie)['status'], '204 No Content')
        self.request('/_visitor/admin-logout', 'POST', {}, cookies=cookie)
        self.assertNotIn('&lt;svg', self.request('/visitor-admin', cookies=cookie)['body'])
        cookie = self.login()
        set_password(self.state, 'new-test-password-456')
        self.assertNotIn('&lt;svg', self.request('/visitor-admin', cookies=cookie)['body'])

    def test_last_seen_is_throttled_and_unique_visitors_are_not_names(self):
        cookie = self.register('同名')
        self.register('同名')
        self.now += 299
        self.request('/_visitor/check', cookies=cookie)
        with closing(self.app.connect()) as db:
            self.assertEqual(db.execute('SELECT MIN(last_seen) FROM visitors').fetchone()[0], self.now - 299)
        self.now += 1
        self.request('/_visitor/check', cookies=cookie)
        with closing(self.app.connect()) as db:
            self.assertEqual(db.execute('SELECT MAX(last_seen) FROM visitors').fetchone()[0], self.now)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visitors').fetchone()[0], 2)

    def test_concurrency_pagination_and_cookie_security(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.register('访客' + str(n)), range(53)))
        cookie = self.login()
        response = self.request('/visitor-admin', cookies=cookie)
        self.assertIn('第 1 / 2 页', response['body'])
        for attribute in ('Secure', 'HttpOnly', 'SameSite=Lax', 'Domain=nwuc.cn'):
            self.assertIn(attribute, self.request('/_visitor/enter', 'POST', {'nickname': '安全'})['headers']['Set-Cookie'])
        with closing(self.app.connect()) as db:
            stored = db.execute('SELECT token_hash FROM visitors LIMIT 1').fetchone()[0]
        self.assertNotIn(stored, response['body'])
        self.assertEqual(response['headers']['Cache-Control'], 'no-store')

    def test_templates_and_public_routes_do_not_expose_data(self):
        self.assertIn('不会公开展示', self.request('/_visitor/welcome')['body'])
        self.assertEqual(self.request('/_visitor/health')['body'], '{"ready": true}')
        self.assertEqual(self.request('/_visitor/../admin.json')['status'], '404 Not Found')
        self.assertEqual(self.request('/_visitor/health', host='evil.test')['status'], '400 Bad Request')

    def test_nginx_preserves_certbot_counter_and_is_idempotent(self):
        original = '''server { listen 443 ssl; server_name nwuc.cn www.nwuc.cn;
 ssl_certificate /etc/letsencrypt/live/nwuc.cn/fullchain.pem;
 include /etc/nginx/snippets/forest306-counter.conf;
 location / { try_files $uri $uri/ =404; }
} server { listen 80; server_name nwuc.cn www.nwuc.cn; return 301 https://$host$request_uri; }
server { listen 8080; server_name other.test; return 200 'other'; }'''
        output = configure(original)
        self.assertEqual(output.count('include /etc/nginx/snippets/forest306-visitors.conf;'), 2)
        self.assertEqual(configure(output), output)
        self.assertIn('ssl_certificate /etc/letsencrypt/live/nwuc.cn/fullchain.pem;', output)
        self.assertIn('include /etc/nginx/snippets/forest306-counter.conf;', output)
        self.assertTrue(output.endswith("server { listen 8080; server_name other.test; return 200 'other'; }"))
        with self.assertRaises(ValueError):
            configure('server { server_name other.test; }')
        with self.assertRaises(ValueError):
            configure('server { server_name nwuc.cn; auth_request /old; }')


if __name__ == '__main__':
    unittest.main()
