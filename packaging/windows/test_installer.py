"""Windows-only CI integration: real silent install, upgrade, PATH and uninstall.

The old installer uses the same payload with old version metadata, testing the
installer lifecycle rather than claiming to test a historical runtime release.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import winreg

ROOT = Path(__file__).resolve().parents[2]
APP_ID = '{0C8AB115-0E06-48F6-AC2D-0142CC6EE055}_is1'


def registry_path():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as key:
        try: return winreg.QueryValueEx(key, 'Path')[0]
        except FileNotFoundError: return ''


def entries(path):
    return [p.strip().strip('"').rstrip('\\').casefold() for p in path.split(';') if p.strip()]


def installed_version():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + APP_ID,
                        0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        return winreg.QueryValueEx(key, 'DisplayVersion')[0]


def run_installer(path, app):
    result = subprocess.run([str(path), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                             '/SP-', '/TASKS=addtopath,editor', f'/DIR={app}'], timeout=120)
    assert result.returncode == 0, result.returncode


def main():
    before = entries(registry_path())
    with tempfile.TemporaryDirectory(prefix='UCL installer test ') as tmp:
        app = Path(tmp) / 'UCL with spaces'
        token = str(app).rstrip('\\').casefold()
        try:
            run_installer(ROOT / 'dist/ucl-test-old.exe', app)
            assert installed_version() == '0.1.0'
            assert entries(registry_path()).count(token) == 1
            run_installer(ROOT / 'dist/ucl-installer.exe', app)
            sys.path.insert(0, str(ROOT))
            from ucl import __version__
            assert installed_version() == __version__
            # Re-running an installer is safe and does not duplicate PATH entries.
            run_installer(ROOT / 'dist/ucl-installer.exe', app)
            assert entries(registry_path()).count(token) == 1
            assert set(before) <= set(entries(registry_path()))
            env = dict(os.environ)
            env['PATH'] = str(app) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32')
            command = shutil.which('ucl', path=env['PATH'])
            assert command and Path(command).resolve() == (app / 'ucl.exe').resolve()
            result = subprocess.run([command, 'run', str(app / 'examples/multiply.ucl')],
                                    input='6\n7\n', capture_output=True, text=True,
                                    env=env, cwd=tmp, timeout=30)
            assert result.returncode == 0, result.stderr
            assert 'The result is 42' in result.stdout, result.stdout
            # Editor registration must not replace the existing default application.
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Classes\SystemFileAssociations\.ucl\shell\UCLRun\command') as key:
                command_line = winreg.QueryValueEx(key, '')[0]
                assert str(app / 'ucl.exe') in command_line and '"%1"' in command_line
        finally:
            uninstaller = app / 'unins000.exe'
            if uninstaller.exists():
                result = subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], timeout=120)
                assert result.returncode == 0
        assert token not in entries(registry_path())
        assert before == entries(registry_path()), 'Uninstaller modified unrelated PATH entries'
        assert not (app / 'ucl.exe').exists()
        try:
            installed_version()
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Uninstall registration was not removed')
    print('Windows install, upgrade, reinstall, PATH, Explorer command, and uninstall passed.')


if __name__ == '__main__':
    main()
