'use strict';
const {execFile} = require('node:child_process');
const path = require('node:path');

function checkResult(error, stdout, stderr) {
  if (!error) return undefined;
  if (error.code === 'ENOENT') return {line:0,message:'UCL executable not found. Install UCL or configure ucl.executable.',warning:true};
  const message = String(stderr || stdout || error.message).trim();
  const match = /line (\d+):/.exec(message);
  return {line:match ? Math.max(0,Number(match[1])-1) : 0,message};
}

function registerDiagnostics(context,vscode,spawn = execFile) {
  const collection = vscode.languages.createDiagnosticCollection('ucl');
  const jobs = new Map();
  function check(document) {
    if (document.languageId !== 'ucl' || document.uri.scheme !== 'file' || !vscode.workspace.isTrusted) return;
    const config = vscode.workspace.getConfiguration('ucl');
    if (!config.get('checkOnSave',true)) {collection.delete(document.uri); return;}
    const key = document.uri.toString();
    jobs.get(key)?.kill();
    const version = document.version;
    const job = spawn(config.get('executable','ucl'),['check',document.uri.fsPath],
      {cwd:path.dirname(document.uri.fsPath),timeout:10000,maxBuffer:1024*1024,windowsHide:true},
      (error,stdout,stderr) => {
        if (jobs.get(key) !== job) return;
        jobs.delete(key);
        if (document.isClosed || document.version !== version || !vscode.workspace.isTrusted) return;
        const result = checkResult(error,stdout,stderr);
        if (!result) {collection.delete(document.uri); return;}
        const line = Math.min(result.line,Math.max(0,document.lineCount-1));
        const range = new vscode.Range(line,0,line,document.lineAt(line).text.length);
        const diagnostic = new vscode.Diagnostic(range,result.message,result.warning ? vscode.DiagnosticSeverity.Warning : vscode.DiagnosticSeverity.Error);
        diagnostic.source = 'UCL checker';
        collection.set(document.uri,[diagnostic]);
      });
    jobs.set(key,job);
  }
  context.subscriptions.push(collection,vscode.workspace.onDidSaveTextDocument(check),
    vscode.workspace.onDidCloseTextDocument(document => {
      const key = document.uri.toString();
      jobs.get(key)?.kill(); jobs.delete(key); collection.delete(document.uri);
    }), {dispose() {for (const job of jobs.values()) job.kill(); jobs.clear();}});
}
module.exports = {checkResult,registerDiagnostics};
