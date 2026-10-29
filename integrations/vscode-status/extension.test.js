'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const Module = require('node:module');
const os = require('node:os');
const path = require('node:path');
const { version: extensionVersion } = require('./package.json');
const { PassThrough, Writable } = require('node:stream');
const test = require('node:test');
const vm = require('node:vm');

function assertTooltipIncludesCurrentVersion(item) {
  assert.ok(item.tooltip.includes(`CuratorMD V2 ${extensionVersion}.`));
}

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
  parseHermesHealthProbe,
  readHermesHealthProbe,
  hasWorkspaceSettingOverride,
  quotePosixShellArgument,
  activate,
  deactivate,
  dashboardErrorMessage,
  summarizeGoalStates,
  summarizeEventFailureCategories,
  summarizeOperationalAlerts,
  summarizeOperationalQueues,
  showDashboard,
  statusColorMeaning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  validateReviewQueue,
} = require('./extension');
Module._load = originalLoad;

class FakeMcpProcess extends EventEmitter {
  constructor(
    reportRevision = 'a'.repeat(64), denyToolCall = false,
    denyToolName = null, reportFactId = null, emptyReviewQueue = false,
  ) {
    super();
    this.requests = [];
    this.denyToolCall = denyToolCall;
    this.denyToolName = denyToolName;
    this.reportRevision = reportRevision;
    this.reportFactId = reportFactId;
    this.emptyReviewQueue = emptyReviewQueue;
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
          } else if (request.params.name === 'project_metrics') {
            result = { content: [{ type: 'text', text: [
              '# TYPE curatormd_event_failures gauge',
              'curatormd_event_failures{project_id="alpha",category="evidence_rejected"} 0',
              'curatormd_event_failures{project_id="alpha",category="evidence_adapter_error"} 0',
              'curatormd_event_failures{project_id="alpha",category="other"} 0',
            ].join('\n') }] };
          } else if (request.params.name === 'goal_list_page') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', total: 1, offset: 0, limit: 20,
              goals: [{ goal_id: 'goal-1', status: 'active', problem: 'Smoke goal' }],
              next_offset: null,
            }) }] };
          } else if (request.params.name === 'sde_review_queue_cards') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', candidates: this.emptyReviewQueue ? [] : [{
              candidate: {
                candidate_id: 'candidate-1', materiality: 'decision',
                rationale: 'Retain this verified project decision.',
                goal_id: 'goal-1', status: 'pending_review',
              },
              goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal' },
              facts: [{ bullet: 'PRIVATE_REVIEW_FACT_CANARY' }],
              receipt: { receipt_id: 'PRIVATE_REVIEW_RECEIPT_CANARY' },
              }],
            }) }] };
          } else if (request.params.name === 'goal_fact_evidence') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', goal_id: 'goal-1', fact_id: request.params.arguments.fact_id,
              fact_kind: 'verification', criterion_id: 'criterion-1',
              verification_status: 'verified_fact', report_revision: this.reportRevision,
              evidence: [{
                evidence_kind: 'repository_test', locator: 'git-test:runner-1:abc123',
                sha256: 'a'.repeat(64), outcome: 'passed', occurrence_id: null,
                attestation: {
                  adapter_id: 'adapter-1', authenticated_subject: 'local-uid:1000',
                  source_revision: 'git-test:runner-1:abc123',
                  observed_at: '2026-10-27T00:00:00+00:00',
                  valid_until: '2026-10-27T00:05:00+00:00',
                  revocation_checked_at: '2026-10-27T00:00:00+00:00',
                },
              }],
            }) }] };
          } else if (request.params.name === 'goal_report') {
            const facts = this.reportFactId
              ? `\n## Facts to date (showing 1–1 of 1)\n### Verified facts\n- \`${this.reportFactId}\` — Verification: test passed; criterion \`criterion-1\`; 1 evidence reference(s)`
              : '\n## Facts to date (showing 0–0 of 0)';
            result = { content: [{ type: 'text', text: '- Report snapshot: `' + this.reportRevision + '`' + facts + '\n## Open TODOs' }] };
          } else {
            result = { content: [{ type: 'text', text: '- Report snapshot: `' + this.reportRevision + '`\n## Facts to date (showing 0–0 of 0)\n## Open TODOs' }] };
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

class FakeHermesProcess extends EventEmitter {
  constructor(payload, exitCode = 0) {
    super();
    this.stdout = new PassThrough();
    this.killed = false;
    setImmediate(() => {
      this.stdout.end(JSON.stringify(payload), () => this.emit('close', exitCode, null));
    });
  }

  kill() {
    this.killed = true;
    this.emit('close', 1, null);
  }
}

function healthyHermesProbe(projectId = 'alpha') {
  const names = [
    'event_router', 'purge_scheduler', 'database_storage_adapter', 'host_identity',
    'human_review', 'alert_delivery', 'artifact_producer_inventory',
  ];
  return {
    schema_version: 1,
    connected: true,
    project_id: projectId,
    health: {
      project_id: projectId,
      status: 'healthy',
      gate_codes: [],
      database_observation_complete: true,
      dependencies: names.map((name) => ({
        name, status: 'healthy', observed_at: '2026-10-28T12:10:20+00:00', age_seconds: 0,
      })),
      operational_counts: {
        pending_review_count: 0,
        pending_purge_receipt_count: 0,
        pending_purge_artifact_count: 0,
        pending_expiry_purge_receipt_count: 0,
        pending_expiry_purge_artifact_count: 0,
      },
      event_received_count: 0,
      event_failed_count: 0,
      event_quarantined_count: 0,
      event_claimed_count: 0,
      event_expired_claim_count: 0,
      oldest_pending_event_age_seconds: null,
    },
  };
}

test('Hermes health probe requires a complete fresh-schema project-bound result', async () => {
  const payload = healthyHermesProbe();
  const health = parseHermesHealthProbe(JSON.stringify(payload), 'alpha');
  assert.equal(health.status, 'healthy');
  assert.equal(health.dependencies.length, 7);
  assert.throws(() => parseHermesHealthProbe(JSON.stringify(payload), 'other'), /incomplete or project-mismatched/);
  const incomplete = healthyHermesProbe();
  incomplete.health.dependencies.pop();
  assert.throws(() => parseHermesHealthProbe(JSON.stringify(incomplete), 'alpha'), /incomplete or project-mismatched/);

  let invocation;
  const read = await readHermesHealthProbe(
    'fixture-hermes', 'fixture-profile', 'alpha', '/tmp/project',
    (command, args, options) => {
      invocation = { command, args, options };
      return new FakeHermesProcess(payload);
    },
  );
  assert.equal(read.project_id, 'alpha');
  assert.deepEqual(invocation.args, [
    'mcp', 'test', 'curator_v2', '--probe-curator-status', '--json',
  ]);
  assert.equal(invocation.options.cwd, '/tmp/project');
  assert.equal(
    invocation.options.env.HERMES_HOME,
    path.join(os.homedir(), '.hermes', 'profiles', 'fixture-profile'),
  );
});

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
  assert.match(html, /Evidence references/);
  assert.match(html, /type: 'loadEvidence'/);
  assert.match(html, /reference\.locator/);
  assert.match(html, /paragraph\.textContent = fields\.filter\(Boolean\)\.join/);
  assert.doesNotMatch(html, /report\.innerHTML/);
  assert.doesNotMatch(html, /reviews\.innerHTML/);
});

