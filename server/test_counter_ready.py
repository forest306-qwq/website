import json
import subprocess
import unittest
from types import SimpleNamespace

from check_counter_ready import HOSTS, probe, valid_counts, wait_for_ready


GOOD = {'success': True, 'data': {'site_pv': 7, 'site_uv': 3}}


class ReadyTests(unittest.TestCase):
    def test_stale_404_after_reload_then_ready(self):
        rounds = 0
        def check(host):
            nonlocal rounds
            rounds += 1
            return (False, 'HTTP 404') if rounds <= 2 else (True, 'ready')
        waits = []
        passed, _ = wait_for_ready(check, HOSTS, sleep=waits.append)
        self.assertTrue(passed)
        self.assertEqual(rounds, 6)
        self.assertEqual(waits, [1, 1])

    def test_one_lucky_response_does_not_mask_stale_workers(self):
        answers = iter([(False, 'HTTP 404'), (True, 'ready'), (False, 'HTTP 404'),
                        (True, 'ready'), (True, 'ready')])
        passed, _ = wait_for_ready(lambda _: next(answers), ('host',), sleep=lambda _: None)
        self.assertTrue(passed)

    def test_persistent_error_and_www_failure_are_not_reported_as_success(self):
        passed, details = wait_for_ready(
            lambda host: (False, 'HTTP 404') if host.startswith('www') else (True, 'ready'),
            HOSTS, attempts=3, sleep=lambda _: None)
        self.assertFalse(passed)
        self.assertEqual(details['www.nwuc.cn'], (False, 'HTTP 404'))

    def test_curl_checks_local_route_using_real_hostname_and_keeps_tls_validation(self):
        def run(args, **kwargs):
            self.assertIn('www.nwuc.cn:443:127.0.0.1', args)
            self.assertIn('https://www.nwuc.cn/api/site-counter', args)
            self.assertNotIn('--insecure', args)
            self.assertNotIn('--data', args)
            return SimpleNamespace(returncode=0, stdout=json.dumps(GOOD) + '\n200')
        self.assertEqual(probe('www.nwuc.cn', run=run), (True, 'ready'))

    def test_backend_uses_read_only_get_and_correct_host(self):
        def run(args, **kwargs):
            self.assertIn('Host: nwuc.cn', args)
            self.assertIn('http://127.0.0.1:8793/api/site-counter', args)
            self.assertNotIn('--data', args)
            return SimpleNamespace(returncode=0, stdout=json.dumps(GOOD) + '\n200')
        self.assertEqual(probe('backend', backend=True, run=run), (True, 'ready'))

    def test_transport_http_and_json_failures(self):
        for response, reason in [
            (SimpleNamespace(returncode=60, stdout=''), 'TLS'),
            (SimpleNamespace(returncode=0, stdout='<html>404</html>\n404'), '404'),
            (SimpleNamespace(returncode=0, stdout='<html>home page</html>\n200'), 'invalid'),
            (SimpleNamespace(returncode=0, stdout='{"success":true}\n200'), 'invalid')
        ]:
            ok, message = probe('nwuc.cn', run=lambda *a, **kw: response)
            self.assertFalse(ok)
            self.assertIn(reason, message)
        self.assertFalse(probe('nwuc.cn', run=lambda *a, **kw: (_ for _ in ()).throw(
            subprocess.TimeoutExpired('curl', 5)))[0])

    def test_counter_response_requires_real_nonnegative_integer_totals(self):
        self.assertTrue(valid_counts(GOOD))
        for value in ([], {}, {'success': True, 'data': {'site_pv': True, 'site_uv': 0}},
                      {'success': True, 'data': {'site_pv': -1, 'site_uv': 0}}):
            self.assertFalse(valid_counts(value))


if __name__ == '__main__':
    unittest.main()
