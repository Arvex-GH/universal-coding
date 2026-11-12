# Install and use UCL on Windows

## Download

Open [the latest GitHub release](https://github.com/Arvex-GH/universal-coding/releases/latest) and download **`ucl-installer.exe`** from Assets. Windows x64 is the supported installer target (including compatible ARM64 systems via x64 emulation). No Python installation, pip, or C compiler is needed for **`ucl run`**.

Release assets:

- `ucl-installer.exe`: per-user installer and updater.
- `ucl-windows-x64.zip`: portable distribution; extract the **entire** `ucl` folder, not just `ucl.exe`.
- `ucl-language.vsix`: optional VS Code language support.
- `SHA256SUMS.txt`: checksums for the above files.

The installer is currently **unsigned**. Windows SmartScreen may warn because there is no code-signing certificate. Only use artifacts from this repository's releases, inspect the source/build run if needed, and follow your organization's security policies. A checksum detects corruption, not publisher identity.

## Install or update

1. Run `ucl-installer.exe` and leave **Add UCL to my terminal PATH** enabled.
2. UCL installs under `%LOCALAPPDATA%\Programs\UCL` without administrator privileges.
3. Close and reopen your terminal **and text editor**. Existing processes do not automatically acquire a new PATH.
4. Verify:

```powershell
ucl --version
```

To update, close running UCL applications and run the newer `ucl-installer.exe`. A stable application ID and remembered installation directory mean it **updates the existing installation**, not a second copy. Reinstalling does not duplicate PATH entries. Installer-supplied examples are replaced during updates; keep your own projects elsewhere. Installers do not fetch updates in the background. Avoid installing older versions over newer versions.

Uninstall through Windows Installed Apps or the UCL Start Menu entry. It removes the installer-owned PATH entry and UCL's file actions, not unrelated PATH entries or your projects. If UCL was already manually on PATH before installation, its pre-existing entry is intentionally not owned/removed by the installer.

## Your first project

Create a folder, open a text editor, and save this as `multiply.ucl` (not `multiply.ucl.txt`):

```ucl
[
  type is terminal
  ask for number "Enter the first number: " into first
  ask for number "Enter the second number: " into second
  say "The result is " + text(first * second)
]
```

Open a terminal in that folder:

```powershell
ucl run multiply.ucl
```

For the bundled example:

```powershell
ucl run "$env:LOCALAPPDATA\Programs\UCL\examples\multiply.ucl"
```

If you downloaded/cloned the repository and are in its root, the exact command is:

```powershell
ucl run examples/multiply.ucl
```

The Start Menu includes a **UCL command prompt** and an examples-folder shortcut. Optional Explorer integration adds **Run with UCL** for `.ucl` files while keeping your existing default editor. On Windows 11 the action may be under **Show more options**. It also registers Notepad under Open With without taking over file associations. Run files you trust; Explorer execution is not a sandbox.

## Text editors

Any text editor can save `.ucl` files; UCL runs the saved file, not the editor's unsaved buffer.

### Visual Studio Code

Install `ucl-language.vsix` using **Extensions: Install from VSIX…** (or `code --install-extension ucl-language.vsix`). Restart VS Code after installing UCL. The extension provides syntax highlighting, bracket handling and snippets, not an AI autocomplete engine or full language server.

For keyboard-driven run/check, save the following as `.vscode/tasks.json` in your project:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "UCL: run current file",
      "type": "process",
      "command": "ucl",
      "args": ["run", "${file}"],
      "options": {"cwd": "${fileDirname}"},
      "group": {"kind": "build", "isDefault": true},
      "presentation": {"reveal": "always", "focus": true, "panel": "dedicated"},
      "problemMatcher": []
    },
    {
      "label": "UCL: check current file",
      "type": "process",
      "command": "ucl",
      "args": ["check", "${file}"],
      "options": {"cwd": "${fileDirname}"},
      "problemMatcher": []
    }
  ]
}
```

Save the file and press **Ctrl+Shift+B** to run it. Enter answers in the integrated terminal. For a task configured to run the repository example rather than the current file, set args to `["run", "examples/multiply.ucl"]` and cwd to `${workspaceFolder}`.

## Compilation versus standalone packaging

`ucl.exe` is the standalone UCL toolchain. It bundles the existing interpreter, Python runtime libraries, Tk and SQLite so **end users do not install or invoke Python**. It is not a newly self-hosted compiler, and `ucl run` interprets UCL source. A directory of runtime libraries alongside an executable is normal; do not delete `_internal`.

`ucl build file.ucl -o program.exe` is a separate feature: the supported terminal subset is compiled through C99 into machine code and currently requires a compatible GCC/Clang toolchain on PATH. The installer does **not** install that C compiler. Unsupported language features fail explicitly; use `ucl run` for the complete implemented runtime. The interactive multiplication example currently runs with `ucl run`, not the restricted native backend.

## Build/release process for maintainers

The **Windows distribution** GitHub workflow builds on Windows, runs language tests, smoke-tests `ucl.exe` outside the checkout with Python removed from PATH, compiles the installer with Inno Setup 6, and exercises real install → upgrade → reinstall → uninstall in a directory containing spaces. The old-version installer test fixture uses the same runtime payload with old metadata. Pull requests produce downloadable CI artifacts; successful main builds publish a versioned GitHub release and stable asset names. Publishing refuses to overwrite an existing version: bump `ucl.__version__`, `pyproject.toml`, the VS Code extension version, and installer default version together.

To build manually on Windows with Python 3.12 and Inno Setup 6:

```powershell
python -m pip install -e . -r packaging/requirements.txt
python packaging/build.py
python packaging/smoke.py dist/ucl/ucl.exe
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=0.2.0 packaging/windows/ucl-installer.iss
```

Generated distributions and installer binaries stay out of Git; GitHub Release assets are the distribution channel. Code signing, ARM64-native builds and a production-strength auto-updater remain future work.
