'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const Module = require('node:module');
const os = require('node:os');
const path = require('node:path');
const extensionManifest = require('./package.json');
const { version: extensionVersion } = extensionManifest;
const { PassThrough, Writable } = require('node:stream');
const test = require('node:test');
const vm = require('node:vm');

function assertTooltipIncludesCurrentVersion(item) {
  assert.ok(item.tooltip.includes(`CuratorMD V2 ${extensionVersion}.`));
}

const vscodeMock = {
  ThemeColor: class ThemeColor {
    constructor(id) { this.id = id; }
  },
};
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
  parseCuratorQueueSnapshot,
  readHermesHealthProbe,
  readProjectFeeds,
  readConfiguredProjectId,
  resolveDatabasePath,
  resolveEvidenceConfig,
  resolveHermesProfileId,
  hasWorkspaceSettingOverride,
  hostEvidenceConfigArguments,
  quotePosixShellArgument,
  activate,
  deactivate,
  dashboardErrorMessage,
  factEvidenceDisplayStatus,
  initializeWorkspaceAreas,
  summarizeGoalStates,
  summarizeEventFailureCategories,
  summarizeOperationalAlerts,
  summarizeOperationalQueues,
  queueMetricRows,
  queuePanelState,
  showDashboard,
  statusColorMeaning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  validateReviewQueue,
  writePendingReviewDocument,
  writeWorkspaceQueueViews,
} = require('./extension');
Module._load = originalLoad;

function healthyCuratorQueueSnapshot(projectId = 'alpha', overrides = {}) {
  return {
    project_id: projectId,
    observed_at: new Date().toISOString(),
    database_observed_at: new Date().toISOString(),
    database_observation_complete: true,
    status: 'unknown',
    gate_codes: ['dependency_unknown:event_router'],
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
    ...overrides,
  };
}

