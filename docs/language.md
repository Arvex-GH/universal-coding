# UCL language reference (0.1)

## Lexical and execution model

A file is one application object: `[ declarations and actions ]`. Every `[...]` is a block. There are no square-bracket list literals: use `list(1, 2, 3)` and `item(items, 0)` for indexing. Record literals use `{"name": "UCL", "version": 1}`. Quoted strings may contain punctuation, brackets, escaped quotes and `\n`. Statement keywords are case-insensitive; names, string contents and expression names are case-sensitive. Use lowercase `true`, `false`, `nothing`, `and`, `or`, `not`.

Commas/newlines separate statements except inside quoted strings, parentheses and record literals. Semicolons separate entries only in a multi-button statement. `...` in a description is not valid syntax. All blocks are parsed before the first action runs. Syntax errors anywhere in a file prevent execution. Runtime errors can occur after earlier actions have run.

Root `let`, `object`, and `create` declarations initialize before actions and may reference later declarations. Cycles and unresolved dependencies fail. Root functions are registered before initialization. Object properties also dependency-resolve. Keep initializers pure: unresolved dependencies cause retries. Inside functions, routes and event handlers, local declarations/actions execute sequentially. `set` requires an existing name. Setting a scalar in a function changes its local environment; use `self.property` for persistent object state. There is no implicit global scalar assignment.

## Capabilities and application metadata

```ucl
[
  type is terminal
  title is "Application title"
]
```

Types: `terminal`, `gui`, `browser`, `server`, `database`. No type defaults to terminal. `gui`, `browser`, `server` are mutually exclusive; multiple declarations can add `database`/`terminal` capabilities. SQLite declarations are available in all modes. `type is database` is useful for a data-only script. GUI vocabulary requires `gui` or `browser`; routes require `server`.

- `title is EXPRESSION`: window/page title.
- `port is INTEGER`: HTTP port (0 lets the OS assign one).
- `host is "ADDRESS"`: bind address, loopback by default.

Singleton metadata should appear once; if repeated, the last value wins.

## Values, functions and flow

```ucl
[
  let answer be 42
  set answer to answer + 1
  say answer
  if answer > 40 [ say "large" ]
  otherwise [ say "small" ]
  repeat 3 times [ say "hello" ]
  call greet("friend")
  to greet(name) [ say "Hello, " + name ]
]
```

- Declaration: `let NAME be EXPR` (`is` or `to` is also accepted).
- Assignment: `set NAME to EXPR` or `set object.property to EXPR`.
- Output: `say EXPR` or `print EXPR`.
- Numeric input: `ask for number "Prompt: " into NAME`. Waits for one line, stores an integer or finite decimal number, and retries invalid input with a message. End of input reports an error; Ctrl+C cancels. This is a sequential action, not a hoisted declaration: use the value in subsequent actions, not a root `let` initializer. Available in non-GUI, non-HTTP programs through `ucl run`; not yet supported by native builds. See `examples/multiply.ucl`.
- Function: `to NAME(a, b) [ ... ]`; return with `return EXPR`.
- Call expression: `NAME(a, b)`; statement: `call NAME(a, b)`.
- Condition: `if EXPR [ ... ]`, optionally followed immediately by `otherwise [ ... ]`.
- Loop: `repeat EXPR times [ ... ]`; count must be a nonnegative integer.

Expressions support strings, integer/floating literals, booleans, nothing, tuples, records, `+ - * / %`, unary `+ - not`, comparisons `== != < <= > >= in not in`, `and`, `or`, property lookup, builtin calls and UCL function/method calls. Because `//` starts a source comment, write integer division using `integer(a / b)` for nonnegative operands rather than the Python-style `//` operator. No implicit string/number conversion is performed by `+`.

Builtins: `length`, `text`, `number`, `integer`, `list`, `item`, `keys`, `values`, `min`, `max`, `round`, `abs`, `json`, `parse_json`. `item(value, key)` accesses a list element, character, or record field. `number` produces a floating-point value, `integer` truncates toward zero. Builtin function names take precedence over user function names when called, so avoid using them for functions.

## Object templates and instances

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

`object` declares a template object that is itself usable. `create NAME from TEMPLATE` deep-copies its properties and methods into an independent object. Methods access the receiver through `self`. `call another.add(5)` discards a method result. All properties must be declared with `let` before mutation. No inheritance, access modifiers, overloading, constructors or nested object declarations yet. Create can also be used inside a function/handler to create a local instance.

## Desktop/browser UI

```ucl
[
  type is gui
  show text "Welcome"
  show button 2x 1. "Save" is #save; 2. "Cancel" is #cancel
  button #save looks black + padding is 15
  when button #save is clicked [ button #save text is "Saved" ]
]
```

Replace `type is gui` with `type is browser` only when browser rendering is intended. A single button uses `show button "Text" is #id`. IDs are unique across the application and accept letters/digits/underscores/hyphens. Multi-button counts must match definitions; numeric labels are optional list markers, not IDs. Button labels in declarations are quoted string literals. Style accepts a color name or six-digit hex color and optional nonnegative pixel padding. Color availability in desktop mode depends on Tk; platform themes may differ. Invalid color names are rejected by the toolkit. Layout is vertically stacked, using native Tk widgets for desktop and HTML forms for browser. Desktop errors in click handlers show a dialog; browser handler errors return HTTP 500.

## HTTP

```ucl
[
  type is server
  port is 8080
  when post "/echo" [
    status is 201
    respond parse_json(request.body)
  ]
]
```

Supported methods: `get`, `post`, `put`, `delete`, `patch`. Paths match exactly; query strings are excluded from path matching. Route paths are quoted strings. Duplicate method/path declarations fail. Request fields: `request.method`, `request.path`, `request.query` (record of lists), `request.headers` (record), `request.body` (UTF-8 string). Parse JSON explicitly. Responses are JSON, including strings; no implicit HTML response mode in server applications. Default status is 200, default response is JSON null; missing routes return 404. Explicit statuses must be 200–599. `respond` ends the current route immediately. Request bodies are limited to 1 MiB. Handler failures return a generic JSON 500 and log details locally. Requests are serialized around shared application state/database use.

## SQLite

```ucl
[
  database app is ":memory:"
  execute "CREATE TABLE users (name TEXT)" on app
  execute "INSERT INTO users VALUES (?)" on app using list("Ada")
  query "SELECT name FROM users" on app into users
  say item(users, 0).name
]
```

A database declaration is registered before actions. `execute SQL on NAME using PARAMETERS` runs one SQL statement; `using` is optional. `query SQL on NAME using PARAMETERS into RESULT` returns a list of property records. Parameters may be sequences for `?` or records for named bindings. Each statement commits on success and rolls back on failure. Use parameters, not string concatenation, for external input. Connections close on CLI shutdown. Paths resolve against the current working directory. There are no cross-statement transaction blocks or schema migrations yet.
