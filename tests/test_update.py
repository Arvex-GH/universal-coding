import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode
from ucl import Runtime, UCLError, parse, validate, __version__
from ucl.http import HTTPApplication, settings
from ucl.reference import COMMANDS, BUILTINS, markdown


def ready(source, **kwargs):
    output, logs = [], []
    r = Runtime(parse(source), output.append, diagnostic_fn=logs.append, **kwargs)
    r.prepare()
    r.execute()
    return r, output, logs


class UITests(unittest.TestCase):
    def test_real_counter_label_and_terminal(self):
        r, output, logs = ready(Path('examples/counter.ucl').read_text())
        self.assertEqual(r.ui.get('counter')['kind'], 'label')
        self.assertEqual(r.ui.get('counter')['style']['font_size'], 48)
        self.assertEqual(list(r.ui.elements), ['counter', 'click'])
        r.execute(r.handlers['click'])
        r.execute(r.handlers['click'])
        self.assertEqual(r.ui.get('counter')['text'], '2')
        self.assertEqual(output, ['Clicked 1 times', 'Clicked 2 times'])
        self.assertEqual(len(logs), 2)

    def test_native_label_updates_widget(self):
        r, _, _ = ready('[type is gui\nshow label "0" is #count]')
        label = mock.Mock()
        r.widgets['count'] = label
        r.execute(parse('[label #count text is "1"]'))
        self.assertEqual(label.configure.call_args.kwargs['text'], '1')

    def test_style_forward_reference(self):
        r, _, _ = ready('[type is gui\nstyle #count is {"font_size": 40}\nshow text "0" is #count]')
        self.assertEqual(r.ui.get('count')['style']['font_size'], 40)

    def test_duplicate_ids_across_widget_types(self):
        with self.assertRaisesRegex(UCLError, 'duplicate widget'):
            ready('[type is gui\nshow label "0" is #x\nshow button "Hi" is #x]')

    def test_inputs_and_checkboxes(self):
        r, out, _ = ready('''[type is gui
 show input "Name" is #name
 show checkbox "Agree" is #agree
 input #name value is "Ada"
 input #agree value is true
 read input #name into name
 read input #agree into agreed
 say name
 say agreed]''')
        self.assertEqual(out, ['Ada', True])

    def test_state(self):
        r, _, _ = ready('[type is gui\nshow button "Save" is #save\ndisable #save\nhide #save]')
        self.assertFalse(r.ui.get('save')['visible'])
        self.assertFalse(r.ui.get('save')['enabled'])
        r.execute(parse('[enable #save\nreveal #save]'))
        self.assertTrue(r.ui.get('save')['visible'])
        self.assertTrue(r.ui.get('save')['enabled'])

    def test_legacy_style_overrides_defaults_and_generic_style_wins(self):
        r, _, _ = ready('[type is gui\nwindow style is {"background": "white", "padding": 20}\nshow button "Go" is #go\nbutton #go looks blue + padding is 5]')
        self.assertEqual(r.ui.effective_style(r.buttons['go'])['background'], 'blue')
        self.assertEqual(r.ui.effective_style(r.buttons['go'])['padding'], 5)
        r.execute(parse('[style #go is {"background": "red"}]'))
        self.assertEqual(r.ui.effective_style(r.buttons['go'])['background'], 'red')

    def test_close_window_stops_rescheduling(self):
        r, _, _ = ready('[type is gui\nevery 1000 milliseconds [close window]]')
        window = mock.Mock()
        r.populate_desktop(mock.MagicMock(), window)
        window.after.call_args.args[1]()
        window.destroy.assert_called_once()
        self.assertEqual(window.after.call_count, 1)

    def test_bad_styles(self):
        for record in ('{"font_size": 0}', '{"font_size": true}', '{"background": "url(evil)"}', '{"position": "fixed"}', '{"padding": -1}'):
            with self.subTest(record=record), self.assertRaises(UCLError):
                ready('[type is gui\nshow label "X" is #x\nstyle #x is ' + record + ']')

    def test_window_size_and_layout(self):
        r, _, _ = ready('[type is gui\nwindow size is 600 x 400\nlayout is horizontal]')
        self.assertEqual(r.ui.size, (600, 400))
        self.assertEqual(r.ui.direction, 'horizontal')

    def test_bad_window_size_and_timer(self):
        for statement in ('window size is 0 x 100', 'every 1 milliseconds []'):
            with self.subTest(statement=statement), self.assertRaises(UCLError): ready('[type is gui\n' + statement + ']')

    def test_timer_requires_desktop(self):
        with self.assertRaisesRegex(UCLError, 'timers require'): validate(parse('[type is browser\nevery 1000 milliseconds []]'))

    def test_native_timer_schedules_and_updates(self):
        r, _, _ = ready(Path('examples/clock.ucl').read_text())
        tk = mock.MagicMock()
        window = mock.Mock()
        r.populate_desktop(tk, window)
        delay, callback = window.after.call_args.args
        self.assertEqual(delay, 1000)
        callback()
        self.assertEqual(r.ui.get('clock')['text'], '1 seconds')
        self.assertEqual(window.after.call_count, 2)

    def test_timer_failure_stops_and_logs(self):
        r, _, logs = ready('[type is gui\nevery 1000 milliseconds [assert false]]')
        window = mock.Mock()
        r.populate_desktop(mock.MagicMock(), window)
        window.after.call_args.args[1]()
        self.assertEqual(window.after.call_count, 1)
        self.assertIn('assertion failed', logs[0])


