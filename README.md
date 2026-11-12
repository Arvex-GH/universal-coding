# UCL — Universal Coding Language

Plain-English statements. Bracket-based objects. Explicit application capabilities.

UCL is an executable language implementation, not a natural-language AI wrapper. It has a scanner, block parser, capability validator, safe expression interpreter, native desktop renderer, explicit browser renderer, HTTP/SQLite runtime, and a C99 native compiler backend for a terminal subset. It deliberately uses a defined vocabulary rather than guessing what arbitrary English means.

**`type is gui` means a native desktop window. `type is browser` means HTML in a browser. There is no automatic fallback between them.** Mobile is out of scope.

## Install and run

### Windows — no Python installation needed

Download **[ucl-installer.exe from the latest release](https://github.com/Arvex-GH/universal-coding/releases/latest/download/ucl-installer.exe)**, install it, and reopen your terminal/editor:

```powershell
ucl --version
ucl run examples/multiply.ucl
```

The example path assumes you are in this repository. The installer also includes examples under `%LOCALAPPDATA%\Programs\UCL\examples`. Run a newer installer to update the same installation. The installer is currently unsigned. See [Windows installation, updates and editor support](docs/windows.md) for details, portable downloads and the VS Code extension.

The standalone executable bundles the existing UCL runtime; end users do not install or invoke Python. This is distinct from compiling every UCL feature into native code.

### From source (developers / other platforms)

Python 3.10+ is required for source execution. The interpreter has no third-party Python dependencies.

```sh
python -m pip install -e .
ucl run examples/terminal.ucl
ucl run examples/desktop.ucl
```

Without installing, use `python -m ucl` in place of `ucl` from this repository.

Desktop applications require Tk and a graphical desktop session. On Debian/Ubuntu install `python3-tk`; on other systems use a Python distribution with Tk support. A headless server cannot display a desktop window. UCL reports this rather than opening a browser instead.

```ucl
[
  type is gui,
  title is "My application",

  button #1 looks black + padding is 15,
  when button #1 is clicked [
    button #1 text is "Hello!"
  ]

  show button 3x 1. "Click Me!" is #1; 2. "Hello!" is #2; 3. "ByeBye!" is #3
]
```

Style and event declarations can precede the buttons they reference. Commas or newlines separate statements; square brackets **always** denote blocks. `//` introduces a comment outside a quoted string.

## What works

| Area | Implemented |
| --- | --- |
| Language | Located block AST, capability checks, variables, arithmetic, comparisons, short-circuit logic, conditionals, counted loops |
| Declarations | Forward references between root values/objects; functions, buttons, styles, handlers and routes registered before execution; cyclic declarations rejected |
| Objects | Properties, methods using `self`, independent instances cloned from templates, explicit property updates |
| Functions | Parameters, local environments, recursion, return values |
| Terminal | Output, interactive numeric input, command-line execution, native builds for the documented numeric subset |
| Desktop (`gui`) | Native Tk window, title, labels, buttons, colors, padding, click handlers, text updates |
| Browser (`browser`) | HTML renderer, form-based click dispatch, text updates, escaped content |
| HTTP (`server`) | Exact-path GET/POST/PUT/DELETE/PATCH routes, request body/query/headers, JSON responses, status codes |
| Database | SQLite connections, parameterized statements, transactions per statement, query results as objects |
| Tooling | `run`, `check`, `ast`, `words`, `emit-c`, `build`; tests and CI |

## Objects and functions

```ucl
[
  say second.increment(5)
  say counter.value
  create second from counter

  object counter [
    let value be 0
    to increment(amount) [
      set self.value to self.value + amount
      return self.value
    ]
  ]
]
```

This prints `5` and `0`: the second object has independent state. See `examples/functions.ucl` for ordinary functions.

## Run a database-backed HTTP server

```sh
ucl run examples/server.ucl
curl http://127.0.0.1:8080/
curl -X POST http://127.0.0.1:8080/notes \
  -H 'Content-Type: application/json' -d '{"text":"Hello, UCL"}'
curl http://127.0.0.1:8080/notes
```

`examples/server.ucl` creates a persistent SQLite database and implements create/list endpoints with bound SQL parameters. Use `":memory:"` for an ephemeral database.

The default bind address is loopback. For a hosted development preview use:

```sh
ucl run examples/server.ucl --host 0.0.0.0 --port 8080
```

Expose only trusted applications. The included HTTP server is **not a hardened production deployment server**. It has no authentication, TLS, request deadlines, rate limits, or multi-process database management. Put it behind appropriate infrastructure before exposure; see the limitations below.

## Explicit browser rendering

```sh
ucl run examples/browser.ucl
# Visit http://127.0.0.1:8080
```

This example explicitly declares `type is browser`. Desktop examples never start an HTTP renderer. Browser button handlers use same-origin POST forms and redirect back to the page; this is not a JavaScript SPA.

## Native executables

Install Clang/GCC (or another `cc` supporting C99):

```sh
ucl build examples/terminal.ucl -o native-program
./native-program
ucl emit-c examples/terminal.ucl -o program.c
```

The path is **UCL → AST → checked C99 → system compiler → native executable**. Resulting terminal executables do not need Python. This is native compilation through C, not a claim that the whole language already has a direct LLVM backend.

The native subset currently supports root numeric variables, mutation, numeric arithmetic/comparisons, string-literal/numeric output, `if`/`otherwise`, and counted loops. Unsupported features fail explicitly; GUI, browser, HTTP, SQL, objects, functions, lists and dynamic strings currently use the interpreter. Native numbers are C doubles; interpreter integers are arbitrary precision. Do not expect identical overflow, boolean formatting, or precision semantics outside the numeric subset's practical range.

## Developer tools

```sh
ucl check examples/desktop.ucl
ucl ast examples/desktop.ucl
ucl words
python -m unittest discover -s tests -v
```

`check` parses the full file and expression syntax, checks capabilities and block placement; it does not execute code, open databases, resolve dynamic values, or prove runtime correctness. `words` emits the actual statement patterns as JSON for future IDE tooling. This is not an implemented IDE or language server.

## Scope and honest boundaries

This is version 0.2 of a new language, not feature parity with five mature ecosystems. Influences are Python (readability), JavaScript (event-driven web), Java (objects/methods), C (native compilation), and SQL (data access).

Current limits include: no imports/packages, inheritance, interfaces, static type system, exception-handling syntax, async tasks, arbitrary filesystem/process APIs, native GUI compilation, advanced layouts/widgets, dynamic route parameters, WebSockets, browser JavaScript generation, or IDE. Objects support properties and methods, not arbitrary nested executable declarations. Application renderers are mutually exclusive. SQLite is the only database backend. Initializers should be pure because dependency resolution may retry them. Global declarations are order-independent, but **actions still execute in source order**; database schema setup must precede queries. HTTP handlers get request-local scalar variables; object references and database connections are shared and requests are serialized.

The expression interpreter never invokes Python `eval` or `exec` and does not expose Python attributes or imports. Nevertheless, UCL programs can access declared database files, consume CPU/memory, and bind network ports. **It is not a sandbox for hostile programs.**

See [the language reference](docs/language.md), [compiler architecture and research](docs/architecture.md), and [development roadmap](docs/roadmap.md).
