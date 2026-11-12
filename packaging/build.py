"""Build a relocatable UCL directory; usable on Windows and Linux."""
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
        '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build'),
        '--specpath', str(ROOT / 'build'), str(ROOT / 'packaging' / 'entry.py'),
    ], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
