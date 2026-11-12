# Terminal I/O and diagnostics

## Output channels work together

- `say EXPR` / `print EXPR` always write to **stdout**, including in GUI/browser/server programs.
- `log info EXPR`, `log warning EXPR`, `log error EXPR` write diagnostics to **stderr**.
- `log debug EXPR` is shown only when `debugging is on`, `--debug`, or `--trace` enables debugging.
- GUI updates are explicit: `label #status text is EXPR`, for example. Writing to the console never implicitly changes a widget.

```ucl
[
  type is gui
  type is terminal
  debugging is on
  show label "Ready" is #status
  show button "Work" is #work
  when button #work is clicked [
    label #status text is "Done"
    say "Work completed"
    log debug "Status label updated"
  ]
]
```

The installed Windows `ucl.exe` is a console application so the terminal remains attached to native GUI apps. Launch it from a terminal (or the VS Code Run command) to see output; Explorer's Run action opens a persistent console.

## Logging and execution traces

```sh
ucl run examples/counter.ucl --debug
ucl run examples/counter.ucl --trace --log-format json --log-file ucl.log
ucl run examples/terminal-tools.ucl --step-limit 10000
```

`--trace` reports source filename, line and **statement kind**, not evaluated values or secrets. It traces executed actions/callbacks, not every initializer inside declaration preparation. It is an execution trace, not an interactive breakpoint debugger.

JSON diagnostics contain UTC time, level, message and (for HTTP) request_id. Text entries escape control characters to prevent multiline log spoofing. `--log-file` duplicates diagnostics to a UTF-8 append-only file; stdout remains separate. If the log file cannot be written, UCL reports that on the terminal and continues with terminal logging. Manage permissions, retention and rotation externally.

HTTP access records include method, status, duration and generated request ID, but not bodies, Authorization headers or query strings. Explicit user log statements can still expose sensitive data: **never log secrets**. GUI handler errors are both logged and shown in a native error dialog. Timer errors log and stop their timer.

## Interactive input

```ucl
[
  ask for text "Your name: " into name
  ask for number "Age: " into age
  ask for secret "Password: " into password
  say "Hello, " + name
]
```

Numeric input accepts integers/finite decimals and retries invalid values. Text input preserves whitespace; use `trim` as needed. Secret input uses the terminal password reader; a real interactive terminal is required for reliable non-echoed input (the platform reader may warn/fall back without one). EOF raises a catchable error; Ctrl+C exits with status 130. Blocking input is forbidden in GUI/browser/server programs to avoid freezing event processing.

Pass values non-interactively through repeated `--arg` options and read with `argument(0)`, `argument(1)`, etc. Use `environment("NAME", "default")` for configuration. This exposes process environment values to trusted UCL source, not to remote HTTP callers automatically.

## Errors and cooperative limits

```ucl
[
  try [ say number("not a number") ]
  catch problem [ log error problem ]
  assert 2 + 2 == 4
]
```

`try` must be followed immediately by `catch NAME [ ... ]`. Runtime errors include source line information. `assert` raises an error on a false condition. `break` and `continue` require a loop in the same function/handler.

`--step-limit` provides a cooperative action/expression quota for a run. HTTP has a separate per-request `max_steps` quota, including empty loop iterations. Exhaustion cannot be caught to escape the quota. These are **not CPU/memory/time sandboxes**: a single large allocation, slow SQL, filesystem operation or expensive library call is not preempted. Use OS/container limits, bounded inputs and trusted source for deployment.

There is no step-through debugger, variable inspector, hot reload, or automatic stack-local dump yet.
