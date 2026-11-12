"""Portable UCL runtime. No Python eval/exec is used for UCL expressions."""
import ast
import html
import json
import math
import operator
import re
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from .language import UCLError, classify, validate


class Returned(Exception):
    def __init__(self, value): self.value = value


class Reply(Exception):
    def __init__(self, value): self.value = value


class UCLObject(dict):
    """Value properties and methods; no access to Python object attributes."""
    def __init__(self):
        super().__init__()
        self.methods = {}


class Runtime:
    def __init__(self, nodes, output=print, input_fn=None):
        self.nodes = nodes
        self.types = validate(nodes)
        self.env = {}
        self.functions = {}
        self.databases = {}
        self.buttons = {}
        self.handlers = {}
        self.routes = {}
        self.labels = []
        self.output = output
        self.input = input if input_fn is None else input_fn
        self.title = 'UCL Application'
        self.port = 8080
        self.host = '127.0.0.1'
        self.lock = threading.RLock()
        self.widgets = {}
        self.prepared = False

    def expr(self, text, env=None):
        env = self.env if env is None else env
        builtins = {'length': len, 'text': str, 'number': float, 'integer': int,
                    'list': lambda *x: list(x), 'min': min, 'max': max, 'round': round,
                    'json': json.dumps, 'parse_json': json.loads, 'abs': abs,
                    'item': operator.getitem, 'keys': lambda x: list(x.keys()),
                    'values': lambda x: list(x.values())}
        binary = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                  ast.Div: operator.truediv, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
        compare = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                   ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
                   ast.In: lambda a,b: a in b, ast.NotIn: lambda a,b: a not in b}
        def visit(n):
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
                    self.buttons[ident] = {'text': str(self.expr(label)), 'color': None, 'padding': 8}
            elif kind == 'label': self.labels.append(str(self.expr(a[0])))
        for n in self.nodes:
            kind, a = classify(n)
            if kind in {'style', 'click'}:
                ident = a[0]
                if ident not in self.buttons: raise UCLError(f'unknown button #{ident}')
                if kind == 'click':
                    if ident in self.handlers: raise UCLError(f'duplicate click handler #{ident}')
                    self.handlers[ident] = n.children
                else:
                    m = re.fullmatch(r'([A-Za-z]+|#[0-9a-fA-F]{6})(?:\s*\+\s*padding is (\d+))?', a[1])
                    if not m: raise UCLError('style must be COLOR + padding is NUMBER')
                    self.buttons[ident]['color'] = m[1]
                    if m[2]: self.buttons[ident]['padding'] = int(m[2])
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

    def execute(self, nodes=None, env=None):
        env = self.env if env is None else env
        last_if = False
        for n in self.nodes if nodes is None else nodes:
            kind, a = classify(n)
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
                elif kind == 'print': self.output(self.expr(a[0], env))
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
                    for _ in range(count): self.execute(n.children, env)
                elif kind == 'respond': raise Reply(self.expr(a[0], env))
                elif kind == 'status':
                    code = int(a[0])
                    if not 200 <= code <= 599: raise UCLError('status must be between 200 and 599')
                    env['_status'] = code
                elif kind in {'execute', 'query'}:
                    sql, db, params = a[:3]
                    if db not in self.databases: raise UCLError(f'unknown database: {db}')
                    connection = self.databases[db]
                    with connection:
                        cur = connection.execute(self.expr(sql, env), self.expr(params, env) if params else ())
                        if kind == 'query':
                            if cur.description is None: raise UCLError('query requires a statement that returns rows; use execute for schema changes')
                            env[a[3]] = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
                elif kind == 'text':
                    if a[0] not in self.buttons: raise UCLError(f'unknown button #{a[0]}')
                    self.buttons[a[0]]['text'] = str(self.expr(a[1], env))
                    if a[0] in self.widgets: self.widgets[a[0]].configure(text=self.buttons[a[0]]['text'])
            except (UCLError, sqlite3.Error) as e:
                raise UCLError(f'line {n.line}: {e}') from e

    def close(self):
        for connection in self.databases.values(): connection.close()

    def run(self):
        self.prepare()
        self.execute()
        if 'gui' in self.types: self.desktop()
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
        window.title(self.title)
        for label in self.labels: tk.Label(window, text=label).pack(padx=12, pady=6)
        for ident, spec in self.buttons.items():
            options = {'text': spec['text'], 'padx': spec['padding'], 'pady': spec['padding']}
            if spec['color']: options.update(bg=spec['color'], fg='white')
            def click(key=ident):
                try: self.execute(self.handlers.get(key, []))
                except UCLError as e:
                    from tkinter.messagebox import showerror
                    showerror('UCL error', str(e))
            widget = tk.Button(window, command=click, **options)
            widget.pack(padx=12, pady=6)
            self.widgets[ident] = widget
        window.mainloop()

    def page(self):
        content = ''.join('<p>' + html.escape(x) + '</p>' for x in self.labels)
        for ident, spec in self.buttons.items():
            style = f'padding:{spec["padding"]}px;'
            if spec['color']: style += f'background:{spec["color"]};color:white;'
            content += '<form method="post" action="/__ucl/click/' + html.escape(ident, quote=True) + '"><button style="' + style + '">' + html.escape(spec['text']) + '</button></form>'
        return '<!doctype html><html><head><meta charset="utf-8"><title>' + html.escape(self.title) + '</title></head><body>' + content + '</body></html>'

    def make_server(self):
        runtime = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def handle_request(self):
                with runtime.lock:
                    parsed = urlsplit(self.path)
                    try:
                        length = int(self.headers.get('Content-Length', '0'))
                        if length < 0 or length > 1048576: return self.send_value(413, {'error': 'body too large'})
                        raw = self.rfile.read(length).decode('utf-8')
                        if 'browser' in runtime.types:
                            if self.command == 'GET' and parsed.path == '/': return self.send_value(200, runtime.page(), True)
                            if self.command == 'POST' and parsed.path.startswith('/__ucl/click/'):
                                # Same-origin forms only; reject cross-site browser submissions.
                                origin = self.headers.get('Origin')
                                if origin and urlsplit(origin).netloc != self.headers.get('Host'): return self.send_value(403, {'error': 'cross-origin request'})
                                ident = parsed.path.rsplit('/', 1)[-1]
                                if ident not in runtime.buttons: return self.send_value(404, {'error': 'unknown button'})
                                runtime.execute(runtime.handlers.get(ident, []))
                                self.send_response(303)
                                self.send_header('Location', '/')
                                self.send_header('Content-Length', '0')
                                self.end_headers()
                                return
                        body = runtime.routes.get((self.command, parsed.path))
                        if body is None: return self.send_value(404, {'error': 'not found'})
                        env = dict(runtime.env)
                        env['request'] = {'method': self.command, 'path': parsed.path, 'query': parse_qs(parsed.query), 'body': raw, 'headers': dict(self.headers)}
                        env['_status'] = 200
                        try: runtime.execute(body, env)
                        except Reply as r: return self.send_value(env['_status'], r.value)
                        return self.send_value(env['_status'], None)
                    except (UCLError, ValueError, TypeError, UnicodeError, RecursionError) as e:
                        runtime.output(str(e))
                        return self.send_value(500, {'error': 'request failed'})
            def send_value(self, status, value, markup=False):
                data = (value if markup else json.dumps(value)).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if markup else 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(data)
            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = handle_request
        server = ThreadingHTTPServer((self.host, self.port), Handler)
        server.daemon_threads = True
        return server
