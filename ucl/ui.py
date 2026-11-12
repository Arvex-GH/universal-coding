"""Shared, ordered widget model for native Tk and server-rendered browser forms."""
import html
import re
from .language import UCLError

COLORS = {'black', 'white', 'red', 'green', 'blue', 'yellow', 'orange', 'purple',
          'pink', 'gray', 'grey', 'navy', 'teal', 'cyan', 'magenta', 'brown', 'silver', 'lime'}
STYLE_KEYS = {'color', 'background', 'font_size', 'font_weight', 'padding', 'margin', 'width'}


def checked_style(value):
    if not isinstance(value, dict): raise UCLError('style must be a record')
    result = {}
    for key, item in value.items():
        if key not in STYLE_KEYS: raise UCLError(f'unknown style property: {key}')
        if key in {'color', 'background'}:
            if not isinstance(item, str) or not (item.lower() in COLORS or re.fullmatch(r'#[0-9a-fA-F]{6}', item)):
                raise UCLError(f'{key} must be a supported color name or #RRGGBB')
        elif key == 'font_weight':
            if item not in {'normal', 'bold'}: raise UCLError('font_weight must be normal or bold')
        elif type(item) is not int or not 0 <= item <= 512 or (key == 'font_size' and item < 1):
            raise UCLError(f'{key} must be an integer in its supported range (0–512; font_size 1–512)')
        result[key] = item
    return result


