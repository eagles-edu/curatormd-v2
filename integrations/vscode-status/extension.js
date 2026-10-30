'use strict';

const fs = require('node:fs');
const os = require('node:os');
const { spawn } = require('node:child_process');
const { createHash, randomBytes } = require('node:crypto');
const path = require('node:path');
const vscode = require('vscode');
const EXTENSION_VERSION = require('./package.json').version;

const STATUS_LABEL = 'CuratorMD V2';
const STATUS_COLORS = Object.freeze({
  healthy: '#73d216',
  degraded: '#ef2929',
  unknown: '#fce94f',
  review: '#ad7fa8',
  neutral: '#888888',
});
const STATUS_COLOR_MEANINGS = Object.freeze({
  healthy: 'Green means health is healthy with no SDE reviews pending.',
  review: 'Purple means an SDE review is pending and no other health gate is degraded.',
  unknown: 'Yellow means health or the SDE review count is unknown.',
  degraded: 'Red means health is degraded beyond the review-only state.',
  neutral: 'Gray means no health read has been attempted.',
});
const STATUS_READ_FAILURES = Object.freeze({
  'launcher-start': 'Curator did not start; check the Curator launcher in VS Code User settings.',
  'launcher-exit': 'Curator stopped before replying; check the local Curator installation.',
  'read-denied': 'Curator denied the project read; check its local project access grant.',
  'mcp-request': 'Curator could not complete the project read; refresh to try again.',
  'invalid-response': 'Curator returned an unreadable response; check the local installation.',
  timeout: 'Curator did not reply within 15 seconds; refresh to try again.',
  'hermes-probe-start': 'Hermes readiness check did not start; check the Hermes command in User settings.',
  'hermes-probe-exit': 'Hermes readiness check stopped early; use a Hermes version with the Curator status probe.',
  'hermes-probe-timeout': 'Hermes readiness check timed out; refresh to try again.',
  'hermes-probe-invalid': 'Hermes readiness data was incomplete or for another project; check the profile settings.',
  'hermes-probe-profile': 'The Hermes profile setting is invalid; check the User settings value.',
  'status-project-invalid': 'Curator did not identify the configured project; check its project file and grant.',
});
const REPORT_PAGE_SIZE = 16;
const GOAL_PAGE_SIZE = 20;
const MAX_GOAL_CRITERIA = 12;
const MAX_PROJECT_CONFIG_BYTES = 16 * 1024;
const REVIEW_QUEUE_SIZE = 100;
const REQUEST_TIMEOUT_MS = 15000;
const HERMES_HEALTH_TIMEOUT_MS = 20000;
const HERMES_HEALTH_MAX_BYTES = 32768;
const MAX_HEALTH_PROBE_AGE_SECONDS = 60;
const MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS = 5;
const STATUS_REFRESH_INTERVAL_MS = 60000;
const SQLITE_WARNING_BYTES = 250 * 1024 * 1024;
const REQUIRED_HEALTH_PROBES = Object.freeze([
  'event_router', 'purge_scheduler', 'database_storage_adapter', 'host_identity',
  'human_review', 'alert_delivery', 'artifact_producer_inventory',
]);
const REPORT_FACT_ID_PATTERN = /^- `([^`]{1,256})` — /;
let dashboardStatusItem;
let statusRefreshTimer;
let statusRefreshGeneration = 0;

function statusTooltip(message) {
  return `${STATUS_LABEL} ${EXTENSION_VERSION}. ${message}`;
}

function statusColorMeaning(status) {
  return STATUS_COLOR_MEANINGS[status] || STATUS_COLOR_MEANINGS.unknown;
}

function statusReadFailure(error) {
  const fallback = 'The local health read failed; open the dashboard for details.';
  return error && typeof error.code === 'string'
    && Object.prototype.hasOwnProperty.call(STATUS_READ_FAILURES, error.code)
    ? STATUS_READ_FAILURES[error.code]
    : fallback;
}

function goalStartFailure(error) {
  const messages = {
    'launcher-start': 'Curator could not start. Check the local launcher in VS Code User settings.',
    'launcher-exit': 'Curator stopped before saving the task. Check the local installation.',
    'read-denied': 'Curator denied access to this project. Check its local project grant.',
    'mcp-request': 'Curator could not save the task. Refresh and try again.',
    'invalid-response': 'Curator returned an unreadable result. Check the local installation.',
    timeout: 'Curator did not respond in time. Refresh and try again.',
    'goal-start-rejected': 'Curator did not confirm that the task was saved.',
    'goal-readback-mismatch': 'The saved task differs from what you entered. Review it in the dashboard.',
    'goal-report-unavailable': 'The task was saved, but Curator could not return its report.',
    'project-config-invalid': 'The Curator project file could not be read. Check the project setup.',
    'project-config-changed': 'The project changed while you were entering the task. Run Start Task again.',
  };
  const fallback = 'Curator could not confirm task creation. Open the dashboard for details.';
  const code = error && error.code;
  return typeof code === 'string' && Object.prototype.hasOwnProperty.call(messages, code)
    ? messages[code]
    : fallback;
}

function healthGateSummary(health, projectId) {
  if (!health || health.project_id !== projectId || !Array.isArray(health.gate_codes)) {
    return '';
  }
  const codes = health.gate_codes
    .filter((code) => typeof code === 'string' && /^[a-z][a-z0-9_]{0,63}$/.test(code))
    .slice(0, 12);
  const omitted = health.gate_codes.length - codes.length;
  if (codes.length === 0) return '';
  const suffix = omitted > 0 ? `; ${omitted} additional or invalid gate(s)` : '';
  return ` Health gates: ${codes.join(', ')}${suffix}.`;
}

function sqliteSizeWarning(storage, projectId) {
  if (!storage || storage.project_id !== projectId
    || !Number.isSafeInteger(storage.global_database_bytes)
    || storage.global_database_bytes < 0
    || !Number.isSafeInteger(storage.global_wal_bytes)
    || storage.global_wal_bytes < 0) return null;
  const combinedBytes = storage.global_database_bytes + storage.global_wal_bytes;
  return Number.isSafeInteger(combinedBytes) && combinedBytes > SQLITE_WARNING_BYTES
    ? `SQLite main database plus WAL is ${formatBytes(combinedBytes)}, above the 250 MiB warning threshold. Writes remain allowed; SQLite manages WAL checkpointing.`
    : null;
}

function formatBytes(value) {
  if (value === null || value === undefined) return 'unavailable';
  if (value < 1024) return `${value} B`;
  if (value < 1048576) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1048576).toFixed(1)} MiB`;
}

function reportFactIds(report) {
  if (typeof report !== 'string' || report.length > 40000) return new Set();
  return new Set(report.split(/\r?\n/)
    .map((line) => line.match(REPORT_FACT_ID_PATTERN))
    .filter(Boolean)
    .map((match) => match[1]));
}

function isBoundedFactEvidence(value, projectId, goalId, factId, reportRevision) {
  const boundedText = (text, limit) => typeof text === 'string'
    && text.length > 0 && text.length <= limit && !/[\r\n]/.test(text);
  if (!value || value.project_id !== projectId || value.goal_id !== goalId
    || value.fact_id !== factId || value.report_revision !== reportRevision
    || !/^[a-f0-9]{64}$/.test(value.report_revision)
    || !['intent', 'research', 'advice', 'proposal', 'change', 'verification',
      'open_gate', 'completion_claim', 'outcome', 'reopened', 'criteria_amended',
      'cancelled', 'superseded'].includes(value.fact_kind)
    || !['verified_fact', 'recorded_fact', 'unverified_claim', 'open_gate'].includes(value.verification_status)
    || !(value.criterion_id === null || boundedText(value.criterion_id, 128))
    || !Array.isArray(value.evidence) || value.evidence.length > 16) return false;
  return value.evidence.every((reference) => {
    if (!reference || !boundedText(reference.evidence_kind, 64)
      || !boundedText(reference.locator, 1000)
      || !/^[a-f0-9]{64}$/.test(reference.sha256)
      || !['passed', 'failed', 'observed'].includes(reference.outcome)
      || !(reference.occurrence_id === null || /^[a-f0-9]{32}$/.test(reference.occurrence_id))) return false;
    const attestation = reference.attestation;
    if (attestation === null) return true;
    return Boolean(attestation
      && boundedText(attestation.adapter_id, 128)
      && boundedText(attestation.authenticated_subject, 128)
      && boundedText(attestation.source_revision, 256)
      && boundedText(attestation.observed_at, 64)
      && boundedText(attestation.valid_until, 64)
      && boundedText(attestation.revocation_checked_at, 64));
  });
}

function curatorError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function validGoalText(value, limit) {
  return typeof value === 'string'
    && value.trim().length > 0
    && value.length <= limit
    && !/[\r\n]/.test(value);
}

