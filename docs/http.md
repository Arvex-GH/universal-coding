# HTTP APIs and production deployment

UCL 0.3 replaces the development HTTP server with **Waitress 3.0.2**, a maintained production WSGI transport. It adds bounded workers/connections, transport body/header limits, connection timeouts, host validation, optional bearer authentication, CORS allowlists, bounded per-client rate state, execution quotas, request IDs and safe error responses.

**This is a production-capable transport and a hardened application foundation—not an unconditional certification that any UCL program is safe to expose publicly.** There has been no independent security audit or workload-specific capacity certification. UCL programs are trusted executable code. Deploy only after applying and testing the checklist below.

## Routes, requests and responses

```ucl
[
  type is server
  when get "/users/{id}" [
    header "X-App" is "UCL"
    respond {"id": request.params.id}
  ]
  when post "/echo" [
    require type_of(request.json) == "dict" else status 400
    status is 201
    respond request.json
  ]
]
```

Routes support GET/POST/PUT/PATCH/DELETE. Named `{parameter}` captures one path segment; exact routes win over parameterized routes. Duplicate method/path and equivalent parameter shapes are rejected. More complex overlapping templates are evaluated in declaration order: avoid ambiguous patterns and test your routing. There are no regex routes, wildcards, streaming responses, WebSockets or outbound HTTP client commands.

HEAD runs a matching HEAD/GET handler but suppresses its body; handlers should follow HTTP semantics and avoid side effects in GET. OPTIONS is handled by the runtime. Unknown paths return 404; known paths with an unsupported method return 405 and Allow. CORS preflight is evaluated separately from authentication, as browsers require.

Request properties:

| Property | Value |
| --- | --- |
| `request.method` | Uppercase method |
| `request.path` | Decoded path without query |
| `request.params` | Captured path parameter record |
| `request.query` | Record of lists from query string (at most 1000 fields) |
| `request.headers` | Lowercase, hyphenated HTTP header record |
| `request.body` | UTF-8 body text |
| `request.json` | Parsed JSON for application/json, otherwise nothing; invalid JSON, duplicate keys, nonfinite numbers and integers over 256 digits get 400 |
| `request.id` | Runtime-generated correlation ID, not caller-supplied |
| `request.client` | Remote client IP after explicitly configured proxy processing |
| `request.scheme` | http/https after explicitly configured proxy processing |

`respond EXPR` ends the handler with JSON. `respond text EXPR` and `respond html EXPR` select plain text or HTML. HTML is intentionally trusted markup: use `escape_html(untrusted)` when composing it. `status is N` selects 200–599. `require CONDITION else status N` rejects false conditions with generic JSON and 400–599. Validate payload **shape, types, sizes and business rules**, not only JSON syntax.

`header "Name" is EXPR` sets printable ASCII headers; CR/LF and transport-managed headers (including Content-Length/Type) are rejected. Runtime security headers include nosniff, DENY framing, no-store caching, no-referrer and a restrictive CSP. Do not weaken them casually. HEAD, 204, 205 and 304 suppress response bodies; 204/304 omit Content-Length.

Handler exceptions return generic 500 JSON with a correlation ID. Details are logged locally, never tracebacks in HTTP responses. Transport-level failures raised by Waitress itself (such as an oversized header/body) can use its own error format instead of UCL JSON. Access logs contain no request bodies, Authorization values or query strings.

## Every HTTP setting

Declare a record at application scope:

```ucl
http settings is {
  "allowed_hosts": list("api.example.com"),
  "auth_token_environment": "UCL_API_TOKEN",
  "max_body_bytes": 65536,
  "max_steps": 20000
}
```

Newlines/commas inside records are allowed; `list(...)`, not brackets, creates collections.

| Key | Default | Meaning |
| --- | --- | --- |
| `threads` | 4 | Waitress worker pool, maximum 64 |
| `connection_limit` | 100 | Bounded accepted connection budget, maximum 10000 |
| `channel_timeout` | 30 | Inactive-channel timeout in seconds; not a hard handler deadline |
| `max_body_bytes` | 1048576 | Request body limit at transport and application boundaries |
| `max_header_bytes` | 16384 | Waitress header limit |
| `max_response_bytes` | 4194304 | Serialized response limit (serialization/allocation happens before the size check) |
| `max_steps` | 100000 | Cooperative action/expression budget per request, including empty loops |
| `allowed_hosts` | localhost, 127.0.0.1, ::1 | Hostnames/IPs, without ports. `*.example.com` allows proper subdomains, not the bare domain. Bare `*` is rejected |
| `cors_origins` | empty list | Exact http(s) origins, no paths or wildcard. No credentialed CORS mode |
| `auth_token_environment` | empty string | Optional environment variable holding a bearer token of at least 16 characters; missing/short secrets fail startup |
| `rate_limit` | 120 | Per-client requests per fixed window |
| `rate_window_seconds` | 60 | Fixed-window duration; rate state capped at 10000 client keys |
| `access_log` | true | Request summary logging to stderr |
| `secure_cookies` | false | Force Secure browser CSRF cookies behind TLS; also automatic when WSGI scheme is https |
| `trusted_proxy` | empty string | Optional **literal IP** of a trusted reverse proxy. No wildcard. Default ignores untrusted forwarding headers |
| `trusted_proxy_count` | 1 | Trusted proxy hops (maximum 10); used only with trusted_proxy |

