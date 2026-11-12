"""Regenerate the public statement/builtin reference from the toolchain registry."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ucl.reference import markdown

if __name__ == '__main__':
    target = ROOT / 'docs' / 'reference' / 'commands.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown(), encoding='utf-8')
    print(target)
