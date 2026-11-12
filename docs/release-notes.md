## UCL 0.4.0 — Design system and editor assistance

- Real native GUI and browser nested panels, independent vertical/horizontal/grid layouts, column spans, caption-safe grids and input focus/select-all.
- Light/dark themes, semantic design tokens, interaction states and responsive browser breakpoints.
- Native cancellable integer/hex-color animation, browser keyframes/presets/transitions, reduced-motion support.
- Compiled Tailwind/CSS stylesheet integration. Optional pinned Tailwind 3.4.19 build helper; use external compiled output for Tailwind 4. No Node/CDN dependency to run built apps.
- Fix Chromium same-origin form postbacks by using same-origin referrer policy while retaining strict Origin/CSRF checks.
- Allowlisted same-origin image/font assets with traversal/symlink containment checks and bounded responses.
- Explicit interactive TUI renderer with numbered controls, input editing, checkbox toggles, grid layout, truecolor TTY output and sanitized plain redirected output.
- Modern calculator, native design studio, responsive Tailwind browser studio and TUI dashboard examples.
- VS Code context-aware completions, hover reference and trusted save diagnostics. Fixes capability completion accidentally inserting a nested application; all templates now use ucl- prefixes.
- Expanded command/property/migration/editor documentation and regression tests, including real native Tk checks on Windows.

Platform differences are explicit: full compiled CSS belongs to browser rendering, not Tk/TUI. Browser UI remains shared-state, server-rendered and script-free. See docs/design.md and docs/migration-0.4.md.

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
