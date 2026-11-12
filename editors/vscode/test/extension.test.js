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
    languages: {registerCompletionItemProvider: () => ({dispose() {}}), registerHoverProvider: () => ({dispose() {}}), createDiagnosticCollection: () => ({dispose() {}})},
    workspace: {isTrusted: true, getWorkspaceFolder: () => undefined, onDidSaveTextDocument: () => ({dispose() {}}), onDidCloseTextDocument: () => ({dispose() {}})},
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

const {capabilityCompletions, registerCompletions} = require('../completions');
const snippets = require('../snippets/ucl.json');

test('type is t completes only terminal, never an application template', () => {
  assert.deepEqual(capabilityCompletions('    type is t'), ['terminal','tui']);
  assert.deepEqual(capabilityCompletions('type is '), ['gui','browser','server','terminal','database','tui']);
  assert.deepEqual(capabilityCompletions('type is br'), ['browser']);
  assert.deepEqual(capabilityCompletions('TYPE IS T'), ['terminal','tui']);
  assert.deepEqual(capabilityCompletions('say "type is t'), []);
  assert.deepEqual(capabilityCompletions('// type is t'), []);
});

test('completion replacement preserves type is and the surrounding app', () => {
  let provider;
  const vscode = {
    languages: {registerCompletionItemProvider: (language, value) => {provider = value; return {dispose() {}};}, registerHoverProvider: () => ({dispose() {}})},
    CompletionItem: class {constructor(label, kind) {Object.assign(this, {label,kind});}},
    CompletionItemKind: {Keyword: 14},
    Range: class {constructor(line, start, endLine, end) {Object.assign(this,{line,start,endLine,end});}}
  };
  registerCompletions({subscriptions: []}, vscode);
  for (const prefix of ['t', 'ter', 'terminal', '']) {
    const line = '    type is ' + prefix;
    const items = provider.provideCompletionItems({lineAt: () => ({text:line})}, {line:1,character:line.length});
    const item = items.find(item => item.label === 'terminal');
    const replaced = line.slice(0,item.range.start) + item.insertText + line.slice(item.range.end);
    assert.equal('[\n' + replaced + '\n]', '[\n    type is terminal\n]');
  }
});

test('all templates have explicit non-keyword snippet prefixes', () => {
  for (const entry of Object.values(snippets)) assert.match(entry.prefix, /^ucl-/);
  assert.equal(snippets['Terminal application'].prefix, 'ucl-app-terminal');
  assert.equal(snippets['Native desktop application'].prefix, 'ucl-app-gui');
});

const {suggestions,hoverText} = require('../completions');
const {checkResult,registerDiagnostics} = require('../diagnostics');

test('command recommendations replace only the statement prefix', () => {
  const entry = suggestions('  show lab').find(x=>x.key==='label_named');
  assert.ok(entry);
  assert.equal('  show lab'.slice(0,entry.start)+entry.text,'  show label "0" is #counter');
  assert.equal(suggestions('  // show lab').length,0);
  assert.equal(suggestions('say "show lab').length,0);
});

test('widget ids, style keys, values and expression builtins', () => {
  assert.equal(suggestions('style #sa','show button "Save" is #save')[0].text,'save');
  assert.equal(suggestions('style #save is {"rad')[0].text,'radius');
  assert.equal(suggestions('style #save is {"animation": "fa')[0].text,'fade');
  assert.equal(suggestions('say leng')[0].text,'length');
  assert.match(hoverText('theme is dark','theme'),/palette/i);
  assert.match(hoverText('say length(x)','length'),/number of items/i);
  assert.match(hoverText('style #x is {"radius":12}','radius'),/Design property/);
});

test('checker messages retain line locations and handle missing executables', () => {
  assert.equal(checkResult(null,'passed',''),undefined);
  assert.deepEqual(checkResult({code:1},'','UCL error: line 7: unknown statement'),{line:6,message:'UCL error: line 7: unknown statement'});
  assert.equal(checkResult({code:'ENOENT'},'','').warning,true);
});

test('save diagnostics require trust, do not use a shell, and discard stale results', () => {
  let save,callback;
  const recorded = [], diagnostics = [];
  const vscode = {
    workspace:{isTrusted:false,getConfiguration:()=>({get:(key,fallback)=>fallback}),onDidSaveTextDocument:fn=>{save=fn;return {dispose(){}};},onDidCloseTextDocument:()=>({dispose(){}})},
    languages:{createDiagnosticCollection:()=>({set:(uri,list)=>diagnostics.push(list),delete(){},dispose(){}})},
    Range:class {constructor(...args){this.args=args;}},
    Diagnostic:class {constructor(range,message,severity){Object.assign(this,{range,message,severity});}},
    DiagnosticSeverity:{Warning:1,Error:0}
  };
  const document = {languageId:'ucl',uri:{scheme:'file',fsPath:'/file ; literal.ucl',toString:()=>'/file ; literal.ucl'},version:1,lineCount:3,lineAt:()=>({text:'bad'})};
  const job = {kill(){}};
  registerDiagnostics({subscriptions:[]},vscode,(...args)=>{recorded.push(args);callback=args[3];return job;});
  save(document);
  assert.equal(recorded.length,0);
  vscode.workspace.isTrusted=true;
  save(document);
  assert.deepEqual(recorded[0].slice(0,2),['ucl',['check','/file ; literal.ucl']]);
  assert.equal(recorded[0][2].shell,undefined);
  callback({code:1},'','line 2: invalid');
  assert.equal(diagnostics[0][0].range.args[0],1);
  save(document);
  document.version++;
  callback({code:1},'','line 2: stale');
  assert.equal(diagnostics.length,1);
});

test('application templates are context-gated rather than global fuzzy snippets', () => {
  const manifest = require('../package.json');
  assert.equal(manifest.contributes.snippets,undefined);
  assert.equal(suggestions('  ucl-app-t')[0].snippet,true);
  for (const before of ['type is t','type is terminal','type is ucl-app-t']) {
    assert.equal(suggestions(before).some(item=>item.snippet),false);
  }
});
