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
  joinMarkdownParagraphLines,
  McpStdioClient,
  dashboardHtml,
  defaultReviewCommand,
  defaultRouterCommand,
  parseRouterPassResult,
  runEventRouterPass,
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
  healthComponentRows,
  dashboardComponentRows,
  healthHistoryStatus,
  updatePersistentHealthHistory,
  hostFilesystemRows,
  parsePurgeReceiptInspection,
  parseTerminalEventInventory,
  parseEventCompactionProposal,
  queueMetricRows,
  queuePanelState,
  registerDashboardReloader,
  reloadOpenDashboards,
  refreshReviewConsumers,
  showDashboard,
  statusColorMeaning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  reviewDocumentActions,
  launchDocumentReview,
  validateReviewQueue,
  readReviewOutlines,
  writePendingReviewDocument,
  writeWorkspaceQueueViewsDetailed,
  workspaceQueueViewsConfirmResolved,
  writeWorkspaceQueueViews,
  notifyTransportClosed,
} = require('./extension');

test('joins wrapped Markdown prose and preserves structural and hard breaks', () => {
  const source = '# Heading\n\nFirst wrapped\nline here.\n\nHard break  \nnext line\n\n```json\n{\n  "a": 1\n}\n```\n\n- item\n- item two\n\n| a | b |\n| - | - |\n';
  const expected = '# Heading\n\nFirst wrapped line here.\n\nHard break  \nnext line\n\n```json\n{\n  "a": 1\n}\n```\n\n- item\n- item two\n\n| a | b |\n| - | - |\n';
  assert.equal(joinMarkdownParagraphLines(source), expected);
  assert.equal(joinMarkdownParagraphLines(expected), expected);
  assert.equal(joinMarkdownParagraphLines('one\r\ntwo\r\n'), 'one two\r\n');
  const protectedBlocks = '```md\n- item\ncontinued\n```\n\n<div>\nkeep\nlines\n</div>\n\nAfter\nwords\n';
  assert.equal(joinMarkdownParagraphLines(protectedBlocks), '```md\n- item\ncontinued\n```\n\n<div>\nkeep\nlines\n</div>\n\nAfter words\n');
});
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
    toolResponses = {},
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
    this.toolResponses = toolResponses;
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
          } else if (Object.hasOwn(this.toolResponses, request.params.name)) {
            const response = this.toolResponses[request.params.name];
            const value = typeof response === 'function'
              ? response(request.params.arguments || {}) : response;
            result = { content: [{ type: 'text', text: typeof value === 'string'
              ? value : JSON.stringify(value) }] };
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

test('cleanup receipt inspection validates and bounds a project receipt summary', () => {
  const receipt = {
    receipt_id: 'receipt-123',
    purge_status: 'purge_pending',
    canonical_persisted: true,
    cleanup_authorized: true,
    cleanup_canonical_persisted: true,
  };
  const targets = Array.from({ length: 101 }, (_, index) => ({
    artifact: { path: `goal-1/cue-${index}.txt`, sha256: 'a'.repeat(64) },
    status: index === 0 ? 'held' : 'purged',
    outcome: index === 0 ? 'held' : 'deleted',
    attempts: index,
    error: index === 0 ? 'retention_hold' : null,
    next_attempt_in_seconds: null,
    safe_recovery_action: index === 0 ? 'release_artifact_hold' : 'none',
    approval_stale: false,
  }));
  const result = parsePurgeReceiptInspection(JSON.stringify([receipt, targets]), 'receipt-123');
  assert.equal(result.purgeStatus, 'purge_pending');
  assert.equal(result.targetCount, 101);
  assert.equal(result.targets.length, 100);
  assert.equal(result.omittedTargetCount, 1);
  assert.equal(result.targets[0].nextAction, 'release_artifact_hold');
  assert.equal(Object.hasOwn(result.targets[0], 'sha256'), false);
  assert.throws(
    () => parsePurgeReceiptInspection([receipt, targets], 'another-receipt'),
    (error) => error.code === 'invalid-response',
  );
  assert.throws(
    () => parsePurgeReceiptInspection([receipt, [{ ...targets[0], status: 'unknown' }]], 'receipt-123'),
    (error) => error.code === 'invalid-response',
  );
});

test('terminal event inventory is project-bound, bounded, and content-free', () => {
  const inventory = {
    project_id: 'alpha',
    count_after_cursor: 1,
    complete: true,
    next_after_event_id: null,
    events: [{
      event_id: 'evt-quarantine-1',
      status: 'quarantined',
      payload_sha256: 'b'.repeat(64),
      source_id: 'producer-1',
      source_sequence: 4,
    }],
  };
  const result = parseTerminalEventInventory(inventory, 'alpha');
  assert.deepEqual(result.events[0], {
    eventId: 'evt-quarantine-1',
    status: 'quarantined',
    payloadSha256: 'b'.repeat(64),
    sourceId: 'producer-1',
    sourceSequence: 4,
  });
  assert.equal(Object.hasOwn(result.events[0], 'payload'), false);
  assert.throws(
    () => parseTerminalEventInventory(inventory, 'another-project'),
    (error) => error.code === 'invalid-response',
  );
  const sanitized = parseTerminalEventInventory({
    ...inventory, events: [{ ...inventory.events[0], payload: 'must-not-be-present' }],
  }, 'alpha');
  assert.equal(Object.hasOwn(sanitized.events[0], 'payload'), false);
  assert.throws(
    () => parseTerminalEventInventory({ ...inventory, complete: false }, 'alpha'),
    (error) => error.code === 'invalid-response',
  );
});

test('event archive proposal validates the project, page, manifest, and payload-free rows', () => {
  const proposal = {
    project_id: 'alpha', eligible_count: 1, offset: 0, limit: 50,
    manifest_sha256: 'c'.repeat(64),
    items: [{
      project_id: 'alpha', event_id: 'evt-processed-1', event_type: 'goal.started',
      payload_sha256: 'd'.repeat(64), idempotency_sha256: null,
      received_at: '2026-11-07T10:00:00Z', processed_at: '2026-11-07T10:00:01Z',
      source_id: 'producer-1', source_sequence: 9, attempts: 1,
      retry_audit_count: 0, terminal_disposition_count: 0,
      consumer_drain_reference_count: 0,
    }],
  };
  const result = parseEventCompactionProposal(proposal, 'alpha', 0, 50);
  assert.equal(result.eligibleCount, 1);
  assert.equal(result.items[0].eventId, 'evt-processed-1');
  assert.equal(Object.hasOwn(result.items[0], 'payload'), false);
  assert.throws(
    () => parseEventCompactionProposal(proposal, 'other-project', 0, 50),
    (error) => error.code === 'invalid-response',
  );
  assert.throws(
    () => parseEventCompactionProposal({ ...proposal, offset: 50 }, 'alpha', 0, 50),
    (error) => error.code === 'invalid-response',
  );
  assert.throws(
    () => parseEventCompactionProposal({
      ...proposal, items: [{ ...proposal.items[0], attempts: -1 }],
    }, 'alpha', 0, 50),
    (error) => error.code === 'invalid-response',
  );
});

test('health component rows expose every dependency and preserve stale or unknown states', () => {
  const health = healthyHermesProbe().health;
  const healthyRows = healthComponentRows(health, 'alpha');
  assert.equal(healthyRows.length, 7);
  assert.ok(healthyRows.every((row) => row.state === 'healthy'));
  assert.equal(healthyRows[0].label, 'event router');

  health.dependencies[1].status = 'degraded';
  const degradedRows = healthComponentRows(health, 'alpha');
  assert.equal(degradedRows[1].state, 'degraded');

  health.dependencies[1].observed_at = new Date(Date.now() - 70000).toISOString();
  health.dependencies[1].age_seconds = 70;
  const staleRows = healthComponentRows(health, 'alpha');
  assert.equal(staleRows[1].state, 'unknown');
  assert.equal(staleRows[1].stateLabel, 'Stale');

  assert.ok(healthComponentRows(null, 'alpha').every((row) => row.state === 'unknown'));
});

test('dashboard component LEDs include local reads, projections, and history storage', () => {
  const health = healthyHermesProbe('alpha').health;
  const rows = dashboardComponentRows({
    health,
    projectId: 'alpha',
    queueSnapshot: { project_id: 'alpha' },
    workspaceViewsUpdated: false,
    healthHistoryPersisted: false,
  });
  assert.equal(rows.length, 11);
  assert.ok(rows.slice(0, 7).every((row) => row.state === 'healthy'));
  assert.equal(rows[7].label, 'Hermes profile probe');
  assert.equal(rows[7].state, 'healthy');
  assert.equal(rows[8].label, 'Curator MCP queue read');
  assert.equal(rows[8].state, 'healthy');
  assert.equal(rows[9].label, 'Inbox and review projections');
  assert.equal(rows[9].state, 'degraded');
  assert.equal(rows[9].action, 'refreshQueueViews');
  assert.equal(rows[10].label, 'Health history storage');
  assert.equal(rows[10].state, 'unknown');

  const unavailable = dashboardComponentRows({
    health: null,
    projectId: 'alpha',
    healthProbeError: 'hermes-probe-timeout',
    queueProbeError: 'curator-queue-read',
  });
  assert.ok(unavailable.slice(7).every((row) => row.state === 'unknown'));
  assert.match(unavailable[7].value, /timed out/);
  assert.match(unavailable[8].value, /could not read project queue counts/);
});

test('host filesystem rows report available space and fail closed on invalid probes', () => {
  const calls = [];
  const rows = hostFilesystemRows('/workspace', '/data/curator.sqlite', (target) => {
    calls.push(target);
    if (target === '/data/curator.sqlite') throw new Error('database file is not present');
    return target === '/workspace'
      ? { bsize: 4096, blocks: 1000, bfree: 300, bavail: 250 }
      : { bsize: 4096, blocks: 1000, bfree: 80, bavail: 50 };
  });
  assert.deepEqual(calls, ['/workspace', '/data/curator.sqlite', '/data']);
  assert.equal(rows[0].label, 'Workspace filesystem');
  assert.equal(rows[0].state, 'healthy');
  assert.match(rows[0].value, /1000\.0 KiB available \/ 3\.9 MiB total/);
  assert.equal(rows[1].label, 'SQLite filesystem');
  assert.equal(rows[1].state, 'warning');
  assert.match(rows[1].stateLabel, /10% threshold/);
  assert.ok(hostFilesystemRows('relative', '/data/db', () => null)
    .every((row) => row.state === 'unknown'));
  assert.ok(hostFilesystemRows('/workspace', '/data/db', () => ({
    bsize: Number.MAX_SAFE_INTEGER, blocks: 2, bfree: 1, bavail: 1,
  })).every((row) => row.state === 'unknown'));
});

test('dashboard records a project-bound health trend with a fixed 60-check limit', () => {
  class Element {
    constructor() { this.children = []; this.attributes = {}; this.listeners = {}; this.textContent = ''; }
    addEventListener(type, listener) { this.listeners[type] = listener; }
    setAttribute(name, value) { this.attributes[name] = value; }
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
  let receiveMessage;
  let monitorCallback;
  let monitorInterval;
  let savedState = null;
  const window = {
    addEventListener(type, listener) {
      if (type === 'message') receiveMessage = listener;
    },
    setInterval(callback, interval) {
      monitorCallback = callback;
      monitorInterval = interval;
      return 1;
    },
    clearInterval() {},
  };
  const postedMessages = [];
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {
    document,
    window,
    acquireVsCodeApi: () => ({
      postMessage: (message) => postedMessages.push(message),
      getState: () => savedState,
      setState: (state) => { savedState = state; },
    }),
  });

  const firstTime = Date.now() - 65000;
  for (let index = 0; index < 65; index++) {
    const status = index % 2 ? 'degraded' : 'healthy';
    receiveMessage({ data: {
      type: 'healthSnapshot',
      projectId: 'alpha',
      health: { project_id: 'alpha', status, gate_codes: [] },
      healthCheckedAt: new Date(firstTime + index * 1000).toISOString(),
      healthComponentRows: [],
    } });
  }
  assert.equal(elements.get('healthHistoryChart').children.length, 60);
  assert.equal(elements.get('healthHistoryChart').children[59].attributes['data-state'], 'healthy');
  assert.match(elements.get('healthHistorySummary').textContent, /^60 checks/);
  assert.equal(savedState.projectId, 'alpha');
  assert.equal(savedState.healthHistory.length, 60);
  assert.equal(savedState.healthHistory[0].observed_at, new Date(firstTime + 5000).toISOString());
  assert.equal(monitorInterval, 60000);
  elements.get('refresh').disabled = false;
  monitorCallback();
  assert.equal(postedMessages.at(-1).type, 'refreshHealth');

  receiveMessage({ data: {
    type: 'healthSnapshot', projectId: 'beta',
    health: { project_id: 'beta', status: 'unknown', gate_codes: [] },
    healthCheckedAt: new Date(firstTime + 66000).toISOString(),
    healthComponentRows: [],
  } });
  assert.equal(elements.get('healthHistoryChart').children.length, 1);
  assert.equal(elements.get('healthHistoryChart').children[0].attributes['data-state'], 'unknown');
  assert.equal(savedState.projectId, 'beta');
});

test('health history persists a bounded project and Hermes-profile scoped series', async () => {
  const values = new Map();
  const store = {
    get: (key, fallback) => values.has(key) ? values.get(key) : fallback,
    update: async (key, value) => { values.set(key, value); },
  };
  let result;
  const start = Date.now() - 70000;
  for (let index = 0; index < 65; index += 1) {
    result = await updatePersistentHealthHistory(
      store,
      'alpha',
      'alpha-hermes',
      index % 2 ? 'degraded' : 'healthy',
      new Date(start + index * 1000).toISOString(),
    );
  }
  assert.equal(result.persisted, true);
  assert.match(result.scope, /^[a-f0-9]{64}$/);
  assert.equal(result.samples.length, 60);
  assert.equal(result.samples[0].observed_at, new Date(start + 5000).toISOString());
  assert.equal(result.samples.at(-1).observed_at, new Date(start + 64000).toISOString());

  const otherProfile = await updatePersistentHealthHistory(
    store, 'alpha', 'other-hermes', 'unknown', new Date(start + 65000).toISOString(),
  );
  assert.equal(otherProfile.persisted, true);
  assert.notEqual(otherProfile.scope, result.scope);
  assert.equal(otherProfile.samples.length, 1);

  const failed = await updatePersistentHealthHistory({
    get: () => [],
    update: async () => { throw new Error('private persistence detail'); },
  }, 'alpha', 'alpha-hermes', 'healthy', new Date().toISOString());
  assert.equal(failed.persisted, false);
  assert.equal(failed.scope, result.scope);
  assert.deepEqual(failed.samples, []);

  const unreadable = await updatePersistentHealthHistory({
    get: () => [],
    update: async () => {},
  }, 'alpha', 'alpha-hermes', 'healthy', new Date().toISOString());
  assert.equal(unreadable.persisted, false);
  assert.equal(unreadable.scope, result.scope);
});

test('dashboard restores persistent health history returned by the host', () => {
  class Element {
    constructor() { this.children = []; this.attributes = {}; this.textContent = ''; }
    addEventListener() {}
    setAttribute(name, value) { this.attributes[name] = value; }
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
  let receiveMessage;
  let savedState = null;
  const window = { addEventListener(type, listener) {
    if (type === 'message') receiveMessage = listener;
  } };
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {
    document,
    window,
    acquireVsCodeApi: () => ({
      postMessage() {},
      getState: () => savedState,
      setState: (state) => { savedState = state; },
    }),
  });
  const samples = [
    { observed_at: '2026-11-08T01:00:00.000Z', status: 'healthy' },
    { observed_at: '2026-11-08T01:01:00.000Z', status: 'degraded' },
  ];
  receiveMessage({ data: {
    type: 'healthSnapshot',
    projectId: 'alpha',
    health: { project_id: 'alpha', status: 'degraded', gate_codes: ['disk_low'] },
    healthCheckedAt: samples[1].observed_at,
    healthHistory: samples,
    healthHistoryPersisted: true,
    healthHistoryScope: 'a'.repeat(64),
    healthComponentRows: [],
  } });
  assert.equal(elements.get('healthHistoryChart').children.length, 2);
  assert.match(elements.get('healthHistorySummary').textContent, /^2 checks/);
  assert.match(elements.get('healthHistoryRetention').textContent, /Saved by VS Code/);
  assert.equal(savedState.healthHistoryScope, 'a'.repeat(64));
  assert.equal(savedState.healthHistory.length, 2);
});

test('projection health LED runs local rebuild and reflects its verified result', () => {
  class Element {
    constructor() { this.children = []; this.attributes = {}; this.listeners = {}; this.textContent = ''; }
    addEventListener(type, listener) { this.listeners[type] = listener; }
    setAttribute(name, value) { this.attributes[name] = value; }
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
  let receiveMessage;
  const postedMessages = [];
  const window = { addEventListener(type, listener) {
    if (type === 'message') receiveMessage = listener;
  } };
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {
    document,
    window,
    acquireVsCodeApi: () => ({ postMessage: (message) => postedMessages.push(message) }),
  });
  receiveMessage({ data: {
    type: 'healthSnapshot',
    projectId: 'alpha',
    health: { project_id: 'alpha', status: 'healthy', gate_codes: [] },
    healthCheckedAt: new Date().toISOString(),
    healthComponentRows: dashboardComponentRows({
      health: { project_id: 'alpha', status: 'healthy', gate_codes: [] },
      projectId: 'alpha',
      queueSnapshot: { project_id: 'alpha' },
      workspaceViewsUpdated: false,
    }),
  } });
  const projectionRow = elements.get('healthRows').children
    .find((row) => row.children[0].textContent === 'Inbox and review projections');
  const rebuild = projectionRow.children[1].children[0];
  rebuild.listeners.click();
  assert.equal(postedMessages.at(-1).type, 'refreshQueueViews');
  assert.equal(elements.get('refreshQueueViews').disabled, true);

  receiveMessage({ data: {
    type: 'queueViewsRefreshResult',
    status: {
      allUpdated: true,
      reviewQueueUpdated: true,
      reviewDocumentUpdated: true,
      inboxUpdated: true,
      reviewEditorOpen: false,
    },
  } });
  assert.equal(projectionRow.attributes['data-state'], 'healthy');
  assert.equal(projectionRow.children[1].textContent, 'Both local views refreshed');
  assert.equal(projectionRow.children[2].textContent, 'healthy');
  assert.equal(elements.get('refreshQueueViews').disabled, false);
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

test('repeated automatic feed failures cool down and recover automatically', async () => {
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
  const originalNow = Date.now;
  let recovered;
  try {
    Date.now = () => originalNow() + 61000;
    recovered = await readProjectFeeds(options);
  } finally {
    Date.now = originalNow;
  }
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

test('startup binding failures reach the dashboard without transport recovery', async () => {
  const cases = [
    ['project-config-stale', /project config changed after registration/],
    ['consumer-binding-inactive', /consumer binding is inactive/],
    ['project-read-grant-missing', /no active project read grant/],
  ];
  for (const [code, message] of cases) {
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stderr = new PassThrough();
    child.stdin = new Writable({
      write(_chunk, _encoding, callback) {
        callback();
        setImmediate(() => {
          child.emit('exit', 2);
          child.stderr.write(`private detail\nCURATOR_STARTUP_ERROR=${code}\n`);
          child.stderr.end();
          child.emit('close', 2);
        });
      },
    });
    const client = new McpStdioClient('fixture', [], '/tmp', 'fixture-profile', () => child);
    let startupError;
    await assert.rejects(client.initialize(), (error) => {
      startupError = error;
      assert.equal(error.code, code);
      assert.match(dashboardErrorMessage(error), message);
      assert.doesNotMatch(dashboardErrorMessage(error), /private detail|transport closed/);
      return true;
    });
    assert.equal(await notifyTransportClosed(startupError), false);
  }
});

test('closed Curator transport shows one recovery modal with an explicit reload action', async () => {
  const previousWindow = vscodeMock.window;
  const previousCommands = vscodeMock.commands;
  const warnings = [];
  const commands = [];
  vscodeMock.window = {
    showWarningMessage: async (...args) => {
      warnings.push(args);
      return warnings.length === 1 ? 'Dismiss' : 'Reload Window';
    },
  };
  vscodeMock.commands = {
    executeCommand: async (...args) => { commands.push(args); },
  };
  try {
    assert.equal(await notifyTransportClosed({ code: 'launcher-start' }), false);
    assert.equal(await notifyTransportClosed({ code: 'launcher-exit' }), true);
    assert.equal(await notifyTransportClosed({ code: 'launcher-exit' }), false);
    assert.equal(warnings.length, 1);
    assert.match(warnings[0][0], /Save your work, then reload the VS Code window/);
    assert.match(warnings[0][0], /start a fresh Codex session/);
    assert.match(warnings[0][0], /Do not re-enroll the project or recreate its grants/);
    assert.deepEqual(warnings[0][1], { modal: true });
    assert.deepEqual(warnings[0].slice(2), ['Reload Window', 'Dismiss']);

    const client = new McpStdioClient(
      'fixture', [], '/tmp', 'fixture-profile', () => new FakeMcpProcess(),
    );
    await client.initialize();
    await client.callTool('goal_list_page', { offset: 0, limit: 20 });
    client.close();
    assert.equal(await notifyTransportClosed({ code: 'launcher-exit' }), true);
    assert.equal(warnings.length, 2);
    assert.deepEqual(commands, [['workbench.action.reloadWindow']]);
  } finally {
    vscodeMock.window = previousWindow;
    vscodeMock.commands = previousCommands;
  }
});

test('MCP tool failures expose the rejected operation and safe reason code', async () => {
  const child = new FakeMcpProcess(undefined, false, 'sde_review_packet');
  const client = new McpStdioClient('fixture', [], '/tmp', 'fixture-profile', () => child);
  try {
    await client.initialize();
    await assert.rejects(client.callTool('sde_review_packet', { candidate_id: 'candidate-1' }), (error) => {
      assert.equal(error.code, 'mcp-tool-error');
      assert.match(error.message, /rejected sde_review_packet \(forbidden\)/);
      assert.equal(error.reasonCode, 'forbidden');
      assert.equal(error.toolName, 'sde_review_packet');
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
  const healingToolboxHtml = dashboardHtml(
    { cspSource: 'vscode-webview:' }, false, true,
  );
  assert.match(html, /default-src 'none'/);
  assert.match(html, /Facts .* of /);
  assert.match(html, /previous page was cleared/);
  assert.match(html, /reportStale/);
  assert.match(html, /Restarting from the first page/);
  assert.match(html, /function requestGoals\(offset, manualRefresh = false\)/);
  assert.match(html, /api\.postMessage\(\{ type: 'loadGoals', offset, manualRefresh \}\)/);
  assert.match(html, /addEventListener\('click', \(\) => requestGoals\(0, true\)\)/);
  assert.match(html, /requestGoals\(0, true\);/);
  assert.match(html, /window\.setInterval/);
  assert.match(html, /}, 60000\);/);
  assert.match(html, /reportRevision\.slice\(0, 12\)/);
  assert.match(html, /report\.textContent = message\.report/);
  assert.match(html, /Pending SDE review/);
  assert.match(html, /CuratorMD V2 Recovery Manager/);
  assert.match(html, /complete a tracked goal with current passing evidence, then request historical SDE assessment/);
  assert.match(html, /No pending SDE candidates\. Complete a tracked goal with current passing evidence/);
  assert.match(html, /failed read stays unknown/);
  assert.match(html, /choose <em>Refresh evidence<\/em> above the editable decision/);
  assert.match(html, /Retry recovery checks/);
  assert.match(html, /Rebuild local inbox and review views/);
  assert.match(html, /status\.reviewQueueUpdated/);
  assert.match(html, /status\.inboxUpdated/);
  assert.match(html, /Open pending review actions/);
  assert.match(html, /api\.postMessage\(\{ type: 'openPendingReview' \}\)/);
  assert.match(healingToolboxHtml, /recoveryToolbox'\)\.scrollIntoView\(\)/);
  assert.match(healingToolboxHtml, /retryRecoveryReads'\)\.focus\(\)/);
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
  assert.match(html, /Review and confirm in VS Code; no terminal is opened/);
  assert.match(html, /label\.textContent = candidate\.materiality/);
  assert.match(html, /Evidence references/);
  assert.match(html, /type: 'loadEvidence'/);
  assert.match(html, /reference\.locator/);
  assert.match(html, /paragraph\.textContent = fields\.filter\(Boolean\)\.join/);
  assert.doesNotMatch(html, /report\.innerHTML/);
  assert.doesNotMatch(html, /reviews\.innerHTML/);
});

test('recovery toolbox retries diagnostics and routes to attended review without a terminal', () => {
  class Element {
    constructor() {
      this.textContent = '';
      this.disabled = false;
      this.hidden = false;
      this.children = [];
      this.listeners = {};
      this.attributes = {};
      this.dataset = {};
    }

    addEventListener(type, listener) { this.listeners[type] = listener; }
    setAttribute(name, value) { this.attributes[name] = value; }
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
  const messages = [];
  const html = dashboardHtml({ cspSource: 'vscode-webview:' });
  const script = html.match(/<script nonce="[^"]+">([\s\S]*?)<\/script>/)[1];
  vm.runInNewContext(script, {
    document,
    window,
    acquireVsCodeApi: () => ({ postMessage: (message) => messages.push(message) }),
  });

  assert.equal(JSON.stringify(messages[0]), JSON.stringify({
    type: 'loadGoals', offset: 0, manualRefresh: true,
  }));
  elements.get('retryRecoveryReads').listeners.click();
  assert.equal(JSON.stringify(messages[1]), JSON.stringify({
    type: 'loadGoals', offset: 0, manualRefresh: true,
  }));
  elements.get('runEventRouter').listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'runEventRouter'))), {
    type: 'runEventRouter',
  });
  receiveWindowMessage({ data: {
    type: 'eventRouterResult', success: true, ran: false,
    summary: 'No eligible events are queued.',
  } });
  assert.equal(elements.get('eventRouterStatus').textContent, 'No eligible events are queued.');
  elements.get('inspectTerminalEvents').listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'inspectTerminalEvents'))), {
    type: 'inspectTerminalEvents',
  });
  elements.get('openReviewActions').listeners.click();
  assert.equal(JSON.stringify(messages.find((message) => message.type === 'openPendingReview')),
    JSON.stringify({ type: 'openPendingReview' }));
  elements.get('retryPendingPurges').listeners.click();
  assert.equal(JSON.stringify(messages.find((message) => message.type === 'retryPendingPurges')),
    JSON.stringify({ type: 'retryPendingPurges' }));
  document.getElementById('purgeReceiptId').value = 'receipt-123';
  elements.get('inspectPurgeReceipt').listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'inspectPurgeReceipt'))), {
    type: 'inspectPurgeReceipt', receiptId: 'receipt-123',
  });
  receiveWindowMessage({ data: {
    type: 'terminalEventInventory', afterEventId: null,
    inventory: {
      projectId: 'alpha', countAfterCursor: 1, complete: true,
      nextAfterEventId: null,
      events: [{ eventId: 'evt-quarantine-1', status: 'quarantined',
        payloadSha256: 'b'.repeat(64), sourceId: 'producer-1', sourceSequence: 4 }],
    },
  } });
  const eventRow = elements.get('terminalEventInventory').children[0].children[1].children[0];
  assert.equal(eventRow.children[0].textContent, 'evt-quarantine-1');
  assert.equal(eventRow.children[1].textContent, 'quarantined');
  assert.equal(eventRow.children[5].children[0].textContent, 'Retry…');
  eventRow.children[5].children[0].listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'retryQuarantinedEvent'))), {
    type: 'retryQuarantinedEvent', eventId: 'evt-quarantine-1',
    payloadSha256: 'b'.repeat(64), afterEventId: null,
  });
  elements.get('inspectEventArchive').listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'inspectEventArchive'))), {
    type: 'inspectEventArchive', offset: 0,
  });
  receiveWindowMessage({ data: {
    type: 'eventArchiveProposal',
    proposal: {
      projectId: 'alpha', eligibleCount: 1, offset: 0, limit: 50,
      manifestSha256: 'c'.repeat(64),
      items: [{ eventId: 'evt-processed-1', eventType: 'goal.started',
        payloadSha256: 'd'.repeat(64), receivedAt: '2026-11-07T10:00:00Z',
        processedAt: '2026-11-07T10:00:01Z', sourceId: 'producer-1',
        sourceSequence: 9, attempts: 1, retryAuditCount: 0,
        terminalDispositionCount: 0, consumerDrainReferenceCount: 0 }],
    },
  } });
  const archiveTarget = elements.get('eventArchiveProposal');
  assert.match(elements.get('eventArchiveStatus').textContent, /Eligible processed receipts 1–1 of 1/);
  archiveTarget.children[1].listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'archiveEventReceiptPage'))), {
    type: 'archiveEventReceiptPage', offset: 0, manifestSha256: 'c'.repeat(64),
    eventIds: ['evt-processed-1'],
  });
  receiveWindowMessage({ data: {
    type: 'purgeReceiptInspection',
    summary: {
      receiptId: 'receipt-123', purgeStatus: 'purge_pending',
      canonicalPersisted: true, cleanupAuthorized: true,
      cleanupCanonicalPersisted: true, targetCount: 1,
      targets: [{ path: 'goal-1/cue.bin', status: 'held', outcome: 'held', attempts: 2,
        nextAttemptInSeconds: null, nextAction: 'release_artifact_hold',
        approvalStale: false, error: 'retention_hold' }],
      omittedTargetCount: 0,
    },
  } });
  assert.match(elements.get('purgeReceiptStatus').textContent, /receipt-123 · purge_pending/);
  assert.equal(elements.get('purgeReceiptTargets').children[0].children[1].children[0].children[0].textContent, 'goal-1/cue.bin');
  assert.match(elements.get('purgeReceiptTargets').children[0].children[1].children[0].children[5].textContent, /release_artifact_hold.*retention_hold/);
  elements.get('purgeReceiptTargets').children[0].children[1].children[0].children[6].children[0]
    .listeners.click();
  assert.deepEqual(JSON.parse(JSON.stringify(messages.find((message) => message.type === 'releaseArtifactHold'))), {
    type: 'releaseArtifactHold', receiptId: 'receipt-123', artifactPath: 'goal-1/cue.bin',
  });
  assert.match(html, /already approved and canonically persisted/);
  assert.match(html, /Inspect cleanup receipt/);
  assert.match(html, /cannot approve a new deletion/);
  assert.equal(typeof receiveWindowMessage, 'function');
});

