"""Exercise a frozen executable from outside the source checkout, without Python on PATH."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


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
        source = Path(tmp) / 'multiply with spaces.ucl'
        source.write_text('[type is terminal\nask for number "First: " into first\nask for number "Second: " into second\nsay first * second]', encoding='utf-8')
        assert '42' in run('run', str(source), input='6\n7\n')
        assert 'checks passed' in run('check', str(source))
        database = Path(tmp) / 'database.ucl'
        database.write_text('''[
 database db is ":memory:"
 execute "CREATE TABLE n (value INTEGER)" on db
 execute "INSERT INTO n VALUES (?)" on db using list(42)
 query "SELECT value FROM n" on db into rows
 say item(rows, 0).value
]''', encoding='utf-8')
        assert run('run', str(database)).strip() == '42'
    print('Standalone CLI, numeric input, source paths with spaces, and SQLite passed.')


if __name__ == '__main__':
    smoke(sys.argv[1])
