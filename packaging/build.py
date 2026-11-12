"""Build a relocatable UCL distribution, including dependency license notices."""
import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--name', 'ucl', '--onedir', '--console', '--noupx',
        '--paths', str(ROOT),
        '--hidden-import', 'tkinter', '--hidden-import', 'tkinter.messagebox',
        '--copy-metadata', 'waitress',
        '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build'),
        '--specpath', str(ROOT / 'build'), str(ROOT / 'packaging' / 'entry.py'),
    ], cwd=ROOT, check=True)
    target = ROOT / 'dist' / 'ucl'
    licenses = target / 'licenses'
    licenses.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'LICENSE', licenses / 'UCL-LICENSE.txt')
    for package in ('waitress', 'pyinstaller'):
        distribution = importlib.metadata.distribution(package)
        for file in distribution.files or []:
            if '.dist-info' in str(file) and any(word in file.name.lower() for word in ('license', 'copying')):
                source = Path(distribution.locate_file(file))
                if source.is_file(): shutil.copy2(source, licenses / f'{package}-{file.name}')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists(): shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    (licenses / 'README.txt').write_text(
        'UCL is MIT licensed. This distribution bundles CPython (PSF license), '
        'Waitress (ZPL 2.1), the PyInstaller bootloader (GPL with distribution exception), '
        'SQLite (public domain), and Tcl/Tk (their upstream permissive licenses). '
        'License files are included here and in the bundled library/data directories.\n', encoding='utf-8')


if __name__ == '__main__':
    main()
