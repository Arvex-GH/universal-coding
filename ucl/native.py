"""Checked numeric terminal subset lowered to C99, then native machine code."""
import ast
import math
import shutil
import subprocess
from pathlib import Path
from .language import UCLError, classify, validate


def emit_c(nodes):
    types = validate(nodes)
    if types != {'terminal'}:
        raise UCLError('native backend currently supports type is terminal only; use ucl run for other types')
    variables = {}
    for n in nodes:
        kind, args = classify(n)
        if kind == 'let' and n.text.lower().startswith('let '): variables[args[0]] = 'v_' + args[0]
    def expression(text):
        def visit(n):
            if isinstance(n, ast.Constant) and type(n.value) in {int, float, bool}:
                value = float(n.value)
                if not math.isfinite(value): raise UCLError('native numeric literals must be finite')
                return repr(value)
            if isinstance(n, ast.Name) and n.id in variables: return variables[n.id]
            if isinstance(n, ast.Name) and n.id in {'true', 'false'}: return '1' if n.id == 'true' else '0'
            ops = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}
            if isinstance(n, ast.BinOp) and type(n.op) in ops:
                left, right = visit(n.left), visit(n.right)
                if isinstance(n.op, ast.Div): return f'ucl_div({left}, {right})'
                return f'({left} {ops[type(n.op)]} {right})'
            if isinstance(n, ast.UnaryOp) and type(n.op) in {ast.USub, ast.UAdd, ast.Not}:
                return '(' + {ast.USub: '-', ast.UAdd: '+', ast.Not: '!'}[type(n.op)] + visit(n.operand) + ')'
            if isinstance(n, ast.Compare):
                ops = {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.Gt: '>', ast.LtE: '<=', ast.GtE: '>='}
                if all(type(op) in ops for op in n.ops):
                    values = [n.left] + n.comparators
                    return '(' + ' && '.join(f'({visit(values[i])} {ops[type(op)]} {visit(values[i+1])})' for i,op in enumerate(n.ops)) + ')'
            raise UCLError(f'native backend does not support expression: {text}')
        try: return visit(ast.parse(text, mode='eval').body)
        except SyntaxError as e: raise UCLError(f'invalid expression: {text}') from e
    # Resolve top-level let declarations in dependency order without executing them.
    pending = [n for n in nodes if classify(n)[0] == 'let' and n.text.lower().startswith('let ')]
    names = [classify(n)[1][0] for n in pending]
    if len(names) != len(set(names)): raise UCLError('duplicate let declaration')
    initialized = set()
    declarations = []
    while pending:
        remaining = []
        for n in pending:
            _, (name, expr) = classify(n)
            try: tree = ast.parse(expr, mode='eval')
            except SyntaxError as e: raise UCLError(f'invalid expression: {expr}') from e
            deps = {x.id for x in ast.walk(tree) if isinstance(x, ast.Name)} - {'true', 'false'}
            if not deps <= initialized:
                remaining.append(n)
            else:
                declarations.append(f'{variables[name]} = {expression(expr)};')
                initialized.add(name)
        if len(remaining) == len(pending): raise UCLError('unresolved or cyclic native declarations')
        pending = remaining
    serial = 0
    def statements(items, root=False):
        nonlocal serial
        result = []
        for n in items:
            kind, args = classify(n)
            if kind == 'type': continue
            if kind == 'let':
                if root and n.text.lower().startswith('let '): continue
                if args[0] not in variables: raise UCLError('native variables must be declared at application level')
                result.append(f'{variables[args[0]]} = {expression(args[1])};')
            elif kind == 'print':
                try: value = ast.literal_eval(args[0])
                except (ValueError, SyntaxError): value = None
                if isinstance(value, str):
                    # UTF-8 octal escapes avoid C literal and source encoding ambiguities.
                    literal = '"' + ''.join(f'\\{b:03o}' for b in value.encode('utf-8')) + '"'
                    result.append(f'puts({literal});')
                else: result.append(f'printf("%.15g\\n", (double)({expression(args[0])}));')
            elif kind == 'if': result.append(f'if ({expression(args[0])}) {{\n' + statements(n.children) + '\n}')
            elif kind == 'otherwise': result.append('else {\n' + statements(n.children) + '\n}')
            elif kind == 'repeat':
                serial += 1
                count = f'count_{serial}'
                result.append(f'double {count} = {expression(args[0])};\nif (!isfinite({count}) || {count} < 0 || floor({count}) != {count} || {count} > 2147483647) {{ fputs("invalid repeat count\\n", stderr); return 1; }}\nfor (int i_{serial}=0; i_{serial}<(int){count}; ++i_{serial}) {{\n' + statements(n.children) + '\n}')
            else: raise UCLError(f'line {n.line}: {kind} is not supported by native backend; use ucl run')
        return '\n'.join(result)
    body = statements(nodes, True)
    return '#include <stdio.h>\n#include <stdlib.h>\n#include <math.h>\nstatic double ucl_div(double a,double b) { if(b==0) { fputs("division by zero\\n",stderr); exit(1); } return a/b; }\nint main(void) {\n' + '\n'.join('double '+v+' = 0;' for v in variables.values()) + '\n' + '\n'.join(declarations) + '\n' + body + '\nreturn 0;\n}\n'


def build(nodes, output, compiler=None):
    c = emit_c(nodes)
    compiler = compiler or shutil.which('cc') or shutil.which('clang') or shutil.which('gcc')
    if not compiler: raise UCLError('install a C99 compiler (Clang or GCC) to build native executables')
    import tempfile
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ucl-') as tmp:
        source = Path(tmp) / 'program.c'
        source.write_text(c)
        result = subprocess.run([compiler, '-std=c99', '-O2', str(source), '-lm', '-o', str(output)], capture_output=True, text=True)
        if result.returncode: raise UCLError('C compiler failed:\n' + result.stderr)
    return output