async function promptForGoalDefinition() {
  const problem = await vscode.window.showInputBox({
    title: 'Start a Curator V2 task',
    prompt: 'Write a short problem statement. Do not paste a transcript, password, or key.',
    placeHolder: 'What needs to change?',
    ignoreFocusOut: true,
    validateInput: (value) => validGoalText(value, 2000)
      ? undefined
      : 'Enter one line with at most 2,000 characters.',
  });
  if (!problem) return null;

  const criteria = [];
  while (criteria.length < MAX_GOAL_CRITERIA) {
    const description = await vscode.window.showInputBox({
      title: `Success check ${criteria.length + 1}`,
      prompt: 'Enter one observable result. Each check stays separate in the saved task.',
      placeHolder: 'What result can be checked?',
      ignoreFocusOut: true,
      validateInput: (value) => validGoalText(value, 500)
        ? undefined
        : 'Enter one line with at most 500 characters.',
    });
    if (!description) return null;
    criteria.push({
      criterion_id: `criterion-${String(criteria.length + 1).padStart(2, '0')}`,
      description: description.trim(),
    });
    if (criteria.length >= MAX_GOAL_CRITERIA) break;
    const choice = await vscode.window.showQuickPick(
      ['Add another success check', 'Create this active task'],
      {
        title: 'Task success checks',
        placeHolder: `${criteria.length} check(s) entered. Add another or continue.`,
        ignoreFocusOut: true,
      },
    );
    if (!choice) return null;
    if (choice === 'Create this active task') break;
  }

  const summary = `${problem.trim()}\n\nSuccess checks:\n${criteria
    .map((criterion, index) => `${index + 1}. ${criterion.description}`)
    .join('\n')}`;
  const confirmation = await vscode.window.showInformationMessage(
    summary,
    {
      modal: true,
      detail: 'Only this summary and the separate checks will be saved. Retrying the same entry reuses the same task.',
    },
    'Start task',
    'Cancel',
  );
  if (confirmation !== 'Start task') return null;
  return { problem: problem.trim(), criteria };
}

function projectConfigDigest(projectRoot) {
  const bytes = fs.readFileSync(path.join(projectRoot, '.curatormd-v2.toml'));
  if (bytes.length > MAX_PROJECT_CONFIG_BYTES) {
    throw curatorError('project-config-invalid', 'Curator project file is too large.');
  }
  return createHash('sha256').update(bytes).digest('hex');
}

function stableGoalEventIds(projectRoot, profileId, projectId, configDigest, definition) {
  const identity = JSON.stringify({
    project_root: path.resolve(projectRoot),
    profile_id: profileId,
    project_id: projectId,
    config_sha256: configDigest,
    problem: definition.problem,
    success_criteria: definition.criteria,
  });
  const digest = createHash('sha256').update(identity).digest('hex');
  return {
    eventId: `vscode-task-event-${digest}`,
    goalId: `vscode-task-${digest}`,
  };
}

async function startGoalFromWorkspace(spawnProcess = spawn) {
  const workspace = vscode.workspace
    && vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!workspace) {
    vscode.window.showWarningMessage('Open a configured Curator V2 project first.');
    return null;
  }
  const projectRoot = workspace.uri.fsPath;
  if (!fs.existsSync(projectRoot) || !fs.existsSync(path.join(projectRoot, '.curatormd-v2.toml'))) {
    vscode.window.showErrorMessage('This folder is not configured for Curator V2.');
    return null;
  }
  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  if (hasWorkspaceSettingOverride(configuration,
    ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand'])) {
    vscode.window.showErrorMessage('Curator V2 uses User settings for its local connection.');
    return null;
  }
  const databasePath = configuration.get('databasePath', '');
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  if (!databasePath || !profileId || !serverCommand) {
    vscode.window.showErrorMessage('Set the Curator V2 database, profile, and launcher in User settings.');
    return null;
  }

  const definition = await promptForGoalDefinition();
  if (!definition) return null;
  let configDigest;
  try {
    configDigest = projectConfigDigest(projectRoot);
  } catch (error) {
    vscode.window.showErrorMessage(goalStartFailure(error));
    return null;
  }
  const client = new McpStdioClient(serverCommand, [
    '--project-root', projectRoot,
    '--database', databasePath,
    '--profile-id', profileId,
  ], projectRoot, profileId, spawnProcess);
  try {
    await client.initialize();
    const projectPage = JSON.parse(await client.callTool('goal_list_page', { offset: 0, limit: 1 }));
    if (!projectPage || typeof projectPage.project_id !== 'string' || !projectPage.project_id) {
      throw curatorError('status-project-invalid', 'Curator did not return the configured project.');
    }
    if (projectConfigDigest(projectRoot) !== configDigest) {
      throw curatorError('project-config-changed', 'Curator project changed before task creation.');
    }
    const { eventId, goalId } = stableGoalEventIds(
      projectRoot, profileId, projectPage.project_id, configDigest, definition,
    );
    const receipt = JSON.parse(await client.callTool('goal_start', {
      event_id: eventId,
      goal_id: goalId,
      problem: definition.problem,
      success_criteria: definition.criteria,
      initial_status: 'active',
    }));
    if (!receipt || receipt.project_id !== projectPage.project_id
      || receipt.event_id !== eventId || !['processed', 'duplicate'].includes(receipt.status)) {
      throw curatorError('goal-start-rejected', 'Curator did not confirm that the task was saved.');
    }
    const saved = JSON.parse(await client.callTool('goal_status', { goal_id: goalId }));
    const savedGoal = saved && saved.goal;
    const savedCriteria = savedGoal && savedGoal.success_criteria;
    const exactCriteria = Array.isArray(savedCriteria)
      && savedCriteria.length === definition.criteria.length
      && savedCriteria.every((criterion, index) => (
        criterion.criterion_id === definition.criteria[index].criterion_id
        && criterion.description === definition.criteria[index].description
      ));
    if (!savedGoal || savedGoal.goal_id !== goalId
      || savedGoal.project_id !== projectPage.project_id
      || savedGoal.problem !== definition.problem || !exactCriteria) {
      throw curatorError('goal-readback-mismatch', 'The saved task did not match the entered summary.');
    }
    const report = await client.callTool('goal_report', { goal_id: goalId, fact_limit: 1 });
    if (!report.includes(`# Goal \`${goalId}\``)
      || !report.includes('## Success criteria')) {
      throw curatorError('goal-report-unavailable', 'Curator did not return the saved task report.');
    }
    vscode.window.showInformationMessage(`Curator V2 task started: ${goalId}`);
    return { projectId: projectPage.project_id, goalId, eventId };
  } catch (error) {
    vscode.window.showErrorMessage(goalStartFailure(error));
    return null;
  } finally {
    client.close();
  }
}

function parseHermesHealthProbe(stdout, expectedProjectId) {
  if (typeof stdout !== 'string' || Buffer.byteLength(stdout, 'utf8') > HERMES_HEALTH_MAX_BYTES) {
    throw curatorError('hermes-probe-invalid', 'Hermes health response exceeded its size limit.');
  }
  let response;
  try {
    response = JSON.parse(stdout);
  } catch {
    throw curatorError('hermes-probe-invalid', 'Hermes health response was not valid JSON.');
  }
  const health = response && response.health;
  const validCode = (code) => typeof code === 'string'
    && /^[a-z][a-z0-9_:.-]{0,127}$/.test(code);
  const dependencies = health && health.dependencies;
  const healthObservedAt = health && typeof health.observed_at === 'string'
    ? Date.parse(health.observed_at) : Number.NaN;
  const healthAgeSeconds = (Date.now() - healthObservedAt) / 1000;
  const healthObservationFresh = Number.isFinite(healthObservedAt)
    && healthAgeSeconds <= MAX_HEALTH_PROBE_AGE_SECONDS + MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS
    && healthAgeSeconds >= -MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS;
  const dependencyNames = Array.isArray(dependencies)
    ? dependencies.map((dependency) => dependency && dependency.name) : [];
  const dependencyObservationsFresh = Array.isArray(dependencies)
    && dependencies.every((dependency) => {
      if (!dependency || typeof dependency.observed_at !== 'string') return false;
      const observedAt = Date.parse(dependency.observed_at);
      const age = (Date.now() - observedAt) / 1000;
      return Number.isFinite(observedAt)
        && dependency.age_seconds <= MAX_HEALTH_PROBE_AGE_SECONDS
        && age <= MAX_HEALTH_PROBE_AGE_SECONDS + MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS
        && age >= -MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS;
    });
  const dependenciesValid = Array.isArray(dependencies)
    && dependencies.length === REQUIRED_HEALTH_PROBES.length
    && new Set(dependencyNames).size === REQUIRED_HEALTH_PROBES.length
    && REQUIRED_HEALTH_PROBES.every((name) => dependencyNames.includes(name))
    && dependencies.every((dependency) => dependency
      && ['healthy', 'degraded', 'unknown'].includes(dependency.status)
      && typeof dependency.observed_at === 'string'
      && dependency.observed_at.length > 0 && dependency.observed_at.length <= 64
      && Number.isSafeInteger(dependency.age_seconds) && dependency.age_seconds >= 0);
  if (!response || response.schema_version !== 1 || response.connected !== true
    || response.project_id !== expectedProjectId
    || !health || health.project_id !== expectedProjectId
    || !['healthy', 'degraded', 'unknown'].includes(health.status)
    || health.database_observation_complete !== true
    || !Array.isArray(health.gate_codes) || health.gate_codes.length > 128
    || !health.gate_codes.every(validCode) || !dependenciesValid) {
    throw curatorError('hermes-probe-invalid', 'Hermes health response was incomplete or project-mismatched.');
  }
  if (health.status === 'healthy'
    && (health.gate_codes.length > 0
      || dependencies.some((dependency) => dependency.status !== 'healthy')
      || !healthObservationFresh
      || !dependencyObservationsFresh)) {
    throw curatorError('hermes-probe-invalid', 'Hermes health response did not reconcile.');
  }
  return health;
}

