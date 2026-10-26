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
  defaultReviewCommand,
  hasWorkspaceSettingOverride,
  quotePosixShellArgument,
  showDashboard,
  validateReviewQueue,
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
          } else if (request.params.name === 'project_storage_usage') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', logical_record_bytes: 4096,
              event_payload_bytes_retained: 256, fact_count: 2,
              fact_count_limit: 10000, fact_record_bytes: 512,
              fact_record_bytes_limit: 16777216,
              global_database_bytes: 8192, global_wal_bytes: 1024,
              staging: {
                observed_file_bytes: 128,
                inventory_complete: true,
                error_code: null,
              },
              staging_project_byte_limit: 262144000,
            }) }] };
          } else if (request.params.name === 'goal_list_page') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', total: 1, offset: 0, limit: 20,
              goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Smoke goal' }],
              next_offset: null,
            }) }] };
          } else if (request.params.name === 'sde_review_queue') {
            result = { content: [{ type: 'text', text: JSON.stringify([{
              candidate: {
                candidate_id: 'candidate-1', materiality: 'decision',
                rationale: 'Retain this verified project decision.',
                goal_id: 'goal-1', status: 'pending_review',
              },
              goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal' },
            }]) }] };
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
  assert.match(html, /Pending SDE review/);
  assert.match(html, /Review in terminal/);
  assert.match(html, /label\.textContent = candidate\.materiality/);
  assert.doesNotMatch(html, /report\.innerHTML/);
  assert.doesNotMatch(html, /reviews\.innerHTML/);
});

test('launcher, database, and profile settings reject workspace overrides', () => {
  const settings = {
    databasePath: { globalValue: '/home/user/curator.sqlite3' },
    profileId: { globalValue: 'development-profile' },
    serverCommand: { globalValue: '/opt/curator/bin/curatormd-v2-mcp' },
    reviewCommand: { globalValue: '/opt/curator/bin/curatormd-v2-review' },
  };
  const config = { inspect: (name) => settings[name] };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand']),
    false,
  );
  settings.databasePath.workspaceValue = '/tmp/attacker.sqlite3';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand']),
    true,
  );
  delete settings.databasePath.workspaceValue;
  settings.reviewCommand.workspaceFolderValue = '/tmp/attacker-review';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand']),
    true,
  );
});

test('POSIX command quoting keeps paths with spaces and quotes as one argument', () => {
  assert.equal(quotePosixShellArgument("/tmp/a user's project"), "'/tmp/a user'\\''s project'");
  assert.throws(() => quotePosixShellArgument('/tmp/project\nreview'), /control characters/);
});

test('review CLI defaults beside the configured MCP launcher', () => {
  assert.equal(
    defaultReviewCommand('/opt/curator tools/bin/curatormd-v2-mcp'),
    '/opt/curator tools/bin/curatormd-v2-review',
  );
  assert.equal(defaultReviewCommand('curatormd-v2-mcp'), 'curatormd-v2-review');
});