test('status item follows Git Graph and uses project-bound health colors', async () => {
  const items = [];
  const commands = [];
  vscodeMock.StatusBarAlignment = { Left: 1, Right: 2 };
  vscodeMock.window = {
    createStatusBarItem: (alignment, priority) => {
      const item = { alignment, priority, show() {}, dispose() {} };
      items.push(item);
      return item;
    },
  };
  vscodeMock.commands = {
    registerCommand: (name, handler) => {
      const command = { name, handler, dispose() {} };
      commands.push(command);
      return command;
    },
  };
  const subscriptions = [];
  activate({ subscriptions: { push: (...values) => subscriptions.push(...values) } });

  assert.equal(items.length, 1);
  assert.equal(items[0].alignment, vscodeMock.StatusBarAlignment.Left);
  assert.equal(items[0].priority, 0);
  assert.equal(items[0].text, '$(circle-filled) CuratorMD V2');
  assert.equal(items[0].color, '#888888');
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.match(items[0].tooltip, /Gray means no health read has been attempted/);
  assert.equal(commands[0].name, 'curatormdV2.openDashboard');
  assert.equal(subscriptions.length, 3);

  assert.equal(updateStatusBarHealth({ project_id: 'alpha', status: 'healthy' }, 'alpha', []), 'healthy');
  assert.equal(items[0].color, '#73d216');
  assert.match(items[0].tooltip, /Project health: healthy/);
  assert.match(items[0].tooltip, /no SDE reviews pending/);
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.match(items[0].tooltip, /Green means health is healthy with no SDE reviews pending/);
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', [], {
      project_id: 'alpha', global_database_bytes: 262144000, global_wal_bytes: 0,
    },
  ), 'healthy');
  assert.equal(items[0].text, '$(circle-filled) CuratorMD V2: healthy');
  const sqliteWarningStorage = {
    project_id: 'alpha', global_database_bytes: 262144001, global_wal_bytes: 0,
  };
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', [], sqliteWarningStorage,
  ), 'healthy');
  assert.equal(items[0].color, '#73d216');
  assert.match(items[0].text, /SQLite size warning/);
  assert.match(items[0].tooltip, /above the 250 MiB warning threshold/);
  assert.match(items[0].tooltip, /Writes remain allowed; SQLite manages WAL checkpointing/);
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', [], {
      ...sqliteWarningStorage, project_id: 'other',
    },
  ), 'healthy');
  assert.doesNotMatch(items[0].tooltip, /SQLite size warning/);
  const pendingReview = { candidate: { candidate_id: 'review-1' } };
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', [pendingReview],
  ), 'healthy');
  assert.equal(items[0].color, '#ad7fa8');
  assert.equal(items[0].text, '$(circle-filled) CuratorMD V2: review');
  assert.match(items[0].tooltip, /1 pending SDE review/);
  assert.match(items[0].tooltip, /Purple means an SDE review is pending/);
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'degraded', gate_codes: ['review_backlog'],
  }, 'alpha', [pendingReview]), 'degraded');
  assert.equal(items[0].color, '#ad7fa8');
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'degraded',
    gate_codes: ['review_backlog', 'event_failures'],
  }, 'alpha', [pendingReview]), 'degraded');
  assert.equal(items[0].color, '#ef2929');
  assert.match(items[0].tooltip, /Red means health is degraded beyond the review-only state/);
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', null,
  ), 'healthy');
  assert.equal(items[0].color, '#fce94f');
  assert.match(items[0].tooltip, /pending SDE review count unavailable/);
  assert.match(items[0].tooltip, /Yellow means health or the SDE review count is unknown/);
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'unknown',
    gate_codes: ['missing_host_probe', 'not a gate', 'database_observation_failed'],
  }, 'alpha', []), 'unknown');
  assert.equal(items[0].color, '#fce94f');
  assert.match(items[0].tooltip, /Project health: unknown/);
  assert.match(items[0].tooltip, /Health gates: missing_host_probe, database_observation_failed/);
  assert.doesNotMatch(items[0].tooltip, /not a gate/);
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.equal(updateStatusBarHealth(
    { project_id: 'other', status: 'healthy', gate_codes: ['private_gate'] }, 'alpha', [],
  ), 'unknown');
  assert.doesNotMatch(items[0].tooltip, /private_gate/);
  assert.equal(statusColorMeaning('unknown'), 'Yellow means health or the SDE review count is unknown.');

  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-status-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  try {
    const status = await refreshStatusBarHealthFromWorkspace((command) => (
      command === 'fixture-hermes'
        ? new FakeHermesProcess(healthyHermesProbe())
        : new FakeMcpProcess('a'.repeat(64), false, null, null, true)
    ));
    assert.equal(status, 'healthy');
    assert.equal(items[0].color, '#73d216');
    assert.match(items[0].tooltip, /Project health: healthy/);
    assert.match(items[0].tooltip, /no SDE reviews pending/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
  deactivate();
});