function readHermesHealthProbe(command, profileId, projectId, cwd, spawnProcess = spawn) {
  if (typeof profileId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(profileId)) {
    return Promise.reject(curatorError('hermes-probe-profile', 'Hermes profile routing label is invalid.'));
  }
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawnProcess(command, [
        'mcp', 'test', 'curator_v2', '--probe-curator-status', '--json',
      ], {
        cwd,
        env: {
          ...process.env,
          HERMES_HOME: path.join(os.homedir(), '.hermes', 'profiles', profileId),
        },
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'ignore'],
      });
    } catch {
      reject(curatorError('hermes-probe-start', 'Hermes health probe could not start.'));
      return;
    }
    let stdout = '';
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(curatorError('hermes-probe-timeout', 'Hermes health probe timed out.'));
    }, HERMES_HEALTH_TIMEOUT_MS);
    child.stdout.on('data', (chunk) => {
      stdout += String(chunk);
      if (Buffer.byteLength(stdout, 'utf8') > HERMES_HEALTH_MAX_BYTES) {
        child.kill();
        finish(curatorError('hermes-probe-invalid', 'Hermes health response exceeded its size limit.'));
      }
    });
    child.once('error', () => {
      finish(curatorError('hermes-probe-start', 'Hermes health probe could not start.'));
    });
    child.once('close', (code) => {
      if (code !== 0) {
        finish(curatorError('hermes-probe-exit', 'Hermes health probe did not complete.'));
        return;
      }
      try {
        finish(null, parseHermesHealthProbe(stdout, projectId));
      } catch (error) {
        finish(error);
      }
    });
  });
}

function dashboardErrorMessage(error) {
  switch (error && error.code) {
    case 'launcher-start':
      return 'Could not start Curator V2. Check the User setting serverCommand and the installed launcher.';
    case 'launcher-exit':
      return 'The Curator V2 launcher exited before replying. Check its installation and startup.';
    case 'timeout':
      return 'Curator V2 did not respond within 15 seconds. Check the local backend and try again.';
    case 'read-denied':
      return 'Curator V2 denied this read. Check the configured project and its active local read grant.';
    case 'mcp-request':
      return 'The Curator V2 MCP request failed. Check that the installed launcher and backend are compatible.';
    case 'invalid-response':
      return 'Curator V2 returned an invalid response. Check the installed launcher and backend.';
    default:
      return 'Curator read failed. Check User settings, the local project grant, and the launcher.';
  }
}

const GOAL_STATES = Object.freeze([
  'planned', 'active', 'complete', 'open', 'blocked',
  'deferred', 'cancelled', 'superseded',
]);

function summarizeGoalStates(activity, projectId) {
  if (!activity || activity.project_id !== projectId
    || !Number.isSafeInteger(activity.goal_count) || activity.goal_count < 0
    || !Array.isArray(activity.goal_status_counts)) {
    return 'Goal states: unknown. Activity snapshot unavailable or mismatched.';
  }
  const counts = new Map();
  for (const item of activity.goal_status_counts) {
    if (!item || !GOAL_STATES.includes(item.status)
      || !Number.isSafeInteger(item.count) || item.count < 0
      || counts.has(item.status)) {
      return 'Goal states: unknown. Activity snapshot is incomplete.';
    }
    counts.set(item.status, item.count);
  }
  if (counts.size !== GOAL_STATES.length
    || GOAL_STATES.reduce((total, state) => total + counts.get(state), 0) !== activity.goal_count) {
    return 'Goal states: unknown. Activity snapshot is incomplete.';
  }
  return `Goal states: ${GOAL_STATES.map((state) => `${state} ${counts.get(state)}`).join(', ')}.`;
}

function summarizeOperationalQueues(health, projectId) {
  if (!health || health.project_id !== projectId) {
    return 'Operational queues: unknown. Health snapshot unavailable or mismatched.';
  }
  if (health.database_observation_complete !== true) {
    return 'Operational queues: unknown. Database observation is incomplete.';
  }
  const counts = health.operational_counts;
  const queueFields = [
    'pending_review_count', 'pending_purge_receipt_count',
    'pending_purge_artifact_count', 'pending_expiry_purge_receipt_count',
    'pending_expiry_purge_artifact_count',
  ];
  const eventFields = [
    'event_received_count', 'event_failed_count', 'event_quarantined_count',
    'event_claimed_count', 'event_expired_claim_count',
    'oldest_pending_event_age_seconds',
  ];
  const exactCount = (value) => Number.isSafeInteger(value) && value >= 0;
  if (!counts || !queueFields.every((field) => exactCount(counts[field]))
    || !eventFields.every((field) => health[field] === null || exactCount(health[field]))) {
    return 'Operational queues: unknown. Health snapshot is incomplete.';
  }
  const age = health.oldest_pending_event_age_seconds === null
    ? 'none' : `${health.oldest_pending_event_age_seconds}s`;
  return `Events received ${health.event_received_count ?? 'unavailable'}, failed ${health.event_failed_count ?? 'unavailable'}, quarantined ${health.event_quarantined_count ?? 'unavailable'}, active claims ${health.event_claimed_count ?? 'unavailable'}, expired claims ${health.event_expired_claim_count ?? 'unavailable'}; oldest pending age ${age}. Reviews pending ${counts.pending_review_count}; purge pending ${counts.pending_purge_receipt_count} receipts / ${counts.pending_purge_artifact_count} artifacts; expiry pending ${counts.pending_expiry_purge_receipt_count} receipts / ${counts.pending_expiry_purge_artifact_count} artifacts.`;
}

function summarizeEventFailureCategories(metrics, projectId, expectedCount) {
  if (!Number.isSafeInteger(expectedCount) || expectedCount < 0) return null;
  if (expectedCount === 0) return { evidence_rejected: 0, evidence_adapter_error: 0, other: 0 };
  if (typeof metrics !== 'string' || metrics.length > 65536) return null;
  const rows = metrics.split(/\r?\n/)
    .filter((line) => line.startsWith('curatormd_event_failures{'));
  if (!rows.length) return null;

  const counts = new Map();
  for (const row of rows) {
    const match = row.match(/^curatormd_event_failures\{project_id="([^"\\]{1,128})",category="([a-z_]{1,64})"\} (0|[1-9][0-9]{0,14})$/);
    if (!match || match[1] !== projectId
      || !['evidence_rejected', 'evidence_adapter_error', 'other'].includes(match[2])
      || counts.has(match[2])) return null;
    const count = Number(match[3]);
    if (!Number.isSafeInteger(count)) return null;
    counts.set(match[2], count);
  }
  const total = [...counts.values()].reduce((sum, count) => sum + count, 0);
  if (total !== expectedCount) return null;
  return {
    evidence_rejected: counts.get('evidence_rejected') || 0,
    evidence_adapter_error: counts.get('evidence_adapter_error') || 0,
    other: counts.get('other') || 0,
  };
}

function summarizeOperationalAlerts(health, storage, metrics, projectId) {
  const alerts = [];
  const healthMatches = health && health.project_id === projectId;
  const healthComplete = healthMatches && health.database_observation_complete === true;
  const healthStatusValid = healthComplete
    && ['healthy', 'degraded', 'unknown'].includes(health.status)
    && Array.isArray(health.gate_codes)
    && health.gate_codes.every((gate) => typeof gate === 'string'
      && /^[a-z][a-z0-9_:.-]{0,127}$/.test(gate));
  if (!healthStatusValid) {
    alerts.push('Readiness and queues unknown (health snapshot unavailable, incomplete, or mismatched).');
  } else if (health.status !== 'healthy' || health.gate_codes.length > 0) {
    const gates = health.gate_codes.slice(0, 20);
    alerts.push(`Readiness ${health.status}${gates.length ? `: ${gates.join(', ')}` : '.'}`);
  }

  if (healthComplete) {
    const counts = health.operational_counts;
    const eventFields = [
      'event_received_count', 'event_failed_count', 'event_quarantined_count',
      'event_expired_claim_count',
    ];
    const queueFields = [
      'pending_review_count', 'pending_purge_receipt_count',
      'pending_purge_artifact_count', 'pending_expiry_purge_receipt_count',
      'pending_expiry_purge_artifact_count',
    ];
    const countValid = (value) => Number.isSafeInteger(value) && value >= 0;
    if (!counts || !queueFields.every((field) => countValid(counts[field]))
      || !eventFields.every((field) => health[field] === null || countValid(health[field]))) {
      alerts.push('Queue details unknown (health snapshot is incomplete).');
    } else {
      if (health.event_received_count === null) {
        alerts.push('Event intake status unknown.');
      } else if (health.event_received_count > 0) {
        alerts.push(`${health.event_received_count} event receipt(s) waiting to process.`);
      }
      const failuresUnknown = health.event_failed_count === null
        || health.event_quarantined_count === null;
      const failed = health.event_failed_count;
      const quarantined = health.event_quarantined_count;
      if (failuresUnknown) {
        alerts.push('Event failure categories unknown.');
      } else if (failed > 0 || quarantined > 0) {
        const categories = summarizeEventFailureCategories(
          metrics, projectId, failed + quarantined,
        );
        if (!categories) {
          alerts.push(`${failed} failed and ${quarantined} quarantined event receipt(s); category breakdown unknown.`);
        } else {
          alerts.push(`Event failures by category: evidence rejected ${categories.evidence_rejected}, adapter errors ${categories.evidence_adapter_error}, other ${categories.other}.`);
        }
      }
      if (health.event_expired_claim_count === null) {
        alerts.push('Expired event-claim status unknown.');
      } else if (health.event_expired_claim_count > 0) {
        alerts.push(`${health.event_expired_claim_count} expired event claim(s) need retry/reconciliation.`);
      }
      if (counts.pending_review_count) alerts.push(`${counts.pending_review_count} SDE review(s) need a human decision.`);
      if (counts.pending_purge_receipt_count || counts.pending_purge_artifact_count) {
        alerts.push(`Cleanup pending: ${counts.pending_purge_receipt_count} receipt(s), ${counts.pending_purge_artifact_count} artifact(s).`);
      }
      if (counts.pending_expiry_purge_receipt_count || counts.pending_expiry_purge_artifact_count) {
        alerts.push(`Expiry cleanup pending: ${counts.pending_expiry_purge_receipt_count} receipt(s), ${counts.pending_expiry_purge_artifact_count} artifact(s).`);
      }
    }
  }

  const staging = storage && storage.project_id === projectId ? storage.staging : null;
  if (!staging || !Number.isSafeInteger(staging.observed_file_bytes)
    || staging.observed_file_bytes < 0 || typeof staging.inventory_complete !== 'boolean') {
    alerts.push('Staging status unknown (inventory read unavailable or mismatched).');
  } else if (!staging.inventory_complete) {
    alerts.push(`Staging inventory incomplete; observed at least ${staging.observed_file_bytes} bytes.`);
  } else {
    const limit = storage.staging_project_byte_limit;
    if (Number.isSafeInteger(limit) && limit > 0) {
      const ratio = staging.observed_file_bytes / limit;
      if (ratio >= 1) alerts.push('Staging byte warning threshold reached; writes remain allowed.');
      else if (ratio >= 0.75) alerts.push('Staging reached 75% of its warning threshold; writes remain allowed.');
    } else if (limit === null) alerts.push('No staging byte warning threshold is configured.');
    else alerts.push('Staging byte threshold status unknown.');
  }

  return alerts.length
    ? `Attention: ${alerts.join(' ')}`
    : 'No current queue or staging alerts in these snapshots; this does not prove capture completeness.';
}