test('cleanup retry requires attended confirmation and its exact project authorization scope', async () => {
  const messages = [];
  const launched = [];
  let receiveMessage;
  let confirmationText;
  let confirmationOptions;
  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const receiptStatus = {
    receipt_id: 'receipt-abc', purge_status: 'purge_pending',
    canonical_persisted: true, cleanup_authorized: true,
    cleanup_canonical_persisted: true,
  };
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
    showWarningMessage: async (message, options, choice) => {
      confirmationText = message;
      confirmationOptions = options;
      return choice;
    },
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => messages.push(message),
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose() {},
    }),
  };
  try {
    await showDashboard((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        {
          retry_pending_purges: [],
          artifact_purge_status: [receiptStatus, [{
            artifact: { path: 'goal-1/cue.bin', sha256: 'b'.repeat(64) },
            status: 'held', outcome: 'held', attempts: 2,
            error: 'retention_hold', next_attempt_in_seconds: null,
            safe_recovery_action: 'release_artifact_hold', approval_stale: false,
          }]],
        },
      );
      launched.push({ args, child });
      return child;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    await receiveMessage({ type: 'inspectPurgeReceipt', receiptId: 'receipt-abc' });
    assert.equal(launched.length, 2);
    assert.ok(!launched[1].args.includes('--allow-write'));
    assert.ok(launched[1].child.requests.some((request) => request.params?.name === 'artifact_purge_status'));
    assert.equal(messages.at(-1).type, 'purgeReceiptInspection');
    assert.equal(messages.at(-1).summary.targets[0].nextAction, 'release_artifact_hold');
    await receiveMessage({ type: 'retryPendingPurges' });
    assert.ok(confirmationText.includes('project alpha'));
    assert.ok(confirmationText.includes('cannot approve any new deletion'));
    assert.deepEqual(confirmationOptions, { modal: true });
    assert.equal(launched.length, 3);
    assert.ok(launched[2].args.includes('--allow-purge-retry'));
    assert.ok(launched[2].child.requests.some((request) => request.params?.name === 'retry_pending_purges'));
    assert.deepEqual(messages.at(-1), {
      type: 'purgeRetryResult',
      success: true,
      summary: 'No already-authorized due cleanup work was pending.',
    });
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
  }
});