All numeric settings must be positive integers bounded by 1073741824, with smaller thread/connection/proxy-hop maxima as above. Unknown keys and invalid types fail rather than being silently ignored. Use sensible small limits for your workload; broad upper bounds are not recommended defaults.

HTTP CLI overrides are listed in [the CLI reference](reference/cli.md). For a hosted preview, explicitly allow its host, e.g. `--host 0.0.0.0 --allowed-host '*.e2b.app'`; use exact hosts for production whenever possible.

## Authentication and secrets

The global bearer policy applies to all API routes except OPTIONS. It uses constant-time comparison and a generic 401 with WWW-Authenticate. It is a **single service token**, not user accounts, roles, scoped API keys, OAuth, sessions or a full authorization framework. Add application authorization checks where appropriate and use a dedicated identity provider/proxy when you need user authentication.

PowerShell example:

```powershell
# Supply a long random value through your secret manager in production.
$env:UCL_API_TOKEN = "replace-with-a-long-random-secret"
ucl serve examples/secure-api.ucl
curl.exe http://127.0.0.1:8080/health -H "Authorization: Bearer $env:UCL_API_TOKEN"
```

Rotate the environment secret and restart the process to rotate the service token. Never commit it into UCL source, command-line arguments, logs, or installer configuration. The example API stores SQLite files in the working directory; choose a dedicated writable data directory for deployment.

## TLS reverse proxy

Waitress deliberately terminates **plain HTTP**, normally bound to 127.0.0.1 behind a TLS reverse proxy. Do not send bearer tokens over an untrusted plaintext network. A Caddy example:

```caddyfile
api.example.com {
    request_body {
        max_size 64KB
    }
    reverse_proxy 127.0.0.1:8080
}
```

Set the UCL allowed host to api.example.com (Caddy preserves Host). If you need correct forwarded client IP/scheme, configure `"trusted_proxy": "127.0.0.1"` and the actual trusted hop count, and ensure only that proxy can connect to the backend. UCL/Waitress trusts only X-Forwarded-For and X-Forwarded-Proto in that configuration, not arbitrary forwarded host headers. Restrict backend network access; blindly trusting all proxies would let attackers spoof rate-limit identity or scheme.

Without explicit proxy trust, all requests through a local proxy share its IP's rate bucket. Even with trust, the in-process limiter is a **secondary safeguard**, not a distributed abuse-prevention service. Configure primary connection/rate/body limits at the edge. Set HTTPS-only/HSTS policy at the TLS proxy. Browser UIs behind TLS should use secure_cookies true.

## Concurrency, state, database and lifecycle

The transport has bounded workers; UCL handlers currently serialize around shared application state and SQLite connections. This avoids concurrent mutation bugs but **limits throughput**. Request scalar variables are local copies; objects and UI state are shared references. Browser UI state is not per-user isolated.

SQLite statements bind parameters and autocommit by default. `transaction on NAME [ ... ]` groups statements under BEGIN IMMEDIATE and commits on success or rolls back on failure. Nested transactions on one connection are rejected. Keep blocks short; respond after the transaction. Back up your database and test restoration. SQLite is not a replacement for a multi-node database; no PostgreSQL driver/migrations are implemented.

Ctrl+C closes the listener, stops workers (bounded shutdown wait), closes channels and then CLI-owned databases. Long-running library/SQL/file operations are not forcibly killed: budgets are cooperative, not hard deadlines. Use an external process supervisor and bounded shutdown/kill policy. Monitor errors, latency, memory, queueing and rejected requests. Multi-process deployments have separate in-memory counters/rate limits; use external storage when cross-process consistency is required.

## Public-deployment checklist

- [ ] Trusted/reviewed source, supported/patched runtime and current pinned dependency reviewed.
- [ ] Explicit Host allowlist; firewall/private backend binding; no accidental open development dashboard.
- [ ] TLS proxy, HTTPS-only policy, request/body/connection/rate limits at the edge.
- [ ] Authentication and per-operation authorization appropriate to the application.
- [ ] Strict schemas, input length bounds, parameterized SQL, escaped HTML, safe filesystem paths.
- [ ] Secrets from a manager/environment, least-privilege OS identity, restrictive data/log permissions.
- [ ] Process supervision, resource limits, log retention, alerting, backups and restore drills.
- [ ] Measured load/soak testing, rejection-path testing, review of shared state and serial throughput.
- [ ] A threat model and independent security review for sensitive/public services.

The included tests exercise protocol/application safeguards and installer packaging. They do not certify compliance, resistance to every denial-of-service vector, or production suitability for an arbitrary workload.