class McpStdioClient {
  constructor(command, args, cwd, profileId, spawnProcess = spawn) {
    this.child = spawnProcess(command, args, {
      cwd,
      stdio: ['pipe', 'pipe', 'ignore'],
      windowsHide: true,
    });
    this.nextId = 1;
    this.profileId = profileId;
    this.sessionId = randomBytes(16).toString('hex');
    this.pending = new Map();
    this.buffer = '';
    this.closed = false;
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', (chunk) => this._receive(chunk));
    this.child.on('error', () => this._failAll(curatorError(
      'launcher-start', 'Curator MCP process could not start.',
    )));
    this.child.on('exit', () => {
      this.closed = true;
      this._failAll(curatorError(
        'launcher-exit', 'Curator MCP process exited before replying.',
      ));
    });
  }

  async initialize() {
    await this._request('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'curatormd-v2-vscode-dashboard', version: EXTENSION_VERSION },
    });
    this.child.stdin.write(`${JSON.stringify({
      jsonrpc: '2.0',
      method: 'notifications/initialized',
    })}\n`);
  }

  async callTool(name, args) {
    const response = await this._request('tools/call', {
      name,
      arguments: args,
      _meta: {
        'hermes/profile_id': this.profileId,
        'hermes/session_id': this.sessionId,
      },
    });
    if (response.isError) {
      throw curatorError('read-denied', 'Curator rejected the read.');
    }
    const text = (response.content || [])
      .filter((item) => item && item.type === 'text' && typeof item.text === 'string')
      .map((item) => item.text)
      .join('\n');
    if (!text) throw new Error('Curator returned no readable result.');
    return text;
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    this.child.kill();
    this._failAll(new Error('Curator MCP request was closed.'));
  }

  _request(method, params) {
    if (this.closed || this.child.stdin.destroyed) {
      return Promise.reject(new Error('Curator MCP process is unavailable.'));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(curatorError('timeout', 'Curator did not respond within 15 seconds.'));
      }, REQUEST_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
    });
  }

  _receive(chunk) {
    this.buffer += chunk;
    for (;;) {
      const newline = this.buffer.indexOf('\n');
      if (newline < 0) break;
      const line = this.buffer.slice(0, newline).trim();
      this.buffer = this.buffer.slice(newline + 1);
      if (!line) continue;
      let message;
      try {
        message = JSON.parse(line);
      } catch (_) {
        this._failAll(curatorError(
          'invalid-response', 'Curator returned an invalid MCP response.',
        ));
        continue;
      }
      const pending = this.pending.get(message.id);
      if (!pending) continue;
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      if (message.error) pending.reject(curatorError('mcp-request', 'Curator MCP request failed.'));
      else pending.resolve(message.result || {});
    }
  }

  _failAll(error) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}

function activate(context) {
  // Git Graph uses Left priority 1; Left priority 0 places CuratorMD immediately after it.
  const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 0);
  dashboardStatusItem = statusItem;
  statusItem.name = STATUS_LABEL;
  statusItem.text = '$(circle-filled) CuratorMD V2';
  statusItem.color = STATUS_COLORS.neutral;
  statusItem.tooltip = statusTooltip(
    `${statusColorMeaning('neutral')} Click to open the project dashboard.`,
  );
  statusItem.command = 'curatormdV2.openDashboard';
  statusItem.show();

  const openDashboard = vscode.commands.registerCommand(
    'curatormdV2.openDashboard',
    () => showDashboard(),
  );
  const startGoal = vscode.commands.registerCommand(
    'curatormdV2.startGoal',
    () => startGoalFromWorkspace(),
  );
  context.subscriptions.push(statusItem, openDashboard, startGoal);
  void refreshStatusBarHealthFromWorkspace();
  statusRefreshTimer = setInterval(() => {
    void refreshStatusBarHealthFromWorkspace();
  }, STATUS_REFRESH_INTERVAL_MS);
  if (typeof statusRefreshTimer.unref === 'function') statusRefreshTimer.unref();
  context.subscriptions.push({ dispose: () => clearInterval(statusRefreshTimer) });
  if (vscode.workspace && typeof vscode.workspace.onDidChangeWorkspaceFolders === 'function') {
    context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(() => {
      resetStatusBarHealth();
      void refreshStatusBarHealthFromWorkspace();
    }));
  }
  if (vscode.workspace && typeof vscode.workspace.onDidChangeConfiguration === 'function') {
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event || typeof event.affectsConfiguration !== 'function'
        || !event.affectsConfiguration('curatormdV2')) return;
      resetStatusBarHealth();
      void refreshStatusBarHealthFromWorkspace();
    }));
  }
  if (vscode.window && typeof vscode.window.onDidChangeWindowState === 'function') {
    context.subscriptions.push(vscode.window.onDidChangeWindowState((event) => {
      if (event && event.focused) void refreshStatusBarHealthFromWorkspace();
    }));
  }
}

function deactivate() {
  if (statusRefreshTimer) clearInterval(statusRefreshTimer);
  statusRefreshTimer = undefined;
  dashboardStatusItem = undefined;
}

function updateStatusBarHealth(
  health, projectId, reviewItems = null, storage = null, readError = null,
) {
  if (!dashboardStatusItem) return 'unknown';
  const healthStatus = projectId
    && health?.project_id === projectId
    && ['healthy', 'degraded', 'unknown'].includes(health.status)
    ? health.status
    : 'unknown';
  const reviewsKnown = Array.isArray(reviewItems);
  const pendingReviews = reviewsKnown ? reviewItems.length : null;
  const reviewBacklogOnly = healthStatus === 'degraded'
    && Array.isArray(health.gate_codes)
    && health.gate_codes.length === 1
    && health.gate_codes[0] === 'review_backlog';
  let displayStatus = healthStatus;
  if (healthStatus === 'healthy' && !reviewsKnown) displayStatus = 'unknown';
  else if (pendingReviews > 0 && (healthStatus === 'healthy' || reviewBacklogOnly)) {
    displayStatus = 'review';
  }
  const reviewSummary = !reviewsKnown
    ? 'pending SDE review count unavailable'
    : pendingReviews === 0
      ? 'no SDE reviews pending'
      : `${pendingReviews} pending SDE review${pendingReviews === 1 ? '' : 's'}`;
  const storageWarning = sqliteSizeWarning(storage, projectId);
  dashboardStatusItem.text = `$(circle-filled) CuratorMD V2: ${displayStatus}`
    + (storageWarning ? ' · SQLite size warning' : '');
  dashboardStatusItem.color = STATUS_COLORS[displayStatus];
  dashboardStatusItem.tooltip = statusTooltip(
    `${statusColorMeaning(displayStatus)} Project health: ${healthStatus}.`
      + healthGateSummary(health, projectId)
      + (readError ? ` ${statusReadFailure(readError)}` : '')
      + ` ${reviewSummary}. `
      + (storageWarning ? `${storageWarning} ` : '')
      + 'Click to open the project-scoped dashboard.',
  );
  return healthStatus;
}

function resetStatusBarHealth() {
  if (!dashboardStatusItem) return;
  dashboardStatusItem.text = '$(circle-filled) CuratorMD V2';
  dashboardStatusItem.color = STATUS_COLORS.neutral;
  dashboardStatusItem.tooltip = statusTooltip(
    `${statusColorMeaning('neutral')} Click to open the project dashboard.`,
  );
}

