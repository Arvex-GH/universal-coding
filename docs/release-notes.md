## UCL 0.2.0

First standalone Windows distribution of Universal Coding Language.

### Downloads

- **ucl-installer.exe** — per-user Windows x64 installer. Adds UCL to PATH, registers optional Explorer file actions, and updates the existing installation when rerun with a newer release. No separate Python installation is needed for `ucl run`.
- **ucl-windows-x64.zip** — portable UCL executable and required bundled libraries. Extract the whole directory.
- **ucl-language.vsix** — VS Code syntax highlighting, snippets and `.ucl` recognition; install using Extensions: Install from VSIX.
- **SHA256SUMS.txt** — SHA-256 checksums.

After installation, reopen your terminal and run `ucl --version`. Save a `.ucl` file and run `ucl run your-file.ucl`. The bundled multiplication example prompts for two numbers and prints their product.

The language includes terminal numeric input, objects/methods, conditions, loops, functions, native Tk desktop windows (`type is gui`), explicit browser rendering (`type is browser`), HTTP endpoints and SQLite.

### Important boundaries

The installer is unsigned; Windows SmartScreen may warn. The standalone tool bundles UCL's existing runtime; it is not a new self-hosted compiler. `ucl build` is the separate C-backed terminal subset and requires an external C compiler. The HTTP backend is for development, not hardened production hosting. Mobile, a full IDE and comprehensive native compilation are not included.

See `docs/windows.md` in the repository for update/uninstall behavior, editor tasks and full setup instructions.
