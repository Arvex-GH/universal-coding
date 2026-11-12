# UCL for Visual Studio Code

Syntax highlighting, bracket/comment handling, `.ucl` recognition and snippets for Universal Coding Language. This extension is declarative: it does not execute programs or install the compiler, and it is not a full language server.

1. Install UCL using `ucl-installer.exe` from the repository's GitHub Releases.
2. In VS Code, run **Extensions: Install from VSIX…** and select `ucl-language.vsix` from the same release.
3. Restart VS Code so its terminal receives the updated PATH.
4. Open a folder containing your `.ucl` files and run `ucl run examples/multiply.ucl` in its terminal.

A `tasks.json` template for running/checking the current file is documented in `docs/windows.md` in the repository. No Python installation is required by the installed UCL executable.

Snippets: `terminal`, `gui`, `ask`, `route`. This extension is distributed as a release download; it is not claimed to be published to the VS Code Marketplace.
