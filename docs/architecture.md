# Architecture and native-compilation research

## Pipeline

1. `ucl/language.py`: character scanner preserves quoted strings, source lines, parentheses and record literals; square brackets create recursively parsed `Node` blocks.
2. Ordered, anchored statement patterns classify every node. Whole-file validation checks expression syntax, capability vocabulary, and placement of route/function-only operations before execution.
3. `ucl/runtime.py`: function registration and dependency-resolved root declarations precede metadata, connections, route and UI registration. UI styles and handlers resolve after all buttons exist. Duplicate values, functions, database names, routes, properties and button IDs fail.
4. Actions execute in source order through explicit statement dispatch. Expressions are parsed using Python's `ast` parser and traversed by a restricted evaluator. Parsing Python expression syntax is not executing Python: there is no `eval`, `exec`, Python attribute access, arbitrary callable exposure or import access.
5. Backends: terminal output; real Tk desktop widgets; HTTP-served HTML forms; exact-path HTTP routes; SQLite data access. `Runtime.make_server` returns a server object for tests and embedding.
6. `ucl/native.py`: accepts only its documented numeric terminal subset, emits C99, and invokes the system compiler with an argument vector (no shell interpolation). Unsupported features are errors, not silent interpreter fallbacks. Temporary C files are removed automatically; `emit-c` exposes generated source for inspection.

## How C reaches machine code

The official Clang manual describes the stages:

- **Preprocessing**: tokenization, includes, macros.
- **Parsing/semantic analysis**: build and check an AST.
- **Code generation/optimization**: lower to LLVM IR and target-specific code.
- **Assembly**: encode target instructions into object files.
- **Linking**: combine objects and libraries into executables.

Reference: [Clang compiler command guide](https://clang.llvm.org/docs/CommandGuide/clang.html).

UCL does not need C's textual preprocessor. It does need parsing, semantic rules, lowering and a runtime/ABI for dynamic values, object methods, GUI callbacks and network/database operations. Reusing a mature C compiler gives the initial native subset real machine-code output without pretending an English keyword independently maps to one CPU instruction. Built native programs use the C standard library and platform runtime, rather than being universally portable binaries.

## Why two execution paths?

The interpreter makes the broad dynamic feature set usable today. The C path proves a native lowering boundary with explicit rejection of unsupported constructs. Expanding it responsibly requires a typed intermediate representation and a defined tagged-value ABI before implementing strings, closures, objects, networking and UI there. Packaging an interpreter inside an executable would not be the same claim as compiling all those semantics to native code.

## Operational boundaries

No parser-level security promise replaces an OS sandbox. Loops, recursion and data structures have no execution quota. The HTTP runtime limits body size and serializes requests, but uses Python's development HTTP stack without production-grade deadlines/concurrency controls. Browser rendering escapes strings and rejects supplied foreign Origin headers for clicks; it is not an authentication or comprehensive CSRF system. SQLite transactions are statement-scoped. Shutdown closes the listener and CLI-owned connections; applications with long-running active requests need a stronger graceful-shutdown layer before production deployment.

No GUI display is assumed in CI. Tests verify desktop declarations, styles and callbacks without opening a real window. Actual platform widget appearance and desktop accessibility require manual tests on graphical Windows/macOS/Linux sessions.
