"""Fixed Chrome profiles and ports for the three local workflows."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time
from cdp_transport import cdp_urlopen as urlopen

ROOT = Path(__file__).resolve().parent
SESSIONS = {
    'keywords': (9222, 'keyword-loop-profile'),
    'product-hunt': (9230, 'aitdk-cdp-clean-20260909'),
    'google-trends': (9229, 'google-trends-background-profile'),
}


def endpoint(name):
    return f'http://127.0.0.1:{SESSIONS[name][0]}'


def command(name):
    port, folder = SESSIONS[name]
    profile = ROOT / 'runtime' / folder
    args = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--remote-debugging-address=127.0.0.1', f'--remote-debugging-port={port}',
            '--remote-allow-origins=*', f'--user-data-dir={profile}',
            '--profile-directory=Default', '--no-first-run', '--no-default-browser-check']
    if name == 'product-hunt':
        extension = profile / 'Default/Extensions/hhfkpjffbhledfpkhhcoidplcebgdgbk/2.8.1_0'
        args += [f'--disable-extensions-except={extension}', f'--load-extension={extension}', '--no-startup-window']
    elif name == 'google-trends':
        # The Trends client creates its own targets with background=True.
        args += ['--disable-extensions', '--no-startup-window', '--window-size=1280,900']
    else:
        args += ['--disable-extensions', '--no-startup-window']
    return args


def matches_profile(command_line, name):
    args = shlex.split(command_line)
    return (f'--user-data-dir={ROOT / "runtime" / SESSIONS[name][1]}' in args
            and f'--remote-debugging-port={SESSIONS[name][0]}' in args)


def check(name):
    """Check all IPv4/IPv6 listeners before accepting a session."""
    result = subprocess.run(['/usr/sbin/lsof', '-nP', f'-iTCP:{SESSIONS[name][0]}', '-sTCP:LISTEN', '-t'], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError('Cannot inspect Chrome port ownership')
    pids = set(result.stdout.split())
    for pid in pids:
        line = subprocess.check_output(['/bin/ps', '-p', pid, '-o', 'command='], text=True).strip()
        if not matches_profile(line, name):
            raise RuntimeError(f'{name}: port {SESSIONS[name][0]} belongs to another profile/process (PID {pid}); refusing to reuse it')
    if not pids:
        return False
    with urlopen(endpoint(name) + '/json/version', timeout=3) as response:
        if not json.load(response).get('webSocketDebuggerUrl'):
            raise RuntimeError('Port is not a Chrome CDP endpoint')
    return True


def ensure(name):
    if check(name):
        return
    args = command(name)
    if name == 'product-hunt':
        extension = next(a.split('=', 1)[1] for a in args if a.startswith('--load-extension='))
        if not (Path(extension) / 'manifest.json').is_file():
            raise RuntimeError('AITDK extension missing from its dedicated profile')
    (ROOT / 'runtime').mkdir(exist_ok=True)
    with (ROOT / 'runtime' / f'chrome-{name}.log').open('ab') as log:
        process = subprocess.Popen(args, stdout=log, stderr=log, start_new_session=True)
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError(f'{name}: Chrome exited; see runtime/chrome-{name}.log')
        try:
            if check(name):
                return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError(f'{name}: CDP did not become ready')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('session', choices=SESSIONS)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.dry_run:
        print(shlex.join(command(args.session)))
    elif args.check:
        print('ready' if check(args.session) else 'stopped')
    else:
        ensure(args.session)
        print(endpoint(args.session))
