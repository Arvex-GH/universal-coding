"""UCL scanner, recursive block parser, and declaration validation."""
from dataclasses import dataclass, field
import ast
import re


class UCLError(Exception):
    pass


@dataclass
class Node:
    text: str
    line: int
    children: list = field(default_factory=list)


def scan(source):
    tokens, buf, line, start = [], [], 1, 1
    quote = None
    escape = False
    parens = 0
    braces = 0
    i = 0
    def flush():
        if ''.join(buf).strip():
            tokens.append(('text', ''.join(buf).strip(), start))
        buf.clear()
    while i < len(source):
        c = source[i]
        if quote:
            buf.append(c)
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == quote:
                quote = None
        elif source[i:i+2] == '//':
            while i < len(source) and source[i] != '\n':
                i += 1
            continue
        elif c in '\"\'':
            if not buf: start = line
            quote = c
            buf.append(c)
        elif c in '[]':
            flush()
            tokens.append((c, c, line))
        elif c == '(':
            parens += 1
            buf.append(c)
        elif c == ')':
            parens -= 1
            if parens < 0: raise UCLError(f'line {line}: unexpected )')
            buf.append(c)
        elif c == '{':
            braces += 1
            buf.append(c)
        elif c == '}':
            braces -= 1
            if braces < 0: raise UCLError(f'line {line}: unexpected }}')
            buf.append(c)
        elif c in ',\n' and parens == 0 and braces == 0:
            flush()
        else:
            if not buf: start = line
            buf.append(c)
        if c == '\n': line += 1
        i += 1
    if quote: raise UCLError(f'line {line}: unterminated string')
    if parens: raise UCLError(f'line {line}: unclosed parentheses')
    if braces: raise UCLError(f'line {line}: unclosed object literal')
    flush()
    return tokens


def parse(source):
    tokens = scan(source)
    if not tokens or tokens[0][0] != '[':
        raise UCLError('line 1: an application must be enclosed in [ and ]')
    pos = 1
    def block():
        nonlocal pos
        result = []
        while pos < len(tokens):
            kind, text, line = tokens[pos]
            pos += 1
            if kind == ']': return result
            if kind != 'text': raise UCLError(f'line {line}: a block needs a declaration')
            node = Node(text, line)
            if pos < len(tokens) and tokens[pos][0] == '[':
                pos += 1
                node.children = block()
                node.text += ' []'
            result.append(node)
        raise UCLError('missing closing ]')
    result = block()
    if pos != len(tokens): raise UCLError('unexpected content after application block')
    return result


# Ordered patterns are also consumed by the checker and future editor tooling.
PATTERNS = {
    'type': r'type is (gui|browser|server|terminal|database)',
    'title': r'title is (.+)',
    'port': r'port is (\d+)',
    'host': r'host is (.+)',
    'http_settings': r'http settings is (.+)',
    'debugging': r'debugging is (on|off)',
    'window_style': r'window style is (.+)',
    'window_size': r'window size is (\d+) x (\d+)',
    'layout': r'layout is (vertical|horizontal)',
    'widget_style': r'style #([\w-]+) is (.+)',
    'label_named': r'show (?:label|text) (.+) is #([\w-]+)',
    'input': r'show input (.+) is #([\w-]+)',
    'checkbox': r'show checkbox (.+) is #([\w-]+)',
    'label_update': r'label #([\w-]+) text is (.+)',
    'input_update': r'input #([\w-]+) value is (.+)',
    'read_input': r'read input #([\w-]+) into ([A-Za-z_]\w*)',
    'widget_state': r'(enable|disable|hide|reveal) #([\w-]+)',
    'close_window': r'close window',
    'timer': r'every (\d+) milliseconds \[\]',
    'ask_text': r'ask for (text|secret) (.+) into ([A-Za-z_]\w*)',
    'log': r'log (debug|info|warning|error) (.+)',
    'while': r'while (.+) \[\]',
    'for': r'for each ([A-Za-z_]\w*) in (.+) \[\]',
    'break': r'break',
    'continue': r'continue',
    'try': r'try \[\]',
    'catch': r'catch ([A-Za-z_]\w*) \[\]',
    'assert': r'assert (.+)',
    'read_file': r'read file (.+) into ([A-Za-z_]\w*)',
    'write_file': r'(write|append) (.+) to file (.+)',
    'append': r'append (.+) to ([A-Za-z_]\w*)',
    'respond_typed': r'respond (text|html) (.+)',
    'header': r'header (".*?"|\'.*?\') is (.+)',
    'require': r'require (.+) else status (\d+)',
    'transaction': r'transaction on ([A-Za-z_]\w*) \[\]',
    'property': r'set ([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+) (?:to|is) (.+)',
    'create': r'create ([A-Za-z_]\w*) from ([A-Za-z_]\w*)',
    'let': r'(?:let|set) ([A-Za-z_]\w*) (?:be|to|is) (.+)',
    'ask_number': r'ask for number (.+) into ([A-Za-z_]\w*)',
    'print': r'(?:say|print) (.+)',
    'function': r'to ([A-Za-z_]\w*)\s*\((.*?)\) \[\]',
    'call': r'call ([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\((.*?)\)',
    'return': r'return (.+)',
    'if': r'if (.+) \[\]',
    'otherwise': r'otherwise \[\]',
    'repeat': r'repeat (.+) times \[\]',
    'object': r'object ([A-Za-z_]\w*) \[\]',
    'route': r'when (get|post|put|delete|patch) (".*?"|\'.*?\') \[\]',
    'respond': r'respond (.+)',
    'status': r'status is (\d+)',
    'database': r'database ([A-Za-z_]\w*) is (.+)',
    'execute': r'execute (.+?) on ([A-Za-z_]\w*)(?: using (.+))?',
    'query': r'query (.+?) on ([A-Za-z_]\w*)(?: using (.+?))? into ([A-Za-z_]\w*)',
    'buttons': r'show button(?: (\d+)x)? (.+)',
    'style': r'button #([\w-]+) looks (.+)',
    'click': r'when button #([\w-]+) is clicked \[\]',
    'label': r'show text (.+)',
    'text': r'button #([\w-]+) text is (.+)',
}


