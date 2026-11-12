# UCL language and execution model (0.4)

For every available statement/builtin, use the [complete reference](reference/commands.md). This page explains how those statements fit together.

## Blocks and lexical rules

A file is one application object: `[ declarations and actions ]`. Every square-bracket pair denotes a block. Use `list(1, 2, 3)` for a list and `item(values, 0)` for indexing. Record literals use `{"name": "UCL", "version": 3}`. Commas/newlines separate statements outside strings, parentheses and records. Semicolons are only list separators in multiple-button declarations.

Quoted strings may contain punctuation/brackets, escaped quotes and `\n`. `//` starts a comment outside a string; it is not an integer-division operator. Use `floor(a / b)` when floor division is intended. Keywords are case-insensitive; names, expression keywords and string contents are case-sensitive. Use lowercase `true`, `false`, `nothing`, `and`, `or`, `not`, `in`.

## Preparation versus execution

All blocks and expression syntax are parsed/validated before actions run. Root functions register first. Root `let`, `object` and `create` declarations dependency-resolve before metadata/widgets/routes and actions. Forward references work; unresolved/cyclic declarations fail. Keep initializers pure because dependency resolution can retry them.

**Actions still run in source order.** Inputs, file reads and SQL results create sequential values, not hoisted declarations. Consume them in subsequent actions or local functions/handlers, not root `let` initializers. SQL schema creation must execute before queries.

Inside functions, routes and handlers, declarations/actions execute sequentially. Conditions/loops share their enclosing local environment. Functions and HTTP routes use local scalar copies; mutable records, objects and lists can still be shared references. `set` requires an existing value; use explicit object property assignment for persistent state.

`check` verifies full-file syntax, capabilities and context, not all runtime references/types/SQL/filesystem effects. UCL expression evaluation uses a restricted AST evaluator, never Python eval/exec. That does not make programs a resource or filesystem sandbox.

## Application capabilities

`terminal`, `gui`, `browser`, `server`, `database` are available types. With no type declaration, terminal is the default. gui/browser/server are mutually exclusive; terminal/database can accompany them. SQLite is available in all modes. `type is gui` is always native desktop, not an automatic browser wrapper.

Terminal output/logging is available with any renderer. Blocking terminal input is forbidden with GUI/HTTP modes. Simultaneous desktop + HTTP hosting and general background tasks are not implemented.

## Values and expressions

Expressions support strings, integer/floating literals, booleans/nothing, tuples/records, arithmetic `+ - * / %`, unary `+ - not`, comparisons `== != < <= > >= in not in`, short-circuit `and`/`or`, property lookup, builtin calls and UCL function/method calls. Unsupported Python constructs do not become executable just because the scanner accepts expression text. There is no implicit string/number conversion for `+`; use `text` explicitly. Call arguments are positional, not keyword arguments.

Strings/lists/records, conversion, math, JSON, environment/CLI access and HTML escaping are documented in the builtin section of the [reference](reference/commands.md#expression-builtins). Builtin names take precedence when called: do not name your own functions after builtins. Interpreter integers are arbitrary precision; the restricted C backend uses doubles and has separate documented precision limits.

## Objects and methods

```ucl
[
  object counter [
    let value be 0
    to add(amount) [
      set self.value to self.value + amount
      return self.value
    ]
  ]
  create another from counter
  say another.add(5)
  say counter.value
]
```

This prints 5 and 0: an instance deep-copies properties/methods. Templates are themselves usable objects. Methods access their receiver through `self`. Objects currently contain properties and methods, not arbitrary nested executable declarations. There is no inheritance, visibility/access modifier system, static type checking or constructor syntax.

## Flow and errors

Use `if`/immediately following `otherwise`, `repeat N times`, `while CONDITION`, and `for each NAME in COLLECTION`. `break`/`continue` target the innermost loop in the same function/handler. `return` exits a function/method. `try` must immediately precede a `catch NAME` block. `assert` raises a catchable runtime error when false; quota exhaustion cannot be caught to bypass resource controls.

## I/O and databases

Terminal numeric/text/secret input, UTF-8 file reads/writes/appends, stdout, stderr diagnostics and execution traces are described in [debugging and terminal I/O](debugging.md). File paths resolve against the current process working directory; no implicit project-directory sandbox exists.

`database NAME is PATH` opens SQLite before actions. `execute SQL on NAME using PARAMETERS` binds and executes one statement. `query SQL on NAME using PARAMETERS into RESULT` returns row records. `using` is optional; use bound parameters for external input. Autocommit is per statement except inside `transaction on NAME [ ... ]`. That block commits on success and rolls back on runtime failure. Same-connection nesting is rejected; returns/breaks/continues commit successful work before exiting, while errors roll it back. Respond/require belong outside a transaction block. No schema migrations or multi-statement SQL strings are supported.

See [UI](ui.md) and [HTTP](http.md) for backend-specific semantics, security and deployment boundaries.
