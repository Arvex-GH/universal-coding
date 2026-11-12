# CLI reference

The standalone Windows installation exposes `ucl`; source developers may substitute `python -m ucl`.

| Command | Purpose |
| --- | --- |
| `ucl --version` | Print toolchain version |
| `ucl run FILE` | Prepare and execute a UCL program; open its desktop/window or HTTP listener if selected |
| `ucl serve FILE` | Run an HTTP server/browser program; reject terminal/desktop-only files |
| `ucl check FILE` | Parse the complete file and expression syntax; validate capabilities and statement placement without executing/opening databases |
| `ucl ast FILE` | Print the located block AST as JSON |
| `ucl words` | Print parser patterns as JSON (backward compatible) |
| `ucl words --details` | Print syntax, descriptions and patterns from the reference registry |
| `ucl help` | List statement and expression-builtin help topics |
| `ucl help TOPIC` | Explain one statement/builtin, e.g. `label_update`, `transaction`, `escape_html` |
| `ucl emit-c FILE -o OUTPUT.c` | Emit C99 for the restricted native terminal subset |
| `ucl build FILE -o OUTPUT` | Use an installed GCC/Clang-compatible C99 compiler to produce a native executable for that subset |

## Run/serve options

| Option | Behavior |
| --- | --- |
| `--host ADDRESS` | Override HTTP bind interface |
| `--port N` | Override HTTP port, 0–65535 |
| `--debug` | Enable debug diagnostics on stderr |
| `--trace` | Enable debug plus action kind/location traces |
| `--log-format text\|json` | Diagnostic format (text default); stdout unchanged |
| `--log-file PATH` | Also append diagnostics to a UTF-8 log file |
| `--arg VALUE` | Add a program argument, repeatable; use `argument(index)` |
| `--step-limit N` | Positive cooperative action/expression quota for the run |
| `--allowed-host HOST` | Replace HTTP allowed_hosts; repeat to allow multiple hostnames/IPs (without ports) |
| `--auth-token-env NAME` | Set environment variable name holding an API bearer token |
| `--http-threads N` | Waitress worker count, 1–64 |
| `--max-body BYTES` | Maximum HTTP request body bytes |
| `--max-steps N` | HTTP cooperative execution quota per request |

CLI HTTP overrides apply after source declarations. All HTTP settings can also be specified in `http settings is {...}`; see [the full settings table](../http.md).

`check` is **not** full static type/name verification: dynamic values, widget references, file access, SQL, and runtime expression restrictions still require execution tests. The native backend intentionally rejects new dynamic/UI/HTTP features it cannot compile. Packaging an installed tool without a Python dependency does not expand that backend's semantics.

Exit status: 0 success, 1 runtime/build/check error, 2 command-line usage error, 130 Ctrl+C.

## Design build helper (0.4)

```sh
ucl design app.ucl -o app.css
ucl design app.ucl -o app.css --input input.css --config tailwind.config.js
```

Compiles static utility class strings using pinned Tailwind CSS 3.4.19 via npx. Requires Node/npm only for this optional build step; runtime stylesheet rendering does not. Custom config replaces default content scanning and important-utility settings and may execute trusted JavaScript/plugins. Tailwind 4 users can compile externally and load the resulting CSS. See the [design guide](../design.md).
