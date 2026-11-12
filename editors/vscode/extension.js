'use strict';
const path = require('node:path');

function activate(context, vscode = require('vscode')) {
  require('./completions').registerCompletions(context, vscode);
  require('./diagnostics').registerDiagnostics(context, vscode);
  async function execute(action, trace = false) {
    if (!vscode.workspace.isTrusted) {
      vscode.window.showErrorMessage('Trust this workspace before running UCL code.');
      return;
    }
    const document = vscode.window.activeTextEditor?.document;
    if (!document || document.languageId !== 'ucl') {
      vscode.window.showErrorMessage('Open a UCL source file first.');
      return;
    }
    if (!(await document.save()) || document.uri.scheme !== 'file') return;
    const file = document.uri.fsPath;
    const folder = vscode.workspace.getWorkspaceFolder(document.uri);
    // ProcessExecution passes paths as arguments, never interpolated shell text.
    const task = new vscode.Task(
      {type: 'ucl', action, file}, folder || vscode.TaskScope.Global,
      `${action}: ${path.basename(file)}`, 'UCL',
      new vscode.ProcessExecution('ucl', [action, file, ...(trace ? ['--trace'] : [])], {cwd: path.dirname(file)})
    );
    task.presentationOptions = {reveal: vscode.TaskRevealKind.Always, focus: true, panel: vscode.TaskPanelKind.Dedicated};
    await vscode.tasks.executeTask(task);
  }
  context.subscriptions.push(
    vscode.commands.registerCommand('ucl.runFile', () => execute('run')),
    vscode.commands.registerCommand('ucl.checkFile', () => execute('check')),
    vscode.commands.registerCommand('ucl.traceFile', () => execute('run', true))
  );
}

module.exports = {activate};
