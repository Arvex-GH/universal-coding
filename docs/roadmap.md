# UCL development roadmap

The implementation is versioned deliberately. A language with the complete capabilities of Python, JavaScript, Java, C and SQL requires years of specification, libraries and compatibility work. Nothing in this roadmap is claimed as implemented.

## 1. Semantics and diagnostics

- Freeze grammar/version negotiation; structured diagnostic codes, source columns and spans.
- Typed intermediate representation and static name/type analysis; eliminate initializer retry effects.
- Explicit module system, imports, dependency manifests and permission model.
- Full object lifecycle, constructors, interfaces and inheritance/composition design.
- Exceptions, iteration over collections, while loops, string utilities, file APIs and test syntax.
- Fuzz scanner/parser and define resource budgets for embedded execution.

## 2. Runtime and deployment

- Production HTTP adapter, streaming, middleware, TLS deployment guidance, authentication helpers, request limits, graceful shutdown and isolated state.
- Database migration/transaction blocks, indexed access and optional PostgreSQL adapter.
- Async/background tasks with cancellation and defined thread-safety semantics.
- Desktop layouts, inputs, menus, dialogs, accessibility and cross-platform GUI tests.
- Browser state model and assets rather than postback-only forms.

## 3. Native backend

- Tagged value ABI with string/list/record ownership rules.
- User functions, object methods and dynamic runtime primitives in native builds.
- Networking/SQLite/Tk adapters with platform packaging.
- Optional LLVM backend after the IR and conformance suite stabilize.
- Cross-platform distribution, reproducibility and compiler diagnostics mapped to UCL source.

## 4. IDE (after language semantics stabilize)

- Expand `ucl words` into a versioned registry with examples, capability requirements, valid contexts and documentation links.
- Language Server Protocol completion, diagnostics, hover, reference navigation and renaming.
- Context-aware suggestions: `button` without a renderer offers `type is gui` / `type is browser`; `looks` proposes colors and padding.
- Preview/desktop launch controls without silently changing the selected application type.

Mobile support remains explicitly excluded for now.
