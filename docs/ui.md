# Desktop and browser UI

Choose `type is gui` for native Tk widgets or `type is browser` for server-rendered HTML. UI commands share one model; terminal `say` and diagnostic `log` remain available in either mode. You may explicitly add `type is terminal` alongside the chosen renderer, but blocking `ask` statements are forbidden in GUI/HTTP programs.

## Widgets and live text

```ucl
[
  type is gui
  show label "Ready" is #status
  show input "Your name" is #name
  show checkbox "Use uppercase" is #loud
  show button "Greet" is #greet
  when button #greet is clicked [
    read input #name into name
    read input #loud into loud
    if loud [ set name to upper(name) ]
    label #status text is "Hello, " + name
    say "Greeting updated"
  ]
]
```

- A named label is `show label EXPR is #id`; `show text EXPR is #id` is an alias.
- Anonymous static text remains `show text EXPR`.
- Buttons keep the original single/multiple-button syntax. Captions are quoted literals in declarations.
- All named widget IDs are unique across **all** widget types.
- `label #id text is EXPR` and `button #id text is EXPR` update captions.
- `input #id value is EXPR` sets input text or a checkbox boolean.
- `read input #id into NAME` reads text/boolean sequentially; do not consume it in a hoisted root `let` initializer.
- `disable #id` / `enable #id` control interaction; `hide #id` / `reveal #id` control visibility. Native layout is repacked in original order. Browser dispatch also rejects unavailable buttons.

Native inputs have a caption and a single-line entry. There are no native text areas, dropdowns, tables, menus, drag/drop or rich text yet.

## Shared styling

```ucl
[
  type is gui
  title is "Styled counter"
  window size is 500 x 350
  layout is vertical
  window style is {"background": "white", "color": "navy", "font_size": 16}
  style #count is {"font_size": 48, "font_weight": "bold", "padding": 20}
  show label "0" is #count
]
```

See the **[complete design guide](design.md)** and **[exhaustive property matrix](reference/styles.md)** for 0.4 themes/tokens, nested panels, grid layouts, hover/focus/active/disabled states, responsive styles, animations, compiled Tailwind CSS, and TUI support.

`window style` supplies inherited defaults; per-widget records override them. Records can appear before widgets or run in handlers. Legacy `button #id looks COLOR + padding is N` remains supported. `window size` controls native window dimensions (100–4096 pixels). `layout is grid 4 columns` creates a keypad-style layout; `panel #id layout is ...` controls a nested container.

Widgets render in declaration order. Desktop and browser use the same ordered model. This changes 0.2's behavior of grouping labels before all buttons.

## Desktop timers

```ucl
[
  type is gui
  let seconds be 0
  show label "0" is #clock
  every 1000 milliseconds [
    set seconds to seconds + 1
    label #clock text is text(seconds)
  ]
]
```

Timers run on the GUI thread; keep callbacks short. The interval is 10–86400000 ms and schedules again **after** callback completion (not a real-time clock). A failing callback logs to the terminal and stops that timer. Closing the window (or executing `close window` in a handler/timer) ends its event loop. These timers are not background workers, and are not available in browser/server mode.

## Browser behavior and security

Browser UI is a server-rendered postback form, not a JavaScript SPA. Every click submits enabled/visible inputs, validates a signed double-submit CSRF token, executes a handler, then redirects to the updated page. Text is HTML-escaped. Pages include a restrictive CSP, anti-framing and no-store headers.

The browser model is **shared application state**, not a per-user session model. Do not use it as a private multi-user account UI. Cookie security does not isolate widget data. Use it locally or behind appropriate authenticated infrastructure for trusted single-user/admin workflows. A global bearer-token HTTP policy is useful for APIs, but ordinary browser forms cannot supply Authorization headers; protect browser dashboards at the reverse proxy instead. Cookies can be marked Secure with `"secure_cookies": true` behind TLS.
