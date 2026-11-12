# Design system — UCL 0.4

UCL has three explicit interface renderers. `gui` creates real native Tk widgets; `browser` produces HTML/CSS; `tui` creates a portable interactive terminal interface. **Nothing silently substitutes a browser for a desktop app.** Choose one renderer, optionally alongside `terminal` and/or `database`.

## Quick starts

```sh
ucl run examples/native-design.ucl
ucl serve examples/design-studio.ucl
ucl run examples/tui-dashboard.ucl
ucl run examples/modern-calculator.ucl
```

`design-studio.css` is already checked in, so running the browser example needs **no Node, npm, CDN, or internet**. Open the URL printed by `serve`. The modern calculator supports typed numbers, a GUI keypad, persistent operator selection, a smaller first-operand history line, and error recovery.

## Themes and semantic tokens

```ucl
[
  type is gui
  theme is dark
  design tokens is {"primary": "#8b5cf6", "space": 16}
  show button "Save" is #save
  style #save is {"background": "$primary", "padding": "$space", "color": "white"}
]
```

Choose `light` or `dark`. Semantic palette tokens are `background`, `surface`, `text`, `muted`, `primary`, `danger`, and `border`. Custom tokens may be dimensions or colors; they validate against the property where used. Reserved palette tokens must be colors. Themes/tokens resolve before style declarations regardless of ordering. A token reference is a quoted string beginning with `$`.

Themes are opt-in for compatibility. `window style` supplies inherited widget defaults; per-widget records override them; interaction-state records override those. Native platform widget rendering and font metrics still vary.

## Layout that has structure

```ucl
[
  type is gui
  show panel "Account" is #account
  panel #account layout is grid 2 columns
  show input "Name" is #name
  show button "Save" is #save
  place #name inside #account
  place #save inside #account
]
```

