"""Standalone console entry point used by PyInstaller (not a second interpreter)."""
from ucl.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
