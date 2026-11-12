"""WSGI application and bounded Waitress transport. TLS belongs at the reverse proxy."""
from collections import OrderedDict
from http import HTTPStatus
from http.cookies import SimpleCookie
import hashlib
import hmac
import json
import ipaddress
import os
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit
from .language import UCLError
from .values import parse_json

DEFAULTS = {
    'threads': 4, 'connection_limit': 100, 'channel_timeout': 30,
    'max_body_bytes': 1048576, 'max_header_bytes': 16384, 'max_response_bytes': 4194304,
    'max_steps': 100000, 'allowed_hosts': ['localhost', '127.0.0.1', '::1'],
    'cors_origins': [], 'auth_token_environment': '', 'rate_limit': 120,
    'rate_window_seconds': 60, 'access_log': True, 'secure_cookies': False,
    'trusted_proxy': '', 'trusted_proxy_count': 1,
}


def settings(value):
    if not isinstance(value, dict): raise UCLError('http settings must be a record')
    result = {k: list(v) if isinstance(v, list) else v for k,v in DEFAULTS.items()}
    result.update(value)
    for key, item in value.items():
        if key not in DEFAULTS: raise UCLError(f'unknown HTTP setting: {key}')
        if key in {'allowed_hosts', 'cors_origins'}:
            if not isinstance(item, (list, tuple)) or any(not isinstance(x, str) or not x or any(ord(c) < 33 for c in x) for x in item):
                raise UCLError(f'{key} must be a list of nonempty strings')
            result[key] = list(item)
            if not item and key == 'allowed_hosts': raise UCLError('allowed_hosts cannot be empty')
            if key == 'allowed_hosts':
                for hostname in item:
                    candidate = hostname[2:] if hostname.startswith('*.') else hostname
                    try: ipaddress.ip_address(candidate)
                    except ValueError:
                        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', candidate):
                            raise UCLError('allowed_hosts entries must be hostnames/IPs, optionally with a *. subdomain prefix; no ports or bare wildcard')
            if key == 'cors_origins':
                for origin in item:
                    u = urlsplit(origin)
                    if u.scheme not in {'http', 'https'} or not u.netloc or u.path or u.query or u.fragment or u.username is not None:
                        raise UCLError('CORS origins must be exact http(s) origins, not wildcards or paths')
        elif key == 'trusted_proxy':
            if not isinstance(item, str): raise UCLError('trusted_proxy must be a proxy IP address')
            if item:
                try: ipaddress.ip_address(item)
                except ValueError: raise UCLError('trusted_proxy must be a literal proxy IP, never *')
        elif key == 'auth_token_environment':
            if not isinstance(item, str): raise UCLError('auth_token_environment must be an environment variable name')
        elif key in {'access_log', 'secure_cookies'}:
            if type(item) is not bool: raise UCLError(f'{key} must be true or false')
        elif type(item) is not int or item < 1 or item > 1073741824:
            raise UCLError(f'{key} must be a positive bounded integer')
    if result['trusted_proxy_count'] > 10: raise UCLError('trusted_proxy_count must be at most 10')
    if result['threads'] > 64: raise UCLError('threads must be at most 64')
    if result['connection_limit'] > 10000: raise UCLError('connection_limit must be at most 10000')
    return result


def response_header(name, value):
    if not isinstance(name, str) or not re.fullmatch(r'[!#$%&\'*+.^_`|~0-9A-Za-z-]+', name):
        raise UCLError('invalid response header name')
    value = str(value)
    if any(ord(c) < 32 or ord(c) > 126 for c in value): raise UCLError('response headers must be printable ASCII without CR/LF')
    if name.lower() in {'content-length', 'content-type', 'connection', 'transfer-encoding', 'server', 'date', 'upgrade', 'trailer', 'te', 'keep-alive', 'proxy-authenticate', 'proxy-authorization'}:
        raise UCLError('response header is managed by the HTTP transport')
    return name, value


