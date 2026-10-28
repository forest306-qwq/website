import concurrent.futures
import io
import json
from pathlib import Path
import tempfile
import unittest

from counter_service import create_app
from configure_counter_nginx import configure


class CounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix='.counter-test-')
        self.database = Path(self.temp.name) / 'counter.sqlite3'
        self.app = create_app(self.database, b'a' * 32)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, event=None, cookie='', host='nwuc.cn', origin=None, method=None, app=None):
        method = method or ('POST' if event else 'GET')
        data = json.dumps({'event': event}).encode()
        environ = {'HTTP_HOST': host, 'PATH_INFO': '/api/site-counter', 'REQUEST_METHOD': method,
                   'HTTP_ORIGIN': origin if origin is not None else 'https://' + host,
                   'HTTP_X_COUNTER_REQUEST': '1', 'CONTENT_TYPE': 'application/json',
                   'CONTENT_LENGTH': str(len(data)), 'wsgi.input': io.BytesIO(data), 'HTTP_COOKIE': cookie}
        result = {}
        def start(status, headers):
            result['status'] = status
            result['headers'] = dict(headers)
        result['body'] = json.loads(b''.join((app or self.app)(environ, start)))
        return result

    def event(self, n):
        return f'00000000-0000-4000-8000-{n:012d}'

    def cookie(self, result):
        return result['headers']['Set-Cookie'].split(';')[0]

    def test_shared_cookie_totals_and_restart(self):
        first = self.request(self.event(1))
        self.assertEqual(first['body']['data'], {'site_pv': 1, 'site_uv': 1})
        second = self.request(self.event(2), self.cookie(first), host='www.nwuc.cn')
        self.assertEqual(second['body']['data'], {'site_pv': 2, 'site_uv': 1})
        restarted = create_app(self.database, b'a' * 32)
        self.assertEqual(self.request(app=restarted)['body']['data'], {'site_pv': 2, 'site_uv': 1})
        self.assertIn('Domain=nwuc.cn', second['headers']['Set-Cookie'])
        self.assertIn('HttpOnly', second['headers']['Set-Cookie'])

    def test_retry_without_cookie_does_not_count_twice(self):
        first = self.request(self.event(1))
        again = self.request(self.event(1))
        self.assertEqual(first['body'], again['body'])
        self.assertEqual(self.cookie(first), self.cookie(again))

    def test_new_browser_and_tampered_cookie(self):
        first = self.request(self.event(1))
        result = self.request(self.event(2), self.cookie(first) + 'bad')
        self.assertEqual(result['body']['data'], {'site_pv': 2, 'site_uv': 2})

    def test_read_only_get_rejects_foreign_origin_and_bad_payload(self):
        self.assertEqual(self.request()['body']['data'], {'site_pv': 0, 'site_uv': 0})
        self.assertEqual(self.request(self.event(1), origin='https://evil.example')['status'], '403 Forbidden')
        self.assertEqual(self.request('invalid')['status'], '400 Bad Request')
        self.assertEqual(self.request(host='evil.example')['status'], '403 Forbidden')
        self.assertEqual(self.request()['body']['data'], {'site_pv': 0, 'site_uv': 0})

    def test_concurrent_increments(self):
        first = self.request(self.event(1))
        cookie = self.cookie(first)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda n: self.request(self.event(n), cookie), range(2, 42)))
        self.assertEqual(self.request()['body']['data'], {'site_pv': 41, 'site_uv': 1})


class NginxConfigTests(unittest.TestCase):
    def test_certbot_blocks_and_idempotence(self):
        source = ('# server { server_name nwuc.cn; }\n'
                  'server { listen 443 ssl; server_name nwuc.cn www.nwuc.cn; location / { try_files $uri =404; } }\n'
                  'server { if ($host = nwuc.cn) { return 301 https://$host$request_uri; } server_name nwuc.cn www.nwuc.cn; listen 80; }\n'
                  'server { server_name other.example; location / { return 200 "{"; } }\n')
        output = configure(source)
        self.assertEqual(output.count('include /etc/nginx/snippets/forest306-counter.conf;'), 2)
        self.assertEqual(configure(output), output)
        self.assertIn('server_name other.example; location / { return 200 "{"; }', output)

    def test_missing_site_does_not_write_guess(self):
        with self.assertRaises(ValueError):
            configure('server { server_name other.example; }')


if __name__ == '__main__':
    unittest.main()