async function refreshStatusBarHealthFromWorkspace(spawnProcess = spawn) {
  const generation = ++statusRefreshGeneration;
  const workspace = vscode.workspace
    && vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!workspace) {
    resetStatusBarHealth();
    return 'neutral';
  }
  const projectRoot = workspace.uri.fsPath;
  if (!fs.existsSync(projectRoot) || !fs.existsSync(path.join(projectRoot, '.curatormd-v2.toml'))) {
    resetStatusBarHealth();
    return 'neutral';
  }

  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  if (hasWorkspaceSettingOverride(configuration,
    ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand'])) {
    resetStatusBarHealth();
    return 'neutral';
  }
  const databasePath = configuration.get('databasePath', '');
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  const hermesCommand = configuration.get('hermesCommand', 'hermes');
  if (!databasePath || !profileId || !serverCommand || !hermesCommand) {
    resetStatusBarHealth();
    return 'neutral';
  }

  const client = new McpStdioClient(serverCommand, [
    '--project-root', projectRoot,
    '--database', databasePath,
    '--profile-id', profileId,
  ], projectRoot, profileId, spawnProcess);
  try {
    await client.initialize();
    const page = JSON.parse(await client.callTool('goal_list_page', { offset: 0, limit: 1 }));
    if (!page || typeof page.project_id !== 'string' || !page.project_id) {
      throw curatorError('status-project-invalid', 'Curator returned no project binding.');
    }
    const [reviewWire, health, storage] = await Promise.all([
      client.callTool('sde_review_queue_cards', { limit: REVIEW_QUEUE_SIZE })
        .then((wire) => JSON.parse(wire)),
      readHermesHealthProbe(hermesCommand, profileId, page.project_id, projectRoot, spawnProcess),
      client.callTool('project_storage_usage', {})
        .then((wire) => JSON.parse(wire))
        .catch(() => null),
    ]);
    const reviews = validateReviewQueue(reviewWire, page.project_id);
    if (generation !== statusRefreshGeneration
      || vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath !== projectRoot) {
      return 'unknown';
    }
    updateStatusBarHealth(health, page.project_id, reviews, storage);
    if (reviews === null) return 'unknown';
    if (health.status !== 'healthy') return health.status;
    return reviews.length > 0 ? 'review' : 'healthy';
  } catch (error) {
    if (generation === statusRefreshGeneration
      && vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath === projectRoot) {
      updateStatusBarHealth(null, null, null, null, error);
    }
    return 'unknown';
  } finally {
    client.close();
  }
}

