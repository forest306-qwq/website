"""Wait for a restarted backend or gracefully reloaded HTTPS routes without adding visits."""
import argparse
import json
import subprocess
import sys
import time

HOSTS = ('nwuc.cn', 'www.nwuc.cn')


def valid_counts(payload):
    if not isinstance(payload, dict) or payload.get('success') is not True:
        return False
    data = payload.get('data')
    return isinstance(data, dict) and all(
        type(data.get(key)) is int and 0 <= data[key] <= 9007199254740991
        for key in ('site_pv', 'site_uv')
    )


def probe(host, backend=False, run=subprocess.run):
    args = ['curl', '--noproxy', '*', '--silent', '--show-error',
            '--max-time', '3', '--max-filesize', '65536',
            '--write-out', '\n%{http_code}']
    if backend:
        args += ['--header', 'Host: nwuc.cn', 'http://127.0.0.1:8793/api/site-counter']
    else:
        if host not in HOSTS:
            raise ValueError('Unexpected health-check host')
        # Connect locally while retaining the correct TLS SNI and certificate validation.
        args += ['--resolve', host + ':443:127.0.0.1',
                 'https://' + host + '/api/site-counter']
    try:
        result = run(args, capture_output=True, text=True, timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        return False, 'connection timeout or curl unavailable'
    if result.returncode != 0:
        return False, 'connection/TLS error (curl ' + str(result.returncode) + ')'
    body, separator, status = result.stdout.rpartition('\n')
    if not separator or status != '200':
        return False, 'HTTP ' + (status or 'unknown')
    try:
        if valid_counts(json.loads(body)):
            return True, 'ready'
    except (ValueError, TypeError):
        pass
    return False, 'HTTP 200 with an invalid counter response'


def wait_for_ready(check, hosts, attempts=15, sleep=time.sleep):
    """Require two consecutive successful rounds, retrying stale 404s and startup errors."""
    consecutive = 0
    diagnostics = {}
    for attempt in range(attempts):
        diagnostics = {host: check(host) for host in hosts}
        if all(ready for ready, _ in diagnostics.values()):
            consecutive += 1
            if consecutive >= 2:
                return True, diagnostics
        else:
            consecutive = 0
        if attempt + 1 < attempts:
            sleep(1)
    return False, diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', action='store_true')
    args = parser.parse_args()
    hosts = ('backend',) if args.backend else HOSTS
    print('Waiting for ' + ('counter service' if args.backend else 'both HTTPS counter routes') + '...', flush=True)
    ready, diagnostics = wait_for_ready(lambda host: probe(host, backend=args.backend), hosts)
    if not ready:
        for host, (_, reason) in diagnostics.items():
            print(host + ': ' + reason, file=sys.stderr)
        print('Counter did not become ready. No visit was added by these checks.', file=sys.stderr)
        raise SystemExit(1)
    print('Counter health check passed (two consecutive rounds).', flush=True)


if __name__ == '__main__':
    main()
