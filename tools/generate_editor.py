"""Generate editor vocabulary and grammar additions from the runtime registry."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ucl.reference import details, BUILTINS
from ucl.design import STYLE_KEYS, ENUMS, BREAKPOINTS

def data():
    return {'commands':details(),'builtins':BUILTINS,'styles':sorted(STYLE_KEYS),'enums':{k:sorted(v) for k,v in ENUMS.items()},'breakpoints':BREAKPOINTS}

if __name__ == '__main__':
    target = ROOT/'editors/vscode/language-data.json'
    target.write_text(json.dumps(data(),indent=2)+'\n',encoding='utf-8')
    print(target)