test('dashboard maps Curator failures to actionable messages without backend details', () => {
  assert.match(dashboardErrorMessage({ code: 'read-denied' }), /configured project and its active local read grant/);
  assert.match(dashboardErrorMessage({ code: 'launcher-start' }), /serverCommand and the installed launcher/);
  assert.match(dashboardErrorMessage({ code: 'timeout' }), /did not respond within 15 seconds/);
  assert.match(dashboardErrorMessage(new Error('/private/path/secret traceback')), /Curator read failed/);
  assert.doesNotMatch(dashboardErrorMessage(new Error('/private/path/secret traceback')), /private|secret/);
});

test('operational dashboard summaries require exact project-bound queue and goal-state totals', () => {
  const goalStates = [
    'planned', 'active', 'complete', 'open', 'blocked',
    'deferred', 'cancelled', 'superseded',
  ].map((status) => ({ status, count: status === 'active' ? 2 : 0 }));
  const activity = { project_id: 'alpha', goal_count: 2, goal_status_counts: goalStates };
  assert.equal(
    summarizeGoalStates(activity, 'alpha'),
    'Goal states: planned 0, active 2, complete 0, open 0, blocked 0, deferred 0, cancelled 0, superseded 0.',
  );
  assert.match(summarizeGoalStates(activity, 'other'), /unknown.*mismatched/);
  assert.match(
    summarizeGoalStates({ ...activity, goal_count: 3 }, 'alpha'),
    /unknown.*incomplete/,
  );

  const health = {
    project_id: 'alpha',
    database_observation_complete: true,
    event_received_count: 1,
    event_failed_count: 2,
    event_quarantined_count: 3,
    event_claimed_count: 4,
    event_expired_claim_count: 5,
    oldest_pending_event_age_seconds: 60,
    operational_counts: {
      pending_review_count: 6,
      pending_purge_receipt_count: 7,
      pending_purge_artifact_count: 8,
      pending_expiry_purge_receipt_count: 9,
      pending_expiry_purge_artifact_count: 10,
    },
  };
  assert.equal(
    summarizeOperationalQueues(health, 'alpha'),
    'Events received 1, failed 2, quarantined 3, active claims 4, expired claims 5; oldest pending age 60s. Reviews pending 6; purge pending 7 receipts / 8 artifacts; expiry pending 9 receipts / 10 artifacts.',
  );
  assert.match(summarizeOperationalQueues(health, 'other'), /unknown.*mismatched/);
  assert.match(
    summarizeOperationalQueues({ ...health, database_observation_complete: false }, 'alpha'),
    /unknown.*incomplete/,
  );
});

