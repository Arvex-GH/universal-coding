# Runtime/compiler architecture

## Frontend

`ucl/language.py` scans character-by-character, preserving quoted strings, source lines, parentheses and record literals. Square brackets form recursive `Node` blocks. Anchored patterns classify all statements, and validation checks expression syntax, capabilities and placement before execution.

`ucl/reference.py` is a human-facing vocabulary registry keyed to those same patterns. It powers offline help, detailed JSON vocabulary and the generated GitHub reference. Coverage tests require every statement and builtin to be documented.

## Execution

`ucl/runtime.py` registers functions and dependency-resolves root values/objects before actions. Expressions are parsed with Python ast and traversed by an explicit restricted evaluator; there is no eval/exec, import exposure or Python attribute lookup. UCL properties/methods are resolved only through UCL records/objects. Root initializers should be pure because unresolved dependencies may be retried.

Actions dispatch explicitly. Runtime errors are annotated with source lines. Functions have local scalar environments; mutable objects can be shared. SQLite connections are application-owned; transactions override per-statement autocommit. Statement/expression budgets count cooperative interpreter work, not CPU time, memory or blocking library calls.

## Shared UI

`ucl/ui.py` owns an ordered widget model, validated shared styles, current text/input/checkbox state and native widget handles. Native Tk rendering and browser form rendering consume the same state. Updates synchronize native widgets or appear on the next HTML render. Desktop timers use Tk.after, not background threads. Browser state is application-wide, not a per-user session architecture.

## HTTP

`ucl/http.py` is a WSGI application plus a lifecycle adapter for Waitress. It handles configuration, host allowlists, explicit proxy trust, constant-time bearer comparison, signed double-submit browser CSRF, bounded fixed-window rate state, routing, input parsing, response serialization, safe headers and correlation logs. Waitress provides bounded worker/connection controls and HTTP framing/header/body handling; Python's development HTTP server is no longer used.

UCL actions serialize under an application lock, preserving shared-state/SQLite safety at the cost of throughput. Blocking calls are not forcibly canceled. Public deployments still require TLS/reverse-proxy protections, authentication/authorization appropriate to the app, supervision, resource limits and load/security review. See the deployment guide rather than interpreting this architecture as an audit/certification.

## Native compilation and distribution

`ucl/native.py` lowers the documented numeric terminal subset to C99, then invokes a system GCC/Clang-compatible compiler using argument vectors without a shell. Unsupported statements fail explicitly. This backend is separate from standalone tool packaging: the installed Windows `ucl.exe` bundles the interpreter, Waitress, Tk and SQLite, avoiding an end-user Python dependency but not making the entire language self-hosted/native.

C does not translate English keywords directly to independent CPU instructions. Its compiler pipeline performs preprocessing, parsing/semantic analysis, lowering/optimization, code generation, assembly and linking. UCL reuses that mature backend through C, without needing C's textual preprocessor. Official research source: [Clang compiler command guide](https://clang.llvm.org/docs/CommandGuide/clang.html).

Full native strings/objects/GUI/networking require a stable typed IR, value/ownership ABI and runtime libraries; bundling an interpreter is not that achievement. Native output uses platform runtimes and is not a universal cross-platform binary.

## Validation

Unit/integration tests cover syntax, semantics, native subset, UI model/Tk dispatch, terminal I/O, files, logging, WSGI security policies, live Waitress requests and documentation/version consistency. Windows CI builds frozen UCL, tests it outside the checkout, and performs actual install → upgrade → reinstall → uninstall. Desktop appearance/accessibility across operating systems still requires manual graphical testing. No test suite substitutes for independent security review or real deployment load/soak testing.
