# Complete command reference

Generated from `ucl/reference.py`; every parser statement is covered. Use `ucl help TOPIC` or `ucl words --details` offline.

## Commands

- [type](#type)
- [title](#title)
- [port](#port)
- [host](#host)
- [http_settings](#http-settings)
- [debugging](#debugging)
- [window_style](#window-style)
- [window_size](#window-size)
- [layout](#layout)
- [panel](#panel)
- [place](#place)
- [panel_layout](#panel-layout)
- [theme](#theme)
- [design_tokens](#design-tokens)
- [motion](#motion)
- [assets](#assets)
- [stylesheet](#stylesheet)
- [classes](#classes)
- [state_style](#state-style)
- [responsive_style](#responsive-style)
- [animate](#animate)
- [close_interface](#close-interface)
- [widget_style](#widget-style)
- [label_named](#label-named)
- [input](#input)
- [checkbox](#checkbox)
- [label_update](#label-update)
- [input_update](#input-update)
- [focus_input](#focus-input)
- [read_input](#read-input)
- [widget_state](#widget-state)
- [close_window](#close-window)
- [timer](#timer)
- [ask_text](#ask-text)
- [log](#log)
- [while](#while)
- [for](#for)
- [break](#break)
- [continue](#continue)
- [try](#try)
- [catch](#catch)
- [assert](#assert)
- [read_file](#read-file)
- [write_file](#write-file)
- [append](#append)
- [respond_typed](#respond-typed)
- [header](#header)
- [require](#require)
- [transaction](#transaction)
- [property](#property)
- [create](#create)
- [let](#let)
- [ask_number](#ask-number)
- [print](#print)
- [function](#function)
- [call](#call)
- [return](#return)
- [if](#if)
- [otherwise](#otherwise)
- [repeat](#repeat)
- [object](#object)
- [route](#route)
- [respond](#respond)
- [status](#status)
- [database](#database)
- [execute](#execute)
- [query](#query)
- [buttons](#buttons)
- [style](#style)
- [click](#click)
- [label](#label)
- [text](#text)

## type

```ucl
type is gui|browser|server|terminal|database|tui
```

Select capabilities. gui is native desktop; browser is HTML; server exposes routes. tui is an interactive terminal interface. Only one of these four renderers is allowed; add terminal/database alongside it.

## title

```ucl
title is "My app"
```

Set the desktop window or browser page title.

## port

```ucl
port is 8080
```

Choose an HTTP port, 0–65535. Zero asks the operating system for a free port.

## host

```ucl
host is "127.0.0.1"
```

Set the HTTP bind interface. Loopback is the default; 0.0.0.0 exposes interfaces but does not bypass allowed_hosts.

## http settings

```ucl
http settings is {"threads": 4, "allowed_hosts": list("api.example.com")}
```

Configure validated transport/security limits, host/CORS policies, bearer authentication, access logging and request execution budgets. See the HTTP deployment guide for every setting.

## debugging

```ucl
debugging is on
```

Enable log debug messages in the terminal. off suppresses them. say output is independent.

## window style

```ucl
window style is {"background": "white", "font_size": 14}
```

Set shared inherited widget styling and the desktop/page background.

## window size

```ucl
window size is 500 x 400
```

Set the native desktop window dimensions, each 100–4096 pixels. Browser viewport size remains controlled by the browser.

## layout

```ucl
layout is vertical
```

Stack widgets vertically (default), horizontally, or use layout is grid 4 columns (1–12 columns). Grid supports column_span styling and preserves declaration order. Available since 0.4.0.

## panel

```ucl
show panel "Account" is #account
```

Declare a named grouping container for GUI/browser widgets. Use place to assign children; panels may nest without cycles. Default layout is vertical.

## place

```ucl
place #name inside #account
```

Assign a widget to a panel, independent of declaration order. Root declaration; only one parent per widget. GUI/browser only.

## panel layout

```ucl
panel #account layout is grid 2 columns
```

Set a panel layout: vertical, horizontal, or grid 1–12 columns. Other panels keep their own layout.

## theme

```ucl
theme is dark
```

Choose light or dark built-in palettes. Sets semantic tokens background/surface/text/muted/primary/danger/border and sensible widget defaults. Root declaration.

## design tokens

```ucl
design tokens is {"primary": "#7c3aed", "spacing": 12}
```

Declare or override semantic tokens before styles resolve. Reference with "$primary" in style records. Values validate at use; theme/tokens work regardless of declaration order.

## motion

```ucl
motion is off
```

Disable browser and native animations for this app. Browser additionally honors prefers-reduced-motion. Root declaration; on is default.

## assets

```ucl
assets is "public"
```

Serve allowlisted local images/fonts at /__ucl/assets/NAME for browser CSS. Directory is relative to source; traversal, outside symlinks, executable formats, and oversized files are rejected. Authentication/host/rate policies still apply.

## stylesheet

```ucl
stylesheet is "app.css"
```

Load trusted local compiled CSS for browser apps, relative to the UCL source file (8 MiB limit). Supports compiled Tailwind of any version. No CDN or Node runtime needed. See design guide.

## classes

```ucl
classes #save is "rounded-xl bg-indigo-600 hover:bg-indigo-500"
```

Set browser utility classes. Build CSS with ucl design or your own Tailwind pipeline; runtime never fetches remote CSS. Record styles and utilities coexist; helper uses important utilities.

## state style

```ucl
style #save when hover is {"background": "$primary"}
```

Style hover/focus/active/disabled states in GUI or browser. Native bindings update immediately; browser uses CSS pseudo-classes. No TUI hover states.

## responsive style

```ucl
style #save at md is {"font_size": 20}
```

Browser-only min-width variant: sm 640, md 768, lg 1024, xl 1280, 2xl 1536 pixels. Named breakpoints have deterministic ascending cascade.

## animate

```ucl
animate #save to {"background": "#2563eb"} over 300 milliseconds
```

Animate native numeric/#RRGGBB style values with cancellable Tk callbacks, or emit browser keyframes from current to target style. Duration 0–60000 ms. No TUI animations. Browser is server-rendered: animation plays on the next response, not live DOM updates.

## close interface

```ucl
close interface
```

Close a native GUI or end a TUI input loop. Browser/server shutdown is not exposed to click handlers.

## widget style

```ucl
style #counter is {"font_size": 48, "font_weight": "bold"}
```

Set or update validated styles for any widget. Properties: color, background, font_size, font_weight, padding, margin, width, align, border_width, column_span. Can appear before the root widget declaration.

## label named

```ucl
show label "0" is #counter
```

Declare an addressable live text label. show text "0" is #counter is an alias. Requires gui or browser.

## input

```ucl
show input "Your name" is #name
```

Declare a single-line text input with the given caption. Starts empty. Requires gui or browser.

## checkbox

```ucl
show checkbox "I agree" is #agree
```

Declare a boolean checkbox, initially false. Use read input and input value updates to interact with it.

## label update

```ucl
label #counter text is text(clicks)
```

Replace a label value immediately in desktop mode or on the next browser render.

## input update

```ucl
input #name value is "Ada"
```

Set input text or a checkbox boolean. Updates the native widget and shared browser model.

## focus input

```ucl
focus input #display selecting all
```

Focus a native text input, optionally selecting its contents for replacement. Omit selecting all to place the cursor at the end. Available since 0.4.0; requires gui.

## read input

```ucl
read input #name into name
```

Read input text or checkbox boolean into a sequential variable. Browser forms submit their fields before the click handler executes.

## widget state

```ucl
disable #submit
```

enable/disable controls interaction; hide/reveal controls visibility. Applies to any widget; hidden/disabled browser buttons are also rejected server-side.

## close window

```ucl
close window
```

Close an open native desktop window from a handler/timer and end its event loop. Timers are not rescheduled after closure. Not available in browser mode.

## timer

```ucl
every 1000 milliseconds [ say "tick" ]
```

Run a native GUI callback periodically (10–86400000 ms). A failing callback logs an error and stops that timer. Browser timers are not implemented.

## ask text

```ucl
ask for text "Name: " into name
```

Read terminal text. ask for secret hides entered text using the terminal password reader. Not available in GUI/HTTP handlers, to avoid blocking event loops.

## log

```ucl
log info "Ready"
```

Emit debug/info/warning/error diagnostics to stderr; --log-format json and --log-file also apply. GUI applications retain their console; use say alongside GUI updates.

## while

```ucl
while count < 10 [ set count to count + 1 ]
```

Execute a block while its condition is truthy. HTTP execution budgets also count empty loop iterations.

## for

```ucl
for each name in list("Ada", "Lin") [ say name ]
```

Iterate list/tuple/range/string values or record keys, assigning the iteration variable.

## break

```ucl
break
```

Exit the innermost loop; only valid inside a loop in the same function/handler.

## continue

```ucl
continue
```

Skip to the next iteration of the innermost loop.

## try

```ucl
try [ say number("not a number") ]
```

Execute a block and capture UCL runtime failures for an immediately following catch. Execution budget exhaustion cannot be caught.

## catch

```ucl
catch error [ log error error ]
```

Handle the preceding try failure; error receives its diagnostic text. Skipped when no failure occurred.

## assert

```ucl
assert count >= 0
```

Raise a UCL runtime error if the expression is false. Can be handled with try/catch.

## read file

```ucl
read file "notes.txt" into contents
```

Read a UTF-8 text file into a sequential variable. Paths are relative to the process working directory; no implicit sandbox.

## write file

```ucl
write "hello" to file "notes.txt"
```

Write UTF-8 text, replacing the file. append "more" to file "notes.txt" appends instead. Parent directories must exist.

## append

```ucl
append "Ada" to names
```

Append a value to an existing list variable. Mutates the list, including shared object properties that reference that list.

## respond typed

```ucl
respond text "Hello"
```

End a route with text/plain. respond html returns trusted text/html; escape untrusted data yourself. Default respond serializes JSON.

## header

```ucl
header "X-Example" is "value"
```

Set a printable ASCII response header. CR/LF and transport-owned headers are rejected. Requires a route.

## require

```ucl
require request.json != nothing else status 400
```

If false, end the route with a generic JSON rejection and a 400–599 status. Place outside transaction blocks.

## transaction

```ucl
transaction on app [ execute "INSERT INTO notes VALUES (?)" on app using list("hi") ]
```

Run a block in one SQLite BEGIN IMMEDIATE transaction, committing on success and rolling back on failure. Nested transactions on the same connection are rejected. Respond after the block.

## property

```ucl
set self.value to self.value + 1
```

Update an already-declared record/object property, including nested properties.

## create

```ucl
create another from counter
```

Deep-copy an object template into an independent instance. Root instances initialize before actions; local instances initialize sequentially.

## let

```ucl
let count be 0
```

Declare a value (be/is/to accepted). Root let declarations dependency-resolve before actions. set count to 1 updates an existing value sequentially. Function/route scalar environments are local copies.

## ask number

```ucl
ask for number "Number: " into n
```

Read an integer or finite decimal from the terminal, retrying invalid input. EOF is a UCL error; Ctrl+C cancels. Use subsequent actions, not root initializers, to consume input.

## print

```ucl
say "Hello"
```

Write a value to terminal stdout, in any application mode. print is an alias; this never changes GUI text implicitly.

## function

```ucl
to twice(value) [ return value * 2 ]
```

Declare a function or object method with named parameters. Registered before root actions. Methods receive self; scalar locals do not implicitly mutate global scalars.

## call

```ucl
call counter.increment(1)
```

Call a function/method and discard the result. Function/method calls can also appear in expressions.

## return

```ucl
return value
```

End the current function or method, returning a value. Without return the result is nothing.

## if

```ucl
if count > 0 [ say count ]
```

Conditionally execute a block.

## otherwise

```ucl
otherwise [ say "zero" ]
```

Execute the alternative block only when the immediately preceding if was false.

## repeat

```ucl
repeat 3 times [ say "hello" ]
```

Run a block a nonnegative integer number of times.

## object

```ucl
object counter [ let value be 0 ]
```

Declare a property/method object template. Properties dependency-resolve; templates are usable instances as well as clone sources.

## route

```ucl
when get "/users/{id}" [ respond request.params.id ]
```

Declare an HTTP route. Supports get/post/put/delete/patch, named path parameters, exact-path precedence, HEAD fallback and automatic OPTIONS. Duplicate/ambiguous shapes are rejected.

## respond

```ucl
respond {"ok": true}
```

End the route with JSON and the selected status/headers. Missing explicit response is JSON null. JSON cannot contain nonfinite numbers.

## status

```ucl
status is 201
```

Set a route response status, 200–599. HEAD, 204, 205 and 304 suppress response bodies as required.

## database

```ucl
database app is "app.db"
```

Open a SQLite connection before actions. :memory: is ephemeral; relative paths resolve against the working directory. Connections close on shutdown.

## execute

```ucl
execute "INSERT INTO users VALUES (?)" on app using list("Ada")
```

Run one parameterized SQL statement. using is optional. Autocommits per statement unless inside a transaction block.

## query

```ucl
query "SELECT name FROM users" on app into users
```

Run SQL returning rows as a list of property records. Optional using binds parameters. Statements without row results are rejected.

## buttons

```ucl
show button 2x 1. "Save" is #save; 2. "Cancel" is #cancel
```

Declare one or multiple buttons. Single-button form: show button "Save" is #save. Counts must match; widget IDs are unique across the UI.

## style

```ucl
button #save looks black + padding is 15
```

Backward-compatible shorthand for a button background and padding. Prefer style #save is {...} for richer styling.

## click

```ucl
when button #save is clicked [ say "saved" ]
```

Register a desktop/browser click handler. May precede the button declaration. Browser handlers run on the server with submitted input values.

## label

```ucl
show text "Welcome"
```

Declare static text without an ID. Use show label EXPR is #id for later updates.

## text

```ucl
button #save text is "Saved"
```

Update an existing button caption in either renderer.

## Expression builtins

All optional arguments are positional. Python keyword-call syntax is not supported.

- **length** — length(value): number of items/characters.
- **text** — text(value): explicit string conversion.
- **number** — number(value): floating-point conversion.
- **integer** — integer(value): integer conversion, truncating numeric values toward zero.
- **list** — list(a, b, ...): create a list; [] always means a block.
- **item** — item(collection, key): access a list element, character or record field.
- **keys** — keys(record): list of keys.
- **values** — values(record): list of values.
- **min** — min(a, b, ...) or min(collection): minimum.
- **max** — max(a, b, ...) or max(collection): maximum.
- **round** — round(number, digits=0): round a number; pass digits positionally.
- **abs** — abs(number): absolute value.
- **json** — json(value): serialize a value to a JSON string.
- **parse_json** — parse_json(text): parse JSON into UCL values.
- **environment** — environment(name, default=""): read a process environment variable (never log secrets).
- **argument** — argument(index): get a zero-based CLI --arg value.
- **upper** — upper(text): uppercase.
- **lower** — lower(text): lowercase.
- **trim** — trim(text): remove surrounding whitespace.
- **split** — split(text, separator): split a string; omit separator for whitespace.
- **join** — join(values, separator=""): join values as strings.
- **replace** — replace(text, old, new): replace substrings.
- **contains** — contains(collection, value): membership test.
- **range** — range(stop) or range(start, stop, step): lazy integer range.
- **type_of** — type_of(value): runtime type name; object templates use UCLObject.
- **floor** — floor(number): round toward negative infinity.
- **ceil** — ceil(number): round toward positive infinity.
- **sqrt** — sqrt(number): square root; negative arguments raise an error.
- **escape_html** — escape_html(text): escape HTML special characters before interpolating untrusted content into a trusted HTML response.
