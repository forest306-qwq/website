"""Check the entrance and admin routes without registering a synthetic visitor."""
import argparse
import json
import subprocess
import time


def get(path, host='nwuc.cn', backend=False):
    command = ['curl', '--noproxy', '*', '--silent', '--show-error', '--max-time', '3',
               '--max-filesize', '65536', '--write-out', '\n%{http_code}']
    if backend:
        command += ['--header', 'Host: nwuc.cn', 'http://127.0.0.1:8794' + path]
    else:
        command += ['--resolve', host + ':443:127.0.0.1', 'https://' + host + path]
    result = subprocess.run(command, capture_output=True, timeout=5)
    body, _, status = result.stdout.rpartition(b'\n')
    if result.returncode:
        raise ValueError('connection/TLS error: curl ' + str(result.returncode))
    return status.decode('ascii'), body.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', action='store_true')
    args = parser.parse_args()
    consecutive = 0
    problem = 'not ready'
    for attempt in range(15):
        try:
            if args.backend:
                status, body = get('/_visitor/health', backend=True)
                assert status == '200' and json.loads(body).get('ready') is True, 'backend health failed'
                status, _ = get('/_visitor/check', backend=True)
                assert status == '401', 'anonymous backend authorization should be denied'
            else:
                for host in ('nwuc.cn', 'www.nwuc.cn'):
                    for path in ('/index.html', '/diary.html', '/assets/style.css'):
                        status, body = get(path, host)
                        assert status == '200' and 'id="visitor-welcome"' in body, host + path + ': entrance was not enforced (HTTP ' + status + ')'
                    status, body = get('/visitor-admin', host)
                    assert status == '200' and 'data-kind="admin"' in body, host + ': admin login missing'
                    status, _ = get('/_forest306_visitor_check', host)
                    assert status == '404', host + ': internal authorization URL is exposed'
            consecutive += 1
            if consecutive >= 2:
                print('Visitor entrance readiness checks passed. No visitor record was added.')
                return
        except (AssertionError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            problem = str(error)
            consecutive = 0
        if attempt < 14:
            time.sleep(1)
    raise SystemExit('Visitor entrance is not ready: ' + problem)


if __name__ == '__main__':
    main()
