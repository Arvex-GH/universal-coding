"""Portable line-oriented terminal UI; no browser, curses, or raw-mode dependency."""
import re
import shutil
import sys
from .language import UCLError

NAMED = {'black':'#000000','white':'#ffffff','red':'#ff0000','green':'#008000','blue':'#0000ff','yellow':'#ffff00','orange':'#ffa500','purple':'#800080','pink':'#ffc0cb','gray':'#808080','grey':'#808080','navy':'#000080','teal':'#008080','cyan':'#00ffff','magenta':'#ff00ff','brown':'#a52a2a','silver':'#c0c0c0','lime':'#00ff00'}


def safe(value):
    # Neither user input nor app text may inject terminal escape sequences.
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def paint(text, style, color):
    if not color: return text
    codes = []
    for key,code in (('color',38),('background',48)):
        value = style.get(key)
        if not value: continue
        value = NAMED.get(value.lower(),value)
        if re.fullmatch(r'#[a-fA-F0-9]{6}',value): codes.append(f'{code};2;' + ';'.join(str(int(value[i:i+2],16)) for i in (1,3,5)))
    if style.get('font_weight') == 'bold': codes.append('1')
    return ('\x1b['+';'.join(codes)+'m'+text+'\x1b[0m') if codes else text


def render(ui, width=80, color=False):
    width = max(20,min(width,240))
    visible = [i for i,s in ui.elements.items() if s['visible']]
    columns = ui.columns if ui.direction == 'grid' else max(1,min(12,len(visible))) if ui.direction == 'horizontal' else 1
    cell = max(1,(width-2-(columns-1))//columns)
    rows = {}
    actions = {}
    number = 0
    positions = list(ui.positions()) if ui.direction == 'grid' else [(ident,index//columns,index%columns,1) for index,ident in enumerate(visible)]
    for ident,row,column,span in positions:
        spec = ui.get(ident)
        style = ui.effective_style(spec)
        text = spec['text']
        if spec['kind'] != 'label':
            number += 1
            if spec['enabled']: actions[str(number)] = ident
            if spec['kind'] == 'input': text += ': ' + str(spec['value'])
            elif spec['kind'] == 'checkbox': text = ('[x] ' if spec['value'] else '[ ] ') + text
            text = f'{number}. {text}' + ('' if spec['enabled'] else ' (disabled)')
        size = cell*span + span-1
        text = safe(text)[:size]
        align = style.get('align','left')
        text = text.rjust(size) if align == 'right' else text.center(size) if align == 'center' else text.ljust(size)
        rows.setdefault(row,[]).append((column,span,paint(text,style,color)))
    lines = ['┌'+'─'*(width-2)+'┐', '│'+safe(ui.runtime.title)[:width-2].center(width-2)+'│', '├'+'─'*(width-2)+'┤']
    for row in sorted(rows):
        chunks, previous = [],0
        for column,span,text in rows[row]:
            if column > previous: chunks.append(' '*((column-previous)*(cell+1)))
            chunks.append(text)
            previous = column+span
            if previous < columns: chunks.append(' ')
        content = ''.join(chunks)
        # ANSI sequences do not contribute to the visible width.
        visible = len(re.sub(r'\x1b\[[0-9;]*m','',content))
        lines.append('│'+content+' '*max(0,width-2-visible)+'│')
    lines += ['└'+'─'*(width-2)+'┘', 'Enter a control number to activate/edit; q to quit.']
    return '\n'.join(lines),actions


def run(runtime, input_fn=None, output=None, color=None):
    input_fn = input if input_fn is None else input_fn
    output = runtime.output if output is None else output
    color = sys.stdout.isatty() if color is None else color
    ui = runtime.ui
    while not ui.closed:
        page, actions = render(ui,shutil.get_terminal_size((80,24)).columns,color)
        output(page)
        try: command = input_fn('> ').strip()
        except EOFError: break
        if command.lower() in {'q','quit','exit'}: break
        ident = actions.get(command)
        if ident is None:
            output('Choose an enabled control number or q.')
            continue
        spec = ui.get(ident)
        try:
            if spec['kind'] == 'button': runtime.execute(runtime.handlers.get(ident,[]))
            elif spec['kind'] == 'checkbox': ui.update(ident,not spec['value'],'checkbox')
            else: ui.update(ident,input_fn(safe(spec['text'])+': '),'input')
        except EOFError: break
        except UCLError as error: output('Error: '+safe(error))
    ui.closed = True
