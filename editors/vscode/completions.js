'use strict';
const data = require('./language-data.json');
const snippets = require('./snippets/ucl.json');
const CAPABILITIES = ['gui', 'browser', 'server', 'terminal', 'database', 'tui'];
function capabilityCompletions(lineBeforeCursor) {
  const match = /^\s*type\s+is\s+([a-z]*)$/i.exec(lineBeforeCursor);
  if (!match) return [];
  return CAPABILITIES.filter(value => value.startsWith(match[1].toLowerCase()));
}

// Return plain insertion text and explicit replacement spans. Templates only
// replace a command prefix at statement start, never a value inside a statement.
function suggestions(before, source = '') {
  const capability = /^\s*type\s+is\s+([a-z]*)$/i.exec(before);
  if (capability) return capabilityCompletions(before).map(value => ({label:value,text:value,start:before.length-capability[1].length,detail:'UCL application capability'}));
  if (/^\s*\/\//.test(before)) return [];
  const template = /^(\s*)(ucl(?:-[\w-]*)?)$/.exec(before);
  if (template) return Object.entries(snippets).filter(([,entry])=>entry.prefix.startsWith(template[2])).map(([name,entry])=>({label:entry.prefix,text:Array.isArray(entry.body)?entry.body.join('\n'):entry.body,start:template[1].length,detail:entry.description||name,snippet:true}));
  const id = /#([\w-]*)$/.exec(before);
  if (id) return [...new Set([...source.matchAll(/\bis\s+#([\w-]+)/g)].map(m=>m[1]))].filter(name=>name.startsWith(id[1])).map(name=>({label:'#'+name,text:name,start:before.length-id[1].length,detail:'Declared widget'}));
  const value = /\bstyle\b.*["']([a-z_]+)["']\s*:\s*["']([a-z-]*)$/.exec(before);
  if (value && data.enums[value[1]]) return data.enums[value[1]].filter(name=>name.startsWith(value[2])).map(name=>({label:name,text:name,start:before.length-value[2].length,detail:`Value for ${value[1]}`}));
  const property = /\bstyle\b.*\{[^}]*?["']([a-z_]*)$/.exec(before);
  if (property) return data.styles.filter(name=>name.startsWith(property[1])).map(name=>({label:name,text:name,start:before.length-property[1].length,detail:'Design property (see design guide for renderer support)'}));
  const command = /^(\s*)([a-z][a-z ]*)$/i.exec(before);
  const expressions = () => {
    const word = /([a-z_]\w*)$/.exec(before);
    return word ? Object.entries(data.builtins).filter(([name])=>name.startsWith(word[1])).map(([name,detail])=>({label:name,text:name,start:before.length-word[1].length,detail})) : [];
  };
  if (!command) return expressions();
  const prefix = command[2].toLowerCase();
  const types = CAPABILITIES.map(value=>({label:'type is '+value,text:'type is '+value,start:command[1].length,detail:'Select application capability'})).filter(item=>item.text.startsWith(prefix));
  const commands = types.concat(Object.entries(data.commands).filter(([key,entry])=>key!=='type' && entry.syntax.toLowerCase().startsWith(prefix)).map(([key,entry])=>({label:entry.syntax,text:entry.syntax,start:command[1].length,detail:entry.description,key})));
  return commands.length ? commands : expressions();
}

function hoverText(line, word) {
  if (data.builtins[word]) return data.builtins[word];
  if (data.styles.includes(word)) return `Design property: ${word}. ` + (data.enums[word] ? `Values: ${data.enums[word].join(', ')}.` : 'See the design guide for units, ranges and renderer support.');
  const text = line.trim().replace(/\s*\[\s*$/, ' []');
  for (const entry of Object.values(data.commands)) {
    try { if (new RegExp('^(?:'+entry.pattern+')$','i').test(text)) return entry.syntax+'\n\n'+entry.description; } catch { /* Python-only regex constructs are not a reason to run source. */ }
  }
  return undefined;
}

function registerCompletions(context, vscode) {
  context.subscriptions.push(vscode.languages.registerCompletionItemProvider('ucl', {
    provideCompletionItems(document, position) {
      const before = document.lineAt(position.line).text.slice(0,position.character);
      return suggestions(before,document.getText ? document.getText() : '').map(value => {
        const item = new vscode.CompletionItem(value.label,value.snippet ? vscode.CompletionItemKind.Snippet : vscode.CompletionItemKind.Keyword);
        item.insertText = value.snippet ? new vscode.SnippetString(value.text) : value.text;
        item.range = new vscode.Range(position.line,value.start,position.line,position.character);
        item.detail = value.detail;
        return item;
      });
    }
  },' ','#','"'));
  context.subscriptions.push(vscode.languages.registerHoverProvider('ucl', {
    provideHover(document,position) {
      const range = document.getWordRangeAtPosition(position);
      const text = hoverText(document.lineAt(position.line).text,range ? document.getText(range) : '');
      if (text) return new vscode.Hover(text);
    }
  }));
}
module.exports = {capabilityCompletions,suggestions,hoverText,registerCompletions};
