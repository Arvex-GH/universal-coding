"""Optional build-time Tailwind compiler. Running built browser apps needs no Node."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from .language import UCLError

TAILWIND_VERSION = '3.4.19'


def compile_styles(source, output, input_css=None, config=None):
    executable = shutil.which('npx.cmd') or shutil.which('npx')
    if not executable: raise UCLError('Tailwind build requires Node.js/npm (npx), or compile CSS externally and use stylesheet is "app.css"')
    source = Path(source).resolve()
    if not source.is_file(): raise UCLError(f'no source file: {source}')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ucl-tailwind-') as folder:
        folder = Path(folder)
        css = Path(input_css).resolve() if input_css else folder/'input.css'
        if input_css is None: css.write_text('@tailwind base;\n@tailwind components;\n@tailwind utilities;\n',encoding='utf-8')
        settings = Path(config).resolve() if config else folder/'tailwind.config.json'
        if config is None:
            # Raw content avoids glob metacharacters in file paths; record styles
            # coexist with utility classes, which explicitly take precedence.
            settings.write_text(json.dumps({'content':[{'raw':source.read_text(encoding='utf-8'),'extension':'html'}],'important':True}),encoding='utf-8')
        result = subprocess.run([executable,'--yes',f'tailwindcss@{TAILWIND_VERSION}','--input',str(css),'--config',str(settings),'--output',str(output),'--minify'],check=False)
        if result.returncode: raise UCLError(f'Tailwind compiler failed (exit {result.returncode})')
    return output
