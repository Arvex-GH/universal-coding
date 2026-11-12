# UCL Documentation

Welcome to the **UCL 0.4 documentation section**. These pages are readable directly on GitHub; they are versioned with the language, not an unmaintained list of promises.

## Start here

- [Install/update UCL on Windows and configure your editor](windows.md)
- [Language structure, values and execution order](language.md)
- [Complete command and builtin reference](reference/commands.md) — **every statement supported by the parser**, with syntax and behavior
- [Design system: themes, panels, animations, Tailwind and TUI](design.md)
- [Complete style property matrix](reference/styles.md)
- [Upgrade from 0.3](migration-0.4.md)
- [Desktop/browser widgets, live updates and styling](ui.md)
- [Terminal I/O, logging, tracing and debugging](debugging.md)
- [HTTP configuration and production deployment](http.md)
- [CLI command reference](reference/cli.md)
- [Upgrade from 0.2](migration-0.3.md)
- [Compiler/runtime architecture](architecture.md)
- [Remaining work and boundaries](roadmap.md)

## Run your first GUI counter

```ucl
[
  type is gui
  type is terminal
  title is "Click Counter"
  let clicks be 0
  show label "0" is #counter
  style #counter is {"font_size": 48, "font_weight": "bold"}
  show button "Click me!" is #click
  when button #click is clicked [
    set clicks to clicks + 1
    label #counter text is text(clicks)
    say "Clicks: " + text(clicks)
  ]
]
```

Save as `counter.ucl` and run `ucl run counter.ucl --debug`. **The counter is a real label**, not a button workaround. The window and terminal output work together. `type is gui` never silently becomes a browser.

## Offline help

```sh
ucl help
ucl help label_update
ucl help transaction
ucl help escape_html
ucl words --details
```

The same registry generates the [complete reference](reference/commands.md); tests fail if any parser statement or expression builtin is missing or the generated page is stale. Maintainers regenerate it with `python tools/generate_reference.py`.

## Examples

Browse the repository's [examples folder](../examples): `counter.ucl`, `form.ucl`, `clock.ucl`, `browser-counter.ucl`, `terminal-tools.ucl`, `secure-api.ucl`, and the earlier introductory examples. Copy examples to your own project directory before editing installed copies.

## Security and deployment

UCL source files are **trusted executable programs**, not sandboxed documents. They can now read/write files, access environment variables, open databases and listen on network ports. Never run untrusted source simply because it is written in plain English.

The HTTP transport uses Waitress rather than Python's development HTTP server. That provides a production-capable WSGI transport, not automatic application security or a universal production-readiness guarantee. TLS, authentication policy, secret rotation, input schemas, backups, monitoring and load testing remain deployment responsibilities. Read [the deployment guide](http.md) before public exposure.
