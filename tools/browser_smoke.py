"""Run optional real Chromium checks against the actual bounded HTTP transport.
Install tools/browser dependencies first; Linux only. No browser runtime dependency.
"""
from pathlib import Path
import subprocess
import sys
import threading
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ucl import Runtime, parse


def main():
    source = ROOT/'examples/design-studio.ucl'
    runtime = Runtime(parse(source.read_text(encoding='utf-8')),output=lambda value: None)
    runtime.source_name = str(source)
    runtime.prepare()
    runtime.execute()
    runtime.port = 0
    runtime.http_settings.update(access_log=False)
    server = runtime.make_server()
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        subprocess.run(['node',str(ROOT/'tools/browser/smoke.cjs'),f'http://127.0.0.1:{server.server_port}/'],check=True,timeout=90)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
        runtime.close()

if __name__ == '__main__': main()
