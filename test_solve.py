"""Small CLI client for the local solver API.

Examples:
    python test_solve.py
    python test_solve.py --type turnstile --url https://checkout9.iherb.com/auth/ui/account/login \
        --sitekey 0x4AAAAAADmKZAkmJVxUyvHF --action account_check
    python test_solve.py --type cf_clearance --url https://ivasms.com
    python test_solve.py --type turnstile --proxy http://user:pass@host:port
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEMO_URL = "https://demo.turnstile.workers.dev/"
DEMO_SITEKEY = "1x00000000000000000000AA"


def _get(base: str, path: str, params: dict, timeout: float = 15.0) -> dict:
    url = base.rstrip('/') + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def solve(args) -> dict:
    create_params = {'url': args.url}
    if args.type == 'turnstile':
        create_params['sitekey'] = args.sitekey
        if args.action:
            create_params['action'] = args.action
        if args.cdata:
            create_params['cdata'] = args.cdata
    else:
        create_params['timeout'] = args.solve_timeout
    if args.proxy:
        create_params['proxy'] = args.proxy

    created = _get(args.base, '/' + args.type, create_params)
    if created.get('errorId') != 0:
        raise RuntimeError(f"create failed: {created}")
    task_id = created['taskId']
    print(f"taskId={task_id}", flush=True)
    print("status=processing", end='', flush=True)

    deadline = time.monotonic() + args.deadline
    while time.monotonic() < deadline:
        result = _get(args.base, '/result', {'id': task_id})
        if result.get('status') == 'ready' and result.get('errorId') == 0:
            print("\nstatus=ready")
            return result['solution']
        if result.get('errorId') == 1:
            raise RuntimeError(f"solver error: {result}")
        print('.', end='', flush=True)
        time.sleep(2)
    raise TimeoutError(f"deadline exceeded for taskId={task_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Turnstile / cf_clearance solver client")
    parser.add_argument('--type', choices=('turnstile', 'cf_clearance'), default='turnstile')
    parser.add_argument('--base', default='http://127.0.0.1:5072')
    parser.add_argument('--url', help='target page URL (defaults to the demo/ivasms page)')
    parser.add_argument('--sitekey', default=DEMO_SITEKEY)
    parser.add_argument('--action')
    parser.add_argument('--cdata')
    parser.add_argument('--proxy', help='per-request proxy, e.g. http://user:pass@host:port')
    parser.add_argument('--solve-timeout', type=int, default=60,
                        help='server-side cf_clearance cookie wait (seconds)')
    parser.add_argument('--deadline', type=int, default=180,
                        help='client-side total deadline (seconds)')
    args = parser.parse_args()
    if not args.url:
        args.url = DEMO_URL if args.type == 'turnstile' else 'https://ivasms.com/'
    try:
        solution = solve(args)
    except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(solution, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