test('operational alert summary surfaces actionable queues and staging warnings without guessing on unknowns', () => {
  const health = {
    project_id: 'alpha',
    status: 'degraded',
    gate_codes: ['event_failures', 'review_backlog'],
    database_observation_complete: true,
    event_received_count: 2,
    event_failed_count: 1,
    event_quarantined_count: 0,
    event_expired_claim_count: 0,
    operational_counts: {
      pending_review_count: 1,
      pending_purge_receipt_count: 1,
      pending_purge_artifact_count: 2,
      pending_expiry_purge_receipt_count: 0,
      pending_expiry_purge_artifact_count: 0,
    },
  };
  const storage = {
    project_id: 'alpha',
    staging: { observed_file_bytes: 200, inventory_complete: true },
    staging_project_byte_limit: 262,
  };
  const metrics = [
    '# TYPE curatormd_event_failures gauge',
    'curatormd_event_failures{project_id="alpha",category="evidence_rejected"} 1',
    'curatormd_event_failures{project_id="alpha",category="evidence_adapter_error"} 0',
    'curatormd_event_failures{project_id="alpha",category="other"} 0',
  ].join('\n');
  const summary = summarizeOperationalAlerts(health, storage, metrics, 'alpha');
  assert.match(summary, /Readiness degraded: event_failures, review_backlog/);
  assert.match(summary, /2 event receipt\(s\) waiting to process/);
  assert.match(summary, /Event failures by category: evidence rejected 1, adapter errors 0, other 0/);
  assert.match(summary, /1 SDE review\(s\) need a human decision/);
  assert.match(summary, /Cleanup pending: 1 receipt\(s\), 2 artifact\(s\)/);
  assert.match(summary, /Staging reached 75%/);
  assert.match(summary, /writes remain allowed/);

  const incomplete = summarizeOperationalAlerts(
    { ...health, project_id: 'other' }, storage, metrics, 'alpha',
  );
  assert.match(incomplete, /Readiness and queues unknown/);
  assert.doesNotMatch(incomplete, /No current queue or staging alerts/);
  const unknownCounters = summarizeOperationalAlerts(
    { ...health, event_failed_count: null, event_quarantined_count: null },
    { ...storage, staging: { ...storage.staging, inventory_complete: false } },
    metrics,
    'alpha',
  );
  assert.match(unknownCounters, /Event failure categories unknown/);
  assert.match(unknownCounters, /Staging inventory incomplete/);
  const wrongMetrics = summarizeOperationalAlerts(
    health, storage, metrics.replaceAll('project_id="alpha"', 'project_id="other"'), 'alpha',
  );
  assert.match(wrongMetrics, /category breakdown unknown/);
  assert.deepEqual(summarizeEventFailureCategories(metrics, 'alpha', 1), {
    evidence_rejected: 1, evidence_adapter_error: 0, other: 0,
  });
  assert.equal(summarizeEventFailureCategories(metrics, 'other', 1), null);
});