test('quarantined event retry rechecks one exact candidate under attended confirmation', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-event-retry-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const messages = [];
  const launched = [];
  let receiveMessage;
  let confirmationText = '';
  let confirmationOptions;
  const payloadSha256 = 'd'.repeat(64);
  const inventory = {
    project_id: 'alpha', count_after_cursor: 1, complete: true,
    next_after_event_id: null,
    events: [{ event_id: 'evt-quarantined-1', status: 'quarantined',
      payload_sha256: payloadSha256, source_id: 'producer-1', source_sequence: 7 }],
  };
  const userSettings = {
    databasePath: path.join(projectRoot, 'curator.sqlite3'),
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showWarningMessage: async (message, options, choice) => {
      confirmationText = message;
      confirmationOptions = options;
      return choice;
    },
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => messages.push(message),
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose() {},
    }),
  };
  try {
    await showDashboard((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        {
          event_terminal_inventory: inventory,
          event_quarantine_retry: {
            project_id: 'alpha', event_id: 'evt-quarantined-1', status: 'failed',
          },
        },
      );
      launched.push({ args, child });
      return child;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    await receiveMessage({
      type: 'retryQuarantinedEvent', eventId: 'evt-quarantined-1',
      payloadSha256, afterEventId: null,
    });
    assert.equal(launched.length, 4);
    assert.ok(!launched[1].args.includes('--allow-write'));
    assert.ok(launched[1].child.requests.some(
      (request) => request.params?.name === 'event_terminal_inventory',
    ));
    assert.match(confirmationText, /evt-quarantined-1/);
    assert.deepEqual(confirmationOptions, { modal: true, detail: confirmationOptions.detail });
    assert.match(confirmationOptions.detail, /Project: alpha/);
    assert.match(confirmationOptions.detail, /Payload SHA-256/);
    assert.ok(launched[2].args.includes('--allow-event-retry'));
    assert.ok(launched[2].child.requests.some(
      (request) => request.params?.name === 'event_terminal_inventory',
    ));
    const retry = launched[2].child.requests.find(
      (request) => request.params?.name === 'event_quarantine_retry',
    );
    assert.deepEqual(retry.params.arguments, { event_id: 'evt-quarantined-1' });
    assert.ok(launched[3].child.requests.some(
      (request) => request.params?.name === 'event_terminal_inventory',
    ));
    assert.ok(messages.some((message) => message.type === 'terminalEventRetryResult'
      && message.success === true));
    const inventoryMessage = messages.find((message) => message.type === 'terminalEventInventory');
    assert.equal(inventoryMessage.inventory.events[0].status, 'quarantined');
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('processed receipt archival rechecks an exact page and requires attended rationale', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-event-archive-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const messages = [];
  const launched = [];
  let receiveMessage;
  let confirmation = '';
  let confirmationOptions;
  let rationalePrompt;
  const proposal = {
    project_id: 'alpha', eligible_count: 1, offset: 0, limit: 50,
    manifest_sha256: 'c'.repeat(64),
    items: [{
      project_id: 'alpha', event_id: 'evt-processed-1', event_type: 'goal.started',
      payload_sha256: 'd'.repeat(64), idempotency_sha256: null,
      received_at: '2026-11-07T10:00:00Z', processed_at: '2026-11-07T10:00:01Z',
      source_id: 'producer-1', source_sequence: 9, attempts: 1,
      retry_audit_count: 0, terminal_disposition_count: 0,
      consumer_drain_reference_count: 0,
    }],
  };
  const userSettings = {
    databasePath: path.join(projectRoot, 'curator.sqlite3'),
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
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
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showInputBox: async (options) => {
      rationalePrompt = options;
      return 'Archive confirmed processed receipts after retention review.';
    },
    showWarningMessage: async (message, options, choice) => {
      confirmation = message;
      confirmationOptions = options;
      return choice;
    },
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => messages.push(message),
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose() {},
    }),
  };
  try {
    await showDashboard((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        {
          event_receipt_compaction_propose: proposal,
          event_receipt_compaction_archive: (arguments_) => ({
            archive_id: arguments_.archive_id,
            project_id: 'alpha', reviewer_id: 'reviewer-1',
            inventory_sha256: arguments_.inventory_sha256,
            offset: arguments_.offset, event_ids: arguments_.event_ids,
            approval_reason: arguments_.approval_reason,
            archived_at: '2026-11-07T10:01:00Z',
          }),
        },
      );
      launched.push({ args, child });
      return child;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    await receiveMessage({
      type: 'archiveEventReceiptPage', offset: 0,
      manifestSha256: proposal.manifest_sha256,
      eventIds: ['evt-processed-1'],
    });
    assert.equal(launched.length, 4);
    assert.ok(!launched[1].args.includes('--allow-write'));
    assert.ok(launched[2].args.includes('--allow-write'));
    assert.equal(rationalePrompt.title, 'Reason for archiving processed event receipts');
    assert.match(confirmation, /1 processed event receipt/);
    assert.deepEqual(confirmationOptions, { modal: true, detail: confirmationOptions.detail });
    assert.match(confirmationOptions.detail, /Inventory SHA-256/);
    assert.match(confirmationOptions.detail, /payload-free/);
    assert.match(confirmationOptions.detail, /Failed, quarantined, active, and unknown events are not eligible/);
    const writeCalls = launched[2].child.requests;
    assert.ok(writeCalls.some((request) => request.params?.name === 'event_receipt_compaction_propose'));
    const archive = writeCalls.find((request) => request.params?.name === 'event_receipt_compaction_archive');
    assert.ok(archive);
    assert.deepEqual(archive.params.arguments.event_ids, ['evt-processed-1']);
    assert.equal(archive.params.arguments.inventory_sha256, proposal.manifest_sha256);
    assert.equal(archive.params.arguments.offset, 0);
    assert.equal(archive.params.arguments.approval_reason,
      'Archive confirmed processed receipts after retention review.');
    assert.equal(messages.find((message) => message.type === 'eventArchiveResult').success, true);
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('held artifact recovery rechecks and confirms one receipt-scoped hold release', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-hold-release-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const messages = [];
  const launched = [];
  let receiveMessage;
  let releaseCalled = false;
  let inputOptions;
  let confirmation;
  const userSettings = {
    databasePath: path.join(projectRoot, 'curator.sqlite3'),
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
  };
  const heldTarget = {
    artifact: { path: 'goal-1/held.bin', sha256: 'c'.repeat(64) },
    status: 'held', outcome: 'held', attempts: 1, error: 'retention_hold',
    next_attempt_in_seconds: null, safe_recovery_action: 'release_artifact_hold',
    approval_stale: false,
  };
  const readyTarget = {
    ...heldTarget, status: 'pending', outcome: null, error: null,
    safe_recovery_action: 'retry_pending_purges',
  };
  const receipt = {
    receipt_id: 'receipt-held', purge_status: 'purge_pending',
    canonical_persisted: true, cleanup_authorized: true,
    cleanup_canonical_persisted: true,
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showInputBox: async (options) => { inputOptions = options; return 'Owner confirmed no retention need.'; },
    showWarningMessage: async (...args) => { confirmation = args; return 'Release this hold and retry'; },
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => messages.push(message),
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose() {},
    }),
  };
  try {
    await showDashboard((command, args) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        {
          artifact_purge_status: () => [receipt, [releaseCalled ? readyTarget : heldTarget]],
          release_artifact_hold: ({ receipt_id }) => {
            releaseCalled = true;
            return { receipt_id, purge_status: 'purge_pending' };
          },
        },
      );
      launched.push({ args, child });
      return child;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    await receiveMessage({
      type: 'releaseArtifactHold', receiptId: 'receipt-held', artifactPath: 'goal-1/held.bin',
    });
    assert.equal(inputOptions.title, 'Release one cleanup hold');
    assert.match(confirmation[0], /goal-1\/held\.bin/);
    assert.deepEqual(confirmation[1], { modal: true, detail: confirmation[1].detail });
    assert.match(confirmation[1].detail, /Project: alpha/);
    assert.match(confirmation[1].detail, /only this receipt/);
    assert.equal(launched.length, 3);
    assert.ok(!launched[1].args.includes('--allow-write'));
    assert.ok(launched[2].args.includes('--allow-retention-hold-release'));
    assert.ok(launched[2].child.requests.some((request) => request.params?.name === 'release_artifact_hold'));
    assert.equal(messages.at(-1).type, 'purgeReceiptHoldResult');
    assert.equal(messages.at(-1).success, true);
    assert.match(messages.at(-1).summary, /current receipt state is purge_pending/);
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('dashboard refreshes the authoritative queue before opening the pending review document', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-recovery-toolbox-'));
  const reviewPath = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
  fs.mkdirSync(path.dirname(reviewPath), { recursive: true, mode: 0o700 });
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [{
    candidate: {
      candidate_id: 'accepted-candidate', goal_id: 'goal-1', status: 'pending_review',
      materiality: 'decision', rationale: 'Keep the accepted decision in the local queue until refreshed.',
    },
    goal: { goal_id: 'goal-1', project_id: 'alpha', problem: 'Refresh the accepted review.' },
  }], new Map()), true);

  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const previousUri = vscodeMock.Uri;
  let receiveMessage;
  let openedPath;
  let shownDocument;
  const launched = [];
  const warnings = [];
  const userSettings = {
    databasePath: path.join(projectRoot, 'curator.sqlite3'),
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    hermesCommand: 'fixture-hermes',
    evidenceConfig: '',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    textDocuments: [],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
    openTextDocument: async (uri) => {
      openedPath = uri.fsPath;
      return { uri, getText: () => fs.readFileSync(uri.fsPath, 'utf8') };
    },
  };
  vscodeMock.window = {
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: () => {},
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose: () => {},
    }),
    showTextDocument: async (document) => { shownDocument = document; },
    showWarningMessage: async (message) => { warnings.push(message); },
    showErrorMessage: assert.fail,
  };
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.Uri = { file: (fsPath) => ({ fsPath }) };

  try {
    await showDashboard((command, args) => {
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        { sde_review_outline: {
          project_id: 'alpha', candidate_id: 'accepted-candidate', status: 'accepted',
        } },
      );
      launched.push({ command, args, child });
      return child;
    });
    await receiveMessage({ type: 'openPendingReview' });
    assert.equal(openedPath, reviewPath);
    assert.equal(shownDocument.uri.fsPath, reviewPath);
    assert.equal(launched.length, 1);
    assert.ok(launched[0].args.includes('--allow-review'));
    assert.ok(launched[0].child.requests.some((request) => request.params?.name === 'sde_review_queue_cards'));
    assert.ok(launched[0].child.requests.some((request) => request.params?.name === 'event_queue_status'));
    assert.doesNotMatch(fs.readFileSync(reviewPath, 'utf8'), /accepted-candidate/);
    assert.match(fs.readFileSync(reviewPath, 'utf8'), /No pending candidates\./);
    assert.equal(JSON.parse(fs.readFileSync(path.join(projectRoot, '.curatormd-v2', 'inbox', 'status.json'), 'utf8')).project_id, 'alpha');
    assert.deepEqual(warnings, []);
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
    vscodeMock.Uri = previousUri;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
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
  activate({ subscriptions: { push: (...values) => subscriptions.push(...values) } },
    () => new FakeMcpProcess('a'.repeat(64), false, null, null, true));

  assert.equal(items.length, 1);
  assert.equal(items[0].alignment, vscodeMock.StatusBarAlignment.Left);
  assert.equal(items[0].priority, 0);
  assert.equal(items[0].text, '$(circle-filled) CuratorMD V2');
  assert.equal(items[0].color.id, 'textLink.foreground');
  assertTooltipIncludesCurrentVersion(items[0]);
  assert.match(items[0].tooltip, /Blue means no health read has been attempted/);
  assert.match(items[0].tooltip, /Command Palette: CuratorMD V2: Open Recovery Manager/);
  assert.equal(commands[0].name, 'curatormdV2.openDashboard');
  assert.equal(commands[1].name, 'curatormdV2.openHealingToolbox');
  assert.equal(extensionManifest.contributes.commands[1].title, 'CuratorMD V2: Open Recovery Manager');
  assert.equal(commands.length, 4);
  assert.equal(subscriptions.length, 6);

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
  assert.match(items[0].tooltip, /Click to open pending-review\.md/);
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
    vscodeMock.window.showWarningMessage = assert.fail;
    await commands[2].handler();
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
  assert.equal(resolveDatabasePath('missing', bindings, '/state/default.sqlite3'), null);
  assert.equal(resolveDatabasePath('alpha', {}, '/state/default.sqlite3'), '/state/default.sqlite3');
  assert.equal(resolveDatabasePath('alpha', null, '/state/default.sqlite3'), null);
  assert.equal(resolveDatabasePath('alpha', [], '/state/default.sqlite3'), null);
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

