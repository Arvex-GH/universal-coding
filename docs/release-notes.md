## UCL 0.3.0 — Live UI, diagnostics and hardened HTTP

### Download

- **ucl-installer.exe** — update-in-place Windows x64 installer; no separate Python required for `ucl run`.
- **ucl-windows-x64.zip** — portable executable and required bundled libraries; extract the whole directory.
- **ucl-language.vsix** — VS Code syntax/snippets, Run/Check and Run with Trace commands.
- **SHA256SUMS.txt** — asset checksums.

Close UCL programs, run the new installer over your existing installation, reopen terminal/editor, and verify `ucl --version`. The installer remains unsigned; Windows SmartScreen may warn.

### New capabilities

- Real addressable labels with live updates and font sizing: no more counter-button workaround.
- Text inputs, checkboxes, input reads/updates, enabled/visible state, ordered widgets, horizontal/vertical layout and native GUI timers.
- Shared validated colors/fonts/padding/margins/width styling for desktop and browser.
- GUI + terminal stdout and separate debug/info/warning/error diagnostics; JSON/file logs, request IDs and statement tracing.
- Terminal text/secret input, UTF-8 file reads/writes/appends, CLI/environment arguments and more string/math/collection helpers.
- While/for-each loops, break/continue, assertions and try/catch.
- SQLite transaction blocks with rollback on failure.
- Waitress transport instead of the development HTTP server: bounded workers/connections, body/header/time limits, Host validation, explicit proxy trust, optional bearer auth, CORS policy, signed browser CSRF, per-client rate controls and cooperative request execution quotas.
- Parameterized routes, HEAD/OPTIONS handling, parsed JSON requests, validation guards, typed responses and safe custom headers.
- A dedicated GitHub documentation section, complete generated command/builtin reference and offline `ucl help`/`ucl words --details`.

### Start here

Run `ucl run examples/counter.ucl --debug` from the repository, or copy the installed example from your UCL examples folder. Try `form.ucl`, `clock.ucl`, `browser-counter.ucl`, `terminal-tools.ucl` and `secure-api.ucl` next.

Read the repository's `docs/README.md` and `docs/migration-0.3.md` for documentation and intentional compatibility changes. Browser button POSTs now require page CSRF tokens; public/preview hosts must be explicitly allowed.

### Deployment and compiler boundaries

Waitress is a production-capable transport, but no blanket application-security or production-readiness certification is claimed. Public services still need TLS, authentication/authorization policy, safe schemas/filesystem access, supervision, resource limits, backups, monitoring, security review and measured load testing. Handlers serialize shared state; browser widgets are not isolated per user. Quotas are cooperative, not hard CPU/memory/time sandboxes.

The Windows executable bundles the existing runtime, not a fully self-hosted native compiler. `ucl build` remains the restricted C-backed numeric terminal subset and requires a compatible external C compiler. The new dynamic features use `ucl run`/`ucl serve`.
