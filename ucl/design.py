"""Validated design values shared by renderers. No raw CSS interpolation from records."""
import re
from .language import UCLError

PALETTES = {
    'light': {'background': '#f8fafc', 'surface': '#ffffff', 'text': '#0f172a', 'muted': '#64748b', 'primary': '#2563eb', 'danger': '#dc2626', 'border': '#cbd5e1'},
    'dark': {'background': '#0f172a', 'surface': '#1e293b', 'text': '#e2e8f0', 'muted': '#94a3b8', 'primary': '#60a5fa', 'danger': '#f87171', 'border': '#475569'},
}
COLORS = set('black white red green blue yellow orange purple pink gray grey navy teal cyan magenta brown silver lime transparent'.split())
ENUMS = {
    'align': {'left','center','right'}, 'font_weight': {'normal','bold'},
    'display': {'block','inline-block','flex','grid','none'},
    'direction': {'row','column','row-reverse','column-reverse'},
    'justify': {'start','end','center','space-between','space-around','space-evenly'},
    'items': {'start','end','center','stretch','baseline'},
    'overflow': {'auto','hidden','visible','scroll'}, 'position': {'static','relative','absolute','fixed','sticky'},
    'cursor': {'auto','pointer','text','default','not-allowed','wait','move'},
    'shadow': {'none','sm','md','lg','xl'}, 'animation': {'none','fade','slide','pulse','spin','bounce'},
    'easing': {'linear','ease','ease-in','ease-out','ease-in-out'},
    'border_style': {'solid','dashed','dotted','double','none'},
    'text_transform': {'none','uppercase','lowercase','capitalize'},
    'white_space': {'normal','nowrap','pre','pre-wrap'},
    'wrap': {'nowrap','wrap','wrap-reverse'},
}
NUMBERS = set('padding margin width height min_width max_width min_height max_height padding_x padding_y margin_x margin_y gap row_gap column_gap border_width radius font_size letter_spacing line_height top right bottom left z_index grow shrink basis rotate translate_x translate_y transition_ms duration_ms'.split())
COLOR_KEYS = {'color','background','border_color','ring_color'}
STYLE_KEYS = set(ENUMS) | NUMBERS | COLOR_KEYS | {'column_span','opacity','scale','font_family','ring_width'}
NATIVE_KEYS = set('color background font_size font_weight font_family padding padding_x padding_y margin margin_x margin_y width height column_span align border_width border_color cursor'.split())
TUI_KEYS = set('color background column_span align font_weight'.split())
CSS_NAMES = {'background':'background-color','align':'text-align','direction':'flex-direction','justify':'justify-content','items':'align-items','radius':'border-radius','wrap':'flex-wrap','grow':'flex-grow','shrink':'flex-shrink','basis':'flex-basis'}
BREAKPOINTS = {'sm':640, 'md':768, 'lg':1024, 'xl':1280, '2xl':1536}


def checked_style(value, tokens=None):
    if not isinstance(value, dict): raise UCLError('style must be a record')
    result = {}
    for key, item in value.items():
        if isinstance(item, str) and item.startswith('$'):
            if not tokens or item[1:] not in tokens: raise UCLError(f'unknown design token: {item}')
            item = tokens[item[1:]]
        if key not in STYLE_KEYS: raise UCLError(f'unknown style property: {key}')
        if key in COLOR_KEYS:
            if not isinstance(item,str) or not (item.lower() in COLORS or re.fullmatch(r'#[a-fA-F0-9]{6}',item)):
                raise UCLError(f'{key} must be a supported color name or #RRGGBB')
        elif key in ENUMS:
            if not isinstance(item,str) or item not in ENUMS[key]: raise UCLError(f'{key} must be one of: {", ".join(sorted(ENUMS[key]))}')
        elif key == 'font_family':
            if not isinstance(item,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 ,_-]{0,100}',item): raise UCLError('invalid font_family')
        elif key in {'opacity','scale'}:
            if type(item) not in {int,float} or not 0 <= item <= (1 if key == 'opacity' else 10): raise UCLError(f'invalid {key}')
        else:
            low, high = (1,12) if key == 'column_span' else (1,512) if key == 'font_size' else (0,60000) if key in {'duration_ms','transition_ms'} else (-4096,4096) if key in {'top','right','bottom','left','z_index','rotate','translate_x','translate_y','letter_spacing'} else (0,4096)
            if type(item) is not int or not low <= item <= high: raise UCLError(f'{key} must be an integer in {low}–{high}')
        result[key] = item
    return result


def supported(style, renderer):
    allowed = NATIVE_KEYS if renderer == 'gui' else TUI_KEYS if renderer == 'tui' else STYLE_KEYS
    extra = set(style) - allowed
    if extra: raise UCLError(f'{renderer} does not support styles: {", ".join(sorted(extra))}; use browser for CSS-only design')
    if renderer != 'browser' and any(style.get(k) == 'transparent' for k in COLOR_KEYS):
        raise UCLError(f'{renderer} does not support transparent colors')
    return style


def css(style):
    out = []
    transforms = []
    for key,value in style.items():
        if key == 'column_span': out.append(f'grid-column:span {value}'); continue
        if key in {'translate_x','translate_y','rotate','scale'}:
            name = {'translate_x':'translateX','translate_y':'translateY'}.get(key,key)
            transforms.append(f'{name}({value}{"px" if key.startswith("translate") else "deg" if key == "rotate" else ""})'); continue
        if key == 'shadow':
            shadows = {'none':'none','sm':'0 1px 2px #00000018','md':'0 4px 6px #00000022','lg':'0 10px 15px #00000026','xl':'0 20px 25px #00000030'}
            out.append('box-shadow:'+shadows[value]); continue
        if key in {'ring_width','ring_color'}: continue
        if key == 'animation':
            if value != 'none': out.append(f'animation:ucl-{value} {style.get("duration_ms",600)}ms {style.get("easing","ease-out")} {"infinite" if value in {"pulse","spin","bounce"} else "both"}')
            continue
        if key == 'duration_ms': continue
        if key == 'easing': out.append('transition-timing-function:'+value); continue
        if key == 'transition_ms': out.append(f'transition:all {value}ms'); continue
        if key in {'padding_x','padding_y','margin_x','margin_y'}:
            prefix,axis = key.split('_')
            for side in (('left','right') if axis == 'x' else ('top','bottom')): out.append(f'{prefix}-{side}:{value}px')
            continue
        name = CSS_NAMES.get(key,key.replace('_','-'))
        unit = 'pt' if key == 'font_size' else 'ch' if key == 'width' else 'px' if key in NUMBERS and key not in {'z_index','grow','shrink'} else ''
        out.append(f'{name}:{value}{unit}')
    if transforms: out.append('transform:'+' '.join(transforms))
    if 'ring_width' in style: out.append(f'outline:{style["ring_width"]}px solid {style.get("ring_color","#2563eb")}')
    return ';'.join(out)


ANIMATIONS = '''
@keyframes ucl-fade{from{opacity:0}to{opacity:1}}
@keyframes ucl-slide{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes ucl-pulse{50%{opacity:.45}}
@keyframes ucl-spin{to{transform:rotate(360deg)}}
@keyframes ucl-bounce{0%,100%{transform:translateY(-12%)}50%{transform:translateY(0)}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
'''
