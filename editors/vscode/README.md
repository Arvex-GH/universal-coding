# UCL for Visual Studio Code

Syntax highlighting, bracket/comment handling, `.ucl` recognition, snippets, and Run/Check commands for Universal Coding Language. The extension invokes your installed `ucl` executable in an integrated terminal; it does not install the toolchain and is not a full language server. Running code requires workspace trust.

1. Install UCL using `ucl-installer.exe` from the repository's GitHub Releases.
2. In VS Code, run **Extensions: Install from VSIX…** and select `ucl-language.vsix` from the same release.
3. Restart VS Code so its terminal receives the updated PATH.
4. Open a `.ucl` file and click the **Run** triangle in the editor title bar, or use **UCL: Run Current File** / **UCL: Check Current File** / **UCL: Run Current File with Trace** in the command palette. The command saves your file first. Answer input prompts in the integrated terminal.

A `tasks.json` template for running/checking the current file is documented in `docs/windows.md` in the repository. No Python installation is required by the installed UCL executable.

Capability completion is context-aware: after `type is t`, accept `terminal` with Tab/Enter to finish **only that word**. It never inserts another application block.

Application snippets use explicit prefixes: `ucl-app-terminal`, `ucl-app-gui`. Other templates: `ucl-ask-number`, `ucl-route`, `ucl-label`, `ucl-style`, `ucl-input`, `ucl-log`, `ucl-try`, `ucl-foreach`. Type the prefix and accept the snippet suggestion. Bare keywords such as `terminal`, `gui`, and `input` no longer expand into templates inside statements. This extension is distributed as a release download; it is not claimed to be published to the VS Code Marketplace.

## Assistance in 0.4

- Context-aware capability, command-example, widget-ID, style-property and enum-value recommendations. Suggestions replace an explicit range; accepting a capability never pastes a whole application.
- Hover a statement/builtin/property for offline reference. Vocabulary is generated from the runtime registry, not fetched over the network.
- Syntax highlighting distinguishes keywords, widget IDs, strings, numbers, comments, functions/builtins and hex colors. Actual colors depend on your VS Code theme.
- Saving a `.ucl` file in a **trusted** workspace runs `ucl check FILE` and shows parser/capability failures in Problems and as editor diagnostics. This does not execute the UCL program or evaluate runtime styles. Unsaved edits are not checked automatically. Stale checker results are discarded.
- Set `ucl.executable` to the installed CLI path if it is not on PATH. Set `ucl.checkOnSave` to false to disable automatic saved-file checks. Checks have a 10-second timeout. Completion/hover/highlighting do not need UCL installed or workspace trust.

This remains a lightweight language extension, not a full semantic language server: it does not infer variable types or validate runtime widget references/styles. Use Run/Check and the language documentation for those boundaries.

Maintainers regenerate `language-data.json` with `python tools/generate_editor.py` from the repository root. Run tests with `node --test editors/vscode/test/extension.test.js`; package with `npx --yes @vscode/vsce@3.6.2 package` from this directory.
