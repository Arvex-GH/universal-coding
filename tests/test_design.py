import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from ucl import Runtime, UCLError, parse, validate
from ucl.design import checked_style, css, STYLE_KEYS, PALETTES
from ucl.http import HTTPApplication
from ucl.tui import render, run as run_tui


def ready(source, source_name=None):
    r = Runtime(parse(source),output=lambda value: None,diagnostic_fn=lambda value: None)
    if source_name: r.source_name = str(source_name)
    r.prepare()
    r.execute()
    return r


def request(app,path='/',method='GET',body='',cookie=''):
    raw = body.encode()
    env = {'REQUEST_METHOD':method,'PATH_INFO':path,'HTTP_HOST':'localhost','CONTENT_LENGTH':str(len(raw)),
           'wsgi.input':io.BytesIO(raw),'REMOTE_ADDR':'127.0.0.1','wsgi.url_scheme':'http','HTTP_COOKIE':cookie}
    result = {}
    def start(status,headers): result.update(status=int(status.split()[0]),headers=dict(headers))
    result['body'] = b''.join(app(env,start))
    return result


class DesignTests(unittest.TestCase):
    def test_theme_tokens_forward_order(self):
        r = ready('[type is gui\nstyle #x is {"background":"$primary","padding":"$space"}\nshow button "X" is #x\ndesign tokens is {"primary":"#123456","space":14}\ntheme is dark]')
        self.assertEqual(r.ui.get('x')['style'],{'background':'#123456','padding':14})
        self.assertEqual(r.ui.effective_style(r.ui.get('x'))['color'],PALETTES['dark']['text'])

    def test_style_validation_and_renderer_boundaries(self):
        for style in ({'opacity':2},{'animation':'evil'},{'radius':-1},{'font_family':'x; color:red'},{'background':'url(x)'},{'color':True},{'padding':True},{'padding':float('inf')},{'scale':float('nan')},{'unknown':1}):
            with self.subTest(style=style),self.assertRaises(UCLError): checked_style(style)
        for renderer,style in (('gui','{"radius":12}'),('tui','{"font_size":12}'),('gui','{"background":"transparent"}')):
            with self.subTest(renderer=renderer,style=style),self.assertRaises(UCLError): ready(f'[type is {renderer}\nshow label "X" is #x\nstyle #x is {style}]')

    def test_reserved_tokens_validate_as_colors(self):
        with self.assertRaises(UCLError): ready('[type is browser\ntheme is dark\ndesign tokens is {"text":"red;position:fixed"}]')
        with self.assertRaises(UCLError): ready('[type is gui\nshow label "X" is #x\nstyle #x is {"color":"$missing"}]')

    def test_css_groups(self):
        style = checked_style({'padding_x':12,'padding_y':8,'radius':16,'shadow':'lg','opacity':0.5,'rotate':30,'translate_x':12,'scale':1.1,'ring_width':2,'ring_color':'#123456','animation':'slide','duration_ms':200,'transition_ms':300})
        text = css(style)
        for fragment in ('padding-left:12px','padding-bottom:8px','border-radius:16px','box-shadow:','opacity:0.5','rotate(30deg)','translateX(12px)','scale(1.1)','outline:2px solid #123456','ucl-slide 200ms','transition:all 300ms'):
            self.assertIn(fragment,text)

    def test_nested_panels_forward_references_and_order(self):
        r = ready('[type is browser\nplace #b inside #inner\nplace #inner inside #outer\nshow button "Child" is #b\nshow panel "Outer" is #outer\nshow panel "Inner" is #inner\npanel #inner layout is grid 2 columns]')
        page = r.page()
        self.assertLess(page.index('<fieldset id="outer"'),page.index('<fieldset id="inner"'))
        self.assertLess(page.index('<fieldset id="inner"'),page.index('<button type='))
        self.assertIn('grid-template-columns:repeat(2',page)
        self.assertEqual([i for i,*_ in r.ui.positions()],['outer'])

    def test_panel_cycle_and_invalid_parent(self):
        for tail in ('place #a inside #a','place #a inside #b\nplace #b inside #a','place #a inside #missing','panel #a layout is grid 20 columns'):
            with self.subTest(tail=tail),self.assertRaises(UCLError): ready('[type is gui\nshow panel "A" is #a\nshow panel "B" is #b\n'+tail+']')

    def test_native_parent_masters_and_hover_restore(self):
        r = ready('[type is gui\nshow panel "Card" is #card\nshow button "Go" is #go\nplace #go inside #card\nstyle #go is {"background":"#111111"}\nstyle #go when hover is {"background":"#222222"}]')
        tk,window = mock.MagicMock(),mock.MagicMock()
        r.populate_desktop(tk,window)
        self.assertIs(tk.Button.call_args.args[0],tk.LabelFrame.return_value)
        callbacks = {call.args[0]:call.args[1] for call in tk.Button.return_value.bind.call_args_list}
        callbacks['<Enter>'](None)
        self.assertEqual(r.widgets['go'].configure.call_args.kwargs['bg'],'#222222')
        callbacks['<Leave>'](None)
        self.assertEqual(r.widgets['go'].configure.call_args.kwargs['bg'],'#111111')

    def test_responsive_order_and_browser_pseudostates(self):
        r = ready('[type is browser\nshow button "Go" is #go\nstyle #go at lg is {"radius":24}\nstyle #go at sm is {"radius":12}\nstyle #go when hover is {"background":"blue"}\nstyle #go when focus is {"ring_width":2}]')
        page = r.page()
        self.assertLess(page.index('@media(min-width:640px)'),page.index('@media(min-width:1024px)'))
        self.assertIn('[id="go"]:hover',page)
        self.assertIn('[id="go"]:focus',page)
        self.assertIn('prefers-reduced-motion',page)

    def test_native_animation_frames_cancel_and_reduced_motion(self):
        r = ready('[type is gui\nshow label "X" is #x\nstyle #x is {"color":"#000000","font_size":12}]')
        window = r.ui.window = mock.Mock()
        r.widgets['x'] = mock.Mock()
        with mock.patch('ucl.ui.time.monotonic',side_effect=[0,0,0.05,0.1]):
            r.ui.animate('x',{'color':'#ffffff','font_size':24},100)
            callback = window.after.call_args.args[1]
            callback()
            self.assertEqual(r.widgets['x'].configure.call_args.kwargs['fg'],'#808080')
            callback()
            self.assertEqual(r.widgets['x'].configure.call_args.kwargs['fg'],'#ffffff')
        r.ui.animate('x',{'color':'#000000'},100)
        r.ui.style('x',{'color':'#123456'})
        window.after_cancel.assert_called()
        r.ui.motion = False
        r.ui.animate('x',{'color':'#ffffff'},100)
        self.assertEqual(r.widgets['x'].configure.call_args.kwargs['fg'],'#ffffff')

    def test_animation_errors_and_browser_keyframes(self):
        r = ready('[type is gui\nshow label "X" is #x\nstyle #x is {"color":"red"}]')
        with self.assertRaises(UCLError): r.ui.animate('x',{'color':'blue'},100)
        r = ready('[type is browser\nshow label "X" is #x\nstyle #x is {"opacity":0.2}\nanimate #x to {"opacity":1} over 250 milliseconds]')
        self.assertIn('@keyframes ucl-action-0{from{opacity:0.2}to{opacity:1}}',r.page())
        with self.assertRaises(UCLError): r.ui.animate('x',{'opacity':0},60001)
        r.ui.motion = False
        self.assertIn('animation:none!important',r.page())

    def test_capability_and_scope_errors(self):
        for source in ('type is gui\nclasses #x is "rounded"','type is tui\nshow panel "X" is #x','type is tui\nanimate #x to {} over 20 milliseconds','type is terminal\nstyle #x is {}','type is browser\nclose interface','type is tui\ntype is gui','type is gui\nto f() [theme is dark]','type is tui\nask for text "X" into x'):
            with self.subTest(source=source),self.assertRaises(UCLError): validate(parse('['+source+']'))

    def test_stylesheet_path_escaping_and_classes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder)/'app.ucl'
            (Path(folder)/'app.css').write_text('/* </style><script>alert(1)</script> */\n.rounded{border-radius:10px}@media(width < 40rem){.rounded{display:block}}',encoding='utf-8')
            r = ready('[type is browser\nstylesheet is "app.css"\nshow button "<Go>" is #go\nclasses #go is "rounded hover:bg-blue-500"]',file)
            page = r.page()
            self.assertEqual(page.count('</style>'),1)
            self.assertIn(r'\3c /style><script>',page)
            self.assertIn('class="rounded hover:bg-blue-500"',page)
            self.assertIn('&lt;Go&gt;',page)
            self.assertIn('border-radius:10px',page)
            self.assertIn('@media(width < 40rem)',page)

    def test_assets_safe_paths_mime_limits_and_head(self):
        with tempfile.TemporaryDirectory() as folder:
            public = Path(folder)/'public'; public.mkdir()
            (public/'logo.png').write_bytes(b'PNGTEST')
            (public/'bad.html').write_text('<script>bad()</script>')
            (Path(folder)/'private.png').write_bytes(b'SECRET')
            r = ready('[type is browser\nassets is "public"]',Path(folder)/'app.ucl')
            app = HTTPApplication(r)
            response = request(app,'/__ucl/assets/logo.png')
            self.assertEqual(response['status'],200)
            self.assertEqual(response['headers']['Content-Type'],'image/png')
            self.assertEqual(response['body'],b'PNGTEST')
            self.assertEqual(request(app,'/__ucl/assets/logo.png','HEAD')['body'],b'')
            for name in ('../private.png','bad.html','missing.png'):
                self.assertEqual(request(app,'/__ucl/assets/'+name)['status'],404)
            if sys.platform != 'win32':
                (public/'link.png').symlink_to(Path(folder)/'private.png')
                self.assertIsNone(r.ui.asset('link.png'))
            r.http_settings['max_response_bytes'] = 2
            with self.assertRaises(UCLError): r.ui.asset('logo.png')

    def test_hidden_parent_rejects_button_dispatch(self):
        r = ready('[type is browser\nshow panel "P" is #p\nshow button "Go" is #go\nplace #go inside #p\nhide #p]')
        app = HTTPApplication(r)
        response = request(app)
        self.assertNotIn(b'<button',response['body'])
        cookie = response['headers']['Set-Cookie'].split(';',1)[0]
        token = cookie.split('=',1)[1]
        response = request(app,'/__ucl/click/go','POST','_csrf='+token,cookie)
        self.assertEqual(response['status'],403)

    def test_tui_input_checkbox_handler_and_close(self):
        r = ready(Path('examples/tui-dashboard.ucl').read_text())
        commands = iter(['1','Updated name','2','3','4'])
        pages = []
        run_tui(r,lambda prompt: next(commands),pages.append,color=False)
        self.assertEqual(r.ui.get('name')['value'],'Updated name')
        self.assertTrue(r.ui.get('notifications')['value'])
        self.assertEqual(r.ui.get('status')['text'],'Saved: Updated name')
        self.assertTrue(r.ui.closed)
        self.assertNotIn('\x1b',''.join(pages))

    def test_tui_ansi_sanitization_and_disabled_controls(self):
        r = ready('[type is tui\ntheme is dark\nshow label "hello" is #x\nshow button "Go" is #go\ndisable #go]')
        r.ui.update('x','untrusted\x1b[2J','label')
        page,actions = render(r.ui,40,color=True)
        self.assertIn('\x1b[38;2;',page)
        self.assertNotIn('\x1b[2J',page)
        self.assertEqual(actions,{})
        self.assertIn('(disabled)',page)

    def test_style_matrix_generated(self):
        from tools.generate_design import markdown
        self.assertEqual(Path('docs/reference/styles.md').read_text(encoding='utf-8'),markdown())

    def test_same_origin_referrer_policy_for_browser_postbacks(self):
        r = ready('[type is browser]')
        self.assertEqual(request(HTTPApplication(r))['headers']['Referrer-Policy'],'same-origin')

    def test_tui_ascii_fallback_for_legacy_consoles(self):
        r = ready('[type is tui\nshow label "ASCII_OK" is #x]')
        page,_ = render(r.ui,color=False,ascii_only=True)
        page.encode('cp1252')
        self.assertIn('ASCII_OK',page)
        self.assertIn('+---',page)
        outputs = []
        with mock.patch('ucl.tui.sys.stdout') as stream:
            stream.encoding = 'cp1252'
            run_tui(r,lambda prompt:'q',outputs.append,color=False)
        self.assertNotIn('┌',outputs[0])

    def test_editor_vocabulary_generated(self):
        from tools.generate_editor import data
        self.assertEqual(json.loads(Path('editors/vscode/language-data.json').read_text()),data())

    def test_all_examples_prepare(self):
        for name in ('native-design.ucl','design-studio.ucl','tui-dashboard.ucl','modern-calculator.ucl'):
            path = Path('examples')/name
            with self.subTest(name=name):
                r = ready(path.read_text(encoding='utf-8'),path)
                r.close()

    def test_tailwind_command_arguments_no_shell(self):
        from ucl.tailwind import compile_styles
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source ; literal.ucl'; source.write_text('[type is browser]')
            with mock.patch('ucl.tailwind.shutil.which',return_value='/path/npx'),mock.patch('ucl.tailwind.subprocess.run',return_value=mock.Mock(returncode=0)) as call:
                compile_styles(source,Path(folder)/'output.css')
                args = call.call_args.args[0]
                self.assertEqual(args[:3],['/path/npx','--yes','tailwindcss@3.4.19'])
                self.assertNotIn('shell',call.call_args.kwargs)
        with mock.patch('ucl.tailwind.shutil.which',return_value=None),self.assertRaises(UCLError): compile_styles('missing','x')


@unittest.skipUnless(sys.platform == 'win32','Real Tk exercised on Windows CI')
class NativeTkTests(unittest.TestCase):
    def test_real_nested_native_theme_and_animations(self):
        import tkinter as tk
        r = ready(Path('examples/native-design.ucl').read_text(encoding='utf-8'))
        window = tk.Tk()
        window.withdraw()
        try:
            with mock.patch.object(window,'mainloop'):
                r.populate_desktop(tk,window)
            self.assertEqual(r.widgets['save'].cget('bg'),'#8b5cf6')
            self.assertEqual(r.widgets['save'].master,r.widgets['actions'])
            r.execute(r.handlers['save'])
            self.assertEqual(r.widgets['status'].cget('text'),'Saved: New project')
            window.after(500,window.quit)
            window.mainloop()
            self.assertEqual(r.widgets['status'].cget('fg'),'#34d399')
        finally:
            r.ui.close()
