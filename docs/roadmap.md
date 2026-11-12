# Remaining work after UCL 0.3

UCL 0.3 implements live labels, inputs/checkboxes, shared styling, GUI timers, terminal/file I/O, logging/tracing, loops, try/catch, SQLite transaction blocks, and a hardened Waitress-based HTTP foundation. This roadmap lists **unimplemented** work, not capabilities to assume exist.

## Language/runtime

- Formal versioned grammar, source columns/spans, structured diagnostic codes, stronger static name/type analysis.
- Typed IR, modules/imports/packages, dependency manifests, explicit capability/permission policies.
- Initializer graph analysis without retry effects; constructors, interfaces, inheritance/composition semantics.
- Async/background tasks, cancellation and non-blocking database/filesystem adapters.
- OS-level isolation and enforceable CPU/memory limits for untrusted programs (currently not a sandbox).

## UI

- Nested layout containers/grids, menus, dropdowns, tables, multiline editors, dialogs and accessibility/platform test coverage.
- Browser per-user state/session architecture; progressive updates/assets beyond postback forms.
- Concurrent desktop + HTTP hosting with an explicit lifecycle/thread-safety model.

## HTTP/data deployment

- Independent security audit, protocol fuzzing and workload-specific load/soak benchmarks.
- Dedicated schema validation, application authentication/authorization/session integrations.
- Distributed state/rate-limiting adapters, streaming/WebSockets and outbound HTTP clients.
- Hard deadline/cancellation semantics, robust long-running worker drain/abort behavior.
- Database migrations and PostgreSQL adapter; multi-process storage guidelines and operational tooling.

## Compilation/distribution

- Tagged value ownership ABI and full native function/object/string lowering before networking/UI backends.
- Cross-platform packaging and optional LLVM backend after IR/conformance stability.
- Windows code signing, ARM64-native installer, signed update manifests/automatic updater.
- Reproducible dependency lock/build attestation and supply-chain verification.

## Editor/debugger

- Language Server Protocol diagnostics/completion/navigation from the existing vocabulary registry.
- Breakpoints, stepping, call-stack/local-variable inspection, restart/hot reload.
- Context-aware capability fixes (for example missing gui/browser type).

Mobile remains out of scope. Production suitability always depends on the application, infrastructure, threat model and validation, not a version label alone.
