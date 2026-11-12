'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {activate} = require('../extension');

function fixture() {
  const commands = {}, tasks = [], errors = [];
  let saves = 0;
  const document = {languageId: 'ucl', uri: {scheme: 'file', fsPath: '/project with spaces/file;not-a-command.ucl'},
    save: async () => { saves++; return true; }};
  const vscode = {
    workspace: {isTrusted: true, getWorkspaceFolder: () => undefined},
    window: {activeTextEditor: {document}, showErrorMessage: m => errors.push(m)},
    commands: {registerCommand: (name, handler) => {commands[name] = handler; return {dispose() {}};}},
    TaskScope: {Global: 1}, TaskRevealKind: {Always: 1}, TaskPanelKind: {Dedicated: 1},
    ProcessExecution: class { constructor(command, args, options) {Object.assign(this, {command, args, options});} },
    Task: class { constructor(definition, scope, name, source, execution) {Object.assign(this, {definition, scope, name, source, execution});} },
    tasks: {executeTask: async task => tasks.push(task)}
  };
  const context = {subscriptions: []};
  activate(context, vscode);
  return {vscode, commands, tasks, errors, document, context, saves: () => saves};
}

test('run saves and passes the path as one process argument', async () => {
  const f = fixture();
  await f.commands['ucl.runFile']();
  assert.equal(f.saves(), 1);
  assert.equal(f.tasks.length, 1);
  assert.equal(f.tasks[0].execution.command, 'ucl');
  assert.deepEqual(f.tasks[0].execution.args, ['run', f.document.uri.fsPath]);
  assert.equal(f.tasks[0].presentationOptions.focus, true);
});

test('check uses the check subcommand', async () => {
  const f = fixture();
  await f.commands['ucl.checkFile']();
  assert.equal(f.tasks[0].execution.args[0], 'check');
});

test('untrusted workspaces cannot execute', async () => {
  const f = fixture();
  f.vscode.workspace.isTrusted = false;
  await f.commands['ucl.runFile']();
  assert.equal(f.tasks.length, 0);
  assert.equal(f.saves(), 0);
  assert.equal(f.errors.length, 1);
});

test('cancelled save and non-UCL editors do not execute', async () => {
  const f = fixture();
  f.document.save = async () => false;
  await f.commands['ucl.runFile']();
  assert.equal(f.tasks.length, 0);
  f.document.languageId = 'plaintext';
  await f.commands['ucl.runFile']();
  assert.equal(f.tasks.length, 0);
});

test('trace command enables action diagnostics without a shell', async () => {
  const f = fixture();
  await f.commands['ucl.traceFile']();
  assert.deepEqual(f.tasks[0].execution.args, ['run', f.document.uri.fsPath, '--trace']);
});