class UI:
    def __init__(self, runtime):
        self.runtime = runtime
        self.elements = {}
        self.buttons = {}
        self.widgets = {}
        self.variables = {}
        self.captions = {}
        self.direction = 'vertical'
        self.window_style = {}
        self.size = None
        self.window = None
        self.tk = None
        self.closed = False

    def add(self, kind, ident, text):
        if ident == '_csrf': raise UCLError('widget ID _csrf is reserved for browser form security')
        if ident in self.elements: raise UCLError(f'duplicate widget #{ident}')
        spec = {'kind': kind, 'text': str(text), 'value': False if kind == 'checkbox' else '',
                'style': {}, 'enabled': True, 'visible': True, 'padding': 8, 'color': None}
        self.elements[ident] = spec
        if kind == 'button': self.buttons[ident] = spec

    def get(self, ident, kind=None):
        if ident not in self.elements: raise UCLError(f'unknown {kind or "widget"} #{ident}')
        spec = self.elements[ident]
        if kind and spec['kind'] != kind: raise UCLError(f'#{ident} is not a {kind}')
        return spec

    def style(self, ident, style):
        self.get(ident)['style'].update(checked_style(style))
        self.sync(ident)
        if self.window: self.repack()

    def update(self, ident, value, kind):
        spec = self.get(ident, kind)
        spec['value' if kind in {'input', 'checkbox'} else 'text'] = value if kind == 'checkbox' else str(value)
        if ident in self.variables: self.variables[ident].set(spec['value'])
        self.sync(ident)

    def read(self, ident):
        spec = self.get(ident)
        if spec['kind'] not in {'input', 'checkbox'}: raise UCLError('read input requires an input or checkbox')
        return self.variables[ident].get() if ident in self.variables else spec['value']

    def state(self, ident, action):
        spec = self.get(ident)
        if action in {'enable', 'disable'}: spec['enabled'] = action == 'enable'
        else: spec['visible'] = action == 'reveal'
        self.sync(ident)
        if self.window: self.repack()

    def effective_style(self, spec):
        style = dict(self.window_style)
        if spec['color']:
            style.update(background=spec['color'], color='white')
        if spec.get('legacy_padding'): style['padding'] = spec['padding']
        style.update(spec['style'])
        style.setdefault('padding', spec['padding'])
        return style

    def sync(self, ident):
        if self.closed or ident not in self.widgets: return
        spec = self.get(ident)
        style = self.effective_style(spec)
        options = {'font': ('TkDefaultFont', style.get('font_size', 12), style.get('font_weight', 'normal'))}
        if spec['kind'] != 'input': options['text'] = spec['text']
        if spec['kind'] != 'label': options['state'] = 'normal' if spec['enabled'] else 'disabled'
        if 'color' in style: options['fg'] = style['color']
        if 'background' in style: options['bg'] = style['background']
        if 'width' in style: options['width'] = style['width']
        if spec['kind'] in {'label', 'button'}:
            options.update(padx=style['padding'], pady=style['padding'])
        self.widgets[ident].configure(**options)
        if ident in self.captions:
            self.captions[ident].configure(**{k: v for k,v in options.items() if k in {'font', 'fg', 'bg'}})

    def repack(self):
        if self.closed: return
        for widget in list(self.widgets.values()) + list(self.captions.values()): widget.pack_forget()
        for ident, spec in self.elements.items():
            if spec['visible']:
                style = self.effective_style(spec)
                if ident in self.captions:
                    self.captions[ident].pack(side='top' if self.direction == 'vertical' else 'left', padx=8, pady=2)
                self.widgets[ident].pack(side='top' if self.direction == 'vertical' else 'left',
                                         padx=style.get('margin', 8), pady=style.get('margin', 8))

    def close(self):
        if self.closed: return
        if self.window is None: raise UCLError('close window requires an open native window; use it in a handler/timer')
        self.closed = True
        self.window.destroy()

    def mount(self, tk, window):
        self.tk, self.window = tk, window
        window.title(self.runtime.title)
        window.protocol("WM_DELETE_WINDOW", self.close)
        if self.size: window.geometry(f'{self.size[0]}x{self.size[1]}')
        if 'background' in self.window_style: window.configure(bg=self.window_style['background'])
        for ident, spec in self.elements.items():
            kind = spec['kind']
            if kind == 'label': widget = tk.Label(window, text=spec['text'])
            elif kind == 'button':
                def click(key=ident):
                    try: self.runtime.execute(self.runtime.handlers.get(key, []))
                    except UCLError as e:
                        self.runtime.log('error', str(e))
                        from tkinter.messagebox import showerror
                        showerror('UCL error', str(e))
                widget = tk.Button(window, text=spec['text'], command=click)
            else:
                var = tk.BooleanVar(window, value=spec['value']) if kind == 'checkbox' else tk.StringVar(window, value=spec['value'])
                self.variables[ident] = var
                if kind == 'input': self.captions[ident] = tk.Label(window, text=spec['text'])
                widget = tk.Checkbutton(window, text=spec['text'], variable=var) if kind == 'checkbox' else tk.Entry(window, textvariable=var)
            self.widgets[ident] = widget
            self.sync(ident)
        self.repack()
        for delay, body in self.runtime.timers:
            def schedule(ms, nodes):
                def callback():
                    try: self.runtime.execute(nodes)
                    except UCLError as e:
                        self.runtime.log('error', str(e))
                        return
                    if not self.closed: window.after(ms, callback)
                window.after(ms, callback)
            schedule(delay, body)
        window.mainloop()

    def page(self, token):
        escape = lambda x: html.escape(str(x), quote=True)
        def css(style):
            names = {'color': 'color', 'background': 'background-color', 'font_size': 'font-size',
                     'font_weight': 'font-weight', 'padding': 'padding', 'margin': 'margin', 'width': 'width'}
            return ';'.join(names[k] + ':' + str(v) + ('pt' if k == 'font_size' else 'ch' if k == 'width' else 'px' if k in {'padding', 'margin'} else '') for k,v in style.items())
        parts = ['<form method="post"><input type="hidden" name="_csrf" value="' + escape(token) + '">']
        for ident, spec in self.elements.items():
            if not spec['visible']: continue
            attrs = ' id="' + escape(ident) + '" style="' + escape(css(self.effective_style(spec))) + '"'
            if not spec['enabled']: attrs += ' disabled'
            if spec['kind'] == 'label': parts.append('<div' + attrs + '>' + escape(spec['text']) + '</div>')
            elif spec['kind'] == 'button':
                parts.append('<button type="submit" formaction="/__ucl/click/' + escape(ident) + '"' + attrs + '>' + escape(spec['text']) + '</button>')
            elif spec['kind'] == 'input':
                parts.append('<label for="' + escape(ident) + '">' + escape(spec['text']) + '</label><input name="' + escape(ident) + '" value="' + escape(spec['value']) + '"' + attrs + '>')
            else:
                parts.append('<label><input type="checkbox" name="' + escape(ident) + '" value="on"' + (' checked' if spec['value'] else '') + attrs + '>' + escape(spec['text']) + '</label>')
        parts.append('</form>')
        layout = 'column' if self.direction == 'vertical' else 'row'
        return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + escape(self.runtime.title) + '</title></head><body style="' + escape(css(self.window_style)) + '"><main><style>form{display:flex;flex-direction:' + layout + ';align-items:center;gap:8px;max-width:960px;margin:24px auto}input{box-sizing:border-box}</style>' + ''.join(parts) + '</main></body></html>'