async function showDashboard(spawnProcess = spawn) {
  const workspace = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!workspace) {
    resetStatusBarHealth();
    vscode.window.showWarningMessage('Open a Curator-enabled project folder first.');
    return;
  }
  const projectConfigPath = path.join(workspace.uri.fsPath, '.curatormd-v2.toml');
  if (fs.existsSync(workspace.uri.fsPath) && !fs.existsSync(projectConfigPath)) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(
      'This folder has no .curatormd-v2.toml. Open a configured Curator V2 consumer project with an active local read grant.',
    );
    return;
  }
  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  const workspaceOverride = hasWorkspaceSettingOverride(
    configuration,
    ['databasePath', 'profileId', 'serverCommand', 'reviewCommand', 'hermesCommand'],
  );
  const databasePath = configuration.get('databasePath', '');
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  const hermesCommand = configuration.get('hermesCommand', 'hermes');
  const configuredReviewCommand = configuration.get('reviewCommand', '');
  const reviewCommand = configuredReviewCommand || defaultReviewCommand(serverCommand);
  if (workspaceOverride) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(
      'Curator launcher, database, profile, and review CLI settings must be set in User settings, not the project.',
    );
    return;
  }
  if (!databasePath || !profileId || !serverCommand || !hermesCommand) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(
      'Set CuratorMD V2 databasePath and profileId in VS Code settings before opening the dashboard.',
    );
    return;
  }

  const panel = vscode.window.createWebviewPanel(
    'curatormdV2Dashboard',
    'CuratorMD V2',
    vscode.ViewColumn.One,
    { enableScripts: true, localResourceRoots: [] },
  );
  panel.webview.html = dashboardHtml(panel.webview);
  let goalIds = new Set();
  let candidateIds = new Set();
  let projectId = null;
  const reportRevisions = new Map();
  const reportFacts = new Map();
  const reportPages = new Map();
  let requestInProgress = false;

  const withClient = async (operation) => {
    if (requestInProgress) throw new Error('A Curator read is already in progress.');
    requestInProgress = true;
    updateStatusBarHealth(null, null);
    const args = [
      '--project-root', workspace.uri.fsPath,
      '--database', databasePath,
      '--profile-id', profileId,
    ];
    const client = new McpStdioClient(
      serverCommand,
      args,
      workspace.uri.fsPath,
      profileId,
      spawnProcess,
    );
    try {
      await client.initialize();
      return await operation(client);
    } finally {
      client.close();
      requestInProgress = false;
    }
  };

  panel.webview.onDidReceiveMessage(async (message) => {
    try {
      if (!message || typeof message.type !== 'string') return;
      if (message.type === 'loadGoals') {
        candidateIds.clear();
        reportRevisions.clear();
        reportFacts.clear();
        reportPages.clear();
        goalIds.clear();
        projectId = null;
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        const result = await withClient(async (client) => {
          const activityRequest = client.callTool('project_activity_status', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const storageRequest = client.callTool('project_storage_usage', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const metricsRequest = client.callTool('project_metrics', {})
            .catch(() => null);
          const pageRequest = client.callTool('goal_list_page', {
            offset,
            limit: GOAL_PAGE_SIZE,
          }).then((wire) => JSON.parse(wire));
          const reviewRequest = client.callTool('sde_review_queue_cards', {
            limit: REVIEW_QUEUE_SIZE,
          }).then((wire) => JSON.parse(wire)).catch(() => null);
          const [activity, storage, metrics, page, reviews] = await Promise.all([
            activityRequest,
            storageRequest,
            metricsRequest,
            pageRequest,
            reviewRequest,
          ]);
          let health = null;
          let healthProbeError = null;
          if (typeof page.project_id === 'string' && page.project_id) {
            try {
              health = await readHermesHealthProbe(
                hermesCommand,
                profileId,
                page.project_id,
                workspace.uri.fsPath,
                spawnProcess,
              );
            } catch (error) {
              healthProbeError = error && typeof error.code === 'string'
                ? error.code : 'hermes-probe-failed';
            }
          }
          return { health, healthProbeError, activity, storage, metrics, page, reviews };
        });
        const { page, health, healthProbeError, activity, storage, metrics, reviews } = result;
        if (page.project_id !== undefined && page.project_id !== '') {
          projectId = page.project_id;
          goalIds = new Set((page.goals || []).map((goal) => goal.goal_id));
        }
        const reviewItems = validateReviewQueue(reviews, page.project_id);
        updateStatusBarHealth(health, page.project_id, reviewItems, storage);
        candidateIds = new Set((reviewItems || []).map((item) => item.candidate.candidate_id));
        panel.webview.postMessage({
          type: 'goals', page, health, activity, storage, reviews: reviewItems,
          healthProbeError,
          goalStatesSummary: summarizeGoalStates(activity, page.project_id),
          queueSummary: summarizeOperationalQueues(health, page.project_id),
          alertSummary: summarizeOperationalAlerts(health, storage, metrics, page.project_id),
          reviewAvailable: Boolean(reviewCommand),
        });
      } else if (message.type === 'loadReport' && goalIds.has(message.goalId)) {
        const factOffset = Number.isSafeInteger(message.factOffset) && message.factOffset >= 0
          ? message.factOffset : 0;
        const report = await withClient((client) => client.callTool('goal_report', {
          goal_id: message.goalId,
          fact_offset: factOffset,
          fact_limit: REPORT_PAGE_SIZE,
        }));
        const match = report.match(/Facts to date \(showing\s+\d+–\d+\s+of\s+(\d+)\)/);
        const revisionMatch = report.match(/^- Report snapshot: `([a-f0-9]{64})`$/m);
        const reportRevision = revisionMatch ? revisionMatch[1] : null;
        if (!match || !reportRevision) {
          throw curatorError('invalid-response', 'Curator V2 returned an incomplete goal report.');
        }
        if (factOffset > 0) {
          const priorRevision = reportRevisions.get(message.goalId);
          if (!priorRevision || priorRevision !== reportRevision) {
            panel.webview.postMessage({ type: 'reportStale', goalId: message.goalId });
            return;
          }
        }
        if (factOffset === 0 && reportRevision) {
          reportRevisions.set(message.goalId, reportRevision);
        }
        const factIds = reportFactIds(report);
        reportFacts.set(message.goalId, factIds);
        reportPages.set(message.goalId, {
          fact_offset: factOffset,
          fact_limit: REPORT_PAGE_SIZE,
        });
        panel.webview.postMessage({
          type: 'report',
          goalId: message.goalId,
          factOffset,
          factTotal: match ? Number(match[1]) : 0,
          reportRevision,
          report,
        });
      } else if (message.type === 'loadEvidence'
        && goalIds.has(message.goalId)
        && typeof message.factId === 'string'
        && reportFacts.get(message.goalId)?.has(message.factId)
        && reportPages.get(message.goalId)?.fact_offset === message.factOffset
        && reportRevisions.get(message.goalId) === message.reportRevision) {
        const page = reportPages.get(message.goalId);
        const evidence = await withClient(async (client) => JSON.parse(
          await client.callTool('goal_fact_evidence', {
            goal_id: message.goalId,
            fact_id: message.factId,
            ...page,
          }),
        ));
        if (evidence.report_revision !== reportRevisions.get(message.goalId)) {
          panel.webview.postMessage({ type: 'reportStale', goalId: message.goalId });
          return;
        }
        if (!isBoundedFactEvidence(
          evidence, projectId, message.goalId, message.factId, message.reportRevision,
        )) {
          throw curatorError('invalid-response', 'Curator returned an invalid MCP response.');
        }
        panel.webview.postMessage({ type: 'evidence', evidence, factOffset: message.factOffset });
      } else if (message.type === 'openReview'
        && typeof message.candidateId === 'string'
        && typeof reviewCommand === 'string' && reviewCommand.trim().length > 0
        && candidateIds.has(message.candidateId)) {
        const terminal = vscode.window.createTerminal({
          name: 'Curator V2 SDE Review',
          cwd: workspace.uri.fsPath,
        });
        const command = [
          reviewCommand,
          '--project-root', workspace.uri.fsPath,
          '--database', databasePath,
          'review', message.candidateId,
        ].map(quotePosixShellArgument).join(' ');
        terminal.show();
        terminal.sendText(command, true);
      }
    } catch (error) {
      goalIds.clear();
      candidateIds.clear();
      reportRevisions.clear();
      reportFacts.clear();
      reportPages.clear();
      projectId = null;
      updateStatusBarHealth(null, null);
      panel.webview.postMessage({
        type: 'error',
        message: dashboardErrorMessage(error),
      });
    }
  });

  panel.onDidDispose(() => {
    goalIds.clear();
    candidateIds.clear();
  });
}

function dashboardHtml(webview) {
  const nonce = randomBytes(24).toString('base64');
  const csp = webview.cspSource;
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${csp} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CuratorMD V2</title>
  <style>
    body { color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); padding: 1rem 1.4rem; }
    button { color: var(--vscode-button-foreground); background: var(--vscode-button-background); border: 0; padding: .4rem .7rem; margin: .2rem; cursor: pointer; }
    button:disabled { opacity: .5; cursor: default; }
    #goals { display: flex; flex-wrap: wrap; gap: .3rem; margin: .8rem 0; }
    #report { white-space: pre-wrap; overflow-wrap: anywhere; font-family: var(--vscode-editor-font-family); line-height: 1.5; }
    #notice { color: var(--vscode-descriptionForeground); margin: .6rem 0; }
    #error { color: var(--vscode-errorForeground); }
  </style>
</head>
<body>
  <h1>CuratorMD V2</h1>
  <p id="notice">Reads are project-scoped and reauthorized by Curator on each request. Refresh replaces the current page; pages are never joined across reads.</p>
  <section aria-labelledby="healthHeading">
    <h2 id="healthHeading">Project health</h2>
    <p id="health" role="status">Loading an authorized health snapshot…</p>
    <p id="alerts" role="status" aria-live="polite">Loading operational alerts…</p>
  </section>
  <section aria-labelledby="activityHeading">
    <h2 id="activityHeading">Retained activity</h2>
    <p id="activity" role="status">Loading authorized activity totals…</p>
    <p id="goalStates" role="status">Loading goal states…</p>
  </section>
  <section aria-labelledby="queuesHeading">
    <h2 id="queuesHeading">Operational queues</h2>
    <p id="queues" role="status">Loading authorized queue counts…</p>
  </section>
  <section aria-labelledby="storageHeading">
    <h2 id="storageHeading">Storage usage</h2>
    <p id="storage" role="status">Loading authorized storage totals…</p>
  </section>
  <div><button id="refresh">Refresh goals</button> <button id="previousGoals">Previous goals</button> <button id="nextGoals">Next goals</button></div>
  <p id="goalPage"></p><div id="goals"></div>
  <section aria-labelledby="reviewsHeading">
    <h2 id="reviewsHeading">Pending SDE review</h2>
    <p id="reviewNote" role="status">Loading authorized review queue…</p>
    <div id="reviews"></div>
  </section>
  <h2 id="selected"></h2>
  <div><button id="previousFacts">Previous facts</button> <button id="nextFacts">Next facts</button></div>
  <p id="factPage"></p><p id="error" role="alert"></p><pre id="report"></pre>
  <section aria-labelledby="evidenceHeading">
    <h3 id="evidenceHeading">Evidence references</h3>
    <p id="evidenceStatus" role="status">Select a fact to inspect its bounded evidence references.</p>
    <div id="evidenceButtons"></div><div id="evidenceRefs"></div>
  </section>
  <script nonce="${nonce}">
    const api = acquireVsCodeApi();
    let goalOffset = 0;
    let goalTotal = 0;
    let selectedGoal = null;
    let factOffset = 0;
    let factTotal = 0;
    let reportRevision = null;
    const goals = document.getElementById('goals');
    const report = document.getElementById('report');
    const evidenceStatus = document.getElementById('evidenceStatus');
    const evidenceButtons = document.getElementById('evidenceButtons');
    const evidenceRefs = document.getElementById('evidenceRefs');
    const error = document.getElementById('error');
    const health = document.getElementById('health');
    const alertSummary = document.getElementById('alerts');
    const activitySummary = document.getElementById('activity');
    const goalStatesSummary = document.getElementById('goalStates');
    const queueSummary = document.getElementById('queues');
    const storageSummary = document.getElementById('storage');
    const reviewSummary = document.getElementById('reviewNote');
    const reviews = document.getElementById('reviews');
    function formatBytes(value) {
      if (value === null) return 'unavailable';
      if (value < 1024) return value + ' B';
      if (value < 1048576) return (value / 1024).toFixed(1) + ' KiB';
      return (value / 1048576).toFixed(1) + ' MiB';
    }
    function clearDashboard() {
      selectedGoal = null;
      factOffset = 0;
      factTotal = 0;
      reportRevision = null;
      goals.replaceChildren();
      reviews.replaceChildren();
      reviewSummary.textContent = 'Pending SDE review: unknown. Refresh to retry the authorized queue read.';
      report.textContent = '';
      evidenceButtons.replaceChildren();
      evidenceRefs.replaceChildren();
      evidenceStatus.textContent = 'Select a fact to inspect its bounded evidence references.';
      health.textContent = 'Project health: unknown. Refresh to retry the health read.';
      alertSummary.textContent = 'Operational alerts: unknown. Refresh to retry project snapshots.';
      activitySummary.textContent = 'Retained activity: unknown. Refresh to retry the activity read.';
      goalStatesSummary.textContent = 'Goal states: unknown. Refresh to retry the activity read.';
      queueSummary.textContent = 'Operational queues: unknown. Refresh to retry the health read.';
      storageSummary.textContent = 'Storage usage: unknown. Refresh to retry the storage read.';
      document.getElementById('selected').textContent = '';
      document.getElementById('goalPage').textContent = '';
      document.getElementById('factPage').textContent = '';
      document.getElementById('previousGoals').disabled = true;
      document.getElementById('nextGoals').disabled = true;
      document.getElementById('previousFacts').disabled = true;
      document.getElementById('nextFacts').disabled = true;
    }
    function requestGoals(offset) {
      goalOffset = offset;
      selectedGoal = null;
      reportRevision = null;
      report.textContent = '';
      evidenceButtons.replaceChildren();
      evidenceRefs.replaceChildren();
      evidenceStatus.textContent = 'Select a fact to inspect its bounded evidence references.';
      goals.replaceChildren();
      reviews.replaceChildren();
      reviewSummary.textContent = 'Loading the authorized review queue…';
      document.getElementById('selected').textContent = '';
      document.getElementById('factPage').textContent = '';
      document.getElementById('goalPage').textContent = 'Loading a fresh authorized goal page…';
      health.textContent = 'Loading an authorized health snapshot…';
      alertSummary.textContent = 'Loading operational alerts…';
      activitySummary.textContent = 'Loading authorized activity totals…';
      storageSummary.textContent = 'Loading authorized storage totals…';
      api.postMessage({ type: 'loadGoals', offset });
      error.textContent = '';
    }
    function requestReport(offset) {
      if (!selectedGoal) return;
      factOffset = offset;
      report.textContent = 'Loading a fresh authorized report page…';
      evidenceButtons.replaceChildren();
      evidenceRefs.replaceChildren();
      evidenceStatus.textContent = 'Evidence references are cleared while the report refreshes.';
      document.getElementById('factPage').textContent = '';
      api.postMessage({ type: 'loadReport', goalId: selectedGoal, factOffset: offset });
      error.textContent = '';
    }
    function formatLocalTimestamp(value) {
      if (typeof value !== 'string' || value.length > 64) return 'unknown';
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return value;
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit',
        day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
        hourCycle: 'h23',
      }).formatToParts(parsed).reduce((result, part) => {
        result[part.type] = part.value;
        return result;
      }, {});
      return parts.year + '-' + parts.month + '-' + parts.day + ' '
        + parts.hour + ':' + parts.minute + ':' + parts.second + ' +07:00';
    }
    function renderEvidenceButtons() {
      evidenceButtons.replaceChildren();
      const delimiter = String.fromCharCode(96);
      const ids = [];
      for (const line of report.textContent.split(/\\r?\\n/)) {
        const prefix = '- ' + delimiter;
        if (!line.startsWith(prefix)) continue;
        const end = line.indexOf(delimiter, prefix.length);
        if (end <= prefix.length || line.slice(end + 1, end + 4) !== ' — ') continue;
        ids.push(line.slice(prefix.length, end));
      }
      if (!ids.length) {
        evidenceStatus.textContent = 'This report page has no facts with evidence references.';
        return;
      }
      evidenceStatus.textContent = 'Choose a fact to read its source locator, digest, and verification receipt.';
      for (const factId of ids) {
        const button = document.createElement('button');
        button.textContent = 'Evidence for ' + factId.slice(0, 16);
        button.addEventListener('click', () => {
          evidenceStatus.textContent = 'Loading an authorized evidence reference…';
          evidenceRefs.replaceChildren();
          api.postMessage({
            type: 'loadEvidence', goalId: selectedGoal, factId, reportRevision, factOffset,
          });
        });
        evidenceButtons.appendChild(button);
      }
    }
    function renderEvidence(value) {
      evidenceRefs.replaceChildren();
      const evidenceIsCurrent = value.evidence.length > 0 && value.evidence.every((reference) => {
        if (reference.outcome !== 'passed' || !reference.attestation) return false;
        const validUntil = Date.parse(reference.attestation.valid_until);
        return Number.isFinite(validUntil) && validUntil > Date.now();
      });
      const verificationStatus = value.verification_status === 'verified_fact'
        && (!evidenceIsCurrent || value.fact_kind !== 'verification')
        ? 'stale/unknown' : value.verification_status;
      evidenceStatus.textContent = value.fact_kind + ' ' + verificationStatus
        + '; criterion ' + (value.criterion_id || 'not applicable')
        + '; report ' + value.report_revision.slice(0, 12) + '.';
      if (!value.evidence.length) {
        evidenceStatus.textContent += ' No evidence references recorded.';
        return;
      }
      for (const reference of value.evidence) {
        const paragraph = document.createElement('p');
        const fields = [
          'Kind: ' + reference.evidence_kind,
          'Outcome: ' + reference.outcome,
          'Locator: ' + reference.locator,
          'SHA-256: ' + reference.sha256,
          reference.occurrence_id ? 'Occurrence: ' + reference.occurrence_id : null,
        ];
        const attestation = reference.attestation;
        if (attestation) {
          fields.push('Verifier: ' + attestation.adapter_id);
          fields.push('Subject: ' + attestation.authenticated_subject);
          fields.push('Source revision: ' + attestation.source_revision);
          fields.push('Observed: ' + formatLocalTimestamp(attestation.observed_at));
          fields.push('Valid until: ' + formatLocalTimestamp(attestation.valid_until));
          fields.push('Revocation checked: ' + formatLocalTimestamp(attestation.revocation_checked_at));
        }
        paragraph.textContent = fields.filter(Boolean).join(' · ');
        evidenceRefs.appendChild(paragraph);
      }
    }
    document.getElementById('refresh').addEventListener('click', () => requestGoals(0));
    document.getElementById('previousGoals').addEventListener('click', () => requestGoals(Math.max(0, goalOffset - ${GOAL_PAGE_SIZE})));
    document.getElementById('nextGoals').addEventListener('click', () => requestGoals(goalOffset + ${GOAL_PAGE_SIZE}));
    document.getElementById('previousFacts').addEventListener('click', () => requestReport(Math.max(0, factOffset - ${REPORT_PAGE_SIZE})));
    document.getElementById('nextFacts').addEventListener('click', () => requestReport(factOffset + ${REPORT_PAGE_SIZE}));
    window.addEventListener('message', (event) => {
      const message = event.data;
      if (message.type === 'error') {
        clearDashboard();
        error.textContent = message.message;
        return;
      }
      error.textContent = '';
      if (message.type === 'reportStale' && message.goalId === selectedGoal) {
        report.textContent = '';
        evidenceButtons.replaceChildren();
        evidenceRefs.replaceChildren();
        evidenceStatus.textContent = 'Evidence references cleared because the report changed.';
        document.getElementById('factPage').textContent = 'The report changed. Restarting from the first page…';
        requestReport(0);
        return;
      }
      if (message.type === 'goals') {
        const page = message.page;
        const healthSnapshot = message.health;
        const activitySnapshot = message.activity;
        const healthProjectMatches = healthSnapshot
          && healthSnapshot.project_id === page.project_id;
        const validHealthStatus = healthSnapshot
          && ['healthy', 'degraded', 'unknown'].includes(healthSnapshot.status);
        const healthStatus = healthProjectMatches && validHealthStatus
          ? healthSnapshot.status : 'unknown';
        const healthGates = !healthSnapshot
          ? ['health_read_unavailable']
          : !healthProjectMatches
            ? ['health_project_mismatch']
            : !validHealthStatus || !Array.isArray(healthSnapshot.gate_codes)
              ? ['health_observation_invalid']
              : healthSnapshot.gate_codes.filter((gate) => typeof gate === 'string');
        const probeFailure = {
          'hermes-probe-start': 'Hermes could not start. Check the User setting hermesCommand.',
          'hermes-probe-exit': 'Hermes did not complete its trusted health read. Check that its Curator status probe is supported.',
          'hermes-probe-timeout': 'Hermes health read timed out. Try Refresh after checking the profile.',
          'hermes-probe-invalid': 'Hermes returned an invalid or project-mismatched health snapshot.',
          'hermes-probe-failed': 'Hermes health read failed. Check the profile and try again.',
        }[message.healthProbeError];
        health.textContent = 'Project health: ' + healthStatus + '. Open gates: '
          + (healthGates.length ? healthGates.join(', ') : 'none reported') + '.'
          + (probeFailure ? ' ' + probeFailure : '');
        alertSummary.textContent = typeof message.alertSummary === 'string'
          ? message.alertSummary : 'Operational alerts: unknown. Alert summary unavailable.';
        queueSummary.textContent = typeof message.queueSummary === 'string'
          ? message.queueSummary : 'Operational queues: unknown. Snapshot unavailable.';
        goalStatesSummary.textContent = typeof message.goalStatesSummary === 'string'
          ? message.goalStatesSummary : 'Goal states: unknown. Snapshot unavailable.';
        const activityFields = [
          'event_receipt_count', 'processed_event_count', 'received_event_count',
          'failed_event_count', 'quarantined_event_count', 'goal_count',
          'fact_count', 'pending_sde_count', 'approved_sde_count',
          'rejected_sde_count',
        ];
        const activityValid = activitySnapshot
          && activitySnapshot.project_id === page.project_id
          && activityFields.every((field) => Number.isSafeInteger(activitySnapshot[field])
            && activitySnapshot[field] >= 0);
        if (!activitySnapshot) {
          activitySummary.textContent = 'Retained activity: unknown. Activity read unavailable.';
        } else if (activitySnapshot.project_id !== page.project_id) {
          activitySummary.textContent = 'Retained activity: unknown. Project mismatch.';
        } else if (!activityValid) {
          activitySummary.textContent = 'Retained activity: unknown. Invalid activity snapshot.';
        } else {
          activitySummary.textContent = 'Retained receipts: ' + activitySnapshot.event_receipt_count
            + ' (processed ' + activitySnapshot.processed_event_count
            + ', received ' + activitySnapshot.received_event_count
            + ', failed ' + activitySnapshot.failed_event_count
            + ', quarantined ' + activitySnapshot.quarantined_event_count
            + '); goals ' + activitySnapshot.goal_count + '; facts ' + activitySnapshot.fact_count
            + '; SDE candidates pending ' + activitySnapshot.pending_sde_count
            + ', approved ' + activitySnapshot.approved_sde_count
            + ', rejected ' + activitySnapshot.rejected_sde_count + '.';
        }
        const storageSnapshot = message.storage;
        const storageFields = [
          'logical_record_bytes', 'event_payload_bytes_retained', 'fact_count',
          'fact_count_limit', 'fact_record_bytes', 'fact_record_bytes_limit',
        ];
        const validOptionalBytes = (value) => value === null
          || (Number.isSafeInteger(value) && value >= 0);
        const stagingSnapshot = storageSnapshot && storageSnapshot.staging;
        const stagingValid = stagingSnapshot
          && Number.isSafeInteger(stagingSnapshot.observed_file_bytes)
          && stagingSnapshot.observed_file_bytes >= 0
          && typeof stagingSnapshot.inventory_complete === 'boolean'
          && (stagingSnapshot.error_code === null
            || (typeof stagingSnapshot.error_code === 'string'
              && /^[a-z][a-z0-9_]{0,79}$/.test(stagingSnapshot.error_code)))
          && (stagingSnapshot.inventory_complete
            ? stagingSnapshot.error_code === null
            : stagingSnapshot.error_code !== null);
        const stagingLimitValid = storageSnapshot
          && (storageSnapshot.staging_project_byte_limit === null
            || (Number.isSafeInteger(storageSnapshot.staging_project_byte_limit)
              && storageSnapshot.staging_project_byte_limit > 0));
        const storageValid = storageSnapshot
          && storageSnapshot.project_id === page.project_id
          && storageFields.every((field) => Number.isSafeInteger(storageSnapshot[field])
            && storageSnapshot[field] >= 0)
          && storageSnapshot.fact_count_limit > 0
          && storageSnapshot.fact_record_bytes_limit > 0
          && validOptionalBytes(storageSnapshot.global_database_bytes)
          && validOptionalBytes(storageSnapshot.global_wal_bytes)
          && stagingValid
          && stagingLimitValid;
        if (!storageSnapshot) {
          storageSummary.textContent = 'Storage usage: unknown. Storage read unavailable.';
        } else if (storageSnapshot.project_id !== page.project_id) {
          storageSummary.textContent = 'Storage usage: unknown. Project mismatch.';
        } else if (!storageValid) {
          storageSummary.textContent = 'Storage usage: unknown. Invalid storage snapshot.';
        } else {
          let stagingText;
          const stagingLimit = storageSnapshot.staging_project_byte_limit;
          if (!stagingSnapshot.inventory_complete) {
            stagingText = 'Staging scan incomplete; observed at least '
              + formatBytes(stagingSnapshot.observed_file_bytes)
              + ' (code ' + stagingSnapshot.error_code + ').';
          } else if (stagingLimit === null) {
            stagingText = 'Staging scan complete at '
              + formatBytes(stagingSnapshot.observed_file_bytes)
              + '; no byte warning threshold is configured.';
          } else {
            const ratio = stagingSnapshot.observed_file_bytes / stagingLimit;
            const level = ratio >= 1
              ? 'warning threshold reached'
              : ratio >= 0.75 ? 'warning level reached' : 'below warning level';
            stagingText = 'Staging '
              + formatBytes(stagingSnapshot.observed_file_bytes) + ' / '
              + formatBytes(stagingLimit) + ' warning-only threshold; '
              + level + ', and writes remain allowed.';
          }
          storageSummary.textContent = 'Project logical records '
            + formatBytes(storageSnapshot.logical_record_bytes)
            + '; retained event payload '
            + formatBytes(storageSnapshot.event_payload_bytes_retained)
            + '; facts ' + storageSnapshot.fact_count + '/'
            + storageSnapshot.fact_count_limit + ' ('
            + formatBytes(storageSnapshot.fact_record_bytes) + '/'
            + formatBytes(storageSnapshot.fact_record_bytes_limit) + '). Shared SQLite files: database '
            + formatBytes(storageSnapshot.global_database_bytes) + ', WAL '
            + formatBytes(storageSnapshot.global_wal_bytes)
            + ', combined ' + formatBytes(
              storageSnapshot.global_database_bytes === null
                || storageSnapshot.global_wal_bytes === null
                ? null
                : storageSnapshot.global_database_bytes + storageSnapshot.global_wal_bytes,
            ) + ' / ' + formatBytes(${SQLITE_WARNING_BYTES})
            + ' warning-only threshold; '
            + (storageSnapshot.global_database_bytes === null
              || storageSnapshot.global_wal_bytes === null
              ? 'combined size unavailable'
              : storageSnapshot.global_database_bytes + storageSnapshot.global_wal_bytes > ${SQLITE_WARNING_BYTES}
                ? 'warning: combined SQLite size is above threshold'
                : 'below threshold')
            + '. SQLite manages WAL checkpointing; writes remain allowed. '
            + stagingText + ' Model/token usage is not reported here.';
        }
        goalTotal = page.total || 0;
        goalOffset = page.offset || 0;
        document.getElementById('goalPage').textContent = 'Goals ' + (goalTotal ? goalOffset + 1 : 0) + '–' + Math.min(goalOffset + (page.goals || []).length, goalTotal) + ' of ' + goalTotal;
        goals.replaceChildren();
        for (const goal of page.goals || []) {
          const button = document.createElement('button');
          button.textContent = goal.status + ': ' + goal.problem;
          button.addEventListener('click', () => {
            selectedGoal = goal.goal_id;
            factOffset = 0;
            factTotal = 0;
            reportRevision = null;
            document.getElementById('selected').textContent = goal.problem;
            requestReport(0);
          });
          goals.appendChild(button);
        }
        reviews.replaceChildren();
        if (!Array.isArray(message.reviews)) {
          reviewSummary.textContent = 'Review queue: unavailable. Goal browsing remains available.';
        } else if (!message.reviews.length) {
          reviewSummary.textContent = 'No pending SDE candidates.';
        } else {
          reviewSummary.textContent = 'Pending review: ' + message.reviews.length
            + (message.reviews.length === ${REVIEW_QUEUE_SIZE} ? ' shown (queue limit reached).' : '.');
          for (const item of message.reviews) {
            const candidate = item && item.candidate;
            const goal = item && item.goal;
            if (!candidate || typeof candidate.candidate_id !== 'string'
              || typeof goal?.problem !== 'string') continue;
            const row = document.createElement('p');
            const label = document.createElement('span');
            label.textContent = candidate.materiality + ': ' + goal.problem
              + ' — ' + candidate.rationale;
            const button = document.createElement('button');
            button.textContent = 'Review in terminal';
            button.disabled = !message.reviewAvailable;
            button.addEventListener('click', () => api.postMessage({
              type: 'openReview', candidateId: candidate.candidate_id,
            }));
            row.appendChild(label);
            row.appendChild(button);
            reviews.appendChild(row);
          }
          if (!message.reviewAvailable) {
            reviewSummary.textContent += ' Configure the User-scoped reviewCommand to open the attended reviewer.';
          }
        }
        document.getElementById('previousGoals').disabled = goalOffset === 0;
        document.getElementById('nextGoals').disabled = page.next_offset === null || page.next_offset === undefined;
      } else if (message.type === 'report' && message.goalId === selectedGoal) {
        if (message.factOffset > 0 && reportRevision && message.reportRevision && reportRevision !== message.reportRevision) {
          report.textContent = '';
          document.getElementById('factPage').textContent = 'The report changed. Restarting from the first page…';
          requestReport(0);
          return;
        }
        if (message.factOffset === 0) reportRevision = message.reportRevision || null;
        factOffset = message.factOffset;
        factTotal = message.factTotal;
        report.textContent = message.report;
        evidenceRefs.replaceChildren();
        renderEvidenceButtons();
        const revisionLabel = reportRevision ? ' Snapshot ' + reportRevision.slice(0, 12) + '.' : '';
        document.getElementById('factPage').textContent = 'Facts ' + (factTotal ? factOffset + 1 : 0) + '–' + Math.min(factOffset + ${REPORT_PAGE_SIZE}, factTotal) + ' of ' + factTotal + '.' + revisionLabel + ' This page is a fresh read; the previous page was cleared.';
        document.getElementById('previousFacts').disabled = factOffset === 0;
        document.getElementById('nextFacts').disabled = factOffset + ${REPORT_PAGE_SIZE} >= factTotal;
      } else if (message.type === 'evidence' && message.evidence.goal_id === selectedGoal
        && message.factOffset === factOffset) {
        if (!reportRevision || message.evidence.report_revision !== reportRevision) {
          report.textContent = '';
          evidenceButtons.replaceChildren();
          evidenceRefs.replaceChildren();
          evidenceStatus.textContent = 'Evidence references cleared because the report changed.';
          document.getElementById('factPage').textContent = 'The report changed. Restarting from the first page…';
          requestReport(0);
          return;
        }
        renderEvidence(message.evidence);
      }
    });
    requestGoals(0);
  </script>