test('launcher, database, and profile settings reject workspace overrides', () => {
  const settings = {
    databasePath: { globalValue: '/home/user/curator.sqlite3' },
    profileId: { globalValue: 'development-profile' },
    serverCommand: { globalValue: '/opt/curator/bin/curatormd-v2-mcp' },
    hermesCommand: { globalValue: '/opt/hermes/bin/hermes' },
    reviewCommand: { globalValue: '/opt/curator/bin/curatormd-v2-review' },
  };
  const config = { inspect: (name) => settings[name] };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand']),
    false,
  );
  settings.databasePath.workspaceValue = '/tmp/attacker.sqlite3';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'hermesCommand']),
    true,
  );
  delete settings.databasePath.workspaceValue;
  settings.reviewCommand.workspaceFolderValue = '/tmp/attacker-review';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand']),
    true,
  );
});

test('dashboard explains a missing consumer project config before starting the launcher', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-unconfigured-'));
  const errors = [];
  const items = [];
  const commands = [];
  try {
    vscodeMock.StatusBarAlignment = { Left: 1 };
    vscodeMock.workspace = {
      workspaceFolders: [{ uri: { fsPath: projectRoot } }],
      getConfiguration: assert.fail,
    };
    vscodeMock.window = {
      createStatusBarItem: () => {
        const item = { show() {}, dispose() {} };
        items.push(item);
        return item;
      },
      showWarningMessage: assert.fail,
      showErrorMessage: (message) => errors.push(message),
    };
    vscodeMock.commands = {
      registerCommand: (name, handler) => {
        const command = { name, handler, dispose() {} };
        commands.push(command);
        return command;
      },
    };
    activate({ subscriptions: { push() {} } });

    await showDashboard(() => assert.fail('launcher must not start without project config'));

    assert.deepEqual(errors, [
      'This folder has no .curatormd-v2.toml. Open a configured Curator V2 consumer project with an active local read grant.',
    ]);
    assert.equal(items[0].color, '#888888');
    assert.equal(items[0].text, '$(circle-filled) CuratorMD V2');
  } finally {
    deactivate();
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
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
  const valid = { project_id: 'alpha', candidates: [{
    candidate: {
      candidate_id: 'candidate-1', goal_id: 'goal-1', status: 'pending_review',
      materiality: 'decision', rationale: 'Reviewed project decision.',
    },
    goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal' },
    facts: [{ bullet: 'PRIVATE_FACT' }],
    receipt: { receipt_id: 'PRIVATE_RECEIPT' },
  }] };
  const compact = validateReviewQueue(valid, 'alpha');
  assert.equal(compact.length, 1);
  assert.deepEqual(Object.keys(compact[0]), ['candidate', 'goal']);
  assert.equal(validateReviewQueue(valid, 'other'), null);
  assert.equal(validateReviewQueue({ project_id: 'alpha', candidates: [{ candidate: valid.candidates[0].candidate }] }, 'alpha'), null);
});

test('dashboard opens a panel, reads goal and report pages, and clears on disposal', async () => {
  const messages = [];
  let receiveMessage;
  let disposePanel;
  let processCount = 0;
  const processes = [];
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
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

  await showDashboard((command) => {
    if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
    const current = processCount++;
    const child = new FakeMcpProcess(
      current >= 3 ? 'b'.repeat(64) : 'a'.repeat(64),
      current === 4,
      null,
      'fact-1',
    );
    processes.push(child);
    return child;
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
  assert.doesNotMatch(JSON.stringify(goals.reviews), /PRIVATE_REVIEW_(?:FACT|RECEIPT)_CANARY/);
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
  await receiveMessage({
    type: 'loadEvidence', goalId: 'goal-1', factId: 'fact-1',
    reportRevision: 'a'.repeat(64), factOffset: 0,
  });
  const evidence = messages.find((message) => message.type === 'evidence');
  assert.equal(evidence.evidence.project_id, 'alpha');
  assert.equal(evidence.evidence.fact_id, 'fact-1');
  assert.equal(evidence.evidence.report_revision, report.reportRevision);
  assert.match(evidence.evidence.evidence[0].locator, /^git-test:/);
  const evidenceRequest = processes[2].requests.find(
    (request) => request.params?.name === 'goal_fact_evidence',
  );
  assert.equal(evidenceRequest.params.arguments.goal_id, 'goal-1');
  assert.equal(evidenceRequest.params.arguments.fact_id, 'fact-1');
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });
  assert.ok(messages.some((message) => message.type === 'reportStale'));
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });
  assert.equal(
    messages.filter((message) => message.type === 'error').at(-1).message,
    'Curator V2 denied this read. Check the configured project and its active local read grant.',
  );
  disposePanel();
});