class FakeMcpProcess extends EventEmitter {
  constructor(
    reportRevision = 'a'.repeat(64), denyToolCall = false,
    denyToolName = null, reportFactId = null, emptyReviewQueue = false,
    seenGoalEvents = new Set(), goalState = null, queueSnapshot = null,
  ) {
    super();
    this.requests = [];
    this.denyToolCall = denyToolCall;
    this.denyToolName = denyToolName;
    this.reportRevision = reportRevision;
    this.reportFactId = reportFactId;
    this.emptyReviewQueue = emptyReviewQueue;
    this.seenGoalEvents = seenGoalEvents;
    this.goalState = goalState || { status: 'active', lifecycle_revision: 1 };
    this.queueSnapshot = queueSnapshot || healthyCuratorQueueSnapshot();
    this.startedGoal = null;
    this.startedReceiptStatus = null;
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
            result = { isError: true, content: [{ type: 'text', text: JSON.stringify({
              schema_version: 1,
              code: 'forbidden',
              message: 'The caller is not allowed to perform this operation.',
            }) }] };
          } else if (request.params.name === 'project_queue_snapshot') {
            result = { content: [{ type: 'text', text: JSON.stringify(this.queueSnapshot) }] };
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
          } else if (request.params.name === 'event_queue_status') {
            result = { content: [{ type: 'text', text: JSON.stringify({
              received_count: 0, failed_count: 0, quarantined_count: 0,
              oldest_pending_received_at: null, oldest_pending_age_seconds: null,
              claimed_count: 0, expired_claim_count: 0,
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
              goals: [{
                goal_id: 'goal-1', status: this.goalState.status,
                lifecycle_revision: this.goalState.lifecycle_revision,
                problem: 'Smoke goal',
              }],
              next_offset: null,
            }) }] };
          } else if (request.params.name === 'goal_reopen') {
            this.goalState.status = 'active';
            this.goalState.lifecycle_revision += 1;
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha', event_id: request.params.arguments.event_id,
              status: 'processed',
            }) }] };
          } else if (request.params.name === 'goal_start') {
            this.startedGoal = request.params.arguments;
            this.startedReceiptStatus = this.seenGoalEvents.has(this.startedGoal.event_id)
              ? 'duplicate' : 'processed';
            this.seenGoalEvents.add(this.startedGoal.event_id);
            result = { content: [{ type: 'text', text: JSON.stringify({
              project_id: 'alpha',
              event_id: this.startedGoal.event_id,
              status: this.startedReceiptStatus,
            }) }] };
          } else if (request.params.name === 'goal_status' && this.startedGoal) {
            result = { content: [{ type: 'text', text: JSON.stringify({
              goal: {
                goal_id: this.startedGoal.goal_id,
                project_id: 'alpha',
                problem: this.startedGoal.problem,
                success_criteria: this.startedGoal.success_criteria,
              },
              criteria: [],
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
            if (this.startedGoal && request.params.arguments.goal_id === this.startedGoal.goal_id) {
              result = { content: [{ type: 'text', text: `# Goal \`${this.startedGoal.goal_id}\`\n## Success criteria` }] };
              queueMicrotask(() => this.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id: request.id, result })}\n`));
              callback();
              return;
            }
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

class DeferredHermesProcess extends EventEmitter {
  constructor() {
    super();
    this.stdout = new PassThrough();
  }

  respond(payload) {
    this.stdout.end(JSON.stringify(payload), () => this.emit('close', 0, null));
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
      observed_at: new Date().toISOString(),
      gate_codes: [],
      database_observation_complete: true,
      dependencies: names.map((name) => ({
        name, status: 'healthy', observed_at: new Date().toISOString(), age_seconds: 0,
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
  const staleAge = healthyHermesProbe();
  staleAge.health.dependencies[0].age_seconds = 61;
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(staleAge), 'alpha'),
    (error) => error.code === 'hermes-probe-stale',
  );
  const staleTimestamp = healthyHermesProbe();
  staleTimestamp.health.dependencies[0].observed_at = new Date(Date.now() - 66_000).toISOString();
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(staleTimestamp), 'alpha'),
    (error) => error.code === 'hermes-probe-stale',
  );
  const staleHealth = healthyHermesProbe();
  staleHealth.health.observed_at = new Date(Date.now() - 66_000).toISOString();
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(staleHealth), 'alpha'),
    (error) => error.code === 'hermes-probe-stale',
  );
  const futureHealth = healthyHermesProbe();
  futureHealth.health.observed_at = new Date(Date.now() + 6_000).toISOString();
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(futureHealth), 'alpha'),
    (error) => error.code === 'hermes-probe-stale',
  );
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(payload), 'other'),
    (error) => error.code === 'hermes-probe-project-mismatch',
  );
  const incomplete = healthyHermesProbe();
  incomplete.health.dependencies.pop();
  assert.throws(
    () => parseHermesHealthProbe(JSON.stringify(incomplete), 'alpha'),
    (error) => error.code === 'hermes-probe-invalid',
  );

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

test('Curator queue snapshot is project-bound and independent from host readiness status', () => {
  const snapshot = healthyCuratorQueueSnapshot();
  const parsed = parseCuratorQueueSnapshot(JSON.stringify(snapshot), 'alpha');
  assert.equal(parsed.status, 'unknown');
  assert.equal(queuePanelState(parsed, 'alpha'), 'healthy');
  assert.match(summarizeOperationalQueues(parsed, 'alpha'), /Reviews pending 0/);
  assert.throws(
    () => parseCuratorQueueSnapshot(JSON.stringify(snapshot), 'another-project'),
    (error) => error.code === 'curator-queue-project-mismatch',
  );
  assert.throws(
    () => parseCuratorQueueSnapshot(JSON.stringify({ ...snapshot, observed_at: new Date(Date.now() - 70000).toISOString() }), 'alpha'),
    (error) => error.code === 'curator-queue-stale',
  );
  assert.throws(
    () => parseCuratorQueueSnapshot(JSON.stringify({ ...snapshot, database_observed_at: new Date(Date.now() - 70000).toISOString() }), 'alpha'),
    (error) => error.code === 'curator-queue-stale',
  );
  assert.throws(
    () => parseCuratorQueueSnapshot(JSON.stringify({ ...snapshot, database_observation_complete: false }), 'alpha'),
    (error) => error.code === 'curator-queue-invalid',
  );
  assert.throws(
    () => parseCuratorQueueSnapshot(JSON.stringify({ ...snapshot, database_observed_at: '2026-10-30T10:00:00' }), 'alpha'),
    (error) => error.code === 'curator-queue-invalid',
  );
  const partial = parseCuratorQueueSnapshot(JSON.stringify({ ...snapshot, event_failed_count: null }), 'alpha');
  assert.equal(queuePanelState(partial, 'alpha'), 'unknown');
  assert.equal(queueMetricRows(partial, 'alpha').find((row) => row.label === 'Events failed').value, 'unknown');
});

test('project feeds keep queue data when Hermes readiness fails', async () => {
  const feeds = await readProjectFeeds({
    client: { callTool: async () => JSON.stringify(healthyCuratorQueueSnapshot()) },
    projectRoot: '/tmp/curator-independent-health',
    databasePath: '/tmp/curator-independent-health.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-curator',
    hermesCommand: 'fixture-hermes',
    projectId: 'alpha',
    spawnProcess: () => new FakeHermesProcess(healthyHermesProbe(), 1),
  });
  assert.equal(feeds.health, null);
  assert.equal(feeds.healthProbeError, 'hermes-probe-exit');
  assert.equal(feeds.queueProbeError, null);
  assert.equal(queuePanelState(feeds.queueSnapshot, 'alpha'), 'healthy');
});

test('Hermes profiles are selected by exact Curator project binding', async () => {
  const bindings = {
    alpha: 'alpha-hermes',
    'vhost-manager-alpha': 'renew-ssl-coding',
  };
  assert.equal(resolveHermesProfileId('alpha', bindings), 'alpha-hermes');
  assert.equal(resolveHermesProfileId('vhost-manager-alpha', bindings), 'renew-ssl-coding');
  assert.equal(resolveHermesProfileId('unbound-project', bindings), null);
  assert.equal(resolveHermesProfileId('alpha', { alpha: '../wrong-profile' }), null);

  const feeds = await readProjectFeeds({
    client: { callTool: async () => JSON.stringify(healthyCuratorQueueSnapshot()) },
    projectRoot: '/tmp/curator-unbound-hermes-profile',
    databasePath: '/tmp/curator-unbound-hermes-profile.sqlite3',
    profileId: 'curator-routing-label',
    hermesProfileId: resolveHermesProfileId('alpha', {}),
    serverCommand: 'fixture-curator',
    hermesCommand: 'fixture-hermes',
    projectId: 'alpha',
  });
  assert.equal(feeds.health, null);
  assert.equal(feeds.healthProbeError, 'hermes-probe-profile-binding');
  assert.equal(feeds.queueProbeError, null);
  assert.equal(queuePanelState(feeds.queueSnapshot, 'alpha'), 'healthy');
});

test('project feeds keep Hermes readiness when the Curator queue read fails', async () => {
  const feeds = await readProjectFeeds({
    client: { callTool: async () => { throw new Error('fixture queue failure'); } },
    projectRoot: '/tmp/curator-independent-queue',
    databasePath: '/tmp/curator-independent-queue.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-curator',
    hermesCommand: 'fixture-hermes',
    projectId: 'alpha',
    spawnProcess: () => new FakeHermesProcess(healthyHermesProbe()),
  });
  assert.equal(feeds.health.status, 'healthy');
  assert.equal(feeds.healthProbeError, null);
  assert.equal(feeds.queueSnapshot, null);
  assert.equal(feeds.queueProbeError, 'curator-queue-read');
  assert.equal(queuePanelState(feeds.queueSnapshot, 'alpha'), 'unknown');
});

test('project feed reads coalesce overlapping refreshes', async () => {
  let resolveQueue;
  let queueCalls = 0;
  let hermesCalls = 0;
  const client = { callTool: () => {
    queueCalls += 1;
    return new Promise((resolve) => { resolveQueue = resolve; });
  } };
  const options = {
    client,
    projectRoot: '/tmp/curator-coalesced-refresh',
    databasePath: '/tmp/curator-coalesced-refresh.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-curator',
    hermesCommand: 'fixture-hermes',
    projectId: 'alpha',
    spawnProcess: () => {
      hermesCalls += 1;
      return new FakeHermesProcess(healthyHermesProbe());
    },
  };
  const first = readProjectFeeds(options);
  const second = readProjectFeeds(options);
  assert.strictEqual(second, first);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(queueCalls, 1);
  assert.equal(hermesCalls, 1);
  resolveQueue(JSON.stringify(healthyCuratorQueueSnapshot()));
  const result = await first;
  assert.equal(result.queueProbeError, null);
  assert.equal(result.healthProbeError, null);
});

test('three identical automatic feed failures pause until a manual refresh', async () => {
  let queueCalls = 0;
  let hermesCalls = 0;
  let failQueue = true;
  const client = { callTool: async () => {
    queueCalls += 1;
    if (failQueue) throw new Error('fixture queue failure');
    return JSON.stringify(healthyCuratorQueueSnapshot());
  } };
  const options = {
    client,
    projectRoot: '/tmp/curator-paused-refresh',
    databasePath: '/tmp/curator-paused-refresh.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-curator',
    hermesCommand: 'fixture-hermes',
    projectId: 'alpha',
    spawnProcess: () => {
      hermesCalls += 1;
      return new FakeHermesProcess(healthyHermesProbe());
    },
  };
  const attempts = [];
  for (let index = 0; index < 3; index += 1) {
    attempts.push(await readProjectFeeds(options));
  }
  assert.deepEqual(attempts.map((result) => result.queueAutoPaused), [false, false, true]);
  const paused = await readProjectFeeds(options);
  assert.equal(paused.queueProbeError, 'feed-auto-paused');
  assert.equal(paused.queueLastFailureCode, 'curator-queue-read');
  assert.equal(paused.queueAutoPaused, true);
  assert.equal(queueCalls, 3);
  assert.equal(hermesCalls, 4);
  failQueue = false;
  const recovered = await readProjectFeeds({ ...options, trigger: 'manual' });
  assert.equal(recovered.queueProbeError, null);
  assert.equal(recovered.queueLastFailureCode, null);
  assert.equal(recovered.queueAutoPaused, false);
  assert.equal(queueCalls, 4);
  assert.equal(hermesCalls, 5);
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

test('MCP tool failures do not label rejected writes as denied reads', async () => {
  const child = new FakeMcpProcess(undefined, false, 'fact_record');
  const client = new McpStdioClient('fixture', [], '/tmp', 'fixture-profile', () => child);
  try {
    await client.initialize();
    await assert.rejects(client.callTool('fact_record', { fact_id: 'fact-1' }), (error) => {
      assert.equal(error.code, 'mcp-tool-error');
      assert.match(error.message, /rejected the requested operation/);
      assert.equal(error.reasonCode, 'forbidden');
      assert.doesNotMatch(error.message, /permission denied/);
      assert.doesNotMatch(error.message, /caller is not allowed/);
      return true;
    });
  } finally {
    client.close();
  }
});

test('dashboard renders bounded pages as text and never joins prior pages', () => {
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  assert.match(html, /default-src 'none'/);
  assert.match(html, /Facts .* of /);
  assert.match(html, /previous page was cleared/);
  assert.match(html, /reportStale/);
  assert.match(html, /Restarting from the first page/);
  assert.match(html, /function requestGoals\(offset, manualRefresh = false\)/);
  assert.match(html, /api\.postMessage\(\{ type: 'loadGoals', offset, manualRefresh \}\)/);
  assert.match(html, /addEventListener\('click', \(\) => requestGoals\(0, true\)\)/);
  assert.match(html, /requestGoals\(0, true\);\s*if \(false\)/);
  assert.match(html, /reportRevision\.slice\(0, 12\)/);
  assert.match(html, /report\.textContent = message\.report/);
  assert.match(html, /Pending SDE review/);
  assert.ok(html.indexOf('id="reviewsSection"') < html.indexOf('id="goalControls"'));
  assert.match(html, /<details class="dashboard" open>/);
  assert.match(html, /class="dashboard-grid"/);
  assert.match(html, /class="dashboard-card" data-state="unknown"/);
  assert.match(html, /\.dashboard-card\[data-state="unknown"\] \{ border-top: 3px solid #fce94f; \}/);
  assert.match(html, /\.metric-table \[data-state="unknown"\] \{ color: #fce94f; \}/);
  assert.match(html, /\.metric-table tr\[data-state="unknown"\] td \{ color: #fce94f; \}/);
  assert.match(html, /\.metric-table th:first-child, \.metric-table td:first-child \{ width: 28%; \}/);
  assert.match(html, /\.metric-table th:nth-child\(2\), \.metric-table td:nth-child\(2\) \{ width: 42%; \}/);
  assert.match(html, /overflow-wrap: normal; word-break: normal/);
  assert.match(html, /\.metric-table td:nth-child\(2\) \{ overflow-wrap: anywhere; \}/);
  assert.match(html, /@media \(max-width: 620px\)/);
  assert.match(html, /\.metric-table th:last-child, \.metric-table td:last-child \{ width: 30%; min-width: 5\.25rem; \}/);
  assert.match(html, /container: dashboard-card \/ inline-size/);
  assert.match(html, /@container dashboard-card \(max-width: 32rem\)/);
  assert.match(html, /\.metric-table td:last-child \{ white-space: nowrap; \}/);
  assert.match(html, /content: 'Value: '/);
  assert.match(html, /content: 'State: '/);
  assert.match(html, /row\.setAttribute\('data-state', item\.state\)/);
  assert.match(html, /<table class="metric-table"><thead><tr><th scope="col">Metric<\/th><th scope="col">Value<\/th><th scope="col">State<\/th><\/tr>/);
  assert.match(html, /<th scope="col">Queue<\/th><th scope="col">Count<\/th><th scope="col">State<\/th>/);
  assert.match(html, /font-weight: 700/);
  assert.match(html, /font-size: 1rem/);
  assert.match(html, /\.goal-disposition .*font-size: 1rem/);
  assert.match(html, /min\(100%, 360px\)/);
  assert.match(html, /--vscode-textLink-foreground/);
  assert.match(html, /data-state="degraded"/);
  assert.match(html, /data-state="review"/);
  assert.match(html, /state\.textContent = 'Disposition: ' \+ goal\.status/);
  assert.match(html, /timeZone: 'Asia\/Ho_Chi_Minh'/);
  assert.match(html, /formatGoalUpdate\(goal\.updated_at\)/);
  assert.match(html, /nextAction\.textContent = 'Next: ' \+ goal\.next_action/);
  assert.match(html, /Scheduled ACME renewal operation/);
  assert.match(html, /goal\.problem/);
  assert.match(html, /Reopen completed task/);
  assert.match(html, /type: 'reopenGoal'/);
  assert.match(html, /Review in terminal/);
  assert.match(html, /label\.textContent = candidate\.materiality/);
  assert.match(html, /Evidence references/);
  assert.match(html, /type: 'loadEvidence'/);
  assert.match(html, /reference\.locator/);
  assert.match(html, /paragraph\.textContent = fields\.filter\(Boolean\)\.join/);
  assert.doesNotMatch(html, /report\.innerHTML/);
  assert.doesNotMatch(html, /reviews\.innerHTML/);
});

test('dashboard reopens only a completed goal after attended confirmation and uses a write-scoped launcher', async () => {
  const messages = [];
  let receiveMessage;
  const goalState = { status: 'complete', lifecycle_revision: 4 };
  const inputValues = ['Reason for new evidence.', 'Run the fresh checks.'];
  const launched = [];
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
    showInputBox: async () => inputValues.shift(),
    showWarningMessage: async (_message, _options, choice) => choice,
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

  await showDashboard((command, args) => {
    if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
    const child = new FakeMcpProcess(
      'a'.repeat(64), false, null, null, true, new Set(), goalState,
    );
    launched.push({ args, child });
    return child;
  });
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  await receiveMessage({ type: 'reopenGoal', goalId: 'goal-1' });

  const mutationLaunch = launched.find(({ child }) => child.requests.some(
    (request) => request.params?.name === 'goal_reopen',
  ));
  assert.ok(mutationLaunch);
  assert.ok(mutationLaunch.args.includes('--allow-write'));
  const request = mutationLaunch.child.requests.find(
    (item) => item.params?.name === 'goal_reopen',
  );
  assert.deepEqual(request.params.arguments, {
    event_id: request.params.arguments.event_id,
    goal_id: 'goal-1',
    reason: 'Reason for new evidence.',
    next_action: 'Run the fresh checks.',
    expected_lifecycle_revision: 4,
  });
  assert.match(request.params.arguments.event_id, /^[0-9a-f]{32}$/);
  assert.equal(goalState.status, 'active');
  assert.equal(goalState.lifecycle_revision, 5);
  assert.ok(messages.some((message) => message.type === 'goalReopened'));
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
  assert.equal(items[0].color.id, 'textLink.foreground');
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.match(items[0].tooltip, /Blue means no health read has been attempted/);
  assert.equal(commands[0].name, 'curatormdV2.openDashboard');
  assert.equal(commands.length, 2);
  assert.equal(subscriptions.length, 4);

  assert.equal(updateStatusBarHealth({ project_id: 'alpha', status: 'healthy' }, 'alpha', []), 'healthy');
  assert.equal(items[0].color, '#73d216');
  assert.match(items[0].tooltip, /Project health: healthy/);
  assert.match(items[0].tooltip, /no SDE reviews pending/);
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.match(items[0].tooltip, /Green means project health is healthy/);
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', [], {
      project_id: 'alpha', global_database_bytes: 200 * 1024 * 1024,
      global_wal_bytes: 50 * 1024 * 1024,
    },
  ), 'healthy');
  assert.equal(items[0].text, '$(circle-filled) CuratorMD V2: healthy');
  const sqliteWarningStorage = {
    project_id: 'alpha', global_database_bytes: 200 * 1024 * 1024,
    global_wal_bytes: 50 * 1024 * 1024 + 1,
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
  assert.equal(items[0].color, '#4daafc');
  assert.equal(items[0].text, '$(checklist) CuratorMD V2: 1 review');
  assert.equal(items[0].command, 'curatormdV2.openPendingReview');
  assert.match(items[0].tooltip, /Blue means SDE reviews are outstanding/);
  assert.match(items[0].tooltip, /Project health: healthy/);
  assert.match(items[0].tooltip, /1 pending SDE review/);
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'degraded', gate_codes: ['review_backlog'],
  }, 'alpha', [pendingReview]), 'healthy');
  assert.equal(items[0].color, '#4daafc');
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'degraded',
    gate_codes: ['review_backlog', 'event_failures'],
  }, 'alpha', [pendingReview]), 'degraded');
  assert.equal(items[0].color, '#4daafc');
  assert.match(items[0].tooltip, /Blue means SDE reviews are outstanding/);
  assert.match(items[0].tooltip, /Project health: degraded/);
  assert.equal(updateStatusBarHealth(
    { project_id: 'alpha', status: 'healthy' }, 'alpha', null,
  ), 'unknown');
  assert.equal(items[0].color, '#fce94f');
  assert.equal(items[0].command, 'curatormdV2.openDashboard');
  assert.match(items[0].tooltip, /pending SDE review count unavailable/);
  assert.match(items[0].tooltip, /Yellow means the health or SDE review count is unknown/);
  assert.equal(updateStatusBarHealth({
    project_id: 'alpha', status: 'unknown',
    gate_codes: ['missing_host_probe', 'not a gate', 'database_observation_failed'],
  }, 'alpha', []), 'unknown');
  assert.equal(items[0].color, '#fce94f');
  assert.match(items[0].tooltip, /Project health: unknown/);
  assert.match(items[0].tooltip, /Additional health gate: missing host probe/);
  assert.match(items[0].tooltip, /Additional health gate: database observation failed/);
  assert.doesNotMatch(items[0].tooltip, /not a gate/);
  updateStatusBarHealth({
    project_id: 'alpha', status: 'degraded',
    gate_codes: ['dependency_unknown:event_router', 'dependency_unavailable:purge_scheduler'],
  }, 'alpha', []);
  assert.match(items[0].tooltip, /No fresh result is available for work-event routing\./);
  assert.match(items[0].tooltip, /The six-hour cleanup timer check is currently unavailable\./);
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.equal(updateStatusBarHealth(
    { project_id: 'other', status: 'healthy', gate_codes: ['private_gate'] }, 'alpha', [],
  ), 'unknown');
  assert.doesNotMatch(items[0].tooltip, /private_gate/);
  const privateError = Object.assign(new Error('/private/path and secret text'), {
    code: 'launcher-start',
  });
  assert.equal(updateStatusBarHealth(null, null, null, null, privateError), 'unknown');
  assert.match(items[0].tooltip, /check the Curator launcher in VS Code User settings/);
  assert.doesNotMatch(items[0].tooltip, /private\/path|secret text/);
  updateStatusBarHealth(null, null, null, null, { code: 'toString' });
  assert.match(items[0].tooltip, /The local health read failed; open the dashboard for details/);
  assert.doesNotMatch(items[0].tooltip, /function toString/);
  assert.equal(statusColorMeaning('unknown'), 'Yellow means the health or SDE review count is unknown.');

  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-status-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
    evidenceConfig: '/home/eaglesvn/.local/state/curator/evidence.json',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  try {
    let statusMcpArgs;
    const status = await refreshStatusBarHealthFromWorkspace((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      statusMcpArgs = args;
      return new FakeMcpProcess('a'.repeat(64), false, null, null, true);
    });
    assert.equal(status, 'healthy');
    assert.ok(statusMcpArgs.includes('--evidence-config'));
    assert.equal(
      statusMcpArgs[statusMcpArgs.indexOf('--evidence-config') + 1],
      '/home/eaglesvn/.local/state/curator/evidence.json',
    );
    assert.equal(items[0].color, '#73d216');
    assert.match(items[0].tooltip, /Project health: healthy/);
    assert.match(items[0].tooltip, /no SDE reviews pending/);
    const pendingReview = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
    let openedPath;
    let shownDocument;
    vscodeMock.Uri = { file: (filePath) => ({ fsPath: filePath }) };
    vscodeMock.workspace.openTextDocument = async (uri) => {
      openedPath = uri.fsPath;
      return { uri };
    };
    vscodeMock.window.showTextDocument = async (document) => { shownDocument = document; };
    await commands[1].handler();
    assert.equal(openedPath, pendingReview);
    assert.equal(shownDocument.uri.fsPath, pendingReview);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
  deactivate();
});

test('late status refresh cannot overwrite a newer workspace result', async () => {
  const roots = [0, 1].map(() => fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-status-race-')));
  roots.forEach((root) => fs.writeFileSync(path.join(root, '.curatormd-v2.toml'), 'project_id = "alpha"\n'));
  const items = [];
  vscodeMock.StatusBarAlignment = { Left: 1, Right: 2 };
  vscodeMock.window = {
    createStatusBarItem: (alignment, priority) => {
      const item = { alignment, priority, show() {}, dispose() {} };
      items.push(item);
      return item;
    },
  };
  vscodeMock.commands = { registerCommand: () => ({ dispose() {} }) };
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
  };
  vscodeMock.workspace = {
    workspaceFolders: [],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  const subscriptions = [];
  activate({ subscriptions: { push: (...values) => subscriptions.push(...values) } });
  try {
    let delayedHermes;
    vscodeMock.workspace.workspaceFolders = [{ uri: { fsPath: roots[0] } }];
    const oldRefresh = refreshStatusBarHealthFromWorkspace((command) => {
      if (command === 'fixture-hermes') {
        delayedHermes = new DeferredHermesProcess();
        return delayedHermes;
      }
      return new FakeMcpProcess('a'.repeat(64), false, null, null, true);
    });
    await new Promise((resolve) => setImmediate(resolve));
    assert.ok(delayedHermes);

    vscodeMock.workspace.workspaceFolders = [{ uri: { fsPath: roots[1] } }];
    const degradedHealth = healthyHermesProbe();
    degradedHealth.health.status = 'degraded';
    degradedHealth.health.gate_codes = ['database_unavailable'];
    const newStatus = await refreshStatusBarHealthFromWorkspace((command) => (
      command === 'fixture-hermes'
        ? new FakeHermesProcess(degradedHealth)
        : new FakeMcpProcess('a'.repeat(64), false, null, null, true)
    ));
    assert.equal(newStatus, 'degraded');
    assert.equal(items[0].color, '#ef2929');

    delayedHermes.respond(healthyHermesProbe());
    assert.equal(await oldRefresh, 'unknown');
    assert.equal(items[0].color, '#ef2929');
    assert.match(items[0].tooltip, /Project health: degraded/);
  } finally {
    deactivate();
    roots.forEach((root) => fs.rmSync(root, { recursive: true, force: true }));
  }
});

test('status refreshes after Curator settings changes and window focus returns', () => {
  let onConfigurationChange;
  let onWindowStateChange;
  const items = [];
  vscodeMock.StatusBarAlignment = { Left: 1, Right: 2 };
  vscodeMock.window = {
    createStatusBarItem: () => {
      const item = { show() {}, dispose() {} };
      items.push(item);
      return item;
    },
    onDidChangeWindowState: (listener) => {
      onWindowStateChange = listener;
      return { dispose() {} };
    },
  };
  vscodeMock.commands = { registerCommand: () => ({ dispose() {} }) };
  vscodeMock.workspace = {
    workspaceFolders: [],
    getConfiguration: () => ({ get: (_key, fallback) => fallback, inspect: () => ({}) }),
    onDidChangeConfiguration: (listener) => {
      onConfigurationChange = listener;
      return { dispose() {} };
    },
  };
  const subscriptions = [];
  activate({ subscriptions: { push: (...values) => subscriptions.push(...values) } });
  try {
    assert.equal(typeof onConfigurationChange, 'function');
    assert.equal(typeof onWindowStateChange, 'function');

    updateStatusBarHealth({ project_id: 'alpha', status: 'healthy' }, 'alpha', []);
    onConfigurationChange({ affectsConfiguration: (key) => key === 'curatormdV2' });
    assert.equal(items[0].color.id, 'textLink.foreground');

    updateStatusBarHealth({ project_id: 'alpha', status: 'healthy' }, 'alpha', []);
    onWindowStateChange({ focused: true });
    assert.equal(items[0].color.id, 'textLink.foreground');

    updateStatusBarHealth({ project_id: 'alpha', status: 'healthy' }, 'alpha', []);
    onConfigurationChange({ affectsConfiguration: () => false });
    assert.equal(items[0].color, '#73d216');
  } finally {
    deactivate();
  }
});

test('dashboard maps Curator failures to actionable messages without backend details', () => {
  assert.match(dashboardErrorMessage({ code: 'read-denied' }), /configured project and its active local read grant/);
  assert.match(dashboardErrorMessage({ code: 'mcp-tool-error', reasonCode: 'forbidden' }), /denied this request/);
  assert.doesNotMatch(dashboardErrorMessage({ code: 'mcp-tool-error', reasonCode: 'not-a-code' }), /not-a-code/);
  assert.match(dashboardErrorMessage({ code: 'launcher-start' }), /serverCommand and the installed launcher/);
  assert.match(dashboardErrorMessage({ code: 'timeout' }), /did not respond within 15 seconds/);
  assert.match(dashboardErrorMessage(new Error('/private/path/secret traceback')), /Curator read failed/);
  assert.doesNotMatch(dashboardErrorMessage(new Error('/private/path/secret traceback')), /private|secret/);
});

test('fact evidence status becomes stale when its proof expires, moves into the future, or stops matching', () => {
  const now = Date.parse('2026-10-30T06:00:00Z');
  const evidence = (overrides = {}) => ({
    project_id: 'alpha', goal_id: 'goal-1', fact_id: 'fact-1',
    fact_kind: 'verification', criterion_id: 'criterion-1',
    verification_status: 'verified_fact',
    evidence: [{
      outcome: 'passed',
      attestation: {
        observed_at: '2026-10-30T05:00:00Z',
        valid_until: '2026-10-30T07:00:00Z',
        revocation_checked_at: '2026-10-30T05:30:00Z',
      },
    }],
    ...overrides,
  });

  assert.equal(factEvidenceDisplayStatus(evidence(), now), 'verified_fact');
  assert.equal(factEvidenceDisplayStatus(evidence({
    evidence: [{
      outcome: 'passed', attestation: {
        observed_at: '2026-10-30T05:00:00Z',
        valid_until: '2026-10-30T05:59:59Z',
        revocation_checked_at: '2026-10-30T05:30:00Z',
      },
    }],
  }), now), 'stale/unknown');
  assert.equal(factEvidenceDisplayStatus(evidence({
    evidence: [{
      outcome: 'passed', attestation: {
        observed_at: '2026-10-30T06:00:01Z',
        valid_until: '2026-10-30T07:00:00Z',
        revocation_checked_at: '2026-10-30T06:00:02Z',
      },
    }],
  }), now), 'stale/unknown');
  assert.equal(factEvidenceDisplayStatus(evidence({
    verification_status: 'unverified_claim',
  }), now), 'stale/unknown');
  assert.equal(factEvidenceDisplayStatus(evidence({
    fact_kind: 'change', verification_status: 'recorded_fact', evidence: [],
  }), now), 'recorded_fact');
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
  assert.match(summary, /Readiness degraded: event_failures/);
  assert.doesNotMatch(summary, /Readiness degraded: .*review_backlog/);
  assert.match(summary, /2 event receipt\(s\) waiting to process/);
  assert.match(summary, /Event failures by category: evidence rejected 1, adapter errors 0, other 0/);
  assert.match(summary, /1 SDE review\(s\) need a human decision/);
  assert.match(summary, /Cleanup pending: 1 receipt\(s\), 2 artifact\(s\)/);
  assert.match(summary, /Staging reached 75%/);
  assert.match(summary, /writes remain allowed/);

  const incomplete = summarizeOperationalAlerts(
    { ...health, project_id: 'other' }, storage, metrics, 'alpha',
  );
  assert.match(incomplete, /Readiness unknown/);
  assert.match(incomplete, /Operational queues unknown/);
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

test('launcher, database, profile, and evidence settings reject workspace overrides', () => {
  const settings = {
    databasePath: { globalValue: '/home/user/curator.sqlite3' },
    databaseBindings: { globalValue: { alpha: '/home/user/alpha.sqlite3' } },
    evidenceConfigBindings: { globalValue: { alpha: '' } },
    profileId: { globalValue: 'development-profile' },
    serverCommand: { globalValue: '/opt/curator/bin/curatormd-v2-mcp' },
    hermesCommand: { globalValue: '/opt/hermes/bin/hermes' },
    reviewCommand: { globalValue: '/opt/curator/bin/curatormd-v2-review' },
    evidenceConfig: { globalValue: '/home/user/.local/state/curator/evidence.json' },
  };
  const config = { inspect: (name) => settings[name] };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'databaseBindings', 'evidenceConfigBindings', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand', 'evidenceConfig']),
    false,
  );
  settings.databasePath.workspaceValue = '/tmp/attacker.sqlite3';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'databaseBindings', 'evidenceConfigBindings', 'profileId', 'serverCommand', 'hermesCommand', 'evidenceConfig']),
    true,
  );
  delete settings.databasePath.workspaceValue;
  settings.databaseBindings.workspaceValue = { alpha: '/tmp/attacker.sqlite3' };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'databaseBindings', 'evidenceConfigBindings', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand', 'evidenceConfig']),
    true,
  );
  delete settings.databaseBindings.workspaceValue;
  settings.reviewCommand.workspaceFolderValue = '/tmp/attacker-review';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand', 'evidenceConfig']),
    true,
  );
  delete settings.reviewCommand.workspaceFolderValue;
  settings.evidenceConfig.workspaceValue = '/tmp/attacker-evidence.json';
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand', 'evidenceConfig']),
    true,
  );
  delete settings.evidenceConfig.workspaceValue;
  settings.evidenceConfigBindings.workspaceValue = { alpha: '/tmp/attacker-evidence.json' };
  assert.equal(
    hasWorkspaceSettingOverride(config, ['databasePath', 'databaseBindings', 'evidenceConfigBindings', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand', 'evidenceConfig']),
    true,
  );
});

test('workspace project IDs select exact database bindings and fail closed on invalid bindings', () => {
  const bindings = {
    alpha: '/state/alpha.sqlite3',
    beta: '/state/beta.sqlite3',
  };
  assert.equal(resolveDatabasePath('alpha', bindings, '/state/default.sqlite3'), '/state/alpha.sqlite3');
  assert.equal(resolveDatabasePath('missing', bindings, '/state/default.sqlite3'), '/state/default.sqlite3');
  assert.equal(resolveDatabasePath('alpha', { alpha: 'relative.sqlite3' }, '/state/default.sqlite3'), null);
  assert.equal(resolveDatabasePath('alpha', { alpha: null }, '/state/default.sqlite3'), null);
  assert.equal(resolveDatabasePath('../alpha', bindings, '/state/default.sqlite3'), null);
});

test('host evidence config binding can disable a project-incompatible fallback', () => {
  assert.equal(resolveEvidenceConfig(
    'alpha', { alpha: '' }, '/state/vhost-evidence.json',
  ), '');
  assert.equal(resolveEvidenceConfig(
    'beta', { alpha: '' }, '/state/vhost-evidence.json',
  ), '/state/vhost-evidence.json');
  assert.equal(resolveEvidenceConfig('alpha', { alpha: 'relative.json' }, ''), null);
  assert.equal(resolveEvidenceConfig('alpha', {}, ''), '');
});

test('project config reader accepts one bounded root project_id and rejects invalid files', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-project-config-'));
  try {
    const configPath = path.join(projectRoot, '.curatormd-v2.toml');
    fs.writeFileSync(configPath, '# V2 project\nproject_id = "alpha-dev:one" # exact binding\n\n[scope]\nread_paths = []\n');
    assert.equal(readConfiguredProjectId(projectRoot), 'alpha-dev:one');

    fs.writeFileSync(configPath, 'project_id = "alpha"\nproject_id = "beta"\n');
    assert.throws(() => readConfiguredProjectId(projectRoot), { code: 'status-project-invalid' });

    fs.writeFileSync(configPath, '[scope]\nproject_id = "nested"\n');
    assert.throws(() => readConfiguredProjectId(projectRoot), { code: 'status-project-invalid' });

    fs.writeFileSync(configPath, `project_id = "${'x'.repeat(20000)}"\n`);
    assert.throws(() => readConfiguredProjectId(projectRoot), { code: 'status-project-invalid' });

    fs.unlinkSync(configPath);
    fs.symlinkSync('/etc/hostname', configPath);
    assert.throws(() => readConfiguredProjectId(projectRoot), { code: 'status-project-invalid' });
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('host evidence config is passed as an optional host-only launcher argument', () => {
  assert.deepEqual(
    hostEvidenceConfigArguments('/home/eaglesvn/.local/state/curator/evidence.json'),
    ['--evidence-config', '/home/eaglesvn/.local/state/curator/evidence.json'],
  );
  assert.deepEqual(hostEvidenceConfigArguments('  '), []);
  assert.deepEqual(hostEvidenceConfigArguments(null), []);
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
    assert.equal(items[0].color.id, 'textLink.foreground');
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

test('the extension exposes the dashboard without a palette task-creation command', () => {
  assert.deepEqual(extensionManifest.contributes.commands.map((command) => command.command), [
    'curatormdV2.openDashboard',
  ]);
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
  const routine = structuredClone(valid);
  routine.candidates[0].candidate.materiality = 'routine';
  assert.equal(validateReviewQueue(routine, 'alpha')[0].candidate.materiality, 'routine');
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
    hermesProfileBindings: { alpha: 'fixture-profile' },
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
    reviewCommand: '/opt/curator tools/curatormd-v2-review',
    evidenceConfig: '/home/eaglesvn/.local/state/curator/evidence.json',
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

  const launchArguments = [];
  await showDashboard((command, args) => {
    if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
    launchArguments.push(args);
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
  assert.ok(launchArguments[0].includes('--evidence-config'));
  assert.equal(
    launchArguments[0][launchArguments[0].indexOf('--evidence-config') + 1],
    '/home/eaglesvn/.local/state/curator/evidence.json',
  );
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
  assert.match(terminalCalls[1].text, /'--evidence-config'/);
  assert.match(
    terminalCalls[1].text,
    /'\/home\/eaglesvn\/\.local\/state\/curator\/evidence\.json'/,
  );
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
    'Curator denied this request; check the project access grant.',
  );
  await receiveMessage({ type: 'openReview', candidateId: 'candidate-1' });
  assert.equal(terminalCalls.length, 2, 'a denied read clears cached review authority');
  disposePanel();
});

test('dashboard uses the exact database binding and stops when its project ID differs', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-db-binding-'));
  const configPath = path.join(projectRoot, '.curatormd-v2.toml');
  const messages = [];
  let receiveMessage;
  const userSettings = {
    databasePath: '/state/legacy-fallback.sqlite3',
    databaseBindings: { alpha: '/state/alpha-ledger.sqlite3', beta: '/state/beta-ledger.sqlite3' },
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] ?? fallback,
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
  try {
    fs.writeFileSync(configPath, 'project_id = "alpha"\n');
    let launchArgs;
    let process;
    await showDashboard((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      launchArgs = args;
      process = new FakeMcpProcess('a'.repeat(64), false, null, null, true);
      return process;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    assert.equal(launchArgs[launchArgs.indexOf('--database') + 1], '/state/alpha-ledger.sqlite3');
    assert.ok(messages.some((message) => message.type === 'goals'));

    fs.writeFileSync(configPath, 'project_id = "beta"\n');
    messages.length = 0;
    await showDashboard((command) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      process = new FakeMcpProcess('a'.repeat(64), false, null, null, true);
      return process;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    assert.deepEqual(process.requests
      .filter((request) => request.method === 'tools/call')
      .map((request) => request.params.name), ['goal_list_page']);
    assert.ok(messages.some((message) => message.type === 'error'
      && /different project database/.test(message.message)));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    deactivate();
  }
});

test('dashboard rejects goal reports without a valid snapshot revision', async () => {
  const messages = [];
  let receiveMessage;
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
      this.hidden = false;
      this.children = [];
      this.listeners = {};
      this.attributes = {};
    }

    addEventListener(type, listener) { this.listeners[type] = listener; }
    setAttribute(name, value) { this.attributes[name] = value; }
    focus() { this.focused = true; }
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
  const dashboardQueueSnapshot = healthyCuratorQueueSnapshot('alpha', {
    event_received_count: 1,
    oldest_pending_event_age_seconds: 30,
    operational_counts: {
      pending_review_count: 1,
      pending_purge_receipt_count: 0,
      pending_purge_artifact_count: 0,
      pending_expiry_purge_receipt_count: 0,
      pending_expiry_purge_artifact_count: 0,
    },
  });
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0,
    goals: [{ goal_id: 'goal-1', status: 'active', updated_at: '2026-10-30T12:23:11Z', problem: 'active: Vhost Manager SSL renewal completed Scheduled ACME renewal operation 8a431afe-65d1-43c6-85cb-f90fd3323b23 (exit code 0)', next_action: 'Review the latest run.' }],
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
  queueSnapshot: dashboardQueueSnapshot,
  queueSummary: summarizeOperationalQueues(dashboardQueueSnapshot, 'alpha'),
  queueRows: queueMetricRows(dashboardQueueSnapshot, 'alpha'),
  queueState: queuePanelState(dashboardQueueSnapshot, 'alpha'),
  queueCheckedAt: dashboardQueueSnapshot.observed_at,
  healthCheckedAt: new Date().toISOString(),
  storage: storageSnapshot } });
  const goalCard = elements.get('goals').children[0];
  assert.equal(goalCard.children[0].textContent, 'Vhost Manager SSL renewal completed (exit code 0)');
  assert.equal(goalCard.children[1].children[0].textContent, 'Disposition: active');
  assert.equal(goalCard.children[1].children[1].textContent, 'Updated 2026-10-30 19:23 +07');
  assert.equal(goalCard.children[1].children[2].textContent, 'Next: Review the latest run.');
  assert.match(elements.get('health').textContent, /^Project health: healthy · no open gates\. Checked .* \+07$/);
  assert.equal(elements.get('healthPanel').attributes['data-state'], 'healthy');
  assert.equal(elements.get('healthRows').children[0].children[1].textContent, 'healthy');
  assert.equal(elements.get('activity').textContent, 'Retained activity: 3 receipts · 1 goal · 2 facts.');
  assert.equal(elements.get('activityRows').children.length, 9);
  assert.equal(elements.get('activityRows').children[0].children[0].textContent, 'SDE candidates');
  assert.equal(elements.get('activityRows').children[0].children[1].textContent, 'Pending 1 · Approved 0 · Rejected 0');
  assert.equal(elements.get('activityRows').children[1].children[0].textContent, 'Goal states');
  assert.match(elements.get('activityRows').children[1].children[1].textContent, /^\s*planned 0, active 1/);
  assert.match(elements.get('queues').textContent, /Events received 1, failed 0, quarantined 0/);
  assert.equal(elements.get('queueRows').children.length, 9);
  assert.equal(elements.get('queueRows').children[0].children[1].textContent, '1');
  assert.equal(elements.get('queueRows').children[0].children[2].attributes['data-state'], 'review');
  assert.equal(elements.get('storage').textContent, 'SQLite 9.0 KiB · staging 128 B');
  assert.equal(elements.get('storageRows').children.length, 9);
  assert.equal(elements.get('storageRows').children[6].children[1].textContent, '9.0 KiB / 250.0 MiB');
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: null, healthProbeFailure: 'Hermes health read failed.',
  healthCheckedAt: new Date().toISOString(),
  healthGateDescriptions: ['Hermes health read failed.'],
  queueSnapshot: dashboardQueueSnapshot,
  queueSummary: summarizeOperationalQueues(dashboardQueueSnapshot, 'alpha'),
  queueRows: queueMetricRows(dashboardQueueSnapshot, 'alpha'),
  queueState: queuePanelState(dashboardQueueSnapshot, 'alpha'),
  queueCheckedAt: dashboardQueueSnapshot.observed_at } });
  assert.equal(elements.get('healthPanel').attributes['data-state'], 'unknown');
  assert.equal(elements.get('queuesPanel').attributes['data-state'], 'review');
  assert.match(elements.get('queues').textContent, /Checked .* \+07$/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: { project_id: 'alpha', status: 'healthy', gate_codes: [] },
  healthCheckedAt: new Date().toISOString(),
  healthGateDescriptions: [],
  queueSnapshot: null, queueProbeFailure: 'Curator queue read failed.',
  queueCheckedAt: new Date().toISOString(), queueRows: [
    { label: 'Queue snapshot', value: 'Curator queue read failed.', state: 'unknown' },
  ], queueSummary: 'Operational queues: unknown. Curator queue read failed.', queueState: 'unknown' } });
  assert.equal(elements.get('healthPanel').attributes['data-state'], 'healthy');
  assert.equal(elements.get('queuesPanel').attributes['data-state'], 'unknown');
  assert.match(elements.get('queues').textContent, /Curator queue read failed/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, queueSummary: 'Events received 0, failed 1, quarantined 1, active claims 0, expired claims 0; oldest pending age none. Reviews pending 0; purge pending 0 receipts / 0 artifacts; expiry pending 0 receipts / 0 artifacts.',
  queueState: 'degraded', queueRows: [{ label: 'Events failed', value: '1', state: 'degraded' }] } });
  assert.match(elements.get('queues').textContent, /Events received 0, failed 1, quarantined 1/);
  assert.equal(elements.get('queuesPanel').attributes['data-state'], 'degraded');
  const sqliteAtThreshold = {
    ...storageSnapshot,
    global_database_bytes: 262144000,
    global_wal_bytes: 0,
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: sqliteAtThreshold } });
  assert.equal(elements.get('storageRows').children[6].children[2].attributes['data-state'], 'healthy');
  const sqliteAboveThreshold = {
    ...storageSnapshot,
    global_database_bytes: 262144001,
    global_wal_bytes: 0,
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: sqliteAboveThreshold } });
  assert.equal(elements.get('storageRows').children[6].children[2].attributes['data-state'], 'warning');
  assert.equal(elements.get('storageRows').children[6].children[2].textContent, 'Warning · writes allowed');
  const stagingAtWarning = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 196608000, inventory_complete: true, error_code: null },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: stagingAtWarning } });
  assert.equal(elements.get('storageRows').children[7].children[2].attributes['data-state'], 'warning');
  const stagingAtThreshold = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 262144000, inventory_complete: true, error_code: null },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: stagingAtThreshold } });
  assert.equal(elements.get('storageRows').children[7].children[2].textContent, 'Warning · writes allowed');
  const incompleteStaging = {
    ...storageSnapshot,
    staging: { observed_file_bytes: 123, inventory_complete: false, error_code: 'staging_scan_failed' },
  };
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: incompleteStaging } });
  assert.equal(elements.get('storageRows').children[7].children[1].textContent, 'At least 123 B · staging_scan_failed');
  assert.equal(elements.get('storageRows').children[7].children[2].attributes['data-state'], 'unknown');
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, storage: { project_id: 'other' } } });
  assert.match(elements.get('storage').textContent, /unknown\. Project mismatch/);
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: { project_id: 'alpha', status: 'degraded', gate_codes: ['staging_budget_warning'] },
  healthGateDescriptions: ['Staging is near its warning limit; writes remain allowed.'] } });
  assert.equal(elements.get('health').textContent, 'Project health: degraded · 1 open gate. Check time unavailable');
  assert.equal(
    elements.get('healthRows').children[1].children[1].textContent,
    'Staging is near its warning limit; writes remain allowed.',
  );
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: {
    project_id: 'alpha', status: 'degraded',
    gate_codes: ['dependency_unknown:event_router', 'dependency_unavailable:purge_scheduler'],
  }, healthGateDescriptions: [
    'No fresh result is available for work-event routing.',
    'The six-hour cleanup timer check is currently unavailable.',
  ] } });
  assert.equal(
    elements.get('healthRows').children[1].children[1].textContent,
    'No fresh result is available for work-event routing. The six-hour cleanup timer check is currently unavailable.',
  );
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: { project_id: 'other', status: 'healthy', gate_codes: [] },
  healthGateDescriptions: ['Health snapshot belongs to a different project.'] } });
  assert.equal(elements.get('health').textContent, 'Project health: unknown · 1 open gate. Check time unavailable');
  assert.equal(
    elements.get('healthRows').children[1].children[1].textContent,
    'Health snapshot belongs to a different project.',
  );
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: null, healthGateDescriptions: ['Health snapshot unavailable; refresh to retry.'] } });
  assert.equal(elements.get('health').textContent, 'Project health: unknown · 1 open gate. Check time unavailable');
  assert.match(elements.get('healthRows').children[1].children[1].textContent, /Health snapshot unavailable/);
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
    report: '- Report snapshot: `' + 'a'.repeat(64) + '`\n'
      + '## Facts to date (showing 1–1 of 1)\n'
      + '### Verified facts\n- `fact-1` — Verification: test passed',
  } });
  assert.match(elements.get('report').textContent, /Verification: test passed/);
  assert.equal(elements.get('goals').children.length, 1);
  receiveWindowMessage({ data: {
    type: 'evidence',
    factOffset: 0,
    evidence: {
      goal_id: 'goal-1', fact_id: 'fact-1', fact_kind: 'verification',
      verification_status: 'verified_fact', criterion_id: 'criterion-1',
      report_revision: 'a'.repeat(64),
      evidence: [{
        evidence_kind: 'test', outcome: 'passed', locator: 'private-locator',
        sha256: 'b'.repeat(64), occurrence_id: null,
        attestation: {
          adapter_id: 'adapter-1', authenticated_subject: 'local-uid:1000',
          source_revision: 'abc123', observed_at: '2026-10-27T00:00:00+00:00',
          valid_until: '2026-10-27T00:05:00+00:00',
          revocation_checked_at: '2026-10-27T00:00:00+00:00',
        },
      }],
    },
  } });
  assert.equal(elements.get('evidenceRefs').children.length, 1);
  assert.match(elements.get('evidenceStatus').textContent, /stale\/unknown/);

  receiveWindowMessage({ data: {
    type: 'evidence',
    factOffset: 0,
    displayStatus: 'verified_fact',
    evidence: {
      goal_id: 'goal-1', fact_id: 'fact-1', fact_kind: 'verification',
      verification_status: 'verified_fact', criterion_id: 'criterion-1',
      report_revision: 'a'.repeat(64),
      evidence: [{
        evidence_kind: 'test', outcome: 'passed', locator: 'private-locator',
        sha256: 'b'.repeat(64), occurrence_id: null,
        attestation: {
          adapter_id: 'adapter-1', authenticated_subject: 'local-uid:1000',
          source_revision: 'abc123', observed_at: new Date().toISOString(),
          valid_until: new Date(Date.now() + 60_000).toISOString(),
          revocation_checked_at: new Date().toISOString(),
        },
      }],
    },
  } });
  assert.match(elements.get('evidenceStatus').textContent, /verified_fact/);

  receiveWindowMessage({ data: { type: 'error', message: 'Curator read failed.' } });

  assert.equal(elements.get('report').textContent, '');
  assert.equal(elements.get('evidenceRefs').children.length, 0);
  assert.equal(elements.get('evidenceButtons').children.length, 0);
  assert.equal(elements.get('goals').children.length, 0);
  assert.equal(elements.get('selected').textContent, '');
  assert.equal(elements.get('goalPage').textContent, '');
  assert.equal(elements.get('factPage').textContent, '');
  assert.equal(elements.get('error').textContent, 'Curator read failed.');
  assert.equal(elements.get('nextFacts').disabled, true);
  assert.match(elements.get('health').textContent, /Project health: unknown/);
  assert.equal(elements.get('healthRows').children.length, 3);
  assert.equal(elements.get('healthRows').children[0].children[0].textContent, 'Project health');
  assert.equal(
    elements.get('healthRows').children[1].children[1].textContent,
    'Health snapshot unavailable; refresh to retry.',
  );
  receiveWindowMessage({ data: { type: 'goals', page: {
    total: 1, offset: 0, goals: [], next_offset: null, project_id: 'alpha',
  }, health: null, healthProbeError: 'hermes-probe-exit',
  healthProbeFailure: 'Hermes did not return a health snapshot; check the selected Hermes profile and retry.',
  alertSummary: 'Attention: Readiness and queues unknown.' } });
  assert.match(
    elements.get('healthRows').children[1].children[1].textContent,
    /Hermes did not return a health snapshot; check the selected Hermes profile and retry\./,
  );
  assert.doesNotMatch(elements.get('healthRows').children[1].children[1].textContent, /health_read_unavailable/);
  assert.match(
    elements.get('healthRows').children[2].children[1].textContent,
    /Hermes did not return a health snapshot/,
  );
  assert.doesNotMatch(elements.get('healthRows').children[2].children[1].textContent, /health_read_unavailable/);
  assert.match(elements.get('storage').textContent, /Storage usage: unknown/);
});

test('dashboard still reads goals when the health probe is unavailable', async () => {
  const messages = [];
  let receiveMessage;
  const userSettings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
      ['project_activity_status', 'project_storage_usage'],
    ));
  await receiveMessage({ type: 'loadGoals', offset: 0 });

  const goals = messages.find((message) => message.type === 'goals');
  assert.equal(goals.page.goals[0].goal_id, 'goal-1');
  assert.equal(goals.health, null);
  assert.equal(goals.healthProbeError, 'hermes-probe-exit');
  assert.equal(goals.queueProbeError, null);
  assert.equal(goals.queueSnapshot.project_id, 'alpha');
  assert.equal(goals.queueState, 'healthy');
  assert.equal(goals.activity, null);
  assert.equal(goals.storage, null);
});

test('open dashboard retries with the current profile after a settings change', async () => {
  const messages = [];
  let receiveMessage;
  let settingsListener;
  const userSettings = {
    databasePath: '/tmp/curator-settings-refresh.sqlite3',
    profileId: 'first-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: '/tmp/curator-settings-refresh' } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
    onDidChangeConfiguration: (listener) => {
      settingsListener = listener;
      return { dispose() {} };
    },
  };
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showWarningMessage: assert.fail,
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => { messages.push(message); },
        onDidReceiveMessage: (listener) => { receiveMessage = listener; },
      },
      onDidDispose() {},
    }),
  };
  const curatorArguments = [];
  await showDashboard((command, args) => {
    if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
    curatorArguments.push(args);
    return new FakeMcpProcess('a'.repeat(64), false, null, null, true);
  });
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  userSettings.profileId = 'second-profile';
  settingsListener({ affectsConfiguration: () => true });
  assert.ok(messages.some((message) => message.type === 'reloadGoals'));
  await receiveMessage({ type: 'loadGoals', offset: 0 });
  const profileArgument = (args) => args[args.indexOf('--profile-id') + 1];
  assert.equal(profileArgument(curatorArguments[0]), 'first-profile');
  assert.equal(profileArgument(curatorArguments[1]), 'second-profile');
});

test('project workspace exposes inbox, SDE proposals, and side-buffer without copying event payloads', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-workspace-'));
  try {
    initializeWorkspaceAreas(projectRoot);
    const written = writeWorkspaceQueueViews(projectRoot, 'alpha', {
      received_count: 2,
      failed_count: 1,
      quarantined_count: 0,
      oldest_pending_received_at: '2026-10-30T10:00:00+07:00',
      oldest_pending_age_seconds: 60,
      claimed_count: 1,
      expired_claim_count: 0,
      payload: 'MUST_NOT_BE_COPIED',
    }, {
      project_id: 'alpha',
      candidates: [{
        candidate: {
          candidate_id: 'candidate-1', goal_id: 'goal-1', status: 'pending_review',
          materiality: 'decision', rationale: 'Retain this verified project decision.',
          internal_extra: 'MUST_NOT_BE_COPIED',
        },
        goal: {
          goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal',
          internal_extra: 'MUST_NOT_BE_COPIED',
        },
        facts: [{ bullet: 'MUST_NOT_BE_COPIED' }],
      }],
    });

    assert.equal(written, true);
    assert.ok(fs.statSync(path.join(projectRoot, '.curatormd-v2/inbox')).isDirectory());
    assert.ok(fs.statSync(path.join(projectRoot, '.curatormd-v2/sde-proposals')).isDirectory());
    assert.ok(fs.statSync(path.join(projectRoot, '.curatormd-v2/side-buffer')).isDirectory());
    const inbox = fs.readFileSync(path.join(projectRoot, '.curatormd-v2/inbox/status.json'), 'utf8');
    const proposals = fs.readFileSync(path.join(projectRoot, '.curatormd-v2/sde-proposals/pending.json'), 'utf8');
    assert.match(inbox, /"received_count": 2/);
    assert.match(proposals, /Retain this verified project decision/);
    assert.match(proposals, /Open pending-review\.md/);
    assert.match(inbox, /\+07:00/);
    assert.doesNotMatch(`${inbox}\n${proposals}`, /MUST_NOT_BE_COPIED/);
    const inboxPath = path.join(projectRoot, '.curatormd-v2/inbox/status.json');
    const proposalPath = path.join(projectRoot, '.curatormd-v2/sde-proposals/pending.json');
    const inboxBefore = fs.statSync(inboxPath, { bigint: true });
    const proposalBefore = fs.statSync(proposalPath, { bigint: true });
    const inboxBytesBefore = fs.readFileSync(inboxPath);
    const proposalBytesBefore = fs.readFileSync(proposalPath);
    const rewritten = writeWorkspaceQueueViews(projectRoot, 'alpha', {
      received_count: 2,
      failed_count: 1,
      quarantined_count: 0,
      oldest_pending_received_at: '2026-10-30T10:00:00+07:00',
      oldest_pending_age_seconds: 60,
      claimed_count: 1,
      expired_claim_count: 0,
    }, {
      project_id: 'alpha',
      candidates: [{
        candidate: {
          candidate_id: 'candidate-1', goal_id: 'goal-1', status: 'pending_review',
          materiality: 'decision', rationale: 'Retain this verified project decision.',
        },
        goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Smoke goal' },
      }],
    });
    const inboxAfter = fs.statSync(inboxPath, { bigint: true });
    const proposalAfter = fs.statSync(proposalPath, { bigint: true });
    assert.equal(rewritten, true);
    assert.equal(inboxAfter.ino, inboxBefore.ino);
    assert.equal(proposalAfter.ino, proposalBefore.ino);
    assert.equal(inboxAfter.mtimeNs, inboxBefore.mtimeNs);
    assert.equal(proposalAfter.mtimeNs, proposalBefore.mtimeNs);
    assert.deepEqual(fs.readFileSync(inboxPath), inboxBytesBefore);
    assert.deepEqual(fs.readFileSync(proposalPath), proposalBytesBefore);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('project workspace initialization refuses symlinked state areas', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-symlink-'));
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-outside-'));
  try {
    fs.symlinkSync(outside, path.join(projectRoot, '.curatormd-v2'));
    assert.throws(() => initializeWorkspaceAreas(projectRoot), /regular directory/);
    assert.deepEqual(fs.readdirSync(outside), []);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  }
});

test('pending SDE Markdown keeps editable rating and destination changes on refresh', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-sde-review-'));
  try {
    initializeWorkspaceAreas(projectRoot);
    const review = {
      candidate: {
        candidate_id: 'candidate-42',
        goal_id: 'goal-42',
        status: 'pending_review',
        materiality: 'decision',
        rationale: 'Retain the verified project decision.',
      },
      goal: {
        goal_id: 'goal-42',
        project_id: 'alpha',
        problem: 'Bind each task to the configured project.',
      },
    };
    const outline = {
      project_id: 'alpha',
      candidate_id: 'candidate-42',
      goal_id: 'goal-42',
      status: 'pending_review',
      task_started_at: '2026-11-01T09:20:00+07:00',
      successful_completion_at: '2026-11-01T11:45:00+07:00',
      persistence_documents: [
        'persistence/HISTORY.md', 'persistence/LESSONS-LEARNED.md',
      ],
      future_utility: 'Reuse the project binding check for new integrations.',
      supporting_facts: [{
        fact_id: 'fact-42', kind: 'change', bullet: 'The launcher checks the active project.',
      }],
    };
    const destination = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review], new Map([
      ['candidate-42', outline],
    ])), true);
    const generated = fs.readFileSync(destination, 'utf8');
    assert.ok(generated.includes('SDE ID: candidate\\-42'));
    assert.ok(generated.includes('Started: 2026\\-11\\-01T09:20:00\\+07:00'));
    assert.ok(generated.includes('Successfully completed: 2026\\-11\\-01T11:45:00\\+07:00'));
    assert.match(generated, /curator-v2-decision:candidate-42:start/);
    assert.match(generated, /"significance": 3/);

    const edited = generated
      .replace('"significance": 3', '"significance": 4')
      .replace('"documents": []', '"documents": [\n    "persistence/HISTORY.md",\n    "persistence/LESSONS-LEARNED.md"\n  ]');
    fs.writeFileSync(destination, edited, 'utf8');
    const refreshedOutline = { ...outline, future_utility: 'Updated source proposal text.' };
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review], new Map([
      ['candidate-42', refreshedOutline],
    ])), true);
    const refreshed = fs.readFileSync(destination, 'utf8');
    assert.match(refreshed, /"significance": 4/);
    assert.match(refreshed, /"persistence\/LESSONS-LEARNED\.md"/);
    assert.doesNotMatch(refreshed, /Updated source proposal text\./);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
