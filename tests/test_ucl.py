import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
import urllib.request
import urllib.error
from pathlib import Path
from ucl import Runtime, UCLError, parse, validate
from ucl.native import build, emit_c


def runtime(source):
    output = []
    r = Runtime(parse(source), output.append)
    r.prepare()
    r.execute()
    return r, output


class TerminalInputTests(unittest.TestCase):
    def test_multiply_and_prompt_order(self):
        output = []
        answers = iter(['6', '7'])
        prompts = []
        def read(prompt):
            prompts.append(prompt)
            return next(answers)
        r = Runtime(parse(Path('examples/multiply.ucl').read_text()), output.append, read)
        r.run()
        self.assertEqual(prompts, ['Enter the first number: ', 'Enter the second number: '])
        self.assertEqual(output, ['The result is 42'])

    def test_invalid_input_retries_and_accepts_decimals(self):
        output = []
        answers = iter(['oops', '', 'nan', 'inf', '-2.5', '4'])
        r = Runtime(parse(Path('examples/multiply.ucl').read_text()), output.append, lambda prompt: next(answers))
        r.run()
        self.assertEqual(output, ['Please enter a valid number.'] * 4 + ['The result is -10.0'])

    def test_end_of_input_has_diagnostic(self):
        def read(prompt): raise EOFError()
        r = Runtime(parse('[ask for number "Number: " into n]'), input_fn=read)
        with self.assertRaisesRegex(UCLError, 'input ended'): r.run()

    def test_input_not_available_in_http_or_gui(self):
        for app_type in ('server', 'browser', 'gui'):
            with self.subTest(app_type=app_type), self.assertRaises(UCLError):
                validate(parse(f'[type is {app_type}\nask for number "Number: " into n]'))

    def test_native_input_explicitly_rejected(self):
        with self.assertRaisesRegex(UCLError, 'not supported'):
            emit_c(parse(Path('examples/multiply.ucl').read_text()))

    def test_cli_piped_input(self):
        import sys
        result = subprocess.run([sys.executable, '-m', 'ucl', 'run', 'examples/multiply.ucl'],
                                input='6\n7\n', capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('The result is 42', result.stdout)


class LanguageTests(unittest.TestCase):
    def test_forward_values(self):
        r, out = runtime('[say answer\n let answer be base * 2\n let base be 21]')
        self.assertEqual(out, [42])

    def test_forward_function_and_object(self):
        r, out = runtime('[say twice(4)\nsay config.name\nto twice(x) [return x * 2]\nobject config [let name be "UCL"]]')
        self.assertEqual(out, [8, 'UCL'])

    def test_object_methods_and_instances(self):
        r, out = runtime(Path('examples/objects.ucl').read_text())
        self.assertEqual(out, [2, 10, 2])

    def test_forward_object_dependencies(self):
        r, out = runtime('[say answer\nlet answer be config.value\nobject config [let value be base * 2]\nlet base be 21]')
        self.assertEqual(out, [42])

    def test_object_property_order(self):
        r, out = runtime('[object config [let answer be base * 2\nlet base be 21]\nsay config.answer]')
        self.assertEqual(out, [42])

    def test_local_instance(self):
        r, out = runtime('[object config [let value be 2]\nto read() [create local from config\nset local.value to 9\nreturn local.value]\nsay read()\nsay config.value]')
        self.assertEqual(out, [9, 2])

    def test_set_requires_declaration(self):
        with self.assertRaisesRegex(UCLError, 'declare it'): runtime('[set missing to 1]')

    def test_expression_syntax_checked_before_actions(self):
        with self.assertRaisesRegex(UCLError, 'invalid expression'): Runtime(parse('[say "must not run"\nsay 1 +]'))

    def test_indented_line_number(self):
        with self.assertRaisesRegex(UCLError, 'line 3'): validate(parse('[\n  say 1\n  mystery\n]'))

    def test_logic(self):
        r, out = runtime('[let n be 0\nrepeat 3 times [set n to n + 1]\nif n == 3 [say true]\notherwise [say false]]')
        self.assertEqual(out, [True])

    def test_recursive_function(self):
        r, out = runtime('[say factorial(5)\nto factorial(n) [if n <= 1 [return 1]\nreturn n * factorial(n - 1)]]')
        self.assertEqual(out, [120])

    def test_short_circuit(self):
        r, out = runtime('[say false and (1 / 0)\nsay true or missing]')
        self.assertEqual(out, [False, True])

    def test_quotes_and_comments(self):
        r, out = runtime('[// comment\nsay "a,b;[]//"\nsay "quote: \\"hello\\"" ]'.replace('\\\\"', '\\"'))
        self.assertEqual(out[0], 'a,b;[]//')

    def test_json_and_lists(self):
        r, out = runtime('[say {"a": 1, "b": list(2, 3)}]')
        self.assertEqual(out, [{'a': 1, 'b': [2, 3]}])

    def test_invalid_syntax(self):
        for text in ('say "x"', '[say "x"', '[] extra', '["oops]', '[[]]', '[say (1]'):
            with self.subTest(text=text), self.assertRaises(UCLError): parse(text)

    def test_bad_statement(self):
        with self.assertRaisesRegex(UCLError, 'unknown statement'): validate(parse('[fly to moon]'))

    def test_capability(self):
        with self.assertRaisesRegex(UCLError, 'type is gui'): validate(parse('[show button "Hi" is #1]'))
        with self.assertRaisesRegex(UCLError, 'type is server'): validate(parse('[when get "/" [respond true]]'))

    def test_conflicting_types(self):
        with self.assertRaises(UCLError): validate(parse('[type is gui\ntype is browser]'))

    def test_cycle(self):
        with self.assertRaisesRegex(UCLError, 'cyclic'): runtime('[let a be b\nlet b be a]')

    def test_duplicate(self):
        with self.assertRaisesRegex(UCLError, 'duplicate'): runtime('[let a be 1\nlet a be 2]')

    def test_unsafe_python_rejected(self):
        for expr in ('__import__("os")', 'text.__class__', '(lambda: 1)()'):
            with self.subTest(expr=expr), self.assertRaises(UCLError): runtime('[say ' + expr + ']')

    def test_button_declarations_reordered(self):
        r, out = runtime(Path('examples/desktop.ucl').read_text())
        self.assertEqual(r.types, {'gui'})
        self.assertEqual(len(r.buttons), 3)
        self.assertEqual(r.buttons['1']['padding'], 15)
        r.execute(r.handlers['1'])
        self.assertEqual(r.buttons['1']['text'], 'You clicked me!')

    def test_desktop_dispatches_to_tk_not_http(self):
        tk = mock.MagicMock()
        r = Runtime(parse(Path('examples/desktop.ucl').read_text()))
        with mock.patch.dict('sys.modules', {'tkinter': tk}), mock.patch.object(r, 'make_server') as http:
            r.run()
        tk.Tk.assert_called_once()
        tk.Tk.return_value.title.assert_called_once_with('My first UCL desktop app')
        self.assertEqual(tk.Button.call_count, 3)
        tk.Tk.return_value.mainloop.assert_called_once()
        http.assert_not_called()

    def test_desktop_failure_does_not_fallback(self):
        tk = mock.MagicMock()
        tk.Tk.side_effect = RuntimeError('no display')
        r = Runtime(parse('[type is gui]'))
        with mock.patch.dict('sys.modules', {'tkinter': tk}), mock.patch.object(r, 'make_server') as http:
            with self.assertRaisesRegex(UCLError, 'graphical display'): r.run()
        http.assert_not_called()

    def test_button_count(self):
        with self.assertRaisesRegex(UCLError, 'count'): runtime('[type is gui\nshow button 2x "Hi" is #1]')

    def test_bad_button_reference(self):
        with self.assertRaisesRegex(UCLError, 'unknown button'): runtime('[type is browser\nbutton #no looks black]')

    def test_scope(self):
        for text in ('[return 1]', '[respond true]', '[otherwise [say 1]]'):
            with self.subTest(text=text), self.assertRaises(UCLError): validate(parse(text))

    def test_sql_parameters(self):
        r, out = runtime('''[
        database db is ":memory:"
        execute "CREATE TABLE things (name TEXT)" on db
        execute "INSERT INTO things VALUES (?)" on db using list("a' ; DROP TABLE things; --")
        query "SELECT name FROM things" on db into rows
        say rows
        ]''')
        self.assertEqual(out[0][0]['name'], "a' ; DROP TABLE things; --")
        with self.assertRaisesRegex(UCLError, 'returns rows'):
            r.execute(parse('[query "CREATE TABLE other (name TEXT)" on db into rows]'))
        r.close()

    def test_line_diagnostic(self):
        with self.assertRaisesRegex(UCLError, 'line 2'):
            runtime('[\nsay 1 / 0\n]')

    def test_all_examples_parse(self):
        for p in Path('examples').glob('*.ucl'):
            with self.subTest(path=p): validate(parse(p.read_text()))


class HTTPTests(unittest.TestCase):
    def start(self, source):
        self.r, _ = runtime(source)
        self.r.port = 0
        self.server = self.r.make_server()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.r.close()

    def request(self, path, data=None):
        with urllib.request.urlopen(self.url + path, data=data, timeout=3) as response:
            return response.status, response.read()

    def test_routes_and_database(self):
        self.start(Path('examples/server.ucl').read_text().replace('"app.db"', '":memory:"'))
        status, data = self.request('/')
        self.assertEqual(json.loads(data)['language'], 'UCL')
        status, data = self.request('/notes', b'{"text":"hello"}')
        self.assertEqual(status, 201)
        status, data = self.request('/notes')
        self.assertEqual(json.loads(data), [{'id': 1, 'text': 'hello'}])
        with self.assertRaises(urllib.error.HTTPError) as ctx: self.request('/missing')
        self.assertEqual(ctx.exception.code, 404)

    def test_browser_button(self):
        self.start(Path('examples/browser.ucl').read_text())
        self.assertIn(b'Click Me!', self.request('/')[1])
        self.assertIn(b'Hello from UCL!', self.request('/__ucl/click/hello', b'')[1])

    def test_query(self):
        self.start('[type is server\nwhen get "/" [respond request.query]]')
        self.assertEqual(json.loads(self.request('/?name=UCL')[1]), {'name': ['UCL']})

    def test_html_escaped(self):
        self.start('[type is browser\nshow text "<script>bad()</script>"]')
        self.assertNotIn(b'<script>', self.request('/')[1])

    def test_cross_origin_click(self):
        self.start(Path('examples/browser.ucl').read_text())
        req = urllib.request.Request(self.url + '/__ucl/click/hello', data=b'', headers={'Origin': 'https://evil.invalid'})
        with self.assertRaises(urllib.error.HTTPError) as ctx: urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)


@unittest.skipUnless(shutil.which('cc'), 'C compiler not installed')
class NativeTests(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = build(parse(source), Path(tmp) / 'app')
            return subprocess.run([str(path)], capture_output=True, text=True)

    def test_terminal_parity(self):
        source = Path('examples/terminal.ucl').read_text()
        r, output = runtime(source)
        self.assertEqual(self.compile_run(source).stdout.splitlines(), [str(x) for x in output])

    def test_unicode_and_escaping(self):
        self.assertEqual(self.compile_run('[say "Hallo, 世界! 100%"] ').stdout, 'Hallo, 世界! 100%\n')

    def test_division_zero(self):
        result = self.compile_run('[say 1 / 0]')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('division by zero', result.stderr)

    def test_bad_count(self):
        self.assertNotEqual(self.compile_run('[repeat 1.5 times [say 1]]').returncode, 0)

    def test_unsupported_fails(self):
        with self.assertRaises(UCLError): emit_c(parse('[type is gui]'))
        with self.assertRaises(UCLError): emit_c(parse('[say length("abc")]'))


if __name__ == '__main__': unittest.main()
