"""Portable UCL runtime. No Python eval/exec is used for UCL expressions."""
import ast
import html
import json
import math
import os
import sys
import time
from pathlib import Path
from contextlib import contextmanager, nullcontext
import operator
import re
import sqlite3
import threading
from .language import UCLError, classify, validate
from .ui import UI, checked_style
from .values import parse_json


class Returned(Exception):
    def __init__(self, value): self.value = value


class Reply(Exception):
    def __init__(self, value, kind='json'): self.value, self.kind = value, kind


class LoopBreak(Exception): pass


class LoopContinue(Exception): pass


class UCLObject(dict):
    """Value properties and methods; no access to Python object attributes."""
    def __init__(self):
        super().__init__()
        self.methods = {}


class Runtime:
    def __init__(self, nodes, output=print, input_fn=None, diagnostic_fn=None):
        self.nodes = nodes
        self.types = validate(nodes)
        self.env = {}
        self.functions = {}
        self.databases = {}
        self.ui = UI(self)
        self.buttons = self.ui.buttons
        self.handlers = {}
        self.routes = {}
        self.labels = []
        self.output = output
        self.input = input if input_fn is None else input_fn
        self.title = 'UCL Application'
        self.port = 8080
        self.host = '127.0.0.1'
        self.lock = threading.RLock()
        self.widgets = self.ui.widgets
        self.timers = []
        self.http_settings = {}
        self.debug = False
        self.trace = False
        self.log_format = 'text'
        self.diagnostic = diagnostic_fn or (lambda message: print(message, file=sys.stderr))
        self.log_file = None
        self.source_name = '<program>'
        self.arguments = []
        self._steps = None
        self._transactions = set()
        self.prepared = False

    def expr(self, text, env=None):
        env = self.env if env is None else env
        builtins = {'length': len, 'text': str, 'number': float, 'integer': int,
                    'list': lambda *x: list(x), 'min': min, 'max': max, 'round': round,
                    'json': lambda value: json.dumps(value, allow_nan=False), 'parse_json': parse_json, 'abs': abs,
                    'item': operator.getitem, 'keys': lambda x: list(x.keys()),
                    'values': lambda x: list(x.values()),
                    'environment': lambda name, default='': os.environ.get(name, default),
                    'argument': lambda index: self.arguments[index],
                    'upper': lambda value: str(value).upper(), 'lower': lambda value: str(value).lower(),
                    'trim': lambda value: str(value).strip(),
                    'split': lambda value, separator=None: str(value).split(separator),
                    'join': lambda values, separator='': separator.join(str(v) for v in values),
                    'replace': lambda value, old, new: str(value).replace(old, new),
                    'contains': lambda value, part: part in value,
                    'range': lambda *args: range(*args), 'type_of': lambda value: type(value).__name__,
                    'floor': math.floor, 'ceil': math.ceil, 'sqrt': math.sqrt, 'escape_html': html.escape}

        binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                  ast.Div: operator.truediv, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
        compare = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                   ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                   ast.In: lambda a,b: a in b, ast.NotIn: lambda a,b: a not in b}
        def visit(n):
            self.step()
            if isinstance(n, ast.Constant): return n.value
            if isinstance(n, ast.Name):
                if n.id in {'true', 'false', 'nothing'}: return {'true': True, 'false': False, 'nothing': None}[n.id]
                if n.id in env: return env[n.id]
                raise UCLError(f'unknown name: {n.id}')
            if isinstance(n, ast.BinOp) and type(n.op) in binary: return binary[type(n.op)](visit(n.left), visit(n.right))
            if isinstance(n, ast.UnaryOp):
                if isinstance(n.op, ast.Not): return not visit(n.operand)
                if isinstance(n.op, ast.USub): return -visit(n.operand)
                if isinstance(n.op, ast.UAdd): return +visit(n.operand)
            if isinstance(n, ast.BoolOp):
                value = visit(n.values[0])
                for item in n.values[1:]:
                    if isinstance(n.op, ast.And) and not value: return value
                    if isinstance(n.op, ast.Or) and value: return value
                    value = visit(item)
                return value
            if isinstance(n, ast.Compare):
                left = visit(n.left)
                for op, right in zip(n.ops, n.comparators):
                    right = visit(right)
                    if type(op) not in compare or not compare[type(op)](left, right): return False
                    left = right
                return True
            if isinstance(n, ast.Dict): return {visit(k): visit(v) for k,v in zip(n.keys,n.values)}
            if isinstance(n, ast.Tuple): return tuple(visit(x) for x in n.elts)
            if isinstance(n, ast.Attribute):
                obj = visit(n.value)
                if not isinstance(obj, dict): raise UCLError('property access requires an object')
                return obj[n.attr]
            if isinstance(n, ast.Subscript): return visit(n.value)[visit(n.slice)]
            if isinstance(n, ast.Call) and not n.keywords:
                args = [visit(a) for a in n.args]
                if isinstance(n.func, ast.Name):
                    if n.func.id in builtins: return builtins[n.func.id](*args)
                    return self.call(n.func.id, args, env)
                if isinstance(n.func, ast.Attribute):
                    obj = visit(n.func.value)
                    if not isinstance(obj, UCLObject) or n.func.attr not in obj.methods:
                        raise UCLError(f'unknown method: {n.func.attr}')
                    return self.invoke(obj.methods[n.func.attr], args, {**env, 'self': obj}, n.func.attr)
            raise UCLError(f'unsupported expression: {text}')
        try: return visit(ast.parse(text, mode='eval').body)
        except UCLError: raise
        except (SyntaxError, ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError) as e:
            raise UCLError(f'expression {text!r}: {e}') from e

    def call(self, name, args, env):
        if name not in self.functions: raise UCLError(f'unknown function: {name}')
        return self.invoke(self.functions[name], args, env, name)

    def invoke(self, function, args, env, name):
        params, body = function
        if len(params) != len(args): raise UCLError(f'{name} expects {len(params)} arguments')
        local = dict(env)
        local.update(zip(params, args))
        try: self.execute(body, local)
        except Returned as r: return r.value
        return None

    def prepare(self):
        if self.prepared: return
        # Register functions first, then declarations, then execute statements.
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'function':
                if a[0] in self.functions: raise UCLError(f'duplicate function: {a[0]}')
                params = [p.strip() for p in a[1].split(',') if p.strip()]
                if len(set(params)) != len(params) or any(not re.fullmatch(r'[A-Za-z_]\w*', p) for p in params):
                    raise UCLError(f'line {n.line}: invalid function parameters')
                self.functions[a[0]] = (params, n.children)
        # Variables are dependency-resolved: forward references work; cycles fail.
        pending = [n for n in self.nodes if classify(n)[0] in {'object', 'create'} or (classify(n)[0] == 'let' and n.text.lower().startswith('let '))]
        names = [classify(n)[1][0] for n in pending]
        if len(names) != len(set(names)): raise UCLError('duplicate declaration; use set to change a value')
        while pending:
            remaining = []
            for n in pending:
                kind, a = classify(n)
                name = a[0]
                try:
                    if kind == 'object': self.env[name] = self.make_object(n.children)
                    elif kind == 'create':
                        import copy
                        obj = self.expr(a[1])
                        if not isinstance(obj, UCLObject): raise UCLError('create requires an object template')
                        self.env[name] = copy.deepcopy(obj)
                    else: self.env[name] = self.expr(a[1])
                except UCLError as e:
                    if 'unknown name:' not in str(e): raise
                    remaining.append(n)
            if len(remaining) == len(pending): raise UCLError('unresolved or cyclic declarations: ' + ', '.join(classify(n)[1][0] for n in remaining))
            pending = remaining
        # Theme and tokens resolve before widget styles, regardless of source order.
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'theme': self.ui.set_theme(a[0].lower())
            elif kind == 'motion': self.ui.motion = a[0].lower() == 'on'
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'design_tokens': self.ui.set_tokens(self.expr(a[0]))
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'title': self.title = str(self.expr(a[0]))
            elif kind == 'port':
                self.port = int(a[0])
                if not 0 <= self.port <= 65535: raise UCLError('port must be between 0 and 65535')
            elif kind == 'host': self.host = str(self.expr(a[0]))
            elif kind == 'database':
                if a[0] in self.databases: raise UCLError(f'duplicate database: {a[0]}')
                self.databases[a[0]] = sqlite3.connect(str(self.expr(a[1])), check_same_thread=False)
            elif kind == 'route':
                key = (a[0].upper(), self.expr(a[1]))
                if key in self.routes: raise UCLError(f'duplicate route: {key}')
                self.routes[key] = n.children
            elif kind == 'buttons':
                count, spec = a
                entries = re.findall(r'(?:\d+\.\s*)?("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')\s+is\s+#([\w-]+)', spec)
                residue = re.sub(r'(?:\d+\.\s*)?("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')\s+is\s+#[\w-]+', '', spec)
                if not entries or residue.strip(' ;') or len(entries) != int(count or 1): raise UCLError(f'line {n.line}: button count or definition is invalid')
                for label, ident in entries:
                    if ident in self.buttons: raise UCLError(f'duplicate button #{ident}')
                    self.ui.add('button', ident, self.expr(label))
            elif kind == 'label':
                text = str(self.expr(a[0]))
                self.labels.append(text)
                self.ui.add('label', f'_label_{len(self.labels)}', text)
            elif kind in {'label_named', 'input', 'checkbox', 'panel'}:
                self.ui.add('label' if kind == 'label_named' else kind, a[1], self.expr(a[0]))
            elif kind == 'window_style': self.ui.window_style = self.ui.check_style(self.expr(a[0]))
            elif kind == 'assets': self.ui.set_assets(self.expr(a[0]))
            elif kind == 'stylesheet': self.ui.load_stylesheet(self.expr(a[0]))
            elif kind == 'window_size':
                self.ui.size = tuple(map(int, a))
                if any(not 100 <= x <= 4096 for x in self.ui.size): raise UCLError('window dimensions must be 100–4096')
            elif kind == 'layout':
                self.ui.direction = 'grid' if a[1] else a[0].lower()
                if a[1]:
                    self.ui.columns = int(a[1])
                    if not 1 <= self.ui.columns <= 12: raise UCLError('grid columns must be 1–12')
            elif kind == 'debugging': self.debug = a[0].lower() == 'on'
            elif kind == 'http_settings':
                from .http import settings
                self.http_settings = settings(self.expr(a[0]))
            elif kind == 'timer':
                if not 10 <= int(a[0]) <= 86400000: raise UCLError('timer interval must be 10–86400000 milliseconds')
                self.timers.append((int(a[0]), n.children))
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'place': self.ui.place(a[0], a[1])
            elif kind == 'panel_layout': self.ui.panel_layout(a[0], a[1], a[2])
        for n in self.nodes:
            kind, a = classify(n)
            if kind == 'widget_style': self.ui.style(a[0], self.expr(a[1]))
            elif kind == 'classes': self.ui.set_classes(a[0], self.expr(a[1]))
            elif kind in {'state_style', 'responsive_style'}: self.ui.variant(a[0], a[1].lower(), self.expr(a[2]))
            if kind in {'style', 'click'}:
                ident = a[0]
                if ident not in self.buttons: raise UCLError(f'unknown button #{ident}')
                if kind == 'click':
                    if ident in self.handlers: raise UCLError(f'duplicate click handler #{ident}')
                    self.handlers[ident] = n.children
                else:
                    m = re.fullmatch(r'([A-Za-z]+|#[0-9a-fA-F]{6})(?:\s*\+\s*padding is (\d+))?', a[1])
                    if not m: raise UCLError('style must be COLOR + padding is NUMBER')
                    checked_style({'background': m[1]})
                    self.buttons[ident]['color'] = m[1]
                    if m[2]:
                        checked_style({'padding': int(m[2])})
                        self.buttons[ident]['padding'] = int(m[2])
                        self.buttons[ident]['legacy_padding'] = True
        self.prepared = True

    def make_object(self, children):
        obj = UCLObject()
        pending = []
        for n in children:
            kind, a = classify(n)
            if kind == 'function':
                params = [p.strip() for p in a[1].split(',') if p.strip()]
                if len(params) != len(set(params)) or any(not re.fullmatch(r'[A-Za-z_]\w*', p) for p in params):
                    raise UCLError(f'line {n.line}: invalid method parameters')
                if a[0] in obj.methods: raise UCLError(f'duplicate method: {a[0]}')
                obj.methods[a[0]] = (params, n.children)
            elif kind == 'let' and n.text.lower().startswith('let '): pending.append(n)
            else: raise UCLError(f'line {n.line}: objects contain let properties and to methods')
        names = [classify(n)[1][0] for n in pending]
        if len(names) != len(set(names)): raise UCLError('duplicate object property')
        while pending:
            remaining = []
            for n in pending:
                _, (name, expr) = classify(n)
                try: obj[name] = self.expr(expr, {**self.env, **obj})
                except UCLError as e:
                    if 'unknown name:' not in str(e): raise
                    remaining.append(n)
            if len(remaining) == len(pending):
                # Let the outer declaration resolver retry if globals are missing.
                raise UCLError('unknown name: unresolved object property')
            pending = remaining
        return obj

    def log(self, level, message, **fields):
        if level == 'debug' and not self.debug: return
        record = {'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'level': level, 'message': str(message), **fields}
        line = json.dumps(record, ensure_ascii=True) if self.log_format == 'json' else f'[{level.upper()}] {message}' + (f' request_id={fields["request_id"]}' if 'request_id' in fields else '')
        # Keep a log entry on one terminal line; JSON escapes control characters.
        if self.log_format != 'json':
            line = ''.join({'\r': r'\r', '\n': r'\n', '\t': r'\t'}.get(c, f'\\x{ord(c):02x}') if ord(c) < 32 or ord(c) == 127 else c for c in line)
        self.diagnostic(line)
        if self.log_file:
            try:
                with Path(self.log_file).open('a', encoding='utf-8') as stream: stream.write(line + '\n')
            except OSError:
                self.log_file = None
                self.diagnostic('[ERROR] Cannot write diagnostic log file; continuing with terminal logging only.')

    @contextmanager
    def budget(self, maximum):
        previous = self._steps
        self._steps = maximum
        try: yield
        finally: self._steps = previous

    def step(self):
        if self._steps is not None:
            self._steps -= 1
            if self._steps < 0: raise UCLError('execution step limit exceeded')

    def execute(self, nodes=None, env=None):
        env = self.env if env is None else env
        last_if = False
        caught_error = None
        for n in self.nodes if nodes is None else nodes:
            kind, a = classify(n)
            self.step()
            if self.trace: self.log('debug', f'{self.source_name}:{n.line}: {kind}')
            try:
                if kind == 'let':
                    if env is self.env and any(n is item for item in self.nodes) and n.text.lower().startswith('let '): continue
                    if n.text.lower().startswith('set ') and a[0] not in env: raise UCLError(f'unknown name: {a[0]}; declare it with let first')
                    env[a[0]] = self.expr(a[1], env)
                elif kind == 'property':
                    path, value = a
                    parts = path.split('.')
                    obj = self.expr('.'.join(parts[:-1]), env)
                    if not isinstance(obj, dict) or parts[-1] not in obj: raise UCLError(f'unknown property: {path}')
                    obj[parts[-1]] = self.expr(value, env)
                elif kind == 'create':
                    if env is self.env and n in self.nodes: continue
                    import copy
                    template = self.expr(a[1], env)
                    if not isinstance(template, UCLObject): raise UCLError('create requires an object template')
                    env[a[0]] = copy.deepcopy(template)
                elif kind == 'ask_number':
                    prompt = str(self.expr(a[0], env))
                    while True:
                        try:
                            raw = self.input(prompt).strip()
                        except EOFError as e:
                            raise UCLError('input ended before a number was entered') from e
                        try:
                            try: value = int(raw)
                            except ValueError: value = float(raw)
                            if isinstance(value, float) and not math.isfinite(value):
                                raise ValueError('not finite')
                        except ValueError:
                            self.output('Please enter a valid number.')
                            continue
                        env[a[1]] = value
                        break
                elif kind == 'ask_text':
                    prompt = str(self.expr(a[1], env))
                    try:
                        if a[0].lower() == 'secret':
                            import getpass
                            env[a[2]] = getpass.getpass(prompt)
                        else: env[a[2]] = self.input(prompt)
                    except EOFError as e: raise UCLError('input ended before text was entered') from e
                elif kind == 'log': self.log(a[0].lower(), self.expr(a[1], env))
                elif kind == 'print': self.output(self.expr(a[0], env))
                elif kind == 'assert':
                    if not self.expr(a[0], env): raise UCLError('assertion failed: ' + a[0])
                elif kind == 'read_file': env[a[1]] = Path(self.expr(a[0], env)).read_text(encoding='utf-8')
                elif kind == 'write_file':
                    value, path = str(self.expr(a[1], env)), Path(self.expr(a[2], env))
                    with path.open('a' if a[0].lower() == 'append' else 'w', encoding='utf-8') as stream: stream.write(value)
                elif kind == 'append':
                    if a[1] not in env or not isinstance(env[a[1]], list): raise UCLError('append requires a declared list')
                    env[a[1]].append(self.expr(a[0], env))
                elif kind == 'try':
                    caught_error = None
                    try: self.execute(n.children, env)
                    except UCLError as e:
                        # Execution quotas cannot be caught to escape their limit.
                        if self._steps is not None and self._steps < 0: raise
                        caught_error = str(e)
                elif kind == 'catch':
                    if caught_error is not None:
                        env[a[0]] = caught_error
                        self.execute(n.children, env)
                elif kind == 'break': raise LoopBreak()
                elif kind == 'continue': raise LoopContinue()
                elif kind in {'while', 'for'}:
                    iterable = self.expr(a[1], env) if kind == 'for' else None
                    if kind == 'for' and not isinstance(iterable, (list, tuple, str, dict, range)):
                        raise UCLError('for each requires a collection')
                    iterator = iter(iterable) if kind == 'for' else None
                    while True:
                        self.step()
                        if kind == 'while':
                            if not self.expr(a[0], env): break
                        else:
                            try: env[a[0]] = next(iterator)
                            except StopIteration: break
                        try: self.execute(n.children, env)
                        except LoopBreak: break
                        except LoopContinue: continue
                elif kind == 'close_window': self.ui.close()
                elif kind == 'label_update': self.ui.update(a[0], self.expr(a[1], env), 'label')
                elif kind == 'input_update':
                    spec = self.ui.get(a[0])
                    if spec['kind'] not in {'input', 'checkbox'}: raise UCLError('input update requires input or checkbox')
                    value = self.expr(a[1], env)
                    if spec['kind'] == 'checkbox' and type(value) is not bool: raise UCLError('checkbox values must be true or false')
                    self.ui.update(a[0], value, spec['kind'])
                elif kind == 'classes': self.ui.set_classes(a[0], self.expr(a[1], env))
                elif kind in {'state_style', 'responsive_style'}: self.ui.variant(a[0], a[1].lower(), self.expr(a[2], env))
                elif kind == 'animate': self.ui.animate(a[0], self.expr(a[1], env), int(a[2]))
                elif kind == 'close_interface': self.ui.close_interface()
                elif kind == 'focus_input': self.ui.focus(a[0], bool(a[1]))
                elif kind == 'read_input': env[a[1]] = self.ui.read(a[0])
                elif kind == 'widget_state': self.ui.state(a[1], a[0].lower())
                elif kind == 'widget_style': self.ui.style(a[0], self.expr(a[1], env))
                elif kind == 'header':
                    from .http import response_header
                    name, value = response_header(self.expr(a[0], env), self.expr(a[1], env))
                    env['_headers'][name] = value
                elif kind == 'require':
                    if not self.expr(a[0], env):
                        code = int(a[1])
                        if not 400 <= code <= 599: raise UCLError('require status must be 400–599')
                        env['_status'] = code
                        raise Reply({'error': 'request rejected'})
                elif kind == 'respond_typed': raise Reply(self.expr(a[1], env), a[0].lower())
                elif kind == 'transaction':
                    db = a[0]
                    if db not in self.databases: raise UCLError(f'unknown database: {db}')
                    if db in self._transactions: raise UCLError('nested transactions on the same database are not supported')
                    connection = self.databases[db]
                    self._transactions.add(db)
                    try:
                        connection.execute('BEGIN IMMEDIATE')
                        try: self.execute(n.children, env)
                        except (Returned, LoopBreak, LoopContinue):
                            connection.commit()
                            raise
                        except BaseException:
                            connection.rollback()
                            raise
                        else: connection.commit()
                    finally: self._transactions.remove(db)
                elif kind == 'call': self.expr(f'{a[0]}({a[1]})', env)
                elif kind == 'return': raise Returned(self.expr(a[0], env))
                elif kind == 'if':
                    last_if = bool(self.expr(a[0], env))
                    if last_if: self.execute(n.children, env)
                elif kind == 'otherwise':
                    if not last_if: self.execute(n.children, env)
                elif kind == 'repeat':
                    count = self.expr(a[0], env)
                    if type(count) is not int or count < 0: raise UCLError('repeat count must be a nonnegative integer')
                    for _ in range(count):
                        self.step()
                        try: self.execute(n.children, env)
                        except LoopBreak: break
                        except LoopContinue: continue
                elif kind == 'respond': raise Reply(self.expr(a[0], env))
                elif kind == 'status':
                    code = int(a[0])
                    if not 200 <= code <= 599: raise UCLError('status must be between 200 and 599')
                    env['_status'] = code
                elif kind in {'execute', 'query'}:
                    sql, db, params = a[:3]
                    if db not in self.databases: raise UCLError(f'unknown database: {db}')
                    connection = self.databases[db]
                    with (nullcontext() if db in self._transactions else connection):
                        cur = connection.execute(self.expr(sql, env), self.expr(params, env) if params else ())
                        if kind == 'query':
                            if cur.description is None: raise UCLError('query requires a statement that returns rows; use execute for schema changes')
                            env[a[3]] = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
                elif kind == 'text':
                    if a[0] not in self.buttons: raise UCLError(f'unknown button #{a[0]}')
                    self.ui.update(a[0], self.expr(a[1], env), 'button')
            except (UCLError, sqlite3.Error, OSError, ValueError, TypeError, RuntimeError) as e:
                raise UCLError(f'line {n.line}: {e}') from e

    def close(self):
        server = getattr(self, '_server', None)
        if server:
            server.server_close()
            if server.server.task_dispatcher.threads:
                self.log('warning', 'HTTP workers are still active; database cleanup deferred to avoid closing in-use connections')
                return
        for connection in self.databases.values(): connection.close()
        self.databases.clear()

    def run(self):
        self.prepare()
        self.execute()
        if 'gui' in self.types: self.desktop()
        elif 'tui' in self.types:
            from .tui import run
            run(self)
        elif self.types & {'server', 'browser'}:
            server = self.make_server()
            self.output(f'UCL listening on http://{self.host}:{server.server_port}')
            try: server.serve_forever()
            finally: server.server_close()

    def desktop(self):
        try:
            import tkinter as tk
            window = tk.Tk()
        except Exception as e:
            raise UCLError('Desktop GUI requires Tk and a graphical display. Install python3-tk and run on your desktop; use type is browser only if you want a browser.') from e
        try:
            self.populate_desktop(tk, window)
        except tk.TclError as e:
            window.destroy()
            raise UCLError(f'desktop renderer: {e}') from e

    def populate_desktop(self, tk, window):
        self.ui.mount(tk, window)

    def page(self):
        return self.ui.page('')

    def make_server(self):
        from .http import Server
        self._server = Server(self)
        return self._server
