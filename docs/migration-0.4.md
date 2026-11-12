# Upgrade from UCL 0.3 to 0.4

Install the latest Windows installer over the existing installation. It keeps the same application identity and PATH integration. Install the matching VSIX via **Extensions → ⋯ → Install from VSIX…**, then reload VS Code. Terminal/editor-only usage remains supported; Python is not needed for the standalone Windows distribution.

## New capabilities

- `type is tui`: portable numbered-control terminal interface.
- Native/browser nested panels, independent grid layouts and column spans.
- `theme`, `design tokens`, interaction states, responsive browser variants and animations.
- Local compiled CSS/Tailwind stylesheets and allowlisted image/font assets.
- `ucl design FILE -o CSS`: optional pinned Tailwind 3 build helper; normal execution is offline/Node-free.
- Native input focus/select-all support; modern calculator example.
- VS Code context-aware capability/command/widget/style suggestions, hover reference and syntax/capability diagnostics on save.

See the [design guide](design.md), [property matrix](reference/styles.md), and [command reference](reference/commands.md) for every syntax and platform boundary.

## Compatibility and intentional differences

- Existing 0.3 native/browser/terminal programs remain supported. Themes are opt-in.
- **Snippet prefixes changed.** Use `ucl-app-terminal` / `ucl-app-gui` for whole applications; other snippets also start with `ucl-`. `terminal` and `gui` no longer insert whole blocks inside `type is ...`. The completion provider inserts/replaces only the capability value there. Typing `t` offers `terminal` and the new `tui` capability.
- New commands require the 0.4 runtime, not just an updated editor extension.
- CSS-only properties/classes are rejected by native/TUI renderers. Tailwind parity means actual compiled browser CSS, not identical Tk/terminal rendering. Native animations support integer and hex-color interpolation only.
- The helper is pinned to Tailwind **3.4.19**; Tailwind 4 projects should use their own CSS build and supply the resulting file via `stylesheet is`.
- Browser CSP now permits same-origin images/fonts and data images, but no scripts or external image/font origins. Only explicitly configured allowlisted asset files are served.
- Browser pages remain shared-state server-rendered forms, not SPAs or isolated per-user sessions. No new authentication/session abstraction is implied.
- UCL files, stylesheets, Tailwind configs/plugins and asset directories are trusted application code/assets, not hostile-input sandboxes.