</body>
</html>`;
}

function hasWorkspaceSettingOverride(configuration, settingNames) {
  return settingNames.some((name) => {
    const inspected = configuration.inspect(name);
    return inspected && (
      inspected.workspaceValue !== undefined ||
      inspected.workspaceFolderValue !== undefined
    );
  });
}

function quotePosixShellArgument(value) {
  const argument = String(value);
  if (/[\u0000-\u001f\u007f]/.test(argument)) {
    throw new Error('Curator review command arguments cannot contain control characters.');
  }
  return `'${argument.replace(/'/g, `'\\''`)}'`;
}

function defaultReviewCommand(serverCommand) {
  if (path.basename(serverCommand) === 'curatormd-v2-mcp') {
    return path.join(path.dirname(serverCommand), 'curatormd-v2-review');
  }
  return 'curatormd-v2-review';
}

function validateReviewQueue(value, projectId) {
  if (!value || typeof value !== 'object'
    || value.project_id !== projectId
    || !Array.isArray(value.candidates)
    || value.candidates.length > REVIEW_QUEUE_SIZE
    || typeof projectId !== 'string' || !projectId) return null;
  const candidateIds = new Set();
  for (const item of value.candidates) {
    const candidate = item && item.candidate;
    const goal = item && item.goal;
    if (!candidate || !goal
      || typeof candidate.candidate_id !== 'string'
      || !/^[A-Za-z0-9_-]{1,128}$/.test(candidate.candidate_id)
      || candidateIds.has(candidate.candidate_id)
      || candidate.status !== 'pending_review'
      || !['implementation', 'decision', 'recovery', 'verified_lesson'].includes(candidate.materiality)
      || typeof candidate.rationale !== 'string' || !candidate.rationale.trim()
      || candidate.rationale.length > 1000
      || typeof candidate.goal_id !== 'string'
      || candidate.goal_id !== goal.goal_id
      || goal.project_id !== projectId
      || typeof goal.problem !== 'string' || !goal.problem.trim()
      || goal.problem.length > 4000) return null;
    candidateIds.add(candidate.candidate_id);
  }
  return value.candidates.map(({ candidate, goal }) => ({
    candidate: {
      candidate_id: candidate.candidate_id,
      goal_id: candidate.goal_id,
      status: candidate.status,
      materiality: candidate.materiality,
      rationale: candidate.rationale,
    },
    goal: {
      goal_id: goal.goal_id,
      project_id: goal.project_id,
      problem: goal.problem,
    },
  }));
}

module.exports = {
  activate,
  deactivate,
  McpStdioClient,
  dashboardHtml,
  defaultReviewCommand,
  parseHermesHealthProbe,
  readHermesHealthProbe,
  startGoalFromWorkspace,
  dashboardErrorMessage,
  summarizeGoalStates,
  summarizeEventFailureCategories,
  summarizeOperationalQueues,
  summarizeOperationalAlerts,
  hasWorkspaceSettingOverride,
  quotePosixShellArgument,
  showDashboard,
  statusColorMeaning,
  sqliteSizeWarning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  validateReviewQueue,
};
