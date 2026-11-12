# UCL for Visual Studio Code

Syntax highlighting, bracket/comment handling, `.ucl` recognition, snippets, and Run/Check commands for Universal Coding Language. The extension invokes your installed `ucl` executable in an integrated terminal; it does not install the toolchain and is not a full language server. Running code requires workspace trust.

1. Install UCL using `ucl-installer.exe` from the repository's GitHub Releases.
2. In VS Code, run **Extensions: Install from VSIX…** and select `ucl-language.vsix` from the same release.
3. Restart VS Code so its terminal receives the updated PATH.
4. Open a `.ucl` file and click the **Run** triangle in the editor title bar, or use **UCL: Run Current File** / **UCL: Check Current File** / **UCL: Run Current File with Trace** in the command palette. The command saves your file first. Answer input prompts in the integrated terminal.

A `tasks.json` template for running/checking the current file is documented in `docs/windows.md` in the repository. No Python installation is required by the installed UCL executable.

Snippets: `terminal`, `gui`, `ask`, `route`. This extension is distributed as a release download; it is not claimed to be published to the VS Code Marketplace.
