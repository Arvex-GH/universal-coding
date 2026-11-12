# UCL — Universal Coding Language

Plain-English statements. Bracket-based objects. Explicit application capabilities.

**UCL 0.3** adds live labels, inputs/checkboxes, styling for desktop and web, GUI timers, terminal/file I/O, logging/tracing, richer flow control, SQLite transactions, and a hardened Waitress-based HTTP runtime.

## 📖 Documentation

### [Open the UCL documentation section →](docs/README.md)

- **[Every command and builtin](docs/reference/commands.md)** — syntax and behavior, generated from the toolchain's reference registry
- [GUI/browser widgets and styling](docs/ui.md)
- [Terminal I/O and debugging](docs/debugging.md)
- [HTTP settings and production deployment](docs/http.md)
- [CLI commands/options](docs/reference/cli.md)
- [Language model](docs/language.md) · [Upgrade from 0.2](docs/migration-0.3.md)

Offline: `ucl help label_update`, `ucl help transaction`, `ucl words --details`.

## Install on Windows — no Python installation needed

Download **[ucl-installer.exe](https://github.com/Arvex-GH/universal-coding/releases/latest/download/ucl-installer.exe)** from the [latest release](https://github.com/Arvex-GH/universal-coding/releases/latest), install, and reopen your terminal/editor:

```powershell
ucl --version
ucl run examples/counter.ucl --debug
```

The example path assumes you are in this repository. Installed copies are also under `%LOCALAPPDATA%\Programs\UCL\examples`; copy them into your own project before editing. Run a newer installer to update the same installation without duplicate PATH entries. The installer is currently **unsigned**; Windows SmartScreen may warn.

Install the release's `ucl-language.vsix` using VS Code's **Extensions: Install from VSIX…** for highlighting, snippets and Run/Check commands. See [Windows setup and editor integration](docs/windows.md).

The standalone tool bundles the existing UCL interpreter/runtime, Waitress, Tk and SQLite. Users do not install/invoke Python. That is separate from compiling every UCL feature into native code.

## A real GUI counter, with terminal output too

```ucl
[
  type is gui
  type is terminal
  title is "Click Counter"
  window size is 420 x 320
  window style is {"background": "white", "font_size": 14}
  let clicks be 0

  show label "0" is #counter
  style #counter is {"font_size": 48, "font_weight": "bold", "color": "navy"}
  show button "Click me!" is #click
  style #click is {"background": "blue", "color": "white", "padding": 15}

  when button #click is clicked [
    set clicks to clicks + 1
    label #counter text is text(clicks)
    say "Clicks: " + text(clicks)
    log debug "Updated the GUI"
  ]
]
```

`type is gui` means a **native desktop window**. `type is browser` explicitly chooses HTML. There is no automatic fallback. The counter above is a real, dynamically updated label, not a second button. `say` writes stdout; `log` writes stderr; both can accompany GUI changes.

## What works

| Area | Implemented |
| --- | --- |
| Language | Located block AST, capability/context checks, values, arithmetic/comparisons, short-circuit logic, conditions, counted/while/collection loops, break/continue, assertions, try/catch |
| Objects/functions | Dependency-resolved root values/objects, forward functions/handlers, properties, self methods, cloned instances, parameters, recursion, returns |
| UI | Native desktop or explicit browser renderer; ordered labels/buttons/inputs/checkboxes, live values/text, enabled/visible state, shared validated styles, vertical/horizontal layouts, native timers |
| Terminal/files | Numeric/text/password input, stdout, string/math/collection helpers, CLI/environment configuration, UTF-8 reads/writes/appends |
| Diagnostics | Debug/info/warning/error levels, terminal stderr, optional JSON/file logs, action kind/location tracing, cooperative step quotas |
| HTTP | Waitress transport, named route parameters, JSON/text/HTML responses, headers, request validation, HEAD/OPTIONS, host/CORS policies, bearer authentication, signed browser CSRF, limits/rate controls, request IDs |
| Database | SQLite bound SQL, result records, statement autocommit and explicit transactional blocks |
| Distribution/tooling | Windows installer/upgrades, portable ZIP, VS Code extension, offline/reference help, AST/check tools, CI, restricted native C backend |

## Examples

```sh
ucl run examples/counter.ucl --debug
ucl run examples/form.ucl
ucl run examples/clock.ucl
ucl run examples/terminal-tools.ucl --trace
ucl serve examples/browser-counter.ucl
```

[Browse all examples](examples). A browser counter may share UI syntax with desktop, but still declares `type is browser` explicitly. GUI source execution needs Tk and a graphical session; a headless machine cannot display a native window.

### API with database and security controls

[examples/secure-api.ucl](examples/secure-api.ucl) shows named parameters, JSON validation, bearer authentication, transaction blocks and response headers. Set `UCL_API_TOKEN` to a long random secret in your environment before starting:

```sh
ucl serve examples/secure-api.ucl
```

The default interface/Host policy is loopback. For public deployment, configure exact hosts, authentication and TLS infrastructure as described in **[the HTTP deployment guide](docs/http.md)**. For a hosted preview explicitly allow its hostname, for example `--host 0.0.0.0 --allowed-host '*.e2b.app'`.

The development HTTP server has been replaced by a production-capable WSGI transport, but **this is not a blanket production-readiness guarantee**. Application authorization, TLS, input schemas, safe file paths, resource limits, backups, supervision, monitoring, security review and load testing remain essential. UCL handlers currently serialize shared state, and browser UI state is application-wide rather than per-user isolated.

## Source install and tests

Python 3.10+ for source execution:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
node --test editors/vscode/test/extension.test.js
python tools/generate_reference.py
```

Use `python -m ucl` instead of `ucl` when working directly from the checkout. The sole runtime package dependency is the pinned Waitress transport. Tk availability depends on your Python/OS distribution (for example python3-tk on Debian/Ubuntu); the Windows standalone build bundles it.

## Native compilation boundary

```sh
ucl build examples/terminal.ucl -o native-program
ucl emit-c examples/terminal.ucl -o program.c
```

The restricted numeric terminal subset lowers **UCL → AST → C99 → system compiler → machine code**. It requires an installed GCC/Clang-compatible C compiler; its output does not require Python. Native numbers use C doubles, unlike arbitrary-precision interpreter integers. New dynamic/UI/HTTP/file features are not automatically supported by this backend and fail explicitly. Interactive multiplication currently uses `ucl run`, not `ucl build`.

## Boundaries

UCL is a defined language, not an AI wrapper that guesses arbitrary English. It is not feature parity with five mature ecosystems. Influences remain Python (readability), JavaScript (events/web), Java (objects), C (native lowering) and SQL (data access).

Programs are **trusted executable source**, not sandboxed documents: they can read/write files, access environment values, open databases, listen on ports, allocate memory and consume CPU. Cooperative quotas do not preempt blocking/library calls. No modules/package ecosystem, static type system, inheritance, general async/background tasks, full IDE debugger, advanced UI containers, per-user browser sessions, full native compilation or mobile target is claimed.

See [architecture](docs/architecture.md) and the [remaining-work roadmap](docs/roadmap.md).