class HTTPApplication:
    def __init__(self, runtime):
        self.runtime = runtime
        self.config = settings(runtime.http_settings)
        name = self.config['auth_token_environment']
        self.token = os.environ.get(name, '') if name else ''
        if name and len(self.token) < 16: raise UCLError(f'{name} must contain a bearer token of at least 16 characters')
        self.csrf_key = secrets.token_bytes(32)
        self.rates = OrderedDict()
        self.route_patterns = []
        shapes = set()
        for (method, path), nodes in runtime.routes.items():
            if not isinstance(path, str) or not path.startswith('/') or '?' in path or '#' in path:
                raise UCLError('routes must start with / and contain no query or fragment')
            names = re.findall(r'\{([A-Za-z_]\w*)\}', path)
            if len(names) != len(set(names)): raise UCLError('duplicate route parameter')
            shape = re.sub(r'\{[A-Za-z_]\w*\}', '{}', path)
            if (method, shape) in shapes: raise UCLError(f'ambiguous route: {path}')
            shapes.add((method, shape))
            pattern = re.escape(path)
            for name in names: pattern = pattern.replace(re.escape('{' + name + '}'), f'(?P<{name}>[^/]+)')
            self.route_patterns.append((method, re.compile('^' + pattern + '$'), nodes))

    def host_allowed(self, host):
        if not host or any(ord(c) < 33 or ord(c) > 126 for c in host): return False
        try:
            parsed = urlsplit('//' + host)
            if not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment:
                return False
            _ = parsed.port
            hostname = parsed.hostname.lower()
        except ValueError: return False
        for allowed in self.config['allowed_hosts']:
            allowed = allowed.lower()
            if hostname == allowed or (allowed.startswith('*.') and hostname.endswith(allowed[1:]) and hostname != allowed[2:]):
                return True
        return False

    def csrf(self):
        nonce = secrets.token_hex(24)
        return nonce + '.' + hmac.new(self.csrf_key, nonce.encode(), hashlib.sha256).hexdigest()

    def valid_csrf(self, token):
        if not isinstance(token, str) or len(token) != 113: return False
        nonce, sep, digest = token.partition('.')
        return bool(sep) and hmac.compare_digest(digest, hmac.new(self.csrf_key, nonce.encode(), hashlib.sha256).hexdigest())

    def limited(self, address):
        now = time.monotonic()
        count, since = self.rates.pop(address, (0, now))
        if now - since >= self.config['rate_window_seconds']: count, since = 0, now
        self.rates[address] = (count + 1, since)
        while len(self.rates) > 10000: self.rates.popitem(last=False)
        return count >= self.config['rate_limit']

    def match(self, method, path):
        key = (method, path)
        if key in self.runtime.routes: return self.runtime.routes[key], {}
        for candidate, pattern, nodes in self.route_patterns:
            if candidate == method:
                m = pattern.fullmatch(path)
                if m: return nodes, m.groupdict()
        return None, {}

    def __call__(self, environ, start_response):
        started = time.monotonic()
        request_id = secrets.token_hex(8)
        method = environ.get('REQUEST_METHOD', 'GET').upper()
        origin = environ.get('HTTP_ORIGIN', '')
        cors = origin in self.config['cors_origins']
        def finish(status, value, kind='json', headers=None, mime=None):
            content_type = mime or {'json': 'application/json', 'text': 'text/plain', 'html': 'text/html'}[kind] + '; charset=utf-8'
            data = value if mime else (json.dumps(value, allow_nan=False) if kind == 'json' else str(value)).encode('utf-8')
            if len(data) > self.config['max_response_bytes']:
                status, data, content_type = 500, b'{"error":"response too large"}', 'application/json; charset=utf-8'
            if status in {204, 205, 304}: data = b''
            values = {'Content-Type': content_type, 'Content-Length': str(len(data)),
                      'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                      'Referrer-Policy': 'same-origin', 'Cache-Control': 'no-store', 'X-Request-ID': request_id,
                      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"}
            if status in {204, 304}: values.pop('Content-Length')
            for key, item in (headers or {}).items():
                # Enforce safe header syntax even for application-generated mappings.
                response_header(key, item)
                for old in list(values):
                    if old.lower() == key.lower(): del values[old]
                values[key] = item
            if cors:
                values.update({'Access-Control-Allow-Origin': origin, 'Vary': 'Origin'})
            start_response(f'{status} {HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Response"}', list(values.items()))
            if self.config['access_log']:
                self.runtime.log('info', f'{method} -> {status} ({(time.monotonic()-started)*1000:.1f} ms)', request_id=request_id)
            return [b'' if method == 'HEAD' else data]
        # Import here to avoid runtime/transport circular imports.
        from .runtime import Reply
        with self.runtime.lock:
            try:
                if not self.host_allowed(environ.get('HTTP_HOST', environ.get('SERVER_NAME', ''))):
                    return finish(400, {'error': 'host not allowed'})
                if self.limited(environ.get('REMOTE_ADDR', 'unknown')):
                    return finish(429, {'error': 'rate limit exceeded'}, headers={'Retry-After': str(self.config['rate_window_seconds'])})
                if origin and not cors and method == 'OPTIONS': return finish(403, {'error': 'origin not allowed'})
                if method == 'OPTIONS':
                    if cors:
                        return finish(204, None, headers={'Access-Control-Allow-Methods': 'GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS', 'Access-Control-Allow-Headers': 'Authorization, Content-Type'})
                    return finish(204, None, headers={'Allow': 'GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS'})
                if self.token:
                    supplied = environ.get('HTTP_AUTHORIZATION', '')
                    if not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + self.token).encode('utf-8')):
                        return finish(401, {'error': 'unauthorized'}, headers={'WWW-Authenticate': 'Bearer'})
                if method not in {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE'}:
                    return finish(405, {'error': 'method not allowed'}, headers={'Allow': 'GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS'})
                raw_length = environ.get('CONTENT_LENGTH', '') or '0'
                if len(raw_length) > 12 or not re.fullmatch(r'\d+', raw_length): return finish(400, {'error': 'invalid content length'})
                length = int(raw_length)
                if length > self.config['max_body_bytes']: return finish(413, {'error': 'body too large'})
                raw = environ['wsgi.input'].read(length)
                if len(raw) != length: return finish(400, {'error': 'incomplete request body'})
                try: body = raw.decode('utf-8')
                except UnicodeError: return finish(400, {'error': 'body must be UTF-8'})
                content_type = environ.get('CONTENT_TYPE', '').split(';')[0].lower()
                payload = None
                if content_type == 'application/json' and body:
                    try: payload = parse_json(body)
                    except (ValueError, RecursionError): return finish(400, {'error': 'invalid JSON'})
                path = environ.get('PATH_INFO', '/')
                # PEP 3333 represents UTF-8 path bytes via latin-1 strings.
                try: path = path.encode('latin-1').decode('utf-8')
                except UnicodeError: pass
                if 'browser' in self.runtime.types:
                    if method in {'GET','HEAD'} and path.startswith('/__ucl/assets/'):
                        asset = self.runtime.ui.asset(path[len('/__ucl/assets/'):])
                        if asset is None: return finish(404, {'error':'asset not found'})
                        return finish(200,asset[0],mime=asset[1])
                    cookies = SimpleCookie()
                    try: cookies.load(environ.get('HTTP_COOKIE', ''))
                    except Exception: pass
                    cookie = cookies.get('ucl_csrf')
                    saved_token = cookie.value if cookie else ''
                    if method in {'GET', 'HEAD'} and path == '/':
                        token = saved_token if self.valid_csrf(saved_token) else self.csrf()
                        headers = {'Set-Cookie': 'ucl_csrf=' + token + '; Path=/; HttpOnly; SameSite=Strict' + ('; Secure' if self.config['secure_cookies'] or environ.get('wsgi.url_scheme') == 'https' else '')}
                        return finish(200, self.runtime.ui.page(token), 'html', headers)
                    if method == 'POST' and path.startswith('/__ucl/click/'):
                        if origin and urlsplit(origin).netloc.lower() != environ.get('HTTP_HOST', '').lower():
                            return finish(403, {'error': 'cross-origin request'})
                        try: fields = parse_qs(body, max_num_fields=1000)
                        except ValueError: return finish(400, {'error': 'too many fields'})
                        supplied = fields.get('_csrf', [''])[0]
                        if not self.valid_csrf(saved_token) or not hmac.compare_digest(saved_token, supplied):
                            return finish(403, {'error': 'invalid CSRF token'})
                        ident = path.rsplit('/', 1)[-1]
                        if ident not in self.runtime.buttons: return finish(404, {'error': 'unknown button'})
                        spec = self.runtime.ui.get(ident)
                        if not self.runtime.ui.available(ident): return finish(403, {'error': 'button unavailable'})
                        for key, spec in self.runtime.ui.elements.items():
                            if self.runtime.ui.available(key) and spec['kind'] in {'input', 'checkbox'}:
                                spec['value'] = key in fields if spec['kind'] == 'checkbox' else fields.get(key, [''])[0]
                        with self.runtime.budget(self.config['max_steps']):
                            self.runtime.execute(self.runtime.handlers.get(ident, []))
                        return finish(303, '', 'text', {'Location': '/'})
                    return finish(404, {'error': 'not found'})
                nodes, params = self.match(method, path)
                if nodes is None and method == 'HEAD': nodes, params = self.match('GET', path)
                if nodes is None:
                    allowed = [m for m in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'} if self.match(m, path)[0] is not None]
                    if allowed:
                        if 'GET' in allowed and 'HEAD' not in allowed: allowed.append('HEAD')
                        allowed.append('OPTIONS')
                    return finish(405 if allowed else 404, {'error': 'method not allowed' if allowed else 'not found'}, headers={'Allow': ', '.join(sorted(allowed))} if allowed else None)
                try: query = parse_qs(environ.get('QUERY_STRING', ''), max_num_fields=1000)
                except ValueError: return finish(400, {'error': 'too many query fields'})
                env = dict(self.runtime.env)
                env['_status'], env['_headers'] = 200, {}
                env['request'] = {'method': method, 'path': path, 'params': params, 'query': query,
                                  'body': body, 'json': payload, 'id': request_id,
                                  'client': environ.get('REMOTE_ADDR', ''), 'scheme': environ.get('wsgi.url_scheme', 'http'),
                                  'headers': {k[5:].replace('_', '-').lower(): v for k,v in environ.items() if k.startswith('HTTP_')}}
                if environ.get('CONTENT_TYPE'): env['request']['headers']['content-type'] = environ['CONTENT_TYPE']
                if environ.get('CONTENT_LENGTH'): env['request']['headers']['content-length'] = environ['CONTENT_LENGTH']
                with self.runtime.budget(self.config['max_steps']):
                    try: self.runtime.execute(nodes, env)
                    except Reply as reply: return finish(env['_status'], reply.value, reply.kind, env['_headers'])
                return finish(env['_status'], None, headers=env['_headers'])
            except Exception as error:
                self.runtime.log('error', f'{type(error).__name__}: {error}', request_id=request_id)
                return finish(500, {'error': 'request failed', 'request_id': request_id})


class Server:
    """Lifecycle adapter retaining the embedding API from UCL 0.2."""
    def __init__(self, runtime):
        from waitress import create_server
        self.application = HTTPApplication(runtime)
        config = self.application.config
        self.server = create_server(self.application, host=runtime.host, port=runtime.port,
                                    threads=config['threads'], connection_limit=config['connection_limit'],
                                    channel_timeout=config['channel_timeout'], cleanup_interval=1,
                                    max_request_body_size=config['max_body_bytes'],
                                    max_request_header_size=config['max_header_bytes'],
                                    expose_tracebacks=False, clear_untrusted_proxy_headers=True,
                                    asyncore_loop_timeout=0.1, ident='UCL',
                                    **({'trusted_proxy': config['trusted_proxy'],
                                        'trusted_proxy_count': config['trusted_proxy_count'],
                                        'trusted_proxy_headers': {'x-forwarded-for', 'x-forwarded-proto'}}
                                       if config['trusted_proxy'] else {}))
        self.server_port = int(self.server.effective_port)
        self.closed = False

    def serve_forever(self):
        try:
            # Use the transport loop directly: BaseWSGIServer.run swallows Ctrl+C,
            # whereas UCL promises cancellation status 130 after its own cleanup.
            self.server.asyncore.loop(timeout=self.server.adj.asyncore_loop_timeout,
                                      map=self.server._map,
                                      use_poll=self.server.adj.asyncore_use_poll)
        except OSError as error:
            # shutdown() may close a descriptor while the select loop is waking.
            if not self.closed or error.errno not in {9, 10038}: raise
        except ValueError:
            # select() can report an already-closed negative descriptor instead.
            if not self.closed: raise

    def shutdown(self):
        if not self.closed:
            self.closed = True
            self.server.task_dispatcher.shutdown(timeout=5)
            from waitress import wasyncore
            wasyncore.close_all(map=self.server._map)

    def server_close(self): self.shutdown()