test('router command defaults beside MCP and accepts only a bounded single-project result', async () => {
  assert.equal(
    defaultRouterCommand('/opt/curator tools/bin/curatormd-v2-mcp'),
    '/opt/curator tools/bin/curatormd-v2-router',
  );
  assert.equal(defaultRouterCommand('curatormd-v2-mcp'), 'curatormd-v2-router');
  const wire = JSON.stringify({
    attempted: 3, claim_lost: 0, failed: 1, processed: 2, project_count: 1,
    pending: 1, quarantined: 0, claimed: 0, expired_claims: 0,
  });
  assert.deepEqual(parseRouterPassResult(wire, 1), {
    exitCode: 1, attempted: 3, claimLost: 0, failed: 1, processed: 2,
    pending: 1, quarantined: 0, claimed: 0, expiredClaims: 0,
  });
  assert.throws(() => parseRouterPassResult(wire, 2), (error) => error.code === 'router-result-invalid');
  assert.throws(() => parseRouterPassResult(JSON.stringify({
    ...JSON.parse(wire), project_count: 2,
  }), 0), (error) => error.code === 'router-result-invalid');

  let invocation;
  const result = await runEventRouterPass(
    '/opt/curator tools/bin/curatormd-v2-router', '/workspace/project',
    '/data/project.sqlite3', (command, args, options) => {
      invocation = { command, args, options };
      const child = new EventEmitter();
      child.stdout = new PassThrough();
      child.stderr = new PassThrough();
      child.kill = () => { child.emit('close', null); };
      setImmediate(() => {
        child.stdout.end(wire);
        child.emit('close', 1, null);
      });
      return child;
    }, 25,
  );
  assert.deepEqual(invocation, {
    command: '/opt/curator tools/bin/curatormd-v2-router',
    args: [
      '--database', '/data/project.sqlite3', '--project-root', '/workspace/project',
      '--batch-limit', '25', '--route-events',
    ],
    options: {
      cwd: '/workspace/project', shell: false, windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  });
  assert.equal(result.processed, 2);
});

test('one-shot routing is scoped to the configured project and requires attended confirmation', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-router-pass-'));
  fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
  const previousWorkspace = vscodeMock.workspace;
  const previousWindow = vscodeMock.window;
  const previousViewColumn = vscodeMock.ViewColumn;
  const messages = [];
  const launched = [];
  let receiveMessage;
  let confirmation = '';
  let confirmationOptions;
  let routerInvocation;
  const databasePath = path.join(projectRoot, 'curator.sqlite3');
  const serverCommand = path.join(projectRoot, 'venv', 'bin', 'curatormd-v2-mcp');
  const userSettings = {
    databasePath,
    profileId: 'fixture-profile',
    hermesProfileBindings: { alpha: 'fixture-profile' },
    serverCommand,
    hermesCommand: 'fixture-hermes',
  };
  vscodeMock.workspace = {
    workspaceFolders: [{ uri: { fsPath: projectRoot } }],
    getConfiguration: () => ({
      get: (key, fallback) => userSettings[key] || fallback,
      inspect: () => ({ globalValue: true }),
    }),
  };
  vscodeMock.ViewColumn = { One: 1 };
  vscodeMock.window = {
    showWarningMessage: async (text, options, choice) => {
      confirmation = text;
      confirmationOptions = options;
      return choice;
    },
    showErrorMessage: assert.fail,
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => messages.push(message),
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose() {},
    }),
  };
  const queue = {
    received_count: 2, failed_count: 1, quarantined_count: 3,
    claimed_count: 4, expired_claim_count: 1,
  };
  try {
    await showDashboard((command, args, options) => {
      if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
      if (command === path.join(projectRoot, 'venv', 'bin', 'curatormd-v2-router')) {
        routerInvocation = { command, args, options };
        const child = new EventEmitter();
        child.stdout = new PassThrough();
        child.stderr = new PassThrough();
        child.kill = () => { child.emit('close', null); };
        setImmediate(() => {
          child.stdout.end(JSON.stringify({
            attempted: 3, claim_lost: 0, failed: 1, processed: 2, project_count: 1,
            pending: 1, quarantined: 3, claimed: 1, expired_claims: 1,
          }));
          child.emit('close', 1, null);
        });
        return child;
      }
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, true, new Set(), null, null,
        { event_queue_status: queue },
      );
      launched.push({ command, args, options, child });
      return child;
    });
    await receiveMessage({ type: 'loadGoals', offset: 0 });
    await receiveMessage({ type: 'runEventRouter' });
    assert.ok(confirmation.includes('project alpha'));
    assert.deepEqual(confirmationOptions, { modal: true, detail: confirmationOptions.detail });
    assert.match(confirmationOptions.detail, /2 received, 1 failed, 3 quarantined/);
    assert.match(confirmationOptions.detail, /their recorded goal and fact updates/);
    assert.ok(routerInvocation);
    assert.deepEqual(routerInvocation.args, [
      '--database', databasePath,
      '--project-root', projectRoot,
      '--batch-limit', '100',
      '--route-events',
    ]);
    assert.equal(routerInvocation.options.shell, false);
    const result = messages.find((message) => message.type === 'eventRouterResult');
    assert.equal(result.success, true);
    assert.equal(result.ran, true);
    assert.match(result.summary, /processed 2, failed 1/);
    assert.match(result.summary, /Queue work remains; health stays gated/);
    assert.ok(launched.some(({ child }) => child.requests.some(
      (request) => request.params?.name === 'event_queue_status',
    )));
  } finally {
    vscodeMock.workspace = previousWorkspace;
    vscodeMock.window = previousWindow;
    vscodeMock.ViewColumn = previousViewColumn;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('the extension exposes dashboard and healing commands without palette task creation', () => {
  assert.deepEqual(extensionManifest.contributes.commands.map((command) => command.command), [
    'curatormdV2.openDashboard',
    'curatormdV2.openHealingToolbox',
    'curatormdV2.joinMarkdownParagraphLines',
  ]);
  assert.equal(extensionManifest.contributes.commands[1].title, 'CuratorMD V2: Open Recovery Manager');
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
  const reviewErrors = [];
  let receiveMessage;
  let disposePanel;
  let panelDisposed = false;
  let failNextSpawn = false;
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
    showErrorMessage: (message) => { reviewErrors.push(message); },
    createTerminal: (options) => ({
      show: () => terminalCalls.push({ action: 'show', options }),
      sendText: (text, addNewLine) => terminalCalls.push({ action: 'sendText', text, addNewLine }),
    }),
    createWebviewPanel: () => ({
      webview: {
        cspSource: 'vscode-webview:',
        postMessage: (message) => {
          if (panelDisposed) throw new Error('Webview is disposed');
          messages.push(message);
        },
        onDidReceiveMessage: (handler) => { receiveMessage = handler; },
      },
      onDidDispose: (handler) => {
        disposePanel = () => {
          panelDisposed = true;
          handler();
        };
      },
    }),
  };

  const launchArguments = [];
  await showDashboard((command, args) => {
    if (command === 'fixture-hermes') return new FakeHermesProcess(healthyHermesProbe());
    if (failNextSpawn) {
      failNextSpawn = false;
      throw new Error('fixture process failed after the dashboard closed');
    }
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
  assert.equal(terminalCalls.length, 0, 'review actions must never launch an interactive terminal');
  assert.equal(reviewErrors.length, 1);
  assert.match(reviewErrors[0], /review was not recorded/);
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
  assert.equal(terminalCalls.length, 0, 'a denied read clears cached review authority');
  disposePanel();
  failNextSpawn = true;
  await assert.doesNotReject(() => receiveMessage({ type: 'loadGoals', offset: 0 }));
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
  healthComponentRows: healthComponentRows(healthyHermesProbe('alpha').health, 'alpha'),
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
  storage: storageSnapshot,
  hostFilesystemRows: hostFilesystemRows('/workspace', '/data/curator.sqlite', () => ({
    bsize: 4096, blocks: 1000, bfree: 900, bavail: 800,
  })) } });
  const goalCard = elements.get('goals').children[0];
  assert.equal(goalCard.children[0].textContent, 'Vhost Manager SSL renewal completed (exit code 0)');
  assert.equal(goalCard.children[1].children[0].textContent, 'Disposition: active');
  assert.equal(goalCard.children[1].children[1].textContent, 'Updated 2026-10-30 19:23 +07');
  assert.equal(goalCard.children[1].children[2].textContent, 'Next: Review the latest run.');
  assert.match(elements.get('health').textContent, /^Project health: healthy · no open gates\. Checked .* \+07$/);
  assert.equal(elements.get('healthPanel').attributes['data-state'], 'healthy');
  assert.equal(elements.get('healthRows').children[0].children[1].textContent, 'healthy');
  assert.equal(elements.get('healthRows').children.length, 10);
  assert.equal(elements.get('healthRows').children[3].children[0].textContent, 'event router');
  assert.match(elements.get('healthRows').children[3].children[1].textContent, /^healthy · checked /);
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
  assert.match(elements.get('storage').textContent, /^SQLite 9\.0 KiB · staging 128 B · workspace free Used /);
  assert.equal(elements.get('storageRows').children.length, 11);
  assert.equal(elements.get('storageRows').children[6].children[1].textContent, '9.0 KiB / 250.0 MiB');
  assert.equal(elements.get('storageRows').children[9].children[0].textContent, 'Workspace filesystem');
  assert.equal(elements.get('storageRows').children[9].children[2].attributes['data-state'], 'healthy');
  receiveWindowMessage({ data: { type: 'goals', page: {
    project_id: 'alpha', total: 1, offset: 0, goals: [], next_offset: null,
  }, storage: storageSnapshot, hostFilesystemRows: hostFilesystemRows(
    '/workspace', '/data/curator.sqlite', () => ({
      bsize: 4096, blocks: 1000, bfree: 80, bavail: 50,
    }),
  ) } });
  assert.equal(elements.get('storageRows').children[9].children[2].attributes['data-state'], 'warning');
  assert.equal(elements.get('storagePanel').attributes['data-state'], 'warning');
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

    const reviewOnly = writeWorkspaceQueueViewsDetailed(projectRoot, 'alpha', null, {
      project_id: 'alpha',
      candidates: [{
        candidate: {
          candidate_id: 'candidate-2', goal_id: 'goal-2', status: 'pending_review',
          materiality: 'decision', rationale: 'Refresh the review projection independently.',
        },
        goal: {
          goal_id: 'goal-2', project_id: 'alpha', problem: 'Review projection recovery',
        },
      }],
    }, new Map(), new Set(['candidate-1']));
    assert.deepEqual(reviewOnly, {
      reviewQueueUpdated: true,
      reviewDocumentUpdated: true,
      inboxUpdated: false,
      allUpdated: false,
    });
    assert.match(fs.readFileSync(
      path.join(projectRoot, '.curatormd-v2/sde-proposals/pending-review.md'), 'utf8',
    ), /Review projection recovery/);
    const staleInbox = JSON.parse(fs.readFileSync(inboxPath, 'utf8'));
    staleInbox.generated_at = new Date(Date.now() - (10 * 60 * 1000)).toISOString();
    fs.writeFileSync(inboxPath, JSON.stringify(staleInbox));
    assert.deepEqual(
      workspaceQueueViewsConfirmResolved(projectRoot, 'alpha', 'candidate-1'),
      {
        reviewDocumentResolved: true,
        reviewQueueResolved: true,
        inboxFresh: false,
        allResolved: false,
      },
    );
    const oldInboxTimestamp = Date.parse(staleInbox.generated_at);
    const refreshedStaleProjections = writeWorkspaceQueueViewsDetailed(
      projectRoot,
      'alpha',
      {
        received_count: 2,
        failed_count: 1,
        quarantined_count: 0,
        oldest_pending_received_at: '2026-10-30T10:00:00+07:00',
        oldest_pending_age_seconds: 60,
        claimed_count: 1,
        expired_claim_count: 0,
      },
      {
        project_id: 'alpha',
        candidates: [{
          candidate: {
            candidate_id: 'candidate-2', goal_id: 'goal-2', status: 'pending_review',
            materiality: 'decision', rationale: 'Refresh the review projection independently.',
          },
          goal: {
            goal_id: 'goal-2', project_id: 'alpha', problem: 'Review projection recovery',
          },
        }],
      },
      new Map(),
      new Set(['candidate-1']),
    );
    assert.deepEqual(refreshedStaleProjections, {
      reviewQueueUpdated: true,
      reviewDocumentUpdated: true,
      inboxUpdated: true,
      allUpdated: true,
    });
    const refreshedInbox = JSON.parse(fs.readFileSync(inboxPath, 'utf8'));
    assert.ok(Date.parse(refreshedInbox.generated_at) > oldInboxTimestamp);
    assert.deepEqual(
      workspaceQueueViewsConfirmResolved(projectRoot, 'alpha', 'candidate-1'),
      {
        reviewDocumentResolved: true,
        reviewQueueResolved: true,
        inboxFresh: true,
        allResolved: true,
      },
    );
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

test('pending review keeps completion claims separate from verified successful work', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-completion-'));
  const projectId = 'alpha';
  const candidateId = 'candidate-completion-42';
  const candidate = {
    candidate_id: candidateId,
    goal_id: 'goal-completion-42',
    status: 'pending_review',
    materiality: 'verified_lesson',
    rationale: 'Retain the completed task result for owner review.',
  };
  const claim = {
    fact_id: 'completion-fact-42',
    criterion_id: 'works',
    bullet: 'Completion claim: Checks passed: `npm test` passed.',
  };
  const outline = {
    project_id: projectId,
    candidate_id: candidateId,
    goal_id: candidate.goal_id,
    status: 'pending_review',
    goal_status: 'complete',
    evidence_status: 'current_passing',
    successful_completion_evidence_current: true,
    completion_claim: claim,
    supporting_facts: [{
      fact_id: 'change-fact-42',
      kind: 'change',
      bullet: 'The tested change is ready for review.',
    }],
  };
  const review = {
    candidate,
    goal: {
      goal_id: candidate.goal_id,
      project_id: projectId,
      problem: 'Render local completion proof in the pending review document.',
    },
  };
  try {
    initializeWorkspaceAreas(projectRoot);
    assert.equal(writePendingReviewDocument(
      projectRoot, projectId, [review], new Map([[candidateId, outline]]),
    ), true);
    const reviewPath = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    const documentText = fs.readFileSync(reviewPath, 'utf8');
    assert.match(documentText, /- Completed successfully:\n  - No recorded passing verification supports a successful-completion claim\./);
    assert.doesNotMatch(documentText, /- Completed successfully:\n  - Completion claim: Checks passed:/);
    const jsonFences = [...documentText.matchAll(/```json\n([\s\S]*?)\n```/g)];
    assert.equal(jsonFences.length, 2);
    assert.equal(jsonFences[0][1], jsonFences[1][1]);
    assert.deepEqual(JSON.parse(jsonFences[0][1]).completed, []);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('completed SDE review refresh reloads the open dashboard for its project', async () => {
  const previousWorkspace = vscodeMock.workspace;
  const projectRoot = '/tmp/curator-review-dashboard-refresh';
  const messages = [];
  let disposeDashboard;
  try {
    vscodeMock.workspace = { workspaceFolders: [] };
    registerDashboardReloader(projectRoot, async () => {
      messages.push({ type: 'reloadGoals' });
    }, { onDidDispose: (dispose) => { disposeDashboard = dispose; } });

    await refreshReviewConsumers(projectRoot);
    assert.deepEqual(messages, [{ type: 'reloadGoals' }]);

    disposeDashboard();
    await refreshReviewConsumers(projectRoot);
    assert.deepEqual(messages, [{ type: 'reloadGoals' }]);
  } finally {
    vscodeMock.workspace = previousWorkspace;
  }
});

for (const inventoryComplete of [true, false]) test(`pending SDE Accept allows missing evidence with inventory complete=${inventoryComplete}`, async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-flow-'));
  const projectId = 'alpha';
  const candidateId = 'candidate-42';
  const candidate = {
    candidate_id: candidateId,
    goal_id: 'goal-42',
    status: 'pending_review',
    materiality: 'decision',
    rationale: 'Retain the verified project decision.',
  };
  const target = 'persistence/HISTORY.md';
  const outline = {
    project_id: projectId,
    candidate_id: candidateId,
    goal_id: candidate.goal_id,
    status: 'pending_review',
    evidence_status: 'not_current_or_missing',
    successful_completion_evidence_current: false,
    persistence_documents: [target],
    supporting_facts: [],
  };
  const remainingCandidate = {
    candidate_id: 'candidate-remaining-43',
    goal_id: 'goal-remaining-43',
    status: 'pending_review',
    materiality: 'routine',
    rationale: 'Keep the other pending proposal available for review.',
  };
  const remainingOutline = {
    project_id: projectId,
    candidate_id: remainingCandidate.candidate_id,
    goal_id: remainingCandidate.goal_id,
    status: 'pending_review',
    evidence_status: 'current_passing',
    successful_completion_evidence_current: true,
    persistence_documents: [target],
    supporting_facts: [],
  };
  const artifact = {
    path: 'goal-42/scratch/review-cue.bin',
    sha256: 'e'.repeat(64),
    device_id: 12,
    inode_id: 34,
    occurrence_id: 'occurrence-42',
    retention_hold: null,
    reacquisition_action: 'not_recorded',
  };
  const packet = {
    detail: { candidate },
    artifact_inventory: {
      usage: { inventory_complete: inventoryComplete },
      manifest_sha256: inventoryComplete ? 'a'.repeat(64) : null,
      artifacts: [artifact],
    },
    dependency_map_sha256: 'b'.repeat(64),
    artifact_dependencies: [{ artifact, evidence_dependencies: [] }],
  };
  const binding = { sha256: 'c'.repeat(64), binding: {} };
  const reviewResponses = {
    sde_review_outline: outline,
    sde_review_packet: packet,
    sde_prepare_review_binding: binding,
    sde_confirm: { receipt_id: 'receipt-42' },
    sde_project_review_target: 'written',
    sde_review_projection_status: [[target, 'd'.repeat(64), '2026-11-04T00:00:00+00:00']],
    sde_finalize_review_projection: { receipt_id: 'receipt-42', purge_status: inventoryComplete ? 'complete' : 'purge_pending' },
    artifact_purge_status: [{ receipt_id: 'receipt-42', purge_status: inventoryComplete ? 'complete' : 'purge_pending' }, []],
  };
  const projectFile = path.join(projectRoot, '.curatormd-v2.toml');
  fs.writeFileSync(projectFile, 'project_id = "alpha"\n');
  const priorWorkspace = vscodeMock.workspace;
  const priorWindow = vscodeMock.window;
  const priorUri = vscodeMock.Uri;
  const priorRange = vscodeMock.Range;
  const priorCodeLens = vscodeMock.CodeLens;
  const children = [];
  const launchArgs = [];
  const warnings = [];
  const information = [];
  const errors = [];
  const terminalCalls = [];
  const quickPickCalls = [];
  let reviewRefreshCompleted = false;
  const settings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
    evidenceConfig: '/tmp/evidence.json',
  };
  try {
    initializeWorkspaceAreas(projectRoot);
    fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
    const reviewPath = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    assert.equal(writePendingReviewDocument(projectRoot, projectId, [{
      candidate,
      goal: { goal_id: candidate.goal_id, project_id: projectId, problem: 'Smoke goal' },
    }, {
      candidate: remainingCandidate,
      goal: {
        goal_id: remainingCandidate.goal_id,
        project_id: projectId,
        problem: 'Keep the remaining proposal in the queue.',
      },
    }], new Map([[candidateId, outline], [remainingCandidate.candidate_id, remainingOutline]])), true);
    let documentText = fs.readFileSync(reviewPath, 'utf8');
    let documentDirty = false;
    const document = {
      uri: { fsPath: reviewPath },
      get isDirty() { return documentDirty; },
      get lineCount() { return documentText.split('\n').length; },
      lineAt: (line) => ({ text: documentText.split('\n')[line] }),
      getText: () => documentText,
      positionAt: (offset) => ({ offset }),
      save: async () => {
        fs.writeFileSync(reviewPath, documentText, 'utf8');
        documentDirty = false;
        return true;
      },
    };
    vscodeMock.Uri = { file: (fsPath) => ({ fsPath }) };
    vscodeMock.Range = class Range {
      constructor(start, end) { this.start = start; this.end = end; }
    };
    vscodeMock.WorkspaceEdit = class WorkspaceEdit {
      replace(uri, range, replacement) { this.change = { uri, range, replacement }; }
    };
    vscodeMock.CodeLens = class CodeLens {
      constructor(range, command) { this.range = range; this.command = command; }
    };
    vscodeMock.workspace = {
      workspaceFolders: [{ uri: { fsPath: projectRoot } }],
      textDocuments: [document],
      openTextDocument: async () => document,
      applyEdit: async (edit) => {
        assert.equal(edit.change.uri.fsPath, reviewPath);
        documentText = documentText.slice(0, edit.change.range.start.offset)
          + edit.change.replacement + documentText.slice(edit.change.range.end.offset);
        documentDirty = true;
        return true;
      },
      getConfiguration: () => ({
        get: (key, fallback) => settings[key] ?? fallback,
        inspect: () => ({ globalValue: true }),
      }),
    };
    vscodeMock.window = {
      showTextDocument: async () => ({ document }),
      showQuickPick: async (items, options) => {
        quickPickCalls.push({ items, options });
        return options.canPickMany ? items : items[0];
      },
      showWarningMessage: async (message, options, confirmation) => {
        warnings.push({ message, options, confirmation });
        return confirmation;
      },
      showInformationMessage: async (message) => { information.push(message); },
      showErrorMessage: async (message) => { errors.push(message); },
      createTerminal: () => { terminalCalls.push('opened'); throw new Error('terminal opened'); },
    };

    const actionLine = documentText.split('\n').findIndex(
      (line) => line === `<!-- curator-v2-actions: ${candidateId} -->`,
    );
    const headingLine = documentText.split('\n').findIndex(
      (line) => line.endsWith('Editable decision'),
    );
    const lenses = reviewDocumentActions(document);
    const selectedLenses = lenses.filter((lens) => lens.command.arguments[0] === candidateId);
    assert.equal(selectedLenses.length, 4);
    assert.ok(actionLine < headingLine);
    assert.deepEqual(selectedLenses.map((lens) => lens.command.title), ['Accept', 'Reject', 'Withdraw', 'Refresh evidence']);

    await launchDocumentReview(candidateId, 'approve', (command, args) => {
      launchArgs.push({ command, args });
      const isFinalReviewProcess = children.length === 3;
      const processResponses = isFinalReviewProcess ? {
        ...reviewResponses,
        sde_review_outline: ({ candidate_id: requestedCandidateId }) => (
          requestedCandidateId === candidateId
            ? { ...outline, status: 'approved' } : remainingOutline
        ),
        sde_review_queue_cards: {
          project_id: projectId,
          candidates: [{
            candidate: remainingCandidate,
            goal: {
              goal_id: remainingCandidate.goal_id,
              project_id: projectId,
              problem: 'Keep the remaining proposal in the queue.',
            },
          }],
        },
        event_queue_status: {
          received_count: 0,
          failed_count: 2,
          quarantined_count: 0,
          claimed_count: 0,
          expired_claim_count: 0,
          oldest_pending_age_seconds: null,
          oldest_pending_received_at: null,
        },
      } : reviewResponses;
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, false, new Set(), null, null, processResponses,
      );
      children.push(child);
      return child;
    }, async (refreshedRoot) => {
      assert.equal(refreshedRoot, projectRoot);
      reviewRefreshCompleted = true;
    });

    assert.equal(errors.length, 0);
    assert.deepEqual(terminalCalls, []);
    assert.equal(warnings.length, inventoryComplete ? 1 : 2);
    assert.match(warnings[0].message, /Accept SDE candidate-42/);
    assert.match(warnings[0].options.detail, /Automated evidence is missing or stale/);
    assert.match(warnings[0].options.detail, inventoryComplete
      ? /verified; eligible transient artifacts then clear automatically/
      : /inventory is incomplete.*cleanup remains pending/);
    assert.doesNotMatch(warnings[0].options.detail, /cleanup approval|Inventory SHA-256|Dependency map SHA-256/);
    assert.equal(quickPickCalls.length, 0, 'acceptance does not open a selection palette');
    assert.equal(information.length, inventoryComplete ? 1 : 0);
    if (inventoryComplete) assert.match(information[0], /accepted and receipt receipt-42 finalized/);
    else assert.match(warnings[1].message, /cleanup status is purge_pending/);
    assert.equal(reviewRefreshCompleted, true);
    assert.match(documentText, /candidate-remaining-43/);
    assert.doesNotMatch(documentText, /candidate-42/);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending.json',
    ), 'utf8')).candidates.map(({ candidate: pending }) => pending.candidate_id), [
      'candidate-remaining-43',
    ]);
    assert.equal(JSON.parse(fs.readFileSync(path.join(
      projectRoot, '.curatormd-v2', 'inbox', 'status.json',
    ), 'utf8')).failed_count, 2, 'successful review refresh preserves independent failed receipts');
    assert.equal(children.length, 4);
    assert.ok(launchArgs.slice(0, 3).every(({ args }) => args.includes('--allow-review')
      && !args.includes('--allow-write')));
    assert.ok(launchArgs[3].args.includes('--allow-review'));
    assert.ok(launchArgs[3].args.includes('--allow-write'));
    const confirm = children[3].requests.find(
      (request) => request.params?.name === 'sde_confirm',
    );
    assert.ok(confirm);
    assert.equal(confirm.params.arguments.decision, 'approved');
    assert.equal(confirm.params.arguments.artifact_inventory_complete, inventoryComplete);
    if (!inventoryComplete) assert.equal(confirm.params.arguments.dependency_map_sha256, '0'.repeat(64));
    assert.equal(confirm.params.arguments.evidence_override_reason, null);
    assert.equal(confirm.params.arguments.expected_review_binding_sha256, binding.sha256);
    assert.deepEqual(
      JSON.parse(confirm.params.arguments.review_draft_json).documents,
      [target],
    );
    assert.deepEqual(confirm.params.arguments.artifacts, inventoryComplete ? [{
      path: artifact.path,
      sha256: artifact.sha256,
      device_id: artifact.device_id,
      inode_id: artifact.inode_id,
      occurrence_id: artifact.occurrence_id,
      reacquisition_action: 'not_required',
    }] : []);
    assert.ok(children[3].requests.some(
      (request) => request.params?.name === 'sde_finalize_review_projection',
    ));
    assert.ok(children[2].requests.some(
      (request) => request.params?.name === 'sde_prepare_review_binding'
        && request.params.arguments.decision === 'approved',
    ));
    assert.ok(children[3].requests.some(
      (request) => request.params?.name === 'sde_prepare_review_binding'
        && request.params.arguments.decision === 'approved',
    ));
    assert.ok(children[3].requests.some(
      (request) => request.params?.name === 'artifact_purge_status',
    ));
    assert.ok(children[3].requests.some(
      (request) => request.params?.name === 'sde_review_queue_cards',
    ));
    assert.ok(children[3].requests.some(
      (request) => request.params?.name === 'event_queue_status',
    ));
    assert.ok(children.every((child) => child.requests.every(
      (request) => request.params?.name !== 'artifact_cleanup_approve',
    )));
  } finally {
    vscodeMock.workspace = priorWorkspace;
    vscodeMock.window = priorWindow;
    vscodeMock.Uri = priorUri;
    vscodeMock.Range = priorRange;
    vscodeMock.CodeLens = priorCodeLens;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('pending SDE Withdraw clears one stale proposal in VS Code and retains its audit receipt', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-withdraw-'));
  const projectId = 'alpha';
  const candidateId = 'candidate-withdraw-42';
  const candidate = {
    candidate_id: candidateId,
    goal_id: 'goal-withdraw-42',
    status: 'pending_review',
    materiality: 'implementation',
    rationale: 'Clear this stale alpha test proposal.',
  };
  const outline = {
    project_id: projectId,
    candidate_id: candidateId,
    goal_id: candidate.goal_id,
    status: 'pending_review',
    evidence_status: 'not_current_or_missing',
    supporting_facts: [{ fact_id: 'fact-retained-42' }],
  };
  const withdrawal = {
    withdrawal_id: 'withdrawal-42',
    project_id: projectId,
    candidate_id: candidateId,
    reviewer_id: 'local-uid:1000',
    rationale: 'Clear stale alpha proposal before retest.',
    candidate_sha256: 'd'.repeat(64),
  };
  const reviewResponses = {
    sde_review_outline: outline,
    sde_withdraw_candidates: [withdrawal],
  };
  const priorWorkspace = vscodeMock.workspace;
  const priorWindow = vscodeMock.window;
  const priorUri = vscodeMock.Uri;
  const priorRange = vscodeMock.Range;
  const priorCodeLens = vscodeMock.CodeLens;
  const children = [];
  const launchArgs = [];
  const warnings = [];
  const information = [];
  const errors = [];
  const terminalCalls = [];
  const settings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
  };
  try {
    initializeWorkspaceAreas(projectRoot);
    fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
    const reviewPath = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    assert.equal(writePendingReviewDocument(projectRoot, projectId, [{
      candidate,
      goal: { goal_id: candidate.goal_id, project_id: projectId, problem: 'Smoke goal' },
    }], new Map([[candidateId, outline]])), true);
    const documentText = fs.readFileSync(reviewPath, 'utf8');
    assert.doesNotMatch(documentText, /Edit this JSON copy to change the significance rating/);
    assert.doesNotMatch(documentText, /These actions do not open a terminal/);
    const document = {
      uri: { fsPath: reviewPath },
      isDirty: false,
      get lineCount() { return documentText.split('\n').length; },
      lineAt: (line) => ({ text: documentText.split('\n')[line] }),
      getText: () => documentText,
      save: async () => true,
    };
    vscodeMock.Uri = { file: (fsPath) => ({ fsPath }) };
    vscodeMock.Range = class Range {
      constructor(start, end) { this.start = start; this.end = end; }
    };
    vscodeMock.CodeLens = class CodeLens {
      constructor(range, command) { this.range = range; this.command = command; }
    };
    vscodeMock.workspace = {
      workspaceFolders: [{ uri: { fsPath: projectRoot } }],
      textDocuments: [document],
      openTextDocument: async () => document,
      getConfiguration: () => ({
        get: (key, fallback) => settings[key] ?? fallback,
        inspect: () => ({ globalValue: true }),
      }),
    };
    vscodeMock.window = {
      showTextDocument: async () => ({ document }),
      showInputBox: async () => 'Clear stale alpha proposal before retest.',
      showWarningMessage: async (message, options, confirmation) => {
        warnings.push({ message, options, confirmation });
        return confirmation;
      },
      showInformationMessage: async (message) => { information.push(message); },
      showErrorMessage: async (message) => { errors.push(message); },
      createTerminal: () => { terminalCalls.push('opened'); throw new Error('terminal opened'); },
    };

    const lenses = reviewDocumentActions(document);
    assert.deepEqual(lenses.map((lens) => lens.command.title), ['Accept', 'Reject', 'Withdraw', 'Refresh evidence']);
    const spawnReviewProcess = (command, args) => {
      launchArgs.push({ command, args });
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, false, new Set(), null, null, reviewResponses,
      );
      children.push(child);
      return child;
    };
    await launchDocumentReview(candidateId, 'withdraw', spawnReviewProcess);

    assert.deepEqual(errors, []);
    assert.deepEqual(terminalCalls, []);
    assert.equal(warnings.length, 1);
    assert.match(warnings[0].message, /Withdraw SDE proposal candidate-withdraw-42/);
    assert.match(warnings[0].options.detail, /task facts and evidence remain unchanged/);
    assert.match(information[0], /source facts retained.*withdrawal-42/);
    assert.equal(children.length, 2);
    assert.ok(launchArgs[0].args.includes('--allow-review'));
    assert.ok(!launchArgs[0].args.includes('--allow-write'));
    assert.ok(launchArgs[1].args.includes('--allow-review'));
    assert.ok(launchArgs[1].args.includes('--allow-write'));
    const withdrawalCall = children[1].requests.find(
      (request) => request.params?.name === 'sde_withdraw_candidates',
    );
    assert.ok(withdrawalCall);
    assert.deepEqual(withdrawalCall.params.arguments.candidate_ids, [candidateId]);
    assert.equal(withdrawalCall.params.arguments.rationale, 'Clear stale alpha proposal before retest.');
    assert.ok(children.every((child) => child.requests.every(
      (request) => request.params?.name !== 'sde_review_packet',
    )));
  } finally {
    vscodeMock.workspace = priorWorkspace;
    vscodeMock.window = priorWindow;
    vscodeMock.Uri = priorUri;
    vscodeMock.Range = priorRange;
    vscodeMock.CodeLens = priorCodeLens;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('Refresh evidence reopens the source task and withdraws the stale proposal without a terminal', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-refresh-'));
  const projectId = 'alpha';
  const candidateId = 'candidate-refresh-42';
  const candidate = {
    candidate_id: candidateId,
    goal_id: 'goal-refresh-42',
    status: 'pending_review',
    materiality: 'implementation',
    rationale: 'Clear stale proof before a fresh review.',
  };
  const completeOutline = {
    project_id: projectId,
    candidate_id: candidateId,
    goal_id: candidate.goal_id,
    goal_status: 'complete',
    lifecycle_revision: 7,
    problem: 'Verify the local alpha review path.',
    status: 'pending_review',
    evidence_status: 'not_current_or_missing',
    supporting_facts: [{ fact_id: 'fact-refresh-42' }],
  };
  const activeOutline = { ...completeOutline, goal_status: 'active', lifecycle_revision: 8 };
  let outlineReads = 0;
  const responses = {
    sde_review_outline: () => (outlineReads++ < 2 ? completeOutline : activeOutline),
    goal_reopen: { project_id: projectId, status: 'processed' },
    sde_withdraw_candidates: [{
      candidate_id: candidateId,
      withdrawal_id: 'withdrawal-refresh-42',
      candidate_sha256: 'd'.repeat(64),
    }],
  };
  const priorWorkspace = vscodeMock.workspace;
  const priorWindow = vscodeMock.window;
  const priorUri = vscodeMock.Uri;
  const priorRange = vscodeMock.Range;
  const priorCodeLens = vscodeMock.CodeLens;
  const children = [];
  const launchArgs = [];
  const warnings = [];
  const information = [];
  const errors = [];
  const terminalCalls = [];
  const settings = {
    databasePath: '/tmp/curator.sqlite3',
    profileId: 'fixture-profile',
    serverCommand: 'fixture-mcp',
  };
  try {
    initializeWorkspaceAreas(projectRoot);
    fs.writeFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'project_id = "alpha"\n');
    const reviewPath = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
    assert.equal(writePendingReviewDocument(projectRoot, projectId, [{
      candidate,
      goal: { goal_id: candidate.goal_id, project_id: projectId, problem: completeOutline.problem },
    }], new Map([[candidateId, completeOutline]])), true);
    const documentText = fs.readFileSync(reviewPath, 'utf8');
    const document = {
      uri: { fsPath: reviewPath },
      isDirty: false,
      get lineCount() { return documentText.split('\n').length; },
      lineAt: (line) => ({ text: documentText.split('\n')[line] }),
      getText: () => documentText,
      save: async () => true,
    };
    vscodeMock.Uri = { file: (fsPath) => ({ fsPath }) };
    vscodeMock.Range = class Range { constructor(start, end) { this.start = start; this.end = end; } };
    vscodeMock.CodeLens = class CodeLens { constructor(range, command) { this.range = range; this.command = command; } };
    vscodeMock.workspace = {
      workspaceFolders: [{ uri: { fsPath: projectRoot } }],
      textDocuments: [document],
      openTextDocument: async () => document,
      getConfiguration: () => ({
        get: (key, fallback) => settings[key] ?? fallback,
        inspect: () => ({ globalValue: true }),
      }),
    };
    vscodeMock.window = {
      showTextDocument: async () => ({ document }),
      showInputBox: async () => 'Refresh current passing evidence for the source task.',
      showWarningMessage: async (message, options, confirmation) => {
        warnings.push({ message, options, confirmation });
        return confirmation;
      },
      showInformationMessage: async (message) => { information.push(message); },
      showErrorMessage: async (message) => { errors.push(message); },
      createTerminal: () => { terminalCalls.push('opened'); throw new Error('terminal opened'); },
    };

    const lenses = reviewDocumentActions(document);
    assert.deepEqual(lenses.map((lens) => lens.command.title), ['Accept', 'Reject', 'Withdraw', 'Refresh evidence']);
    await launchDocumentReview(candidateId, 'refresh-evidence', (command, args) => {
      launchArgs.push({ command, args });
      const child = new FakeMcpProcess(
        'a'.repeat(64), false, null, null, false, new Set(), null, null, responses,
      );
      children.push(child);
      return child;
    });

    assert.deepEqual(errors, []);
    assert.deepEqual(terminalCalls, []);
    assert.equal(warnings.length, 1);
    assert.match(warnings[0].message, /Reopen/);
    assert.match(warnings[0].options.detail, /earlier verification is kept as historical evidence/);
    assert.match(information[0], /task reopened and stale proposal withdrawn/i);
    assert.equal(children.length, 3);
    assert.ok(launchArgs.every(({ args }) => args.includes('--allow-review')));
    assert.ok(launchArgs.slice(1).every(({ args }) => args.includes('--allow-write')));
    assert.ok(!launchArgs[0].args.includes('--allow-write'));
    const reopen = children[1].requests.find((request) => request.params?.name === 'goal_reopen');
    assert.ok(reopen);
    assert.equal(reopen.params.arguments.expected_lifecycle_revision, 7);
    assert.equal(reopen.params.arguments.goal_id, candidate.goal_id);
    const withdrawal = children[2].requests.find(
      (request) => request.params?.name === 'sde_withdraw_candidates',
    );
    assert.ok(withdrawal);
    assert.deepEqual(withdrawal.params.arguments.candidate_ids, [candidateId]);
    assert.ok(withdrawal.params.arguments.rationale.includes('Refresh current passing evidence'));
  } finally {
    vscodeMock.workspace = priorWorkspace;
    vscodeMock.window = priorWindow;
    vscodeMock.Uri = priorUri;
    vscodeMock.Range = priorRange;
    vscodeMock.CodeLens = priorCodeLens;
    fs.rmSync(projectRoot, { recursive: true, force: true });
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
        fact_id: 'fact-42',
        kind: 'change',
        bullet: 'Task summary: Read-only source tracing is complete; tests were not run and verification remains open.',
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
    assert.ok(generated.includes('Task started (+07): 2026\\-11\\-01T09:20:00\\+07:00'));
    assert.ok(generated.includes('Successful completion (+07): 2026\\-11\\-01T11:45:00\\+07:00'));
    assert.match(generated, /curator-v2-decision:candidate-42:start/);
    assert.match(generated, /"significance": 3/);
    const jsonFences = [...generated.matchAll(/```json\n([\s\S]*?)\n```/g)];
    assert.equal(jsonFences.length, 2);
    assert.equal(jsonFences[0][1], jsonFences[1][1]);
    assert.match(jsonFences[0][1], /"completed": \[\n    "Task summary: Read-only source tracing is complete; tests were not run and verification remains open\."\n  \]/);
    assert.match(generated, /Completed task work, with verification still open:/);

    const draftStart = generated.indexOf('<!-- curator-v2-decision:candidate-42:start -->');
    const draftEnd = generated.indexOf('<!-- curator-v2-decision:candidate-42:end -->');
    const editedDraft = generated.slice(draftStart, draftEnd)
      .replace('"significance": 3', '"significance": 4')
      .replace(/"completed": \[\n    "Task summary:[^\n]+\n  \]/, '"completed": []')
      .replace('"documents": []', '"documents": [\n    "persistence/HISTORY.md",\n    "persistence/LESSONS-LEARNED.md"\n  ]');
    const edited = generated.slice(0, draftStart) + editedDraft + generated.slice(draftEnd);
    fs.writeFileSync(destination, edited, 'utf8');
    const refreshedOutline = { ...outline, future_utility: 'Updated source proposal text.' };
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review], new Map([
      ['candidate-42', refreshedOutline],
    ])), true);
    const refreshed = fs.readFileSync(destination, 'utf8');
    assert.match(refreshed, /"significance": 4/);
    assert.match(refreshed, /"persistence\/LESSONS-LEARNED\.md"/);
    assert.match(refreshed, /Updated source proposal text\./);
    const refreshedFences = [...refreshed.matchAll(/```json\n([\s\S]*?)\n```/g)];
    assert.equal(refreshedFences.length, 2);
    assert.equal(refreshedFences[0][1], refreshedFences[1][1]);
    assert.match(refreshedFences[0][1], /"completed": \[\n    "Task summary:/);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('resolved proposals leave the pending document only after terminal status is confirmed', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-withdrawn-review-'));
  const review = {
    candidate: {
      candidate_id: 'candidate-withdrawn', goal_id: 'goal-withdrawn',
      status: 'pending_review', materiality: 'routine',
      rationale: 'This proposal is being cleared for retest.',
    },
    goal: {
      goal_id: 'goal-withdrawn', project_id: 'alpha',
      problem: 'Test withdrawal refresh of the pending review document.',
    },
  };
  try {
    const destination = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review]), true);
    const original = fs.readFileSync(destination, 'utf8');
    assert.equal(writePendingReviewDocument(
      projectRoot, 'alpha', [], new Map(), new Set(['candidate-withdrawn']),
    ), true);
    const refreshed = fs.readFileSync(destination, 'utf8');
    assert.match(refreshed, /No pending candidates\./);
    assert.doesNotMatch(refreshed, /candidate-withdrawn/);
    assert.notEqual(original, refreshed);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('pending review keeps generated prose contiguous across refresh and preserves decisions', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-prose-'));
  const reviewPath = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
  const rationale = 'A long proposal rationale should remain one contiguous source line so that the editor can wrap it responsively to the available width.';
  const review = {
    candidate: { candidate_id: 'candidate-prose', goal_id: 'goal-prose', status: 'pending_review', materiality: 'routine', rationale },
    goal: { goal_id: 'goal-prose', project_id: 'alpha', problem: 'Keep prose responsive.' },
  };
  try {
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review]), true);
    const original = fs.readFileSync(reviewPath, 'utf8');
    assert.ok(original.includes(`- Proposal rationale: ${rationale}\n`));
    const marker = '<!-- curator-v2-decision:candidate-prose:start -->';
    const start = original.indexOf(marker) + marker.length;
    const edited = original.slice(0, start) + original.slice(start)
      .replace('"documents": []', '"documents": ["persistence/HISTORY.md"]');
    assert.notEqual(edited, original);
    fs.writeFileSync(reviewPath, edited);
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review]), true);
    const refreshed = fs.readFileSync(reviewPath, 'utf8');
    assert.ok(refreshed.includes(`- Proposal rationale: ${rationale}\n`));
    assert.ok(refreshed.includes('"documents": ["persistence/HISTORY.md"]'));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('pending review checksum tolerates and preserves extra trailing blank lines', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-review-trailing-lines-'));
  const reviewPath = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  try {
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', []), true);
    const generated = fs.readFileSync(reviewPath, 'utf8');
    const edited = `${generated}${'\n'.repeat(37)}`;
    fs.writeFileSync(reviewPath, edited, 'utf8');

    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', []), true);
    assert.equal(fs.readFileSync(reviewPath, 'utf8'), edited);
    assert.equal(
      workspaceQueueViewsConfirmResolved(projectRoot, 'alpha', 'candidate-removed')
        .reviewDocumentResolved,
      true,
    );
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('queue refresh preserves unsaved review edits and reports the Markdown view as stale', async () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-accepted-review-'));
  const reviewPath = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  const review = {
    candidate: {
      candidate_id: 'candidate-accepted', goal_id: 'goal-accepted',
      status: 'pending_review', materiality: 'routine',
      rationale: 'Record the accepted owner decision.',
    },
    goal: {
      goal_id: 'goal-accepted', project_id: 'alpha',
      problem: 'Test removal of a canonically accepted SDE proposal.',
    },
  };
  const previousWorkspace = vscodeMock.workspace;
  try {
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review]), true);
    const original = fs.readFileSync(reviewPath, 'utf8');
    const draftStart = original.indexOf('<!-- curator-v2-decision:candidate-accepted:start -->');
    const draftEnd = original.indexOf('<!-- curator-v2-decision:candidate-accepted:end -->');
    const editableDraft = original.slice(draftStart, draftEnd)
      .replace('"significance": 1', '"significance": 4')
      .replace('"documents": []', '"documents": [\n    "persistence/HISTORY.md"\n  ]');
    const edited = original.slice(0, draftStart) + editableDraft + original.slice(draftEnd);
    assert.notEqual(edited, original);
    let saved = false;
    const openDocument = {
      uri: { fsPath: reviewPath },
      isDirty: true,
      getText: () => edited,
      async save() {
        saved = true;
        fs.writeFileSync(reviewPath, edited, 'utf8');
        openDocument.isDirty = false;
        return true;
      },
    };
    vscodeMock.workspace = { textDocuments: [openDocument] };
    const statusReads = [];
    const { outlines, resolvedCandidateIds } = await readReviewOutlines({
      callTool: async (name, args) => {
        statusReads.push({ name, candidateId: args.candidate_id });
        return JSON.stringify({
          project_id: 'alpha', candidate_id: args.candidate_id, status: 'approved',
        });
      },
    }, { project_id: 'alpha', candidates: [] }, 'alpha', projectRoot);

    assert.deepEqual(statusReads, [{
      name: 'sde_review_outline', candidateId: 'candidate-accepted',
    }]);
    assert.equal(outlines.size, 0);
    assert.deepEqual([...resolvedCandidateIds], ['candidate-accepted']);
    assert.equal(saved, false);
    assert.equal(openDocument.isDirty, true);
    assert.equal(openDocument.getText(), edited);
    assert.equal(writeWorkspaceQueueViews(projectRoot, 'alpha', {
      received_count: 0,
      failed_count: 0,
      quarantined_count: 0,
      claimed_count: 0,
      expired_claim_count: 0,
      oldest_pending_age_seconds: null,
      oldest_pending_received_at: null,
    }, { project_id: 'alpha', candidates: [] }, outlines, resolvedCandidateIds), false);

    const refreshed = fs.readFileSync(reviewPath, 'utf8');
    assert.equal(refreshed, original);
    assert.match(openDocument.getText(), /"significance": 4/);
    assert.match(refreshed, /candidate-accepted/);
    const pending = JSON.parse(fs.readFileSync(path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending.json',
    ), 'utf8'));
    assert.deepEqual(pending.candidates, []);
  } finally {
    vscodeMock.workspace = previousWorkspace;
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test('withdrawal refresh preserves owner edits to a removed proposal', () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-v2-withdrawn-edits-'));
  const review = {
    candidate: {
      candidate_id: 'candidate-edited', goal_id: 'goal-edited',
      status: 'pending_review', materiality: 'routine',
      rationale: 'This proposal is being cleared for retest.',
    },
    goal: {
      goal_id: 'goal-edited', project_id: 'alpha',
      problem: 'Test owner edit preservation during withdrawal refresh.',
    },
  };
  try {
    const destination = path.join(
      projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
    );
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', [review]), true);
    const original = fs.readFileSync(destination, 'utf8');
    const edited = original.replace(/("significance": )\d+/, '$1 4');
    assert.notEqual(edited, original);
    fs.writeFileSync(destination, edited, 'utf8');
    assert.equal(writePendingReviewDocument(projectRoot, 'alpha', []), false);
    assert.equal(fs.readFileSync(destination, 'utf8'), edited);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});
