'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const Module = require('node:module');
const { PassThrough, Writable } = require('node:stream');
const test = require('node:test');

const vscodeMock = {};
const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === 'vscode') return vscodeMock;
  return originalLoad.call(this, request, parent, isMain);
};
const {
  McpStdioClient,
  dashboardHtml,
  hasWorkspaceSettingOverride,
  showDashboard,
} = require('./extension');
Module._load = originalLoad;

class FakeMcpProcess extends EventEmitter {
  constructor(reportRevision = 'a'.repeat(64)) {
    super();
    this.requests = [];
    this.stdout = new PassThrough();
    this.stdin = new Writable({
      write: (chunk, _encoding, callback) => {
        const request = JSON.parse(String(chunk).trim());
        this.requests.push(request);
        if (request.id !== undefined) {
          let result;
          if (request.method === 'initialize') {
            result = { protocolVersion: '2024-11-05', capabilities: {}, serverInfo: { name: 'fixture', version: '1' } };
          } else if (request.params.name === 'goal_list_page') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', total: 1, offset: 0, limit: 20,
              goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Smoke goal' }],
              next_offset: null,
            }) }] };
          } else {
            result = { content: [{ type: 'text', text: '- Report snapshot: `' + reportRevision + '`\n## Facts to date (showing 0–0 of 0)\n## Open TODOs' }] };
          }
          queueMicrotask(() => this.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id: request.id, result })}\n`));
        }
        callback();
      },
    });
  }

  kill() {
    this.emit('exit', 0, null);
  }
}

test('MCP stdio dashboard client initializes and reads a tool result', async () => {
  const child = new FakeMcpProcess();
  const client = new McpStdioClient('fixture', [], '/tmp', 'fixture-profile', () => child);
  await client.initialize();
  const result = await client.callTool('goal_list_page', { offset: 0, limit: 20 });
  assert.equal(JSON.parse(result).project_id, 'alpha');
  const call = child.requests.find((request) => request.method === 'tools/call');
  assert.equal(call.params._meta['hermes/profile_id'], 'fixture-profile');
  assert.match(call.params._meta['hermes/session_id'], /^[0-9a-f]{32}$/);
  client.close();
});

test('dashboard renders bounded pages as text and never joins prior pages', () => {
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  assert.match(html, /default-src 'none'/);
  assert.match(html, /Facts .* of /);
  assert.match(html, /previous page was cleared/);
  assert.match(html, /reportStale/);
  assert.match(html, /Restarting from the first page/);
  assert.match(html, /reportRevision\.slice\(0, 12\)/);
  assert.match(html, /report\.textContent = message\.report/);
  assert.doesNotMatch(html, /report\.innerHTML/);
});

test('launcher, database, and profile settings reject workspace overrides', () => {
  const settings = {
    databasePath: { globalValue: '/home/user/curator.sqlite3' },
    profileId: { globalValue: 'development-profile' },
    serverCommand: { globalValue: '/opt/curator/bin/curatormd-v2-mcp' },
  };
  const config = { inspect: (name) => settings[name] };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand']),
    false,
  );
  settings.databasePath.workspaceValue = '/tmp/attacker.sqlite3';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand']),
    true,
  );
});

test('dashboard opens a panel, reads goal and report pages, and clears on disposal', async () => {
  const messages = [];
  let receiveMessage;
  let disposePanel;
  let reportReadCount = 0;
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: '/tmp/project' } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showWarningMessage: assert.fail,
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => { messages.push(message); },
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose: (handler) => { disposePanel = handler; },
    }),
  };

  await showDashboard(() => new FakeMcpProcess(
    reportReadCount++ >= 2 ? 'b'.repeat(64) : 'a'.repeat(64),
  ));
  assert.equal(typeof receiveMessage, 'function');
  assert.equal(typeof disposePanel, 'function');
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  const goals = messages.find((message) => message.type === 'goals');
  assert.equal(goals.page.goals[0].goal_id, 'goal-1');
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 0 });
  const report = messages.find((message) => message.type === 'report');
  assert.match(report.report, /Open TODOs/);
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });
  assert.ok(messages.some((message) => message.type === 'reportStale'));
  disposePanel();
});
