"""Exercise frozen UCL outside the source checkout with Python removed from PATH."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request


def smoke(executable):
    executable = Path(executable).resolve()
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PATH'] = str(Path(env.get('SystemRoot', r'C:\Windows')) / 'System32') if os.name == 'nt' else '/usr/bin:/bin'
    with tempfile.TemporaryDirectory(prefix='ucl standalone test ') as tmp:
        def run(*args, input=None):
            result = subprocess.run([str(executable), *args], input=input, text=True,
                                    capture_output=True, cwd=tmp, env=env, timeout=30)
            if result.returncode:
                raise AssertionError(f'{args}: {result.stdout}\n{result.stderr}')
            return result.stdout
        assert run('--version').startswith('UCL ')
        assert 'label #' in run('help', 'label_update')
        source = Path(tmp) / 'multiply with spaces.ucl'
        source.write_text('[type is terminal\nask for number "First: " into first\nask for number "Second: " into second\nsay first * second]', encoding='utf-8')
        assert '42' in run('run', str(source), input='6\n7\n')
        assert 'checks passed' in run('check', str(source))
        database = Path(tmp) / 'database.ucl'
        database.write_text('''[
 database db is ":memory:"
 execute "CREATE TABLE n (value INTEGER)" on db
 transaction on db [execute "INSERT INTO n VALUES (?)" on db using list(42)]
 query "SELECT value FROM n" on db into rows
 say item(rows, 0).value
]''', encoding='utf-8')
        assert run('run', str(database)).strip() == '42'
        if os.name == 'nt':
            gui = Path(tmp) / 'gui.ucl'
            gui.write_text('''[type is gui
 show label "0" is #counter
 style #counter is {"font_size": 48}
 show input "Name" is #name
 show checkbox "Agree" is #agree
 every 20 milliseconds [
   label #counter text is "1"
   say "GUI_OK"
   close window
 ]
]''', encoding='utf-8')
            assert 'GUI_OK' in run('run', str(gui))
            native = Path(__file__).resolve().parents[1] / 'examples' / 'native-design.ucl'
            design = Path(tmp) / 'native-design.ucl'
            original = native.read_text(encoding='utf-8').rstrip()
            design.write_text(original[:-1] + '\n every 100 milliseconds [\n say "NATIVE_DESIGN_OK"\n close interface\n ]\n]', encoding='utf-8')
            assert 'NATIVE_DESIGN_OK' in run('run', str(design))
        tui = Path(tmp) / 'tui.ucl'
        tui.write_text('[type is tui\ntheme is dark\nshow label "TUI_OK" is #ok\nshow button "Quit" is #quit\nwhen button #quit is clicked [close interface]]', encoding='utf-8')
        assert 'TUI_OK' in run('run', str(tui), input='1\n')
        api = Path(tmp) / 'api.ucl'
        api.write_text('''[type is server
 port is 0
 http settings is {"auth_token_environment": "UCL_SMOKE_TOKEN", "access_log": false}
 when post "/echo/{id}" [respond {"id": request.params.id, "body": request.json}]
]''', encoding='utf-8')
        env['UCL_SMOKE_TOKEN'] = 'standalone-smoke-test-token-123456789'
        process = subprocess.Popen([str(executable), 'serve', str(api)], cwd=tmp, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = queue.Queue()
        def read_startup(): lines.put(process.stdout.readline())
        threading.Thread(target=read_startup, daemon=True).start()
        success = False
        try:
            line = lines.get(timeout=20)
            assert 'UCL listening on ' in line, line
            url = line.strip().split('http://', 1)[1]
            url = 'http://' + url + '/echo/42'
            request = urllib.request.Request(url, data=b'{"hello":"UCL"}', headers={'Content-Type': 'application/json'})
            try: urllib.request.urlopen(request, timeout=5)
            except urllib.error.HTTPError as error: assert error.code == 401
            else: raise AssertionError('Standalone bearer authentication was bypassed')
            request.add_header('Authorization', 'Bearer ' + env['UCL_SMOKE_TOKEN'])
            with urllib.request.urlopen(request, timeout=5) as response:
                assert json.load(response) == {'id': '42', 'body': {'hello': 'UCL'}}
            success = True
        finally:
            process.terminate()
            try: stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            if not success: print(stdout + stderr, file=sys.stderr)
            if process.returncode not in {0, -15, 1} and os.name != 'nt':
                raise AssertionError(stdout + stderr)
    print('Standalone CLI/help/input/SQLite/HTTP/auth passed; native Tk widgets/updates also tested on Windows.')


if __name__ == '__main__':
    smoke(sys.argv[1])
