'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const Module = require('node:module');
const { PassThrough, Writable } = require('node:stream');
const test = require('node:test');
const vm = require('node:vm');

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
  constructor(reportRevision = 'a'.repeat(64), denyToolCall = false, denyToolName = null) {
    super();
    this.requests = [];
    this.denyToolCall = denyToolCall;
    this.denyToolName = denyToolName;
    this.stdout = new PassThrough();
    this.stdin = new Writable({
      write: (chunk, _encoding, callback) => {
        const request = JSON.parse(String(chunk).trim());
        this.requests.push(request);
        if (request.id !== undefined) {
          let result;
          if (request.method === 'initialize') {
            result = { protocolVersion: '2024-11-05', capabilities: {}, serverInfo: { name: 'fixture', version: '1' } };
          } else if (this.denyToolCall || (Array.isArray(this.denyToolName)
            ? this.denyToolName.includes(request.params.name)
            : request.params.name === this.denyToolName)) {
            result = { isError: true, content: [{ type: 'text', text: 'permission denied' }] };
          } else if (request.params.name === 'project_health') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', status: 'healthy', gate_codes: [],
            }) }] };
          } else if (request.params.name === 'project_activity_status') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha',
              event_receipt_count: 3,
              processed_event_count: 2,
              received_event_count: 1,
              failed_event_count: 0,
              quarantined_event_count: 0,
              goal_count: 1,
              fact_count: 2,
              pending_sde_count: 1,
              approved_sde_count: 0,
              rejected_sde_count: 0,
            }) }] };
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
  let processCount = 0;
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

  await showDashboard(() => {
    const current = processCount++;
    return new FakeMcpProcess(
      reportReadCount++ >= 2 ? 'b'.repeat(64) : 'a'.repeat(64),
      current === 3,
    );
  });
  assert.equal(typeof receiveMessage, 'function');
  assert.equal(typeof disposePanel, 'function');
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  const goals = messages.find((message) => message.type === 'goals');
  assert.equal(goals.page.goals[0].goal_id, 'goal-1');
  assert.equal(goals.health.status, 'healthy');
  assert.equal(goals.activity.event_receipt_count, 3);
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 0 });
  const report = messages.find((message) => message.type === 'report');
  assert.match(report.report, /Open TODOs/);
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });
  assert.ok(messages.some((message) => message.type === 'reportStale'));
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });
  assert.equal(
    messages.filter((message) => message.type === 'error').at(-1).message,
    'Curator read failed. Check User settings, the local project grant, and the launcher.',
  );
  disposePanel();
});

test('dashboard clears previously rendered data when a fresh read is denied', () => {
  class Element {
    constructor() {
      this.textContent = '';
      this.disabled = false;
      this.children = [];
      this.listeners = {};
    }

    addEventListener(type, listener) { this.listeners[type] = listener; }
    appendChild(child) { this.children.push(child); }
    replaceChildren(...children) { this.children = children; }
  }

  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, new Element());
      return elements.get(id);
    },
    createElement() { return new Element(); },
  };
  let receiveWindowMessage;
  const window = {
    addEventListener(type, listener) {
      if (type === 'message') receiveWindowMessage = listener;
    },
  };
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {
    document,
    window,
    acquireVsCodeApi: () => ({ postMessage() {} }),
  });

  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha',
    total: 1,
    offset: 0,
    goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Private goal' }],
    next_offset: null,
  },
  health: { project_id: 'alpha', status: 'healthy', gate_codes: [] },
  activity: {
    project_id: 'alpha', event_receipt_count: 3, processed_event_count: 2,
    received_event_count: 1, failed_event_count: 0, quarantined_event_count: 0,
    goal_count: 1, fact_count: 2, pending_sde_count: 1,
    approved_sde_count: 0, rejected_sde_count: 0,
  } } });
  assert.match(elements.get('health').textContent, /Project health: healthy\. Open gates: none reported\./);
  assert.match(elements.get('activity').textContent, /Retained receipts: 3 \(processed 2, received 1, failed 0, quarantined 0\); goals 1; facts 2; SDE candidates pending 1, approved 0, rejected 0\./);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: { project_id: 'alpha', status: 'degraded', gate_codes: ['staging_budget_warning'] } } });
  assert.match(elements.get('health').textContent, /degraded\. Open gates: staging_budget_warning/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: { project_id: 'other', status: 'healthy', gate_codes: [] } } });
  assert.match(elements.get('health').textContent, /unknown\. Open gates: health_project_mismatch/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: null } });
  assert.match(elements.get('health').textContent, /unknown\. Open gates: health_read_unavailable/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1,
    offset: 0,
    goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Private goal' }],
    next_offset: null,
    project_id: 'alpha',
  }, health: { project_id: 'alpha', status: 'healthy', gate_codes: [] } } });
  elements.get('goals').children[0].listeners.click();
  receiveWindowMessage({ data: {
    type: 'report',
    goalId: 'goal-1',
    factOffset: 0,
    factTotal: 1,
    reportRevision: 'a'.repeat(64),
    report: 'Private facts',
  } });
  assert.equal(elements.get('report').textContent, 'Private facts');
  assert.equal(elements.get('goals').children.length, 1);

  receiveWindowMessage({ data: { type: 'error', message: 'Curator read failed.' } });

  assert.equal(elements.get('report').textContent, '');
  assert.equal(elements.get('goals').children.length, 0);
  assert.equal(elements.get('selected').textContent, '');
  assert.equal(elements.get('goalPage').textContent, '');
  assert.equal(elements.get('factPage').textContent, '');
  assert.equal(elements.get('error').textContent, 'Curator read failed.');
  assert.equal(elements.get('nextFacts').disabled, true);
  assert.match(elements.get('health').textContent, /Project health: unknown/);
});

test('dashboard still reads goals when the health probe is unavailable', async () => {
  const messages = [];
  let receiveMessage;
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
      onDidDispose() {},
    }),
  };

  await showDashboard(() => new FakeMcpProcess(
    'a'.repeat(64), false, ['project_health', 'project_activity_status'],
  ));
  await receiveMessage({ type: 'loadGoals', offset: 0 });

  const goals = messages.find((message) => message.type === 'goals');
  assert.equal(goals.page.goals[0].goal_id, 'goal-1');
  assert.equal(goals.health, null);
  assert.equal(goals.activity, null);
});