def classify(node):
    for name, pattern in PATTERNS.items():
        m = re.fullmatch(pattern, node.text, re.I)
        if m: return name, m.groups()
    raise UCLError(f'line {node.line}: unknown statement: {node.text}')


UI_KINDS = {'buttons', 'style', 'click', 'label', 'text', 'window_style', 'window_size',
            'layout', 'widget_style', 'label_named', 'input', 'checkbox', 'label_update',
            'input_update', 'read_input', 'widget_state'}
DECLARATIONS = {'type', 'title', 'port', 'host', 'function', 'route', 'database', 'buttons',
                'style', 'click', 'label', 'object', 'http_settings', 'debugging',
                'window_style', 'window_size', 'layout', 'label_named', 'input', 'checkbox', 'timer'}


def validate(nodes):
    types = {classify(n)[1][0].lower() for n in nodes if classify(n)[0] == 'type'} or {'terminal'}
    if len(types & {'gui', 'browser', 'server'}) > 1:
        raise UCLError('choose one application renderer: gui, browser, or server')
    def walk(items, scope='root', loop=False, transaction=False):
        previous = None
        for n in items:
            kind, args = classify(n)
            expressions = []
            if kind in {'title', 'host', 'print', 'return', 'if', 'repeat', 'respond', 'label',
                        'ask_number', 'while', 'assert', 'append', 'read_file', 'require',
                        'http_settings', 'window_style', 'label_named', 'input', 'checkbox'}:
                expressions = [args[0]]
            elif kind in {'let', 'property', 'database', 'text', 'label_update', 'input_update',
                          'widget_style', 'ask_text', 'log', 'for', 'respond_typed'}:
                expressions = [args[1]]
            elif kind == 'write_file': expressions = [args[1], args[2]]
            elif kind == 'header': expressions = list(args)
            elif kind == 'call': expressions = [f'{args[0]}({args[1]})']
            elif kind in {'execute', 'query'}: expressions = [args[0]] + ([args[2]] if args[2] else [])
            for expr in expressions:
                try: ast.parse(expr, mode='eval')
                except SyntaxError as e: raise UCLError(f'line {n.line}: invalid expression: {expr}') from e
            if kind in UI_KINDS and not types & {'gui', 'browser'}:
                raise UCLError(f'line {n.line}: add type is gui (desktop) or type is browser')
            if kind in {'timer', 'close_window'} and 'gui' not in types:
                raise UCLError(f'line {n.line}: timers require type is gui; close window also requires gui')
            if kind in {'ask_number', 'ask_text'} and types & {'gui', 'browser', 'server'}:
                raise UCLError(f'line {n.line}: terminal input requires a non-GUI, non-HTTP application')
            if kind == 'route' and 'server' not in types:
                raise UCLError(f'line {n.line}: HTTP routes require type is server')
            if kind == 'http_settings' and not types & {'server', 'browser'}:
                raise UCLError(f'line {n.line}: HTTP settings require server or browser')
            if kind in DECLARATIONS and scope != 'root' and not (scope == 'object' and kind in {'object', 'function'}):
                raise UCLError(f'line {n.line}: {kind} is a declaration and is not allowed here')
            if kind == 'otherwise' and previous != 'if':
                raise UCLError(f'line {n.line}: otherwise must immediately follow if')
            if kind == 'catch' and previous != 'try':
                raise UCLError(f'line {n.line}: catch must immediately follow try')
            if previous == 'try' and kind != 'catch':
                raise UCLError(f'line {n.line}: try requires a following catch')
            if kind in {'respond', 'respond_typed', 'status', 'header', 'require'} and scope != 'route':
                raise UCLError(f'line {n.line}: {kind} requires an HTTP route')
            if transaction and kind in {'respond', 'respond_typed', 'require'}:
                raise UCLError(f'line {n.line}: respond/require must be outside a transaction block')
            if kind == 'return' and scope != 'function':
                raise UCLError(f'line {n.line}: return requires a function')
            if kind in {'break', 'continue'} and not loop:
                raise UCLError(f'line {n.line}: {kind} requires a loop')
            if n.text.endswith(' []'):
                child_scope = kind if kind in {'function', 'route', 'click', 'object', 'timer'} else scope
                child_loop = False if kind in {'function', 'route', 'click', 'object', 'timer'} else loop or kind in {'while', 'for', 'repeat'}
                walk(n.children, child_scope, child_loop, transaction or kind == 'transaction')
            previous = kind
        if previous == 'try': raise UCLError('try requires a following catch')
    walk(nodes)
    return types
