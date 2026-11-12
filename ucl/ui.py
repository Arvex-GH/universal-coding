"""Shared, ordered widget model for native Tk and server-rendered browser forms."""
import html
import re
from .language import UCLError

from pathlib import Path
import time
from .design import checked_style, supported, css, PALETTES, BREAKPOINTS, ANIMATIONS


class UI:
    def __init__(self, runtime):
        self.runtime = runtime
        self.elements = {}
        self.buttons = {}
        self.widgets = {}
        self.variables = {}
        self.captions = {}
        self.direction = 'vertical'
        self.columns = 4
        self.window_style = {}
        self.size = None
        self.window = None
        self.tk = None
        self.closed = False
        self.focused = None
        self.theme = None
        self.tokens = {}
        self.motion = True
        self.stylesheet = ''
        self.assets = None
        self.native_defaults = {}
        self.animation_jobs = {}
        self.animation_versions = {}
        self.animation_current = {}
        self.browser_animations = {}


    def add(self, kind, ident, text):
        if ident == '_csrf': raise UCLError('widget ID _csrf is reserved for browser form security')
        if ident in self.elements: raise UCLError(f'duplicate widget #{ident}')
        spec = {'kind': kind, 'text': str(text), 'value': False if kind == 'checkbox' else '',
                'parent': None, 'layout': ('vertical', 4), 'style': {}, 'variants': {}, 'classes': '', 'states': set(), 'enabled': True, 'visible': True, 'padding': 8, 'color': None}
        self.elements[ident] = spec
        if kind == 'button': self.buttons[ident] = spec

    def get(self, ident, kind=None):
        if ident not in self.elements: raise UCLError(f'unknown {kind or "widget"} #{ident}')
        spec = self.elements[ident]
        if kind and spec['kind'] != kind: raise UCLError(f'#{ident} is not a {kind}')
        return spec

    def style(self, ident, style):
        if self.renderer == 'gui' and self.get(ident)['kind'] == 'input' and 'height' in style:
            raise UCLError('native single-line input does not support height; use font_size')
        self.cancel_animation(ident)
        self.get(ident)['style'].update(self.check_style(style))
        self.sync(ident)
        if self.window: self.repack()

    @property
    def renderer(self):
        return next((x for x in ('gui', 'browser', 'tui') if x in self.runtime.types), 'browser')

    def check_style(self, style):
        return supported(checked_style(style, self.tokens), self.renderer)

    def place(self, ident, parent):
        spec = self.get(ident)
        self.get(parent, 'panel')
        ancestor = parent
        while ancestor is not None:
            if ancestor == ident: raise UCLError('panels cannot contain themselves or form a cycle')
            ancestor = self.get(ancestor)['parent']
        spec['parent'] = parent

    def panel_layout(self, ident, direction, columns):
        count = int(columns) if columns else 4
        if not 1 <= count <= 12: raise UCLError('grid columns must be 1–12')
        self.get(ident, 'panel')['layout'] = ('grid' if columns else direction.lower(), count)

    def set_theme(self, name):
        self.theme = name
        self.tokens.update(PALETTES[name])

    def set_tokens(self, tokens):
        if not isinstance(tokens, dict) or any(not re.fullmatch(r'[a-zA-Z][\w-]*', k) for k in tokens):
            raise UCLError('design tokens must be a record with named keys')
        # Validate values at their point of use; tokens can be colors or dimensions.
        for key,value in tokens.items():
            if key in PALETTES['light']: self.check_style({'color':value})
        self.tokens.update(tokens)

    def set_classes(self, ident, value):
        if not isinstance(value, str) or len(value) > 16384 or any(ord(c) < 32 and c not in '\t\n\r' for c in value):
            raise UCLError('classes must be a string of at most 16384 characters')
        self.get(ident)['classes'] = value

    def variant(self, ident, state, style):
        spec = self.get(ident)
        spec['variants'].setdefault(state, {}).update(self.check_style(style))
        self.sync(ident)

    def set_assets(self, value):
        if not isinstance(value,str): raise UCLError('assets requires a directory path')
        base = Path(self.runtime.source_name).resolve().parent if self.runtime.source_name != '<program>' else Path.cwd()
        directory = (base/value).resolve()
        if not directory.is_dir(): raise UCLError('assets directory does not exist')
        self.assets = directory

    def asset(self, name):
        types = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.svg':'image/svg+xml','.ico':'image/x-icon','.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf','.otf':'font/otf'}
        if self.assets is None: return None
        target = (self.assets/name).resolve()
        if not target.is_relative_to(self.assets) or not target.is_file() or target.suffix.lower() not in types: return None
        if target.stat().st_size > self.runtime.http_settings.get('max_response_bytes',4194304): raise UCLError('asset exceeds max_response_bytes')
        return target.read_bytes(),types[target.suffix.lower()]

    def load_stylesheet(self, value):
        if not isinstance(value, str): raise UCLError('stylesheet requires a file path')
        base = Path(self.runtime.source_name).resolve().parent if self.runtime.source_name != '<program>' else Path.cwd()
        path = base / value
        if path.stat().st_size > 8 * 1024 * 1024: raise UCLError('stylesheet exceeds 8 MiB')
        self.stylesheet = path.read_text(encoding='utf-8')

    def close_interface(self):
        if self.renderer == 'gui': self.close()
        else: self.closed = True

    def cancel_animation(self, ident):
        self.animation_versions[ident] = self.animation_versions.get(ident, 0) + 1
        job = self.animation_jobs.pop(ident, None)
        if job is not None and self.window is not None: self.window.after_cancel(job)
        self.browser_animations.pop(ident, None)
        self.animation_current.pop(ident, None)

    def animate(self, ident, target, duration):
        if not 0 <= duration <= 60000: raise UCLError('animation duration must be 0–60000 milliseconds')
        target = self.check_style(target)
        before = self.effective_style(self.get(ident))
        if self.renderer == 'gui':
            for key, value in target.items():
                if key not in before or not (type(value) is int and type(before[key]) is int or
                    isinstance(value, str) and isinstance(before[key], str) and re.fullmatch(r'#[a-fA-F0-9]{6}',value) and re.fullmatch(r'#[a-fA-F0-9]{6}',before[key])):
                    raise UCLError('native animation requires existing integer or #RRGGBB style values')
        self.cancel_animation(ident)
        self.get(ident)['style'].update(target)
        if not self.motion or duration == 0:
            self.sync(ident)
            if self.window: self.repack()
            return
        if self.renderer == 'browser':
            self.browser_animations[ident] = (before, target, duration)
            return
        if not self.window: return  # Initial state is applied when the window mounts.
        version = self.animation_versions[ident]
        start = time.monotonic()
        def frame():
            if self.closed or self.animation_versions[ident] != version: return
            fraction = min(1, (time.monotonic() - start) * 1000 / duration)
            values = {}
            for key,value in target.items():
                old = before[key]
                if isinstance(value,str):
                    parts = [round(int(old[i:i+2],16) + (int(value[i:i+2],16)-int(old[i:i+2],16))*fraction) for i in (1,3,5)]
                    values[key] = '#' + ''.join(f'{v:02x}' for v in parts)
                else: values[key] = round(old + (value-old)*fraction)
            self.animation_current[ident] = values
            self.sync(ident)
            self.repack()
            if fraction < 1: self.animation_jobs[ident] = self.window.after(16, frame)
            else:
                self.animation_jobs.pop(ident, None)
                self.animation_current.pop(ident, None)
        frame()

    def update(self, ident, value, kind):
        spec = self.get(ident, kind)
        spec['value' if kind in {'input', 'checkbox'} else 'text'] = value if kind == 'checkbox' else str(value)
        if ident in self.variables: self.variables[ident].set(spec['value'])
        self.sync(ident)

    def read(self, ident):
        spec = self.get(ident)
        if spec['kind'] not in {'input', 'checkbox'}: raise UCLError('read input requires an input or checkbox')
        return self.variables[ident].get() if ident in self.variables else spec['value']

    def focus(self, ident, select=False):
        self.get(ident, 'input')
        self.focused = (ident, select)
        if self.closed: return
        if ident in self.widgets:
            widget = self.widgets[ident]
            widget.focus_set()
            widget.selection_clear()
            if select: widget.selection_range(0, 'end')
            else: widget.icursor('end')

    def available(self, ident):
        while ident is not None:
            spec = self.get(ident)
            if not spec['visible'] or not spec['enabled']: return False
            ident = spec['parent']
        return True

    def state(self, ident, action):
        spec = self.get(ident)
        if action in {'enable', 'disable'}: spec['enabled'] = action == 'enable'
        else: spec['visible'] = action == 'reveal'
        self.sync(ident)
        if self.get(ident)['kind'] == 'panel':
            for child in self.elements: self.sync(child)
        if self.window: self.repack()

    def effective_style(self, spec):
        style = {}
        if self.theme:
            style.update(background=self.tokens['surface'], color=self.tokens['text'], font_size=12, padding=10, margin=6, border_width=0)
        style.update(self.window_style)
        if spec['color']:
            style.update(background=spec['color'], color='white')
        if spec.get('legacy_padding'): style['padding'] = spec['padding']
        style.update(spec['style'])
        style.setdefault('padding', spec['padding'])
        for state in ('hover', 'focus', 'active', 'disabled'):
            if state in spec['states'] or state == 'disabled' and not spec['enabled']:
                style.update(spec['variants'].get(state, {}))
        return style

    def sync(self, ident, override=None):
        if self.closed or ident not in self.widgets: return
        spec = self.get(ident)
        style = self.effective_style(spec)
        style.update(self.animation_current.get(ident,{}))
        if override: style.update(override)
        options = dict(self.native_defaults.get(ident, {}))
        options['font'] = (style.get('font_family', 'TkDefaultFont'), style.get('font_size', 12), style.get('font_weight', 'normal'))
        if spec['kind'] != 'input': options['text'] = spec['text']
        if spec['kind'] not in {'label', 'panel'}: options['state'] = 'normal' if self.available(ident) else 'disabled'
        if 'color' in style:
            options['fg'] = style['color']
            if spec['kind'] not in {'label','panel'}: options['disabledforeground'] = style['color']
        if 'background' in style: options['bg'] = style['background']
        if 'width' in style: options['width'] = style['width']
        if 'height' in style and spec['kind'] != 'input': options['height'] = style['height']
        if 'border_color' in style: options.update(highlightbackground=style['border_color'], highlightcolor=style['border_color'], highlightthickness=1)
        if 'cursor' in style: options['cursor'] = {'pointer':'hand2','text':'xterm','default':'arrow','auto':'arrow','wait':'watch','not-allowed':'X_cursor','move':'fleur'}[style['cursor']]
        if 'border_width' in style: options.update(bd=style['border_width'], relief='flat')
        if 'align' in style and spec['kind'] == 'panel': options['labelanchor'] = {'left':'nw','center':'n','right':'ne'}[style['align']]
        if 'align' in style and spec['kind'] != 'panel':
            options['justify'] = style['align']
            if spec['kind'] != 'input': options['anchor'] = {'left': 'w', 'center': 'center', 'right': 'e'}[style['align']]
        if spec['kind'] == 'button' and 'background' in style:
            options['activebackground'] = style['background']
            if 'color' in style: options['activeforeground'] = style['color']
        if spec['kind'] in {'label', 'button', 'panel'}:
            options.update(padx=style.get('padding_x', style['padding']), pady=style.get('padding_y', style['padding']))
        self.widgets[ident].configure(**options)
        if ident in self.captions:
            self.captions[ident].configure(**{k: v for k,v in options.items() if k in {'font', 'fg', 'bg'}})

    def positions(self, parent=None):
        row, column = 0, 0
        columns = self.columns if parent is None else self.get(parent)['layout'][1]
        for ident, spec in self.elements.items():
            if not spec['visible'] or spec['parent'] != parent: continue
            span = min(columns, self.effective_style(spec).get('column_span', 1))
            if column + span > columns: row, column = row + 1, 0
            yield ident, row, column, span
            column += span
            if column == columns: row, column = row + 1, 0

    def repack(self):
        if self.closed: return
        for parent, container in [(None,self.window)] + [(i,self.widgets[i]) for i,s in self.elements.items() if s['kind'] == 'panel']:
            direction, columns = (self.direction,self.columns) if parent is None else self.get(parent)['layout']
            children = [i for i,s in self.elements.items() if s['parent'] == parent]
            for ident in children:
                for widget in [self.widgets[ident]] + ([self.captions[ident]] if ident in self.captions else []):
                    widget.grid_forget() if direction == 'grid' else widget.pack_forget()
            if direction == 'grid':
                for column in range(columns): container.columnconfigure(column, weight=1, uniform='ucl')
                positions = list(self.positions(parent))
                caption_rows = sorted({row for ident,row,_,_ in positions if ident in self.captions})
                for ident,row,column,span in positions:
                    offset = sum(r < row for r in caption_rows)
                    style = self.effective_style(self.get(ident))
                    style.update(self.animation_current.get(ident,{}))
                    if ident in self.captions:
                        self.captions[ident].grid(row=row+offset,column=column,columnspan=span,sticky='ew')
                    self.widgets[ident].grid(row=row+offset+int(row in caption_rows),column=column,columnspan=span,
                        sticky='nsew',padx=style.get('margin_x',style.get('margin',8)),pady=style.get('margin_y',style.get('margin',8)))
            else:
                for ident in children:
                    spec = self.get(ident)
                    if not spec['visible']: continue
                    style = self.effective_style(spec)
                    style.update(self.animation_current.get(ident,{}))
                    if ident in self.captions:
                        self.captions[ident].pack(side='top' if direction == 'vertical' else 'left',padx=8,pady=2)
                    self.widgets[ident].pack(side='top' if direction == 'vertical' else 'left', fill='x' if direction == 'vertical' else 'both',
                        padx=style.get('margin_x',style.get('margin',8)),pady=style.get('margin_y',style.get('margin',8)))

    def close(self):
        if self.closed: return
        if self.window is None: raise UCLError('close window requires an open native window; use it in a handler/timer')
        self.closed = True
        for ident in list(self.animation_jobs): self.cancel_animation(ident)
        self.window.destroy()

    def mount(self, tk, window):
        self.tk, self.window = tk, window
        window.title(self.runtime.title)
        window.protocol("WM_DELETE_WINDOW", self.close)
        if self.size: window.geometry(f'{self.size[0]}x{self.size[1]}')
        if 'background' in self.window_style: window.configure(bg=self.window_style['background'])
        elif self.theme: window.configure(bg=self.tokens['background'])
        def ordered(parent=None):
            for ident,spec in self.elements.items():
                if spec['parent'] == parent:
                    yield ident,spec
                    if spec['kind'] == 'panel': yield from ordered(ident)
        for ident, spec in ordered():
            master = self.widgets[spec['parent']] if spec['parent'] else window
            kind = spec['kind']
            if kind == 'panel': widget = tk.LabelFrame(master, text=spec['text'])
            elif kind == 'label': widget = tk.Label(master, text=spec['text'])
            elif kind == 'button':
                def click(key=ident):
                    if not self.available(key): return
                    try: self.runtime.execute(self.runtime.handlers.get(key, []))
                    except UCLError as e:
                        self.runtime.log('error', str(e))
                        from tkinter.messagebox import showerror
                        showerror('UCL error', str(e))
                widget = tk.Button(master, text=spec['text'], command=click)
            else:
                var = tk.BooleanVar(window, value=spec['value']) if kind == 'checkbox' else tk.StringVar(window, value=spec['value'])
                self.variables[ident] = var
                if kind == 'input' and spec['text']: self.captions[ident] = tk.Label(master, text=spec['text'])
                widget = tk.Checkbutton(master, text=spec['text'], variable=var) if kind == 'checkbox' else tk.Entry(master, textvariable=var)
            self.widgets[ident] = widget
            keys = ['fg', 'bg', 'width', 'bd', 'relief', 'cursor', 'highlightbackground', 'highlightcolor', 'highlightthickness']
            if kind != 'panel': keys.append('justify')
            else: keys.append('labelanchor')
            if kind not in {'panel','input'}: keys += ['anchor', 'height']
            if kind == 'button': keys += ['activebackground','activeforeground']
            if kind not in {'label','panel'}: keys.append('disabledforeground')
            self.native_defaults[ident] = {key:widget.cget(key) for key in keys}
            for event, state, enabled in (('<Enter>', 'hover', True), ('<Leave>', 'hover', False), ('<FocusIn>', 'focus', True), ('<FocusOut>', 'focus', False), ('<ButtonPress-1>', 'active', True), ('<ButtonRelease-1>', 'active', False)):
                def change_state(event, key=ident, name=state, on=enabled):
                    states = self.get(key)['states']
                    states.add(name) if on else states.discard(name)
                    self.sync(key)
                    if any(k in self.get(key)['variants'].get(name,{}) for k in {'margin','margin_x','margin_y','column_span'}): self.repack()
                widget.bind(event, change_state, add='+')
            self.sync(ident)
        self.repack()
        if self.focused: self.focus(*self.focused)
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
        rules = ['*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif}main{padding:24px}form{gap:8px;max-width:960px;margin:0 auto}button,input{font:inherit;border-style:solid}input{background:inherit;color:inherit;border-color:inherit}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.5}label{display:flex;flex-direction:column;gap:6px}input:not([type=checkbox]){width:100%;min-width:0}input:focus-visible,button:focus-visible{outline:2px solid #2563eb;outline-offset:3px}']
        body = dict(self.window_style)
        if self.theme:
            body = {'background': self.tokens['background'], 'color': self.tokens['text'], **body}
        rules.append('body{' + css(body) + '}')
        layout_css = f'display:grid;grid-template-columns:repeat({self.columns},minmax(0,1fr))' if self.direction == 'grid' else 'display:flex;flex-direction:' + ('column' if self.direction == 'vertical' else 'row')
        rules.append('form{' + layout_css + ';align-items:stretch}')
        parts = ['<form method="post"><input type="hidden" name="_csrf" value="' + escape(token) + '">']
        markup = {}
        grid_positions = {ident: (row,col,span) for parent in [None]+[i for i,s in self.elements.items() if s['kind'] == 'panel'] for ident,row,col,span in self.positions(parent)}
        for index,(ident,spec) in enumerate(self.elements.items()):
            if not spec['visible']: continue
            selector = '[id="' + ident + '"]'
            style = self.effective_style(spec)
            placement = ''
            direction = self.direction if spec['parent'] is None else self.get(spec['parent'])['layout'][0]
            if direction == 'grid':
                row,col,span = grid_positions[ident]
                placement = f';grid-column:{col+1}/span {span};grid-row:{row+1}'
            if spec['kind'] == 'panel':
                panel_direction,columns = spec['layout']
                panel_css = f'display:grid;grid-template-columns:repeat({columns},minmax(0,1fr))' if panel_direction == 'grid' else 'display:flex;flex-direction:' + ('column' if panel_direction == 'vertical' else 'row')
                rules.append(selector + '{min-width:0;gap:8px;' + panel_css + '}')
            rules.append(selector + '{' + css(style) + placement + '}')
            for state, variant in sorted(spec['variants'].items(),key=lambda entry: BREAKPOINTS.get(entry[0],0)):
                if state in BREAKPOINTS:
                    rules.append(f'@media(min-width:{BREAKPOINTS[state]}px)' + '{' + selector + '{' + css(variant) + '}}')
                else:
                    pseudo = ':focus-within' if state == 'focus' and spec['kind'] in {'input','checkbox'} else ':has(:disabled)' if state == 'disabled' and spec['kind'] in {'input','checkbox'} else ':' + state
                    rules.append(selector + pseudo + '{' + css(variant) + '}')
            if ident in self.browser_animations and self.motion:
                before,target,duration = self.browser_animations[ident]
                name = f'ucl-action-{index}'
                rules.append('@keyframes ' + name + '{from{' + css({k:before[k] for k in target if k in before}) + '}to{' + css(target) + '}}')
                rules.append(selector + '{animation:' + name + f' {duration}ms ease-out both' + '}')
            attrs = ' id="' + escape(ident) + '" class="' + escape(spec['classes']) + '"'
            disabled = '' if self.available(ident) else ' disabled'
            if spec['kind'] == 'panel':
                direction,columns = spec['layout']
                panel_css = f'display:grid;grid-template-columns:repeat({columns},minmax(0,1fr))' if direction == 'grid' else 'display:flex;flex-direction:' + ('column' if direction == 'vertical' else 'row')
                markup[ident] = '<fieldset' + attrs + disabled + '><legend>' + escape(spec['text']) + '</legend>'
            elif spec['kind'] == 'label': markup[ident] = '<div' + attrs + '>' + escape(spec['text']) + '</div>'
            elif spec['kind'] == 'button':
                markup[ident] = '<button type="submit" formaction="/__ucl/click/' + escape(ident) + '"' + attrs + disabled + '>' + escape(spec['text']) + '</button>'
            elif spec['kind'] == 'input':
                caption = '<span>' + escape(spec['text']) + '</span>' if spec['text'] else ''
                markup[ident] = '<label' + attrs + '>' + caption + '<input name="' + escape(ident) + '" value="' + escape(spec['value']) + '"' + disabled + ' aria-label="' + escape(spec['text'] or 'Value') + '"></label>'
            else:
                markup[ident] = '<label' + attrs + '><input type="checkbox" name="' + escape(ident) + '" value="on"' + (' checked' if spec['value'] else '') + disabled + '>' + escape(spec['text']) + '</label>'
        def children(parent=None):
            result = []
            for ident,spec in self.elements.items():
                if spec['parent'] != parent or not spec['visible']: continue
                result.append(markup[ident])
                if spec['kind'] == 'panel': result.append(children(ident) + '</fieldset>')
            return ''.join(result)
        parts.append(children())
        parts.append('</form>')
        rules.append(self.stylesheet)
        rules.append(ANIMATIONS)
        if not self.motion: rules.append('*,*::before,*::after{animation:none!important;transition:none!important}')
        # Stylesheets are trusted application assets, but cannot break out of <style>.
        stylesheet = re.sub(r'</style', lambda match: r'\3c /style', '\n'.join(rules), flags=re.I)
        return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + escape(self.runtime.title) + '</title><style>' + stylesheet + '</style></head><body><main>' + ''.join(parts) + '</main></body></html>'