test('review queue rejects malformed and cross-project candidates instead of showing zero', () => {
  const valid = [{
    candidate: {
      candidate_id: 'candidate-1', goal_id: 'goal-1', status: 'pending_review',
      materiality: 'decision', rationale: 'Reviewed project decision.',
    },
    goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal' },
  }];
  assert.equal(validateReviewQueue(valid, 'alpha').length, 1);
  assert.equal(validateReviewQueue(valid, 'other'), null);
  assert.equal(validateReviewQueue([{ candidate: valid[0].candidate }], 'alpha'), null);
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
    reviewCommand: '/opt/curator tools/curatormd-v2-review',
  };
  const terminalCalls = [];
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
    createTerminal: (options) => ({
      show: () => terminalCalls.push({ action: 'show', options }),
      sendText: (text, addNewLine) => terminalCalls.push({ action: 'sendText', text, addNewLine }),
    }),
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
  assert.equal(goals.storage.logical_record_bytes, 4096);
  assert.equal(goals.storage.staging.observed_file_bytes, 128);
  assert.equal(goals.reviews.length, 1);
  await receiveMessage({ type: 'openReview', candidateId: 'unlisted-candidate' });
  assert.equal(terminalCalls.length, 0);
  await receiveMessage({ type: 'openReview', candidateId: 'candidate-1' });
  assert.equal(terminalCalls[0].action, 'show');
  assert.equal(terminalCalls[1].action, 'sendText');
  assert.match(terminalCalls[1].text, /'\/opt\/curator tools\/curatormd-v2-review'/);
  assert.match(terminalCalls[1].text, /'\/tmp\/project'/);
  assert.match(terminalCalls[1].text, /'candidate-1'/);
  assert.equal(terminalCalls[1].addNewLine, true);
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

  const storageSnapshot = {
    project_id: 'alpha', logical_record_bytes: 4096,
    event_payload_bytes_retained: 256, fact_count: 2,
    fact_count_limit: 10000, fact_record_bytes: 512,
    fact_record_bytes_limit: 16777216,
    global_database_bytes: 8192, global_wal_bytes: 1024,
    staging: { observed_file_bytes: 128, inventory_complete: true, error_code: null },
    staging_project_byte_limit: 262144000,
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0,
    goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Private goal' }],
    next_offset: null,
  },
  health: { project_id: 'alpha', status: 'healthy', gate_codes: [] },
  activity: {
    project_id: 'alpha', event_receipt_count: 3, processed_event_count: 2,
    received_event_count: 1, failed_event_count: 0, quarantined_event_count: 0,
    goal_count: 1, fact_count: 2, pending_sde_count: 1,
    approved_sde_count: 0, rejected_sde_count: 0,
  },
  storage: storageSnapshot } });
  assert.match(elements.get('health').textContent, /Project health: healthy\. Open gates: none reported\./);
  assert.match(elements.get('activity').textContent, /Retained receipts: 3 \(processed 2, received 1, failed 0, quarantined 0\); goals 1; facts 2; SDE candidates pending 1, approved 0, rejected 0\./);
  assert.match(elements.get('storage').textContent, /Project logical records 4\.0 KiB; retained event payload 256 B; facts 2\/10000 \(512 B\/16\.0 MiB\)\. Shared SQLite files: database 8\.0 KiB, WAL 1\.0 KiB\. Staging 128 B \/ 250\.0 MiB warning-only threshold; below warning level, and writes remain allowed\. Model\/token usage is not reported here\./);
  const stagingAtWarning = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 196608000, inventory_complete: true, error_code: null },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: stagingAtWarning } });
  assert.match(elements.get('storage').textContent, /warning level reached, and writes remain allowed/);
  const stagingAtThreshold = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 262144000, inventory_complete: true, error_code: null },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: stagingAtThreshold } });
  assert.match(elements.get('storage').textContent, /warning threshold reached, and writes remain allowed/);
  const incompleteStaging = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 123, inventory_complete: false, error_code: 'staging_scan_failed' },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: incompleteStaging } });
  assert.match(elements.get('storage').textContent, /Staging scan incomplete; observed at least 123 B \(code staging_scan_failed\)/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, storage: { project_id: 'other' } } });
  assert.match(elements.get('storage').textContent, /unknown\. Project mismatch/);
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
  assert.match(elements.get('storage').textContent, /Storage usage: unknown/);
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
    'a'.repeat(64), false,
    ['project_health', 'project_activity_status', 'project_storage_usage'],
  ));
  await receiveMessage({ type: 'loadGoals', offset: 0 });

  const goals = messages.find((message) => message.type === 'goals');
  assert.equal(goals.page.goals[0].goal_id, 'goal-1');
  assert.equal(goals.health, null);
  assert.equal(goals.activity, null);
  assert.equal(goals.storage, null);
});
