"""Run a build/check and expose failures through GitHub's annotations API as well as logs."""
import os
import subprocess
import sys


def main():
    result = subprocess.run(sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace')
    print(result.stdout, end='')
    if result.returncode and os.environ.get('GITHUB_ACTIONS') == 'true':
        message = result.stdout[-16000:].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error::' + message)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
