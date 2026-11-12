# Upgrade from UCL 0.2 to 0.3

Run the new `ucl-installer.exe` over the existing Windows installation, close/reopen your terminal/editor, then verify `ucl --version`. Install the new VSIX to receive new syntax/snippets. Copy installed examples before editing them: upgrades replace installer-owned copies.

Most existing programs continue to work. Important intentional changes:

1. **Real labels:** replace the old counter-button workaround with `show label "0" is #counter` and `label #counter text is text(clicks)`. Use `style #counter is {"font_size": 48}` for a large counter.
2. **Ordered widgets:** labels/buttons now keep their original interleaved declaration order instead of grouping labels first.
3. **Global widget IDs:** a label and button cannot share one ID.
4. **Portable style validation:** supported color names and six-digit hex values are checked early; padding is bounded. Arbitrary Tk/CSS-specific strings may now fail. The new generic style record is preferred to legacy button shorthand.
5. **HTTP transport:** Waitress replaces the development HTTP server. Source installs now need the pinned runtime dependency from `pip install -e .`; standalone installers bundle it.
6. **Host policy:** loopback hostnames/IPs are allowed by default. A publicly named host or development preview must be explicitly allowed with settings or `--allowed-host`; binding 0.0.0.0 alone is not enough.
7. **Browser CSRF:** raw button POSTs without a valid page cookie/form token are rejected. Fetch/render the page and submit its token; do not construct unauthenticated control POSTs.
8. **HTTP methods:** known paths with a wrong method return 405 instead of 404. HEAD falls back to GET; OPTIONS is handled automatically.
9. **HTTP limits:** request bodies, headers, response sizes, per-client rate and execution steps have finite defaults. Configure them to suit measured workloads.
10. **Access logs:** HTTP request summaries now go to stderr by default; disable with `"access_log": false` if your reverse proxy already handles that need.
11. **Headers:** `request.headers` uses lowercase, hyphenated header names. Avoid relying on source casing from older runtimes.

`type is gui` remains native desktop; `type is browser` remains an explicit choice. `say` still writes stdout in all modes. Application renderer combinations remain mutually exclusive; terminal output can be combined with any renderer, but simultaneous native GUI + HTTP hosting is not implemented.