test('dashboard rejects goal reports without a valid snapshot revision', async () => {
  const messages = [];
  let receiveMessage;
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
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

  await showDashboard((command) => command === 'fixture-hermes'
    ? new FakeHermesProcess(healthyHermesProbe())
    : new FakeMcpProcess('invalid-revision'));
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 0 });

  assert.equal(messages.filter((message) => message.type === 'report').length, 0);
  assert.equal(messages.at(-1).type, 'error');
  assert.equal(messages.at(-1).message, 'Curator V2 returned an invalid response. Check the installed launcher and backend.');
});

test('dashboard refuses a later fact page before a first-page snapshot exists', async () => {
  const messages = [];
  let receiveMessage;
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
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

  await showDashboard((command) => command === 'fixture-hermes'
    ? new FakeHermesProcess(healthyHermesProbe())
    : new FakeMcpProcess());
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  await receiveMessage({ type: 'loadReport', goalId: 'goal-1', factOffset: 16 });

  assert.equal(messages.filter((message) => message.type === 'report').length, 0);
  assert.equal(messages.at(-1).type, 'reportStale');
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
  goalStatesSummary: 'Goal states: planned 0, active 1, complete 0, open 0, blocked 0, deferred 0, cancelled 0, superseded 0.',
  queueSummary: 'Events received 1, failed 0, quarantined 0, active claims 0, expired claims 0; oldest pending age none. Reviews pending 1; purge pending 0 receipts / 0 artifacts; expiry pending 0 receipts / 0 artifacts.',
  storage: storageSnapshot } });
  assert.match(elements.get('health').textContent, /Project health: healthy\. Open gates: none reported\./);
  assert.equal(elements.get('goalStates').textContent, 'Goal states: planned 0, active 1, complete 0, open 0, blocked 0, deferred 0, cancelled 0, superseded 0.');
  assert.equal(elements.get('queues').textContent, 'Events received 1, failed 0, quarantined 0, active claims 0, expired claims 0; oldest pending age none. Reviews pending 1; purge pending 0 receipts / 0 artifacts; expiry pending 0 receipts / 0 artifacts.');
  assert.match(elements.get('activity').textContent, /Retained receipts: 3 \(processed 2, received 1, failed 0, quarantined 0\); goals 1; facts 2; SDE candidates pending 1, approved 0, rejected 0\./);
  assert.match(elements.get('storage').textContent, /Project logical records 4\.0 KiB; retained event payload 256 B; facts 2\/10000 \(512 B\/16\.0 MiB\)\. Shared SQLite files: database 8\.0 KiB, WAL 1\.0 KiB, combined 9\.0 KiB \/ 250\.0 MiB warning-only threshold; below threshold\. SQLite manages WAL checkpointing; writes remain allowed\. Staging 128 B \/ 250\.0 MiB warning-only threshold; below warning level, and writes remain allowed\. Model\/token usage is not reported here\./);
  const sqliteAtThreshold = {
    ...storageSnapshot,
    global_database_bytes: 262144000,
    global_wal_bytes: 0,
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: sqliteAtThreshold } });
  assert.match(elements.get('storage').textContent, /combined 250\.0 MiB \/ 250\.0 MiB warning-only threshold; below threshold/);
  const sqliteAboveThreshold = {
    ...storageSnapshot,
    global_database_bytes: 262144001,
    global_wal_bytes: 0,
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: sqliteAboveThreshold } });
  assert.match(elements.get('storage').textContent, /combined 250\.0 MiB \/ 250\.0 MiB warning-only threshold; warning: combined SQLite size is above threshold\. SQLite manages WAL checkpointing; writes remain allowed/);
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
    hermesCommand: 'fixture-hermes',
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

  await showDashboard((command) => command === 'fixture-hermes'
    ? new FakeHermesProcess(healthyHermesProbe(), 1)
    : new FakeMcpProcess(
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