- Root and each panel independently use `vertical`, `horizontal`, or `grid N columns` (N = 1–12).
- `place #child inside #panel` is a root declaration. References may precede declarations. Panels may nest, but cycles and unknown/non-panel parents are errors.
- Widgets keep declaration order **within their parent**. A widget has one parent; later placement declarations replace earlier ones.
- `column_span` spans grid columns (clamped to the container's column count). Hidden elements are omitted and the remaining grid reflows.
- Native input captions get a separate grid row so captions and controls cannot overlap.
- Hiding/disabling a panel also makes descendants unavailable to browser dispatch and native button handlers. Browser inputs in unavailable panels are not accepted on submission.
- Native panels are real Tk LabelFrames. Browser panels are semantic fieldsets/legends. TUI currently uses a flat grid, not nested panels.

`window size is 620 x 460` controls native window dimensions; browsers and terminals own their viewports. Tk `width` uses character units for ordinary controls and pixels for panels; `height` uses native widget units and does not apply to single-line entries. Browser `width` is in `ch`, other dimensions are pixels. There is no pixel-perfect cross-renderer equivalence.

## Interaction and responsive design

```ucl
style #save is {"background": "#2563eb"}
style #save when hover is {"background": "#1d4ed8"}
style #save when focus is {"border_color": "#a78bfa"}
style #save when disabled is {"color": "gray"}
```

GUI uses native event bindings and restores base styles when leaving a state. Browser uses CSS pseudo-classes; input wrappers use `:focus-within` / `:has(:disabled)`. Native state priority is hover, focus, active, disabled. TUI has no hover/focus CSS states.

Browser-only breakpoints:

```ucl
style #account is {"display": "block"}
style #account at md is {"display": "grid"}
style #account at xl is {"gap": 24}
```

Min-widths: sm 640, md 768, lg 1024, xl 1280, 2xl 1536 pixels. Breakpoints cascade in ascending order, independent of source order. For arbitrary responsive variants, container queries, dark variants, pseudo-elements, group/peer variants, arbitrary values, etc., use compiled Tailwind classes.

## Animations and reduced motion

```ucl
// Browser entry/continuous animation:
style #status is {"animation": "slide", "duration_ms": 500, "easing": "ease-out"}
// In a native GUI or browser handler:
animate #status to {"color": "#34d399"} over 400 milliseconds
```

Browser record presets: `none`, `fade`, `slide`, `pulse`, `spin`, `bounce`. Pulse/spin/bounce repeat; fade/slide finish and hold. `transition_ms` configures CSS transitions, useful for hover/focus changes; `easing` selects a standard easing. Compiled Tailwind/custom CSS may define any keyframes/animation that the browser supports.

Native `animate` interpolates existing integer values and `#RRGGBB` colors with approximately 16 ms Tk callbacks. Use explicit hex start/end colors; named-color interpolation, opacity, CSS transforms, and rounded native widget animation are not implemented. A new animation or direct style change on the same widget cancels its previous animation; closing the window cancels outstanding callbacks. The target model updates immediately. Root animations before mounting establish the initial target rather than animating an unmounted widget. Native interpolation is linear; CSS easing is browser-only.

`motion is off` disables animations. Browser also honors `prefers-reduced-motion: reduce`, including compiled Tailwind animations. Browser apps remain **server-rendered postback apps**: action animations play on the resulting page, not by live DOM patching. Refreshes may replay them. No JavaScript is injected.

## Tailwind: the actual CSS compiler, not a partial imitation

```ucl
[
  type is browser
  stylesheet is "app.css"
  show button "Save" is #save
  classes #save is "rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 md:text-lg transition-colors duration-200"
]
```

Build with the optional helper:

```sh
ucl design app.ucl -o app.css
# Optional trusted Tailwind 3 configuration / custom input CSS:
ucl design app.ucl -o app.css --config tailwind.config.js --input input.css
```

The helper runs **pinned Tailwind CSS 3.4.19** via `npx`; it needs Node.js/npm and registry access at build time. Its default configuration scans this UCL file as raw content, includes base/components/utilities, and makes utilities important so they take precedence over generated record styles. Write complete literal class strings; runtime string concatenation is not discoverable by the compiler. Custom config replaces the defaults: set content scanning, safelists, plugins and `important` yourself. Build failures return a nonzero CLI exit code. Custom config/plugins are trusted executable developer code.

**Tailwind 4 and other CSS toolchains are supported through their compiled CSS output**, not through the pinned v3 helper. Run your project's normal v4 build, then reference the resulting CSS with `stylesheet is`. UCL does not reinterpret utility names, so all utilities/variants produced by that compiler retain browser semantics. The helper does not claim v4 syntax compatibility. CSS features requiring DOM structure need matching nested panels/widgets; features requiring JavaScript do not become interactive merely by adding CSS.

The stylesheet is read relative to the `.ucl` source, limited to 8 MiB, and embedded safely in the HTML. It is a **trusted application asset**, not user input. CSS is inlined; Closing `</style` sequences are escaped to prevent breaking out of the style element, without breaking CSS range queries such as `(width < 40rem)`. No runtime CDN is used. Generated record CSS is validated and cannot contain arbitrary CSS expressions. `classes` is HTML-escaped and limited to 16,384 characters.

Classes attach to the named widget; for inputs/checkboxes this is the caption/control wrapper. Use `focus-within:` for wrapper focus, and arbitrary descendant variants such as `[&_input]:rounded-lg` to target the inner control.

Native GUI/TUI **do not accept Tailwind classes or CSS-only properties**. Unsupported record properties fail explicitly. See the [complete property matrix](reference/styles.md).

### Images/fonts and CSP

```ucl
assets is "public"
```

Serve local images/fonts from `public` at `/__ucl/assets/NAME`; CSS backgrounds and `@font-face` can reference those URLs. Allowed extensions: png, jpg/jpeg, gif, webp, svg, ico, woff/woff2, ttf, otf. No scripts, HTML, directory listings, traversal, outside-root symlinks, or assets beyond the configured HTTP `max_response_bytes`. Files are trusted deployment assets; do not allow untrusted users to modify this directory. The usual host/auth/rate rules apply, and HEAD responses omit the body.

CSP permits same-origin images/fonts and data images, inline styles, and same-origin form submissions. Remote assets, remote imports, scripts and framing remain blocked. Thus a Tailwind utility referencing an external URL may be valid CSS but blocked by this intentional security policy. Copy required assets locally. This is not permission to relax deployment security.

## TUI: explicit, portable and honest

`type is tui` launches an interactive, **line-oriented** terminal interface using the same labels, inputs, checkboxes, buttons, handlers and grid model. Enter a displayed control number: inputs prompt for editing, checkboxes toggle, buttons run handlers. `q` exits; `close interface` ends the loop. EOF also exits.

The renderer fits the terminal width, clips long text, uses Unicode box framing (ASCII fallback for legacy console encodings), and emits truecolor ANSI only when stdout is a TTY. Redirected output is plain text. User/app text cannot inject terminal control sequences. Color/background, bold, alignment and grid column spans are supported. Unsupported CSS/font/spacing properties produce errors instead of pretending to work. TUI ignores implicit theme spacing because terminal cells, not pixel boxes, define the layout.

This is not a full-screen curses application: no raw-mode arrow navigation, terminal mouse support, nested panels or TUI animation. Horizontal mode places up to 12 controls per row; grid gives explicit column counts. Wide/combining Unicode characters can have terminal-specific cell widths. `say` remains ordinary terminal output; use labels for interface content. Blocking `ask` is disallowed in TUI applications to avoid competing input loops.

## Editor and compatibility

Install the 0.4.0 VSIX using [the editor guide](../editors/vscode/README.md). It includes colors, context-aware suggestions, hover reference, and parser/capability diagnostics on save. `type is t` completes a capability value, never an application block. Templates use `ucl-app-terminal`, `ucl-app-gui`, etc.

0.3 programs remain valid unless they relied on malformed style values. New commands require 0.4.0. See [migration notes](migration-0.4.md). Shared browser state, lack of a hostile-code sandbox, and short-running native event callbacks remain important limitations; see [HTTP deployment](http.md).