class LanguageUpdateTests(unittest.TestCase):
    def test_multiline_records_and_calls(self):
        r, out, _ = ready('[type is browser\nhttp settings is {\n"threads": 2,\n"allowed_hosts": list("localhost")\n}\nshow label "0" is #count\nstyle #count is {\n"font_size": 48\n}\nsay join(\nlist("a", "b"), ","\n)]')
        self.assertEqual(r.http_settings['threads'], 2)
        self.assertEqual(r.ui.get('count')['style']['font_size'], 48)
        self.assertEqual(out, ['a,b'])

    def test_strict_json_large_integer_limit(self):
        from ucl.values import parse_json
        with self.assertRaisesRegex(ValueError, '256 digits'): parse_json('9' * 257)

    def test_text_input_and_builtins(self):
        _, out, _ = ready('[ask for text "Name: " into name\nsay upper(trim(name))]', input_fn=lambda prompt: ' Ada ')
        self.assertEqual(out, ['ADA'])

    def test_secret_input(self):
        with mock.patch('getpass.getpass', return_value='secret') as getpass:
            r, out, _ = ready('[ask for secret "Password: " into password\nsay length(password)]')
        getpass.assert_called_once_with('Password: ')
        self.assertEqual(out, [6])

    def test_for_while_break_continue(self):
        _, out, _ = ready('''[
 let total be 0
 for each n in range(10) [
   if n == 2 [continue]
   if n == 5 [break]
   set total to total + n
 ]
 while total < 10 [set total to total + 1]
 say total
]''')
        self.assertEqual(out, [10])

    def test_try_catch_and_assert(self):
        _, out, _ = ready('[try [assert false]\ncatch problem [say contains(problem, "assertion failed")]]')
        self.assertEqual(out, [True])

    def test_try_no_error_skips_handler(self):
        _, out, _ = ready('[try [say "OK"]\ncatch error [say "bad"]]')
        self.assertEqual(out, ['OK'])

    def test_invalid_flow_contexts(self):
        for source in ('[break]', '[continue]', '[try []]', '[catch x []]', '[repeat 1 times [to fn() [break]]]'):
            with self.subTest(source=source), self.assertRaises(UCLError): validate(parse(source))

    def test_append_and_strings(self):
        _, out, _ = ready('[let names be list("Ada")\nappend "Lin" to names\nsay join(names, ", ")\nsay replace("hello", "h", "H")\nsay split("a b")]')
        self.assertEqual(out, ['Ada, Lin', 'Hello', ['a', 'b']])

    def test_utf8_file_write_append_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = json.dumps(str(Path(tmp) / 'notes.txt'))
            _, out, _ = ready('[write "Hello" to file ' + filename + '\nappend " 世界" to file ' + filename + '\nread file ' + filename + ' into result\nsay result]')
        self.assertEqual(out, ['Hello 世界'])

    def test_file_clause_words_inside_literals(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = json.dumps(str(Path(tmp) / 'a to file b.txt'))
            _, out, _ = ready('[let names be list()\nappend "a to file b" to names\nwrite "a to file b" to file ' + filename + '\nread file ' + filename + ' into content\nsay content\nsay names]')
        self.assertEqual(out, ['a to file b', ['a to file b']])

    def test_sql_clause_words_inside_literals(self):
        r, out, _ = ready('[database db is ":memory:"\nquery "SELECT \' on fake using x into y \' AS value" on db into rows\nsay item(rows, 0).value]')
        self.assertEqual(out, [' on fake using x into y '])
        r.close()

    def test_file_error_is_catchable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = json.dumps(str(Path(tmp) / 'missing'))
            _, out, _ = ready('[try [read file ' + path + ' into value]\ncatch error [say "caught"]]')
        self.assertEqual(out, ['caught'])

    def test_quota_stops_empty_infinite_loop(self):
        r = Runtime(parse('[while true []]'))
        r.prepare()
        with r.budget(10), self.assertRaisesRegex(UCLError, 'step limit'): r.execute()

    def test_quota_cannot_be_caught(self):
        r = Runtime(parse('[try [while true []]\ncatch error [say "escape"]]'))
        r.prepare()
        with r.budget(10), self.assertRaisesRegex(UCLError, 'step limit'): r.execute()

    def test_log_levels_and_json(self):
        r, _, logs = ready('[log debug "hidden"\nlog info "visible"]')
        self.assertEqual(logs, ['[INFO] visible'])
        r.debug, r.log_format = True, 'json'
        r.execute(parse('[log debug "shown"]'))
        self.assertEqual(json.loads(logs[-1])['level'], 'debug')

    def test_log_file_and_control_characters(self):
        r, _, logs = ready('[]')
        with tempfile.TemporaryDirectory() as tmp:
            r.log_file = str(Path(tmp) / 'ucl.log')
            r.log('info', 'line1\nline2')
            self.assertEqual(Path(r.log_file).read_text(), '[INFO] line1\\nline2\n')
        self.assertEqual(len(logs), 1)

    def test_transaction_rollback_and_commit(self):
        r, out, _ = ready('''[
 database db is ":memory:"
 execute "CREATE TABLE items (value INTEGER)" on db
 try [transaction on db [execute "INSERT INTO items VALUES (1)" on db\nassert false]]
 catch error [say "rolled back"]
 transaction on db [execute "INSERT INTO items VALUES (2)" on db]
 query "SELECT value FROM items" on db into rows
 say rows
]''')
        self.assertEqual(out, ['rolled back', [{'value': 2}]])
        r.close()

    def test_cli_trace_arguments_and_stdout_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.ucl'
            path.write_text('[say argument(0)\nlog debug "details"]')
            result = subprocess.run([sys.executable, '-m', 'ucl', 'run', str(path), '--trace', '--arg', 'hello', '--log-format', 'json'], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'hello\n')
        self.assertTrue(all(json.loads(line)['level'] == 'debug' for line in result.stderr.splitlines()))


class WSGITests(unittest.TestCase):
    def app(self, routes='when get "/" [respond {"ok": true}]', config=None, app_type='server'):
        r, _, logs = ready('[type is ' + app_type + '\n' + routes + ']')
        self.addCleanup(r.close)
        r.http_settings = {'access_log': False, **(config or {})}
        return HTTPApplication(r), logs

    def request(self, app, path='/', method='GET', body='', **environ):
        raw = body.encode() if isinstance(body, str) else body
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'HTTP_HOST': 'localhost',
               'CONTENT_LENGTH': str(len(raw)), 'wsgi.input': io.BytesIO(raw), 'REMOTE_ADDR': '127.0.0.1',
               'wsgi.url_scheme': 'http', **environ}
        result = {}
        def start(status, headers): result.update(status=int(status.split()[0]), headers=dict(headers))
        result['body'] = b''.join(app(env, start))
        return result

    def test_named_parameter_and_exact_precedence(self):
        app, _ = self.app('when get "/users/{id}" [respond request.params.id]\nwhen get "/users/me" [respond "exact"]')
        self.assertEqual(json.loads(self.request(app, '/users/42')['body']), '42')
        self.assertEqual(json.loads(self.request(app, '/users/me')['body']), 'exact')

    def test_ambiguous_routes_rejected(self):
        with self.assertRaisesRegex(UCLError, 'ambiguous'): self.app('when get "/{x}" []\nwhen get "/{y}" []')

    def test_wrong_method_and_missing_path(self):
        app, _ = self.app()
        self.assertEqual(self.request(app, method='DELETE')['status'], 405)
        self.assertEqual(self.request(app, '/missing')['status'], 404)

    def test_head_and_options(self):
        app, _ = self.app()
        response = self.request(app, method='HEAD')
        self.assertEqual(response['status'], 200)
        self.assertEqual(response['body'], b'')
        self.assertGreater(int(response['headers']['Content-Length']), 0)
        self.assertEqual(self.request(app, method='OPTIONS')['status'], 204)

    def test_bodyless_status_framing(self):
        for code in (204, 205, 304):
            with self.subTest(code=code):
                app, _ = self.app(f'when get "/" [status is {code}\nrespond "ignored"]')
                result = self.request(app)
                self.assertEqual(result['body'], b'')
                if code in (204, 304): self.assertNotIn('Content-Length', result['headers'])
                else: self.assertEqual(result['headers']['Content-Length'], '0')

    def test_host_filter(self):
        app, _ = self.app()
        for host in ('evil.example', 'localhost.evil', 'evil@localhost', '@localhost', 'localhost:bad', 'localhost/path'):
            with self.subTest(host=host): self.assertEqual(self.request(app, HTTP_HOST=host)['status'], 400)
        self.assertEqual(self.request(app, HTTP_HOST='localhost:8080')['status'], 200)

    def test_wildcard_host_is_subdomains_only(self):
        app, _ = self.app(config={'allowed_hosts': ['*.example.com']})
        self.assertEqual(self.request(app, HTTP_HOST='api.example.com')['status'], 200)
        self.assertEqual(self.request(app, HTTP_HOST='example.com')['status'], 400)

    def test_auth_fail_closed(self):
        with mock.patch.dict(os.environ, {'TEST_UCL_TOKEN': ''}):
            with self.assertRaisesRegex(UCLError, 'at least 16'): self.app(config={'auth_token_environment': 'TEST_UCL_TOKEN'})

    def test_bearer_auth(self):
        with mock.patch.dict(os.environ, {'TEST_UCL_TOKEN': 'secret-test-token-123456789'}):
            app, _ = self.app(config={'auth_token_environment': 'TEST_UCL_TOKEN'})
        self.assertEqual(self.request(app)['status'], 401)
        self.assertEqual(self.request(app, HTTP_AUTHORIZATION='Bearer wrong')['status'], 401)
        self.assertEqual(self.request(app, HTTP_AUTHORIZATION='Bearer secret-test-token-123456789')['status'], 200)

    def test_bad_json(self):
        app, _ = self.app('when post "/" [respond request.json]')
        for body in ('{bad', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":1,"x":2}'):
            with self.subTest(body=body): self.assertEqual(self.request(app, method='POST', body=body, CONTENT_TYPE='application/json')['status'], 400)

    def test_json_request_and_validation(self):
        app, _ = self.app('when post "/" [require request.json != nothing else status 400\nrespond request.json]')
        self.assertEqual(self.request(app, method='POST')['status'], 400)
        self.assertEqual(json.loads(self.request(app, method='POST', body='{"hello":"UCL"}', CONTENT_TYPE='application/json')['body']), {'hello': 'UCL'})

    def test_body_limits_and_encoding(self):
        app, _ = self.app(config={'max_body_bytes': 5})
        self.assertEqual(self.request(app, body='123456')['status'], 413)
        self.assertEqual(self.request(app, CONTENT_LENGTH='-1')['status'], 400)
        self.assertEqual(self.request(app, CONTENT_LENGTH='2')['status'], 400)
        self.assertEqual(self.request(app, body=b'\xff')['status'], 400)

    def test_rate_limit(self):
        app, _ = self.app(config={'rate_limit': 2})
        self.assertEqual([self.request(app)['status'] for _ in range(3)], [200, 200, 429])
        self.assertEqual(self.request(app, REMOTE_ADDR='127.0.0.2')['status'], 200)

    def test_response_types_and_headers(self):
        app, _ = self.app('when get "/" [header "X-Test" is "yes"\nrespond text "hello"]')
        response = self.request(app)
        self.assertEqual(response['body'], b'hello')
        self.assertEqual(response['headers']['X-Test'], 'yes')
        self.assertTrue(response['headers']['Content-Type'].startswith('text/plain'))
        self.assertIn('Content-Security-Policy', response['headers'])
        self.assertIn('X-Request-ID', response['headers'])

    def test_header_injection_hidden_from_client(self):
        app, logs = self.app('when get "/" [header "X-Test" is "bad\\r\\nInjected: yes"\nrespond true]')
        response = self.request(app)
        self.assertEqual(response['status'], 500)
        self.assertNotIn(b'CR/LF', response['body'])
        self.assertTrue(logs)

    def test_transport_headers_cannot_be_set(self):
        app, _ = self.app('when get "/" [header "Content-Length" is "999"\nrespond true]')
        self.assertEqual(self.request(app)['status'], 500)

    def test_execution_limit(self):
        app, _ = self.app('when get "/" [while true []]', {'max_steps': 20})
        self.assertEqual(self.request(app)['status'], 500)

    def test_response_limit(self):
        app, _ = self.app('when get "/" [respond "abcdefgh"]', {'max_response_bytes': 2})
        self.assertEqual(self.request(app)['status'], 500)

    def test_cors_exact_allowlist(self):
        app, _ = self.app(config={'cors_origins': ['https://app.example.com']})
        result = self.request(app, method='OPTIONS', HTTP_ORIGIN='https://app.example.com')
        self.assertEqual(result['status'], 204)
        self.assertEqual(result['headers']['Access-Control-Allow-Origin'], 'https://app.example.com')
        self.assertEqual(self.request(app, method='OPTIONS', HTTP_ORIGIN='https://evil.example')['status'], 403)
        self.assertNotIn('Access-Control-Allow-Origin', self.request(app, HTTP_ORIGIN='https://evil.example')['headers'])

    def test_settings_reject_unknown_and_invalid(self):
        for value in ({'typo': True}, {'threads': 10000}, {'allowed_hosts': []}, {'rate_limit': -1}, {'cors_origins': ['*']}, {'access_log': 1}):
            with self.subTest(value=value), self.assertRaises(UCLError): settings(value)

    def test_browser_csrf_and_form_input(self):
        app, _ = self.app('show input "Name" is #name\nshow label "Hello" is #hello\nshow button "Go" is #go\nwhen button #go is clicked [read input #name into name\nlabel #hello text is name]', app_type='browser')
        response = self.request(app)
        page = response['body'].decode()
        token = re.search(r'name="_csrf" value="([^"]+)"', page).group(1)
        cookie = response['headers']['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request(app, '/__ucl/click/go', 'POST')['status'], 403)
        self.assertEqual(self.request(app, '/__ucl/click/go', 'POST', urlencode({'_csrf': token, 'name': '<Ada>'}), HTTP_COOKIE=cookie)['status'], 303)
        self.assertIn(b'&lt;Ada&gt;', self.request(app)['body'])
        self.assertEqual(self.request(app, '/__ucl/click/go', 'POST', '_csrf=' + token, HTTP_COOKIE=cookie, HTTP_ORIGIN='https://evil.example')['status'], 403)

    def test_disabled_browser_button_rejected(self):
        app, _ = self.app('show button "Go" is #go\ndisable #go', app_type='browser')
        response = self.request(app)
        token = re.search(rb'name="_csrf" value="([^"]+)"', response['body']).group(1).decode()
        self.assertEqual(self.request(app, '/__ucl/click/go', 'POST', '_csrf=' + token, HTTP_COOKIE=response['headers']['Set-Cookie'].split(';')[0])['status'], 403)

    def test_secure_cookie_setting(self):
        app, _ = self.app(app_type='browser', routes='', config={'secure_cookies': True})
        self.assertIn('; Secure', self.request(app)['headers']['Set-Cookie'])


class DocumentationTests(unittest.TestCase):
    def test_every_statement_documented(self):
        from ucl.language import PATTERNS
        self.assertEqual(set(COMMANDS), set(PATTERNS))

    def test_reference_is_current(self):
        self.assertEqual(Path('docs/reference/commands.md').read_text(encoding='utf-8'), markdown())

    def test_versions_match(self):
        self.assertEqual(json.loads(Path('editors/vscode/package.json').read_text())['version'], __version__)
        self.assertIn('version = "' + __version__ + '"', Path('pyproject.toml').read_text())
        self.assertIn('#define AppVersion "' + __version__ + '"', Path('packaging/windows/ucl-installer.iss').read_text())

    def test_builtin_registry_matches_evaluator(self):
        import ast
        tree = ast.parse(Path('ucl/runtime.py').read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'builtins' for target in n.targets):
                self.assertEqual({k.value for k in n.value.keys}, set(BUILTINS))
                return
        self.fail('Builtin registry not found')




class LiveTransportTests(unittest.TestCase):
    def start(self, source, config=None):
        import threading
        r, _, _ = ready('[type is server\n' + source + ']')
        r.port = 0
        r.http_settings = {'access_log': False, **(config or {})}
        server = r.make_server()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.url = f'http://127.0.0.1:{server.server_port}'
        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
            r.close()
            self.assertFalse(thread.is_alive(), 'transport did not stop')
        self.addCleanup(cleanup)
        return r

    def request(self, path='/', headers=None, data=None, method=None):
        import urllib.request
        import urllib.error
        request = urllib.request.Request(self.url + path, headers=headers or {}, data=data, method=method)
        try: response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error: response = error
        with response: return response.status, response.read(), dict(response.headers)

    def test_forwarded_identity_ignored_by_default(self):
        self.start('when get "/" [respond request.client]')
        status, body, _ = self.request(headers={'X-Forwarded-For': '203.0.113.9'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), '127.0.0.1')

    def test_explicit_proxy_identity_and_scheme(self):
        self.start('when get "/" [respond {"client": request.client, "scheme": request.scheme}]', {'trusted_proxy': '127.0.0.1'})
        status, body, _ = self.request(headers={'X-Forwarded-For': '203.0.113.9', 'X-Forwarded-Proto': 'https'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {'client': '203.0.113.9', 'scheme': 'https'})

    def test_transport_body_and_header_limits(self):
        self.start('when post "/" [respond true]', {'max_body_bytes': 10, 'max_header_bytes': 1024})
        self.assertEqual(self.request(data=b'x' * 11)[0], 413)
        self.assertEqual(self.request(headers={'X-Large': 'x' * 2000})[0], 431)

    def test_live_host_and_head(self):
        self.start('when get "/" [respond "hello"]')
        self.assertEqual(self.request(headers={'Host': 'evil.example'})[0], 400)
        status, body, headers = self.request(method='HEAD')
        self.assertEqual((status, body), (200, b''))
        self.assertEqual(int(headers['Content-Length']), 7)

    def test_concurrent_shared_object_updates_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        self.start('object stats [let count be 0]\nwhen post "/" [set stats.count to stats.count + 1\nrespond stats.count]')
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda _: json.loads(self.request(data=b'')[1]), range(20)))
        self.assertEqual(sorted(values), list(range(1, 21)))

    def test_request_quota_returns_without_hanging(self):
        self.start('when get "/" [while true []]', {'max_steps': 50})
        self.assertEqual(self.request()[0], 500)

    def test_strict_json_validation_live(self):
        self.start('when post "/" [respond request.json]')
        self.assertEqual(self.request(data=b'{"x":1e999}', headers={'Content-Type': 'application/json'})[0], 400)


if __name__ == '__main__': unittest.main()
