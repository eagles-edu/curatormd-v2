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
  action: '#4daafc',
  neutral: new vscode.ThemeColor('textLink.foreground'),
});
const STATUS_COLOR_MEANINGS = Object.freeze({
  healthy: 'Green means project health is healthy.',
  review: 'Purple marks operational work that needs attention.',
  unknown: 'Yellow means the health or SDE review count is unknown.',
  degraded: 'Red means project health is degraded.',
  action: 'Blue means SDE reviews are outstanding; click to open their review document.',
  neutral: 'Blue means no health read has been attempted.',
});
const STATUS_READ_FAILURES = Object.freeze({
  'launcher-start': 'Curator did not start; check the Curator launcher in VS Code User settings.',
  'launcher-exit': 'Curator MCP transport closed. Save your work, then reload the VS Code window (Codex host) or start a fresh Codex session. Do not re-enroll the project or recreate its grants.',
  'project-config-stale': 'This project config changed after registration. Run the attended curatormd-v2-access update for this project, then refresh. Do not re-enroll the project or recreate its grants.',
  'project-repository-mismatch': 'The selected workspace does not match this project registration. Check the workspace and database binding; do not re-enroll automatically.',
  'project-registration-missing': 'This database has no registration for the configured project. Check the database binding before using attended project registration.',
  'project-registration-inactive': 'This project registration is inactive. Review its access state before attempting recovery.',
  'consumer-binding-missing': 'This project has no consumer binding in the selected database. Check the database binding and lifecycle records.',
  'consumer-binding-inactive': 'This project consumer binding is inactive. Review its access state before attempting recovery.',
  'project-database-bindings-unavailable': 'The owner-only Codex project database map is missing or invalid. Check ~/.config/curatormd-v2/database-bindings.json and its file permissions.',
  'project-database-binding-missing': 'No database is mapped for this exact project ID. Add its owner-managed database binding; Curator will not use another project database.',
  'project-database-file-invalid': 'The mapped project database is missing, shared, or not an owner-controlled regular file.',
  'project-read-grant-missing': 'This local identity has no active project read grant. Review the configured project access grant.',
  'project-write-grant-missing': 'This local identity has no active project write grant for the requested operation.',
  'project-review-grant-missing': 'This local identity has no active project review grant for the requested operation.',
  'project-event-retry-grant-missing': 'This local identity has no active event-retry grant for the requested operation.',
  'project-retention-hold-grant-missing': 'This local identity has no active retention-hold grant for the requested operation.',
  'project-purge-retry-grant-missing': 'This local identity has no active purge-retry grant for the requested operation.',
  'project-binding-changed': 'The project binding changed while Curator was starting. Refresh and retry against the current project state.',
  'launcher-runtime': 'Curator could not initialize its local runtime. Check the database, project config, and launcher installation.',
  'read-denied': 'Curator denied the project read; check its local project access grant.',
  'mcp-tool-error': 'Curator rejected the request; check the project grant and request details.',
  'mcp-request': 'Curator could not complete the project read; refresh to try again.',
  'invalid-response': 'Curator returned an unreadable response; check the local installation.',
  'response-too-large': 'Curator returned a response over the 4 MiB limit; refresh and inspect the local launcher.',
  timeout: 'Curator did not reply within 15 seconds; refresh to try again.',
  'hermes-probe-start': 'Hermes readiness check did not start; check the Hermes command in User settings.',
  'hermes-probe-exit': 'Hermes did not return a health snapshot; check the selected Hermes profile and retry.',
  'hermes-probe-profile-binding': 'No Hermes profile is mapped for this Curator project in VS Code User settings; set curatormdV2.hermesProfileBindings.',
  'hermes-probe-timeout': 'Hermes readiness check timed out; refresh to try again.',
  'hermes-probe-invalid': 'Hermes readiness data is incomplete; check the selected profile.',
  'hermes-probe-project-mismatch': 'Hermes returned health for a different project; check the selected profile binding.',
  'hermes-probe-stale': 'Hermes returned an old health result; refresh to try again.',
  'hermes-probe-unreconciled': 'Hermes health fields disagree; check the selected profile and refresh.',
  'hermes-probe-profile': 'The Hermes profile setting is invalid; check the User settings value.',
  'curator-queue-read': 'Curator could not read project queue counts; check the local project grant and database.',
  'curator-queue-invalid': 'Curator returned incomplete or unreadable queue data; refresh to try again.',
  'curator-queue-project-mismatch': 'Curator returned queue data for a different project; check the project grant.',
  'curator-queue-stale': 'Curator returned an old queue snapshot; refresh to try again.',
  'feed-auto-paused': 'Automatic checks are cooling down after repeated failures and will retry.',
  'status-project-invalid': 'Curator did not identify the configured project; check its project file and grant.',
  'status-project-mismatch': 'Curator returned a different project than this workspace config; check the project database binding.',
  'status-database-binding-invalid': 'No absolute database is mapped for this project; check curatormdV2.databaseBindings or databasePath in User settings.',
  'status-evidence-binding-invalid': 'The host evidence file for this project is invalid; check curatormdV2.evidenceConfigBindings in User settings.',
});
const MCP_ERROR_MESSAGES = Object.freeze({
  invalid_request: 'The request details were invalid; review the entered values.',
  forbidden: 'Curator denied this request; check the project access grant.',
  not_found: 'Curator could not find the requested project record; refresh the dashboard.',
  conflict: 'The project changed during the request; refresh and try again.',
  capacity_exceeded: 'The project reached a configured limit; review storage and queue status.',
  rate_limited: 'Curator is receiving requests too quickly; wait before retrying.',
  internal_error: 'Curator could not complete the request; check the local installation.',
});
const MCP_ERROR_CODES = new Set(Object.keys(MCP_ERROR_MESSAGES));
const STARTUP_ERROR_CODES = new Set([
  'project-config-stale', 'project-repository-mismatch',
  'project-registration-missing', 'project-registration-inactive',
  'consumer-binding-missing', 'consumer-binding-inactive', 'project-read-grant-missing',
  'project-database-bindings-unavailable', 'project-database-binding-missing',
  'project-database-file-invalid',
  'project-write-grant-missing', 'project-review-grant-missing',
  'project-event-retry-grant-missing', 'project-retention-hold-grant-missing',
  'project-purge-retry-grant-missing',
  'project-binding-changed', 'runtime',
]);
const MAX_STARTUP_DIAGNOSTIC_BYTES = 1024;
const TRANSPORT_CLOSED_MESSAGE = 'Curator MCP transport closed. Save your work, then reload the VS Code window (Codex host) or start a fresh Codex session. Do not re-enroll the project or recreate its grants.';
const HEALTH_GATE_LABELS = Object.freeze({
  event_backlog: 'Events are waiting to be processed.',
  event_failures: 'One or more events failed; check the inbox.',
  event_quarantine: 'One or more events need retry or review.',
  expired_event_claims: 'An event claim expired before processing finished.',
  sqlite_payload_scrub_pending: 'Temporary event data is waiting for SQLite cleanup.',
  review_backlog: 'An SDE proposal is waiting for your decision.',
  purge_pending: 'Approved cleanup is waiting to finish.',
  purge_artifacts_pending: 'One or more approved files still need cleanup.',
  expiry_purge_pending: 'Expired items are waiting for approved cleanup.',
  expiry_purge_artifacts_pending: 'Expired files are waiting for approved cleanup.',
  event_capacity_exhausted: 'The event inbox has reached its configured limit.',
  fact_capacity_exhausted: 'The project fact limit has been reached.',
  staging_observation_time_unavailable: 'The staging scan time is unavailable.',
  staging_budget_warning: 'Staging is near its warning limit; writes remain allowed.',
  staging_budget_reached: 'Staging is at its warning limit; writes remain allowed.',
  staging_inventory_incomplete: 'The staging scan is incomplete.',
  staging_adapter_unavailable: 'Curator could not scan the staging folder.',
  staging_inventory_unavailable: 'The staging inventory could not be read.',
  staged_artifacts_present: 'Temporary files remain in staging.',
  dependency_probe_failed: 'A required local readiness check failed.',
});
const HEALTH_DEPENDENCY_LABELS = Object.freeze({
  event_router: 'work-event routing',
  purge_scheduler: 'six-hour cleanup timer',
  database_storage_adapter: 'database health check',
  host_identity: 'Hermes host identity',
  human_review: 'local reviewer access',
  alert_delivery: 'maintenance journal',
  artifact_producer_inventory: 'Curator hook setup',
});
const REPORT_PAGE_SIZE = 16;
const GOAL_PAGE_SIZE = 20;
const REVIEW_QUEUE_SIZE = 100;
const REQUEST_TIMEOUT_MS = 15000;
const HERMES_HEALTH_TIMEOUT_MS = 20000;
const HERMES_HEALTH_RETRY_DELAY_MS = 1000;
const REVIEW_REFRESH_RETRY_DELAYS_MS = [0, 500, 1500];
const HERMES_HEALTH_MAX_BYTES = 32768;
const MAX_MCP_RESPONSE_LINE_BYTES = 4 * 1024 * 1024;
const MAX_HEALTH_PROBE_AGE_SECONDS = 60;
const MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS = 5;
const WORKSPACE_PROJECTION_MAX_AGE_SECONDS = 300;
const WORKSPACE_PROJECTION_CLOCK_SKEW_SECONDS = 5;
const STATUS_REFRESH_INTERVAL_MS = 60000;
const HEALTH_HISTORY_LIMIT = 60;
const OPERATIONAL_ERROR_LOG_LIMIT = 100;
const MAX_IDENTICAL_FEED_FAILURES = 3;
const FEED_FAILURE_COOLDOWN_MS = 60000;
const MAX_PROJECT_CONFIG_BYTES = 16 * 1024;
const PROJECT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SQLITE_WARNING_BYTES = 250 * 1024 * 1024;
const HOST_FILESYSTEM_WARNING_PERCENT = 10;
const HEALTH_RECOVERY_ACTIONS = Object.freeze({
  event_router: Object.freeze({ action: 'runEventRouter', actionLabel: 'Route queued events' }),
  purge_scheduler: Object.freeze({ action: 'retryPendingPurges', actionLabel: 'Retry approved cleanup' }),
  human_review: Object.freeze({ action: 'openReviewActions', actionLabel: 'Open reviews' }),
});
const REQUIRED_HEALTH_PROBES = Object.freeze([
  'event_router', 'purge_scheduler', 'database_storage_adapter', 'host_identity',
  'human_review', 'alert_delivery', 'artifact_producer_inventory',
]);
const REPORT_FACT_ID_PATTERN = /^- `([^`]{1,256})` — /;

function healthProbeFailureMessage(code) {
  return typeof code === 'string'
    && Object.prototype.hasOwnProperty.call(STATUS_READ_FAILURES, code)
    ? STATUS_READ_FAILURES[code]
    : 'Health could not be checked. Check the selected Hermes profile and retry.';
}

function queueProbeFailureMessage(code) {
  return typeof code === 'string'
    && Object.prototype.hasOwnProperty.call(STATUS_READ_FAILURES, code)
    ? STATUS_READ_FAILURES[code]
    : 'Curator queue data could not be checked; open the dashboard and refresh.';
}

function healthRecoveryAction(name) {
  return HEALTH_RECOVERY_ACTIONS[name] || {
    action: 'retryRecoveryReads',
    actionLabel: 'Recheck',
  };
}

function feedFailureMessage(code, lastFailureCode, autoPaused, messageForCode) {
  const reasonCode = typeof lastFailureCode === 'string' && lastFailureCode
    ? lastFailureCode : code;
  const reason = messageForCode(reasonCode);
  return autoPaused && reasonCode !== 'feed-auto-paused'
    ? `${reason} Automatic checks are cooling down and will retry.`
    : reason;
}

function healthGateLabel(code) {
  if (Object.prototype.hasOwnProperty.call(HEALTH_GATE_LABELS, code)) {
    return HEALTH_GATE_LABELS[code];
  }
  const dependency = /^dependency_(unknown|unavailable|degraded):([a-z][a-z0-9_]{0,63})$/.exec(code);
  if (dependency) {
    const label = HEALTH_DEPENDENCY_LABELS[dependency[2]];
    if (label) {
      if (dependency[1] === 'unknown') return `No fresh result is available for ${label}.`;
      return `The ${label} check is currently unavailable.`;
    }
  }
  return `Additional health gate: ${code.replace(/[_:.-]+/g, ' ')}.`;
}
let dashboardStatusItem;
let statusRefreshTimer;
let statusRefreshGeneration = 0;
const dashboardReloaders = new Map();
let healthHistoryStore = null;
const healthHistoryWrites = new Map();
const healthHistoryResetCutoffs = new Map();
const operationalErrorWrites = new Map();

function registerDashboardReloader(projectRoot, reload, panel) {
  const key = path.resolve(projectRoot);
  let reloaders = dashboardReloaders.get(key);
  if (!reloaders) {
    reloaders = new Set();
    dashboardReloaders.set(key, reloaders);
  }
  reloaders.add(reload);
  const dispose = () => {
    reloaders.delete(reload);
    if (reloaders.size === 0) dashboardReloaders.delete(key);
  };
  if (typeof panel?.onDidDispose === 'function') panel.onDidDispose(dispose);
  return dispose;
}

async function reloadOpenDashboards(projectRoot) {
  const reloaders = dashboardReloaders.get(path.resolve(projectRoot));
  if (!reloaders) return;
  await Promise.all([...reloaders].map(async (reload) => {
    try { await reload(); } catch (_error) { /* A closed webview does not undo a saved review. */ }
  }));
}

async function refreshReviewConsumers(projectRoot) {
  const workspace = vscode.workspace?.workspaceFolders?.[0];
  if (workspace && path.resolve(workspace.uri.fsPath) === path.resolve(projectRoot)) {
    await refreshStatusBarHealthFromWorkspace();
  }
  await reloadOpenDashboards(projectRoot);
}
let transportClosedAlertShown = false;
const feedRequestsInFlight = new Map();
const feedFailureStates = new Map();

function statusTooltip(message) {
  return `${STATUS_LABEL} ${EXTENSION_VERSION}. ${message} Command Palette: CuratorMD V2: Open Recovery Manager.`;
}

function statusColorMeaning(status) {
  return STATUS_COLOR_MEANINGS[status] || STATUS_COLOR_MEANINGS.unknown;
}

function hostEvidenceConfigArguments(evidenceConfig) {
  return typeof evidenceConfig === 'string' && evidenceConfig.trim()
    ? ['--evidence-config', evidenceConfig.trim()]
    : [];
}

function resolveHermesProfileId(projectId, bindings) {
  if (typeof projectId !== 'string' || !projectId
    || !bindings || typeof bindings !== 'object' || Array.isArray(bindings)
    || !Object.prototype.hasOwnProperty.call(bindings, projectId)) return null;
  const profileId = bindings[projectId];
  return typeof profileId === 'string'
    && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(profileId)
    ? profileId : null;
}

function statusReadFailure(error) {
  const fallback = 'The local health read failed; open the dashboard for details.';
  return error && typeof error.code === 'string'
    && Object.prototype.hasOwnProperty.call(STATUS_READ_FAILURES, error.code)
    ? STATUS_READ_FAILURES[error.code]
    : fallback;
}

function startupFailureCode(stderr) {
  const text = Buffer.isBuffer(stderr) ? stderr.toString('utf8') : stderr;
  if (typeof text !== 'string') return null;
  const match = text.match(/(?:^|\n)CURATOR_STARTUP_ERROR=([a-z-]+)(?:\r?\n|$)/);
  return match && STARTUP_ERROR_CODES.has(match[1])
    ? (match[1] === 'runtime' ? 'launcher-runtime' : match[1])
    : null;
}

async function notifyTransportClosed(error) {
  if (error?.code !== 'launcher-exit' || transportClosedAlertShown
    || typeof vscode.window?.showWarningMessage !== 'function') return false;
  transportClosedAlertShown = true;
  try {
    const action = await vscode.window.showWarningMessage(
      TRANSPORT_CLOSED_MESSAGE,
      { modal: true },
      'Reload Window',
      'Dismiss',
    );
    if (action === 'Reload Window' && typeof vscode.commands?.executeCommand === 'function') {
      await vscode.commands.executeCommand('workbench.action.reloadWindow');
    }
  } catch (_) {
    // The status tooltip still carries the recovery guidance if notification fails.
  }
  return true;
}

function ensureWorkspaceArea(projectRoot, areaName) {
  const stateRoot = path.join(projectRoot, '.curatormd-v2');
  const areaPath = path.join(stateRoot, areaName);
  for (const directory of [stateRoot, areaPath]) {
    try {
      const metadata = fs.lstatSync(directory);
      if (!metadata.isDirectory() || metadata.isSymbolicLink()) {
        throw new Error('Curator workspace area is not a regular directory.');
      }
    } catch (error) {
      if (error && error.code !== 'ENOENT') throw error;
      fs.mkdirSync(directory, { mode: 0o700 });
    }
  }
  return areaPath;
}

function initializeWorkspaceAreas(projectRoot) {
  const stateRoot = path.join(projectRoot, '.curatormd-v2');
  for (const area of ['inbox', 'sde-proposals', 'side-buffer']) {
    ensureWorkspaceArea(projectRoot, area);
  }
  const guide = path.join(stateRoot, 'README.md');
  if (!fs.existsSync(guide)) {
    const guideText = [
      '# Curator V2 project work areas',
      '',
      '- `inbox/status.json` is a generated count-only view. Any payload retained for retry stays in SQLite under its retry and retention rules.',
      '- `sde-proposals/pending-review.md` is the generated review document; its actions open the attended reviewer. `pending.json` is its queue data.',
      '- `side-buffer/` is the configured temporary file area. Curator inventories it and only removes exact files after an approved cleanup receipt.',
      '- The SQLite ledger is authoritative. JSON files here are refreshable views, never approval receipts or canonical facts.',
      '',
    ].join('\n');
    const descriptor = fs.openSync(guide, 'wx', 0o600);
    try { fs.writeFileSync(descriptor, guideText, 'utf8'); } finally { fs.closeSync(descriptor); }
  }
}

function writeWorkspaceProjection(projectRoot, filename, value) {
  const directory = ensureWorkspaceArea(projectRoot, path.dirname(filename));
  const destination = path.join(directory, path.basename(filename));
  const stableValue = { ...value };
  delete stableValue.generated_at;
  try {
    const existingStat = fs.lstatSync(destination);
    if (existingStat.isFile() && !existingStat.isSymbolicLink()
      && existingStat.size <= 1024 * 1024) {
      const existing = JSON.parse(fs.readFileSync(destination, 'utf8'));
      if (existing && typeof existing === 'object' && !Array.isArray(existing)) {
        const stableExisting = { ...existing };
        delete stableExisting.generated_at;
        const generatedAt = typeof existing.generated_at === 'string'
          ? Date.parse(existing.generated_at) : Number.NaN;
        const ageSeconds = (Date.now() - generatedAt) / 1000;
        const projectionFresh = Number.isFinite(generatedAt)
          && ageSeconds <= WORKSPACE_PROJECTION_MAX_AGE_SECONDS
          && ageSeconds >= -WORKSPACE_PROJECTION_CLOCK_SKEW_SECONDS;
        if (JSON.stringify(stableExisting) === JSON.stringify(stableValue)
          && projectionFresh) return false;
      }
    }
  } catch (error) {
    if (!error || error.code !== 'ENOENT') {
      // An unreadable projection is replaced atomically from the authorized snapshot.
    }
  }
  const temporary = path.join(directory, `.${path.basename(filename)}.${process.pid}.${randomBytes(6).toString('hex')}.tmp`);
  const contents = `${JSON.stringify(value, null, 2)}\n`;
  try {
    fs.writeFileSync(temporary, contents, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    fs.renameSync(temporary, destination);
  } catch (error) {
    try { fs.unlinkSync(temporary); } catch (_cleanupError) { /* Best-effort temporary cleanup. */ }
    throw error;
  }
  return true;
}

function writeWorkspaceQueueViewsDetailed(
  projectRoot, projectId, inbox, reviewWire, outlines = new Map(), resolvedCandidateIds = new Set(),
) {
  const inboxFields = [
    'received_count', 'failed_count', 'quarantined_count',
    'claimed_count', 'expired_claim_count',
  ];
  const normalizedReviews = validateReviewQueue(reviewWire, projectId);
  const inboxValid = Boolean(inbox && inboxFields.every((field) => Number.isSafeInteger(inbox[field]) && inbox[field] >= 0)
      && (inbox.oldest_pending_age_seconds === null
        || (Number.isSafeInteger(inbox.oldest_pending_age_seconds)
          && inbox.oldest_pending_age_seconds >= 0)));
  let reviewQueueUpdated = false;
  let reviewDocumentUpdated = false;
  let inboxUpdated = false;
  if (normalizedReviews !== null) {
    try {
      writeWorkspaceProjection(projectRoot, 'sde-proposals/pending.json', {
        project_id: projectId,
        generated_at: new Date(Date.now() + (7 * 60 * 60 * 1000)).toISOString().replace('Z', '+07:00'),
        source: 'Curator V2 SQLite review queue',
        canonical: false,
        queue_limit: REVIEW_QUEUE_SIZE,
        may_be_truncated: normalizedReviews.length === REVIEW_QUEUE_SIZE,
        review_action: 'Open pending-review.md to select a candidate for attended review.',
        candidates: normalizedReviews,
      });
      reviewQueueUpdated = true;
    } catch (_) { /* The inbox view can still refresh independently. */ }
    try {
      reviewDocumentUpdated = writePendingReviewDocument(
        projectRoot, projectId, normalizedReviews, outlines, resolvedCandidateIds,
      );
    } catch (_) { /* Keep a failure visible while preserving the current document. */ }
  }
  if (inboxValid) {
    try {
      writeWorkspaceProjection(projectRoot, 'inbox/status.json', {
        project_id: projectId,
        generated_at: new Date(Date.now() + (7 * 60 * 60 * 1000)).toISOString().replace('Z', '+07:00'),
        source: 'Curator V2 SQLite inbox summary',
        canonical: false,
        received_count: inbox.received_count,
        failed_count: inbox.failed_count,
        quarantined_count: inbox.quarantined_count,
        oldest_pending_received_at: typeof inbox.oldest_pending_received_at === 'string'
          ? inbox.oldest_pending_received_at.slice(0, 64) : null,
        oldest_pending_age_seconds: inbox.oldest_pending_age_seconds,
        claimed_count: inbox.claimed_count,
        expired_claim_count: inbox.expired_claim_count,
      });
      inboxUpdated = true;
    } catch (_) { /* Keep the prior count-only projection and report it as stale. */ }
  }
  return {
    reviewQueueUpdated,
    reviewDocumentUpdated,
    inboxUpdated,
    allUpdated: reviewQueueUpdated && reviewDocumentUpdated && inboxUpdated,
  };
}

function writeWorkspaceQueueViews(
  projectRoot, projectId, inbox, reviewWire, outlines = new Map(), resolvedCandidateIds = new Set(),
) {
  return writeWorkspaceQueueViewsDetailed(
    projectRoot, projectId, inbox, reviewWire, outlines, resolvedCandidateIds,
  ).allUpdated;
}

function writePendingReviewDocument(
  projectRoot, projectId, reviews, outlines = new Map(), resolvedCandidateIds = new Set(),
) {
  const directory = ensureWorkspaceArea(projectRoot, 'sde-proposals');
  const destination = path.join(directory, 'pending-review.md');
  const openDocument = vscode.workspace?.textDocuments?.find(
    (document) => document.uri?.fsPath === destination,
  );
  if (openDocument?.isDirty) return false;
  let previousDrafts = new Map();
  let existingContent = null;
  let previousTrailingNewlines = null;
  try {
    const metadata = fs.lstatSync(destination);
    if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.size > 1024 * 1024) return false;
    const existing = fs.readFileSync(destination, 'utf8');
    existingContent = existing;
    const marker = pendingReviewChecksumMarker(existing);
    if (!marker) return false;
    const oldBody = existing.slice(marker.length);
    const parts = reviewDraftParts(oldBody);
    if (!parts) return false;
    const hash = (value) => createHash('sha256').update(value, 'utf8').digest('hex');
    if (hash(parts.normalized) !== marker.checksum
      && hash(normalizeReviewChecksumWhitespace(parts.normalized)) !== marker.checksum
      && hash(oldBody) !== marker.checksum) return false;
    previousTrailingNewlines = trailingReviewNewlineCount(oldBody);
    const currentIds = new Set(reviews.map(({ candidate }) => candidate.candidate_id));
    const removedIds = [...parts.drafts.keys()].filter((id) => !currentIds.has(id));
    if (removedIds.some((id) => !resolvedCandidateIds.has(id))) return false;
    previousDrafts = new Map([...parts.drafts].filter(([id]) => currentIds.has(id)));
  } catch (error) { if (!error || error.code !== 'ENOENT') throw error; }
  const safe = (value) => value.replace(/[\r\n]+/g, ' ').replace(/[\\`*_{}\[\]#+!<>|~\-]/g, '\\$&');
  const pushParagraph = (text, firstPrefix = '') => {
    const paragraph = text.trim().replace(/\s+/g, ' ');
    if (paragraph) lines.push(`${firstPrefix}${paragraph}`);
  };
  const pushField = (label, value) => pushParagraph(`${label}: ${value}`, '- ');
  const pushFacts = (facts, fallback) => {
    if (facts.length === 0) {
      pushParagraph(fallback, '  - ');
      return;
    }
    for (const fact of facts) pushParagraph(safe(fact.bullet), '  - ');
  };
  const lines = [
    '# Pending SDE reviews', '',
  ];
  pushParagraph(`Project: ${safe(projectId)}`);
  lines.push('');
  pushParagraph('Review each proposal and its editable JSON copy. Accept and Reject open the attended reviewer. Withdraw clears a proposal while retaining its source facts and receipt. Refresh evidence reopens the source task for a new proof pass, then withdraws the stale proposal; it does not accept or delete facts.');
  lines.push('');
  if (reviews.length === REVIEW_QUEUE_SIZE) {
    pushParagraph('Only the first 100 candidates are shown.');
    lines.push('');
  }
  if (reviews.length === 0) {
    lines.push('No pending candidates.', '');
  }
  let candidateNumber = 0;
  for (const { candidate, goal } of reviews) {
    candidateNumber += 1;
    const outline = outlines.get(candidate.candidate_id);
    const outlineMatchesCandidate = Boolean(outline
      && outline.project_id === projectId
      && outline.candidate_id === candidate.candidate_id
      && outline.goal_id === goal.goal_id
      && outline.status === 'pending_review'
      && Array.isArray(outline.supporting_facts)
      && outline.supporting_facts.length <= 32
      && outline.supporting_facts.every((fact) => fact && typeof fact.bullet === 'string'
        && fact.bullet.length <= 1000 && typeof fact.kind === 'string'
        && /^[a-z_]{1,32}$/.test(fact.kind)));
    const supportingFacts = outlineMatchesCandidate ? outline.supporting_facts : [];
    const verificationFacts = supportingFacts.filter((fact) => fact.kind === 'verification');
    const changeFacts = supportingFacts.filter((fact) => fact.kind === 'change');
    const suggestedSignificance = ({
      implementation: 4,
      decision: 3,
      recovery: 3,
      verified_lesson: 2,
      routine: 1,
    })[candidate.materiality] ?? null;
    const proposedTitle = goal.problem;
    const proposalRationale = outlineMatchesCandidate
      && typeof outline.proposal_rationale === 'string'
      && outline.proposal_rationale.length <= 1000
      ? outline.proposal_rationale : candidate.rationale;
    const proposedLesson = outlineMatchesCandidate
      && candidate.materiality === 'verified_lesson'
      && typeof outline.future_utility === 'string' && outline.future_utility.length <= 1000
      ? outline.future_utility : '';
    const verifiedCompletion = outlineMatchesCandidate
      && (outline.successful_completion_evidence_recorded === true
        || outline.successful_completion_evidence_current === true)
      && verificationFacts.length > 0;
    const taskSummaries = changeFacts
      .filter((fact) => /^Task summary:/i.test(fact.bullet))
      .slice(0, 1);
    const completed = verifiedCompletion
      ? verificationFacts.map((fact) => fact.bullet).slice(0, 32)
      : taskSummaries.map((fact) => fact.bullet).slice(0, 32);
    const draft = {
      title: proposedTitle,
      significance: suggestedSignificance,
      documents: [],
      problem: goal.problem,
      completed,
      difficulties: [],
      plan_changes: [],
      lessons: proposedLesson ? [proposedLesson] : [],
      future_utility: outline && typeof outline.future_utility === 'string'
        && outline.future_utility.length <= 1000
        ? outline.future_utility : '',
    };
    const draftJson = JSON.stringify(draft, null, 2);
    let fence = '```';
    while (draftJson.includes(fence)) fence += '`';
    let draftBlock = previousDrafts.get(candidate.candidate_id);
    if (draftBlock) {
      const savedJson = /^(`{3,}json\n)([\s\S]*)(\n`{3,})$/.exec(draftBlock);
      if (savedJson) {
        try {
          const savedDecision = JSON.parse(savedJson[2]);
          if (Array.isArray(savedDecision.completed) && savedDecision.completed.length === 0
            && completed.length > 0) {
            savedDecision.completed = completed;
            draftBlock = `${savedJson[1]}${JSON.stringify(savedDecision, null, 2)}${savedJson[3]}`;
          }
        } catch (_) {
          // Keep an owner's malformed draft intact for attended repair.
        }
      }
    } else {
      draftBlock = `${fence}json\n${draftJson}\n${fence}`;
    }
    const proposedBlock = draftBlock;
    lines.push(`<!-- curator-v2-candidate: ${candidate.candidate_id} -->`,
      `## SDE candidate ${candidateNumber}`, '',
      `### ${candidateNumber}. Proposed entry`, '');
    lines.push(proposedBlock, '');
    pushField('SDE ID', safe(candidate.candidate_id));
    pushField('Proposed title', safe(proposedTitle));
    pushField('Task started (+07)', outline && typeof outline.task_started_at === 'string'
      ? safe(outline.task_started_at) : 'Unknown');
    pushField('Successful completion (+07)', outline && typeof outline.successful_completion_at === 'string'
      ? safe(outline.successful_completion_at) : 'Unknown');
    pushField('Significance', suggestedSignificance === null
      ? 'Choose 0–5'
      : `${suggestedSignificance} / 5 initial recommendation; owner-editable. Use this rating to guide future compression, summarization, archiving, and culling. A rating of 5 requires extra confirmation.`);
    pushField('Proposal rationale', safe(proposalRationale));
    lines.push('- Available persistence documents:');
    if (outline && Array.isArray(outline.persistence_documents)
      && outline.persistence_documents.length <= 16
      && outline.persistence_documents.every((document) => typeof document === 'string'
        && document.length <= 512 && !document.startsWith('/') && !document.includes('\\'))) {
      for (const document of outline.persistence_documents) pushParagraph(`\`${safe(document)}\``, '  - ');
    } else {
      pushParagraph('Choose one or more configured persistence documents in the editable copy.', '  - ');
    }

    lines.push('', `### ${candidateNumber}. Task and outcomes`, '');
    pushField('Problem / plan task', safe(goal.problem));
    lines.push('- Completed successfully:');
    if (verifiedCompletion) {
      pushFacts(
        verificationFacts.length > 0 ? verificationFacts : [completionClaim],
        'No successful work is recorded.',
      );
      pushParagraph('The attended reviewer checks the current evidence before acceptance.', '  - ');
    } else {
      pushFacts([], 'No recorded passing verification supports a successful-completion claim.');
      if (taskSummaries.length > 0) {
        lines.push('- Completed task work, with verification still open:');
        pushFacts(taskSummaries, 'No task summary is recorded.');
      }
      for (const fact of verificationFacts) {
        pushParagraph(`Recorded verification, not current proof: ${safe(fact.bullet)}`, '  - ');
      }
    }
    lines.push('- Difficulties encountered:');
    pushFacts([], 'No difficulty is separately recorded.');
    lines.push('- Plan changes required:');
    pushFacts([], 'No plan change is separately recorded.');
    lines.push('- Lessons learned:');
    pushFacts(proposedLesson ? [{ bullet: proposedLesson }] : [], 'No lesson is separately stated.');
    if (outlineMatchesCandidate && typeof outline.future_utility === 'string'
      && outline.future_utility.length <= 1000) pushField('Future utility', safe(outline.future_utility));
    if (changeFacts.length > 0) {
      lines.push('- Other recorded work:');
      pushFacts(changeFacts.slice(0, 8), 'No change facts are available.');
      if (changeFacts.length > 8) pushParagraph('Additional change facts are available in the attended review.', '  - ');
    }
    lines.push('', `<!-- curator-v2-actions: ${candidate.candidate_id} -->`);
    lines.push(`### ${candidateNumber}. Editable decision`, '');
    lines.push('',
      `<!-- curator-v2-decision:${candidate.candidate_id}:start -->`,
      draftBlock,
      `<!-- curator-v2-decision:${candidate.candidate_id}:end -->`, '');
  }
  let body = `${lines.join('\n').replace(/\n+$/, '')}\n`;
  const generatedTrailingNewlines = trailingReviewNewlineCount(body);
  if (previousTrailingNewlines !== null && previousTrailingNewlines > generatedTrailingNewlines) {
    body += '\n'.repeat(previousTrailingNewlines - generatedTrailingNewlines);
  }
  if (Buffer.byteLength(body, 'utf8') > 1024 * 1024 - 128) return false;
  const generated = reviewDraftParts(body);
  if (!generated) return false;
  const checksum = createHash('sha256')
    .update(normalizeReviewChecksumWhitespace(generated.normalized), 'utf8').digest('hex');
  const content = `<!-- sha256:${checksum} -->\n${body}`;
  if (existingContent === content) return true;
  if (openDocument && openDocument.getText() === content) return true;
  const temporary = path.join(directory, `.pending-review.${process.pid}.${randomBytes(6).toString('hex')}.tmp`);
  try {
    fs.writeFileSync(temporary, content, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    try {
      const current = fs.lstatSync(destination);
      if (!current.isFile() || current.isSymbolicLink() || current.size > 1024 * 1024
        || existingContent === null || fs.readFileSync(destination, 'utf8') !== existingContent) {
        fs.unlinkSync(temporary);
        return false;
      }
    } catch (error) {
      if (!error || error.code !== 'ENOENT' || existingContent !== null) throw error;
    }
    fs.renameSync(temporary, destination);
  } catch (error) {
    try { fs.unlinkSync(temporary); } catch (_cleanupError) { /* Best effort. */ }
    throw error;
  }
  return true;
}

function reviewDraftParts(body) {
  const drafts = new Map();
  const normalized = [];
  const lines = body.split('\n');
  for (let index = 0; index < lines.length; index += 1) {
    const start = /^<!-- curator-v2-decision:([A-Za-z0-9_-]{1,128}):start -->$/.exec(lines[index]);
    if (!start) {
      if (lines[index].startsWith('<!-- curator-v2-decision:')) return null;
      normalized.push(lines[index]);
      continue;
    }
    if (drafts.has(start[1])) return null;
    const end = `<!-- curator-v2-decision:${start[1]}:end -->`;
    const saved = [];
    index += 1;
    while (index < lines.length && lines[index] !== end) {
      if (lines[index].startsWith('<!-- curator-v2-decision:')) return null;
      saved.push(lines[index++]);
    }
    if (index >= lines.length) return null;
    drafts.set(start[1], saved.join('\n'));
    normalized.push(start[0], '<!-- curator-v2-draft-content -->', end);
  }
  return { drafts, normalized: normalized.join('\n') };
}

function pendingReviewChecksumMarker(content) {
  const match = /^<!-- (?:curator-v2-generated-sha256: |sha256:)([0-9a-f]{64}) -->\n/.exec(content);
  return match ? { checksum: match[1], length: match[0].length } : null;
}

function trailingReviewNewlineCount(value) {
  return (/\n*$/.exec(value) || [''])[0].length;
}

function normalizeReviewChecksumWhitespace(value) {
  const trailingNewlines = trailingReviewNewlineCount(value);
  return trailingNewlines > 1
    ? `${value.slice(0, -trailingNewlines)}\n`
    : value;
}

function pendingReviewDocumentState(content) {
  const marker = pendingReviewChecksumMarker(content);
  if (!marker) return null;
  const body = content.slice(marker.length);
  const parts = reviewDraftParts(body);
  if (!parts) return null;
  const hash = (value) => createHash('sha256').update(value, 'utf8').digest('hex');
  if (hash(parts.normalized) !== marker.checksum
    && hash(normalizeReviewChecksumWhitespace(parts.normalized)) !== marker.checksum
    && hash(body) !== marker.checksum) return null;
  const candidateIds = [...content.matchAll(/^<!-- curator-v2-candidate: ([A-Za-z0-9_-]{1,128}) -->$/gm)]
    .map((match) => match[1]);
  if (candidateIds.length > REVIEW_QUEUE_SIZE
    || new Set(candidateIds).size !== candidateIds.length
    || candidateIds.length !== parts.drafts.size
    || candidateIds.some((candidateId) => !parts.drafts.has(candidateId))) return null;
  return { candidateIds, drafts: parts.drafts };
}

function isUnmodifiedReviewDocument(content) {
  return pendingReviewDocumentState(content) !== null;
}

function tryWriteWorkspaceQueueViews(
  projectRoot, projectId, inbox, reviewWire, outlines = new Map(), resolvedCandidateIds = new Set(),
) {
  try {
    return writeWorkspaceQueueViews(
      projectRoot, projectId, inbox, reviewWire, outlines, resolvedCandidateIds,
    );
  } catch (_error) {
    return false;
  }
}

function tryWriteWorkspaceQueueViewsDetailed(
  projectRoot, projectId, inbox, reviewWire, outlines = new Map(), resolvedCandidateIds = new Set(),
) {
  try {
    return writeWorkspaceQueueViewsDetailed(
      projectRoot, projectId, inbox, reviewWire, outlines, resolvedCandidateIds,
    );
  } catch (_error) {
    return {
      reviewQueueUpdated: false,
      reviewDocumentUpdated: false,
      inboxUpdated: false,
      allUpdated: false,
    };
  }
}

function workspaceQueueViewsConfirmResolved(projectRoot, projectId, candidateId) {
  const readProjection = (relativePath) => {
    const destination = path.join(projectRoot, '.curatormd-v2', relativePath);
    try {
      const metadata = fs.lstatSync(destination);
      if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.size > 1024 * 1024) return null;
      return fs.readFileSync(destination, 'utf8');
    } catch (_) {
      return null;
    }
  };
  const reviewPath = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  const reviewText = readProjection('sde-proposals/pending-review.md');
  const reviewState = reviewText === null ? null : pendingReviewDocumentState(reviewText);
  const openDocument = vscode.workspace?.textDocuments?.find(
    (document) => document.uri?.fsPath === reviewPath,
  );
  const reviewDocumentResolved = Boolean(reviewState
    && !reviewState.candidateIds.includes(candidateId)
    && (!openDocument || (!openDocument.isDirty && openDocument.getText() === reviewText)));
  let pending = null;
  let inbox = null;
  try {
    const pendingText = readProjection('sde-proposals/pending.json');
    if (pendingText !== null) pending = JSON.parse(pendingText);
  } catch (_) { /* Keep independent projection outcomes available to the caller. */ }
  try {
    const inboxText = readProjection('inbox/status.json');
    if (inboxText !== null) inbox = JSON.parse(inboxText);
  } catch (_) { /* Keep independent projection outcomes available to the caller. */ }
  const projectionIsFresh = (value) => {
    const generatedAt = value && typeof value.generated_at === 'string'
      ? Date.parse(value.generated_at) : Number.NaN;
    const age = (Date.now() - generatedAt) / 1000;
    return Number.isFinite(generatedAt)
      && age <= WORKSPACE_PROJECTION_MAX_AGE_SECONDS
      && age >= -WORKSPACE_PROJECTION_CLOCK_SKEW_SECONDS;
  };
  const reviewQueueResolved = pending?.project_id === projectId
    && projectionIsFresh(pending)
    && Array.isArray(pending.candidates)
    && pending.candidates.every((item) => item?.candidate?.candidate_id !== candidateId)
  const inboxFresh = inbox?.project_id === projectId
    && projectionIsFresh(inbox)
    && ['received_count', 'failed_count', 'quarantined_count', 'claimed_count',
      'expired_claim_count'].every((field) => Number.isSafeInteger(inbox[field]) && inbox[field] >= 0);
  return {
    reviewDocumentResolved,
    reviewQueueResolved,
    inboxFresh,
    allResolved: reviewDocumentResolved && reviewQueueResolved && inboxFresh,
  };
}

function pendingReviewCandidateIds(projectRoot) {
  const destination = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  try {
    const openDocument = vscode.workspace?.textDocuments?.find(
      (document) => document.uri?.fsPath === destination,
    );
    if (openDocument && typeof openDocument.getText === 'function') {
      return pendingReviewDocumentState(openDocument.getText())?.candidateIds || [];
    }
    const metadata = fs.lstatSync(destination);
    if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.size > 1024 * 1024) return [];
    const content = fs.readFileSync(destination, 'utf8');
    return pendingReviewDocumentState(content)?.candidateIds || [];
  } catch (_) {
    return [];
  }
}

async function readReviewOutlines(client, reviewWire, projectId, projectRoot) {
  const reviews = validateReviewQueue(reviewWire, projectId);
  const outlines = new Map();
  const resolvedCandidateIds = new Set();
  if (!reviews) return { outlines, resolvedCandidateIds };
  const currentIds = new Set(reviews.map(({ candidate }) => candidate.candidate_id));
  const candidatesToRead = [
    ...reviews.map(({ candidate }) => candidate.candidate_id),
    ...pendingReviewCandidateIds(projectRoot).filter((candidateId) => !currentIds.has(candidateId)),
  ];
  let next = 0;
  const worker = async () => {
    while (next < candidatesToRead.length) {
      const candidateId = candidatesToRead[next++];
      try {
        const value = JSON.parse(await client.callTool('sde_review_outline', { candidate_id: candidateId }));
        if (value.project_id !== projectId || value.candidate_id !== candidateId
          || typeof value.status !== 'string') continue;
        if (currentIds.has(candidateId)) outlines.set(candidateId, value);
        else if (value.status !== 'pending_review') resolvedCandidateIds.add(candidateId);
      } catch (_) { /* The document explicitly marks unavailable outlines. */ }
    }
  };
  await Promise.all(Array.from({ length: Math.min(4, candidatesToRead.length) }, () => worker()));
  return { outlines, resolvedCandidateIds };
}

async function refreshWorkspaceQueueViews(client, projectRoot, projectId) {
  const [reviewWire, inboxWire] = await Promise.all([
    client.callTool('sde_review_queue_cards', { limit: REVIEW_QUEUE_SIZE })
      .then((wire) => JSON.parse(wire))
      .catch(() => null),
    client.callTool('event_queue_status', {})
      .then((wire) => JSON.parse(wire))
      .catch(() => null),
  ]);
  const { outlines, resolvedCandidateIds } = await readReviewOutlines(
    client, reviewWire, projectId, projectRoot,
  );
  const updated = tryWriteWorkspaceQueueViewsDetailed(
    projectRoot, projectId, inboxWire, reviewWire, outlines, resolvedCandidateIds,
  );
  const reviewDocumentPath = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  const reviewEditorOpen = Boolean(vscode.workspace?.textDocuments?.some(
    (document) => document.uri?.fsPath === reviewDocumentPath,
  ));
  const reviewBufferUpdated = await refreshOpenPendingReviewDocumentSafely(projectRoot);
  return {
    ...updated,
    reviewEditorOpen,
    reviewBufferUpdated,
    reviewDocumentUpdated: updated.reviewDocumentUpdated && reviewBufferUpdated,
    allUpdated: updated.allUpdated && reviewBufferUpdated,
  };
}

async function retryWorkspaceQueueViewsAfterDecision(
  projectRoot, projectId, candidateId, spawnProcess, refreshAfterReview,
) {
  let status = workspaceQueueViewsConfirmResolved(projectRoot, projectId, candidateId);
  let lastError = null;
  for (const delay of REVIEW_REFRESH_RETRY_DELAYS_MS) {
    if (status.allResolved) break;
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    try {
      await withReviewClient(
        projectRoot,
        (client, actualProjectId) => {
          if (actualProjectId !== projectId) throw new Error('Project binding changed.');
          return refreshWorkspaceQueueViews(client, projectRoot, actualProjectId);
        },
        { spawnProcess },
      );
      lastError = null;
      status = workspaceQueueViewsConfirmResolved(projectRoot, projectId, candidateId);
    } catch (error) {
      lastError = error;
    }
  }
  try {
    await refreshAfterReview(projectRoot);
  } catch (_error) {
    // A saved local projection remains useful even if a dashboard reload fails.
  }
  if (lastError && !status.allResolved) throw lastError;
  return status;
}

async function refreshOpenPendingReviewDocument(projectRoot) {
  const reviewPath = path.join(
    projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  );
  const openDocument = vscode.workspace?.textDocuments?.find(
    (document) => document.uri?.fsPath === reviewPath,
  );
  if (!openDocument) return true;
  if (openDocument.isDirty) return false;
  const generated = fs.readFileSync(reviewPath, 'utf8');
  const current = openDocument.getText();
  if (current === generated) return true;
  if (typeof vscode.workspace?.applyEdit !== 'function'
    || typeof vscode.WorkspaceEdit !== 'function'
    || typeof vscode.Range !== 'function'
    || typeof openDocument.positionAt !== 'function') return false;
  const edit = new vscode.WorkspaceEdit();
  edit.replace(
    openDocument.uri,
    new vscode.Range(openDocument.positionAt(0), openDocument.positionAt(current.length)),
    generated,
  );
  if (!await vscode.workspace.applyEdit(edit) || openDocument.getText() !== generated) return false;
  return openDocument.save();
}

async function refreshOpenPendingReviewDocumentSafely(projectRoot) {
  try {
    return await refreshOpenPendingReviewDocument(projectRoot);
  } catch (_error) {
    return false;
  }
}

function healthGateSummary(health, projectId) {
  if (!health || health.project_id !== projectId || !Array.isArray(health.gate_codes)) {
    return '';
  }
  const codes = health.gate_codes
    .filter((code) => code !== 'review_backlog'
      && typeof code === 'string' && /^[a-z][a-z0-9_:.-]{0,127}$/.test(code))
    .slice(0, 12);
  const omitted = health.gate_codes.filter((code) => code !== 'review_backlog').length - codes.length;
  if (codes.length === 0) return '';
  const suffix = omitted > 0 ? `; ${omitted} additional or invalid gate(s)` : '';
  return ` Health gates: ${codes.map(healthGateLabel).join(' ')}${suffix}.`;
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

function hostFilesystemRows(workspaceRoot, databasePath, statfs = fs.statfsSync) {
  const targets = [
    ['Workspace filesystem', workspaceRoot],
    ['SQLite filesystem', databasePath],
  ];
  return targets.map(([label, target]) => {
    const unknown = {
      label,
      value: 'Filesystem capacity unavailable',
      state: 'unknown',
      stateLabel: 'Unknown',
    };
    if (typeof target !== 'string' || !path.isAbsolute(target) || typeof statfs !== 'function') {
      return unknown;
    }
    const candidates = [target];
    const parent = path.dirname(target);
    if (parent !== target) candidates.push(parent);
    let snapshot = null;
    for (const candidate of candidates) {
      try {
        snapshot = statfs(candidate);
        break;
      } catch (_) { /* A missing database file can still use its containing volume. */ }
    }
    if (!snapshot) return unknown;
    const blockSize = Number(snapshot.bsize);
    const blocks = Number(snapshot.blocks);
    const freeBlocks = Number(snapshot.bfree);
    const availableBlocks = Number(snapshot.bavail);
    if (![blockSize, blocks, freeBlocks, availableBlocks].every(Number.isSafeInteger)
      || blockSize <= 0 || blocks <= 0 || freeBlocks < 0 || freeBlocks > blocks
      || availableBlocks < 0 || availableBlocks > freeBlocks) return unknown;
    const totalBytes = blockSize * blocks;
    const freeBytes = blockSize * freeBlocks;
    const availableBytes = blockSize * availableBlocks;
    if (![totalBytes, freeBytes, availableBytes].every(Number.isSafeInteger)
      || totalBytes <= 0) return unknown;
    const availablePercent = (availableBytes / totalBytes) * 100;
    const state = availablePercent <= HOST_FILESYSTEM_WARNING_PERCENT ? 'warning' : 'healthy';
    return {
      label,
      value: `Used ${formatBytes(totalBytes - freeBytes)} · ${formatBytes(availableBytes)} available / ${formatBytes(totalBytes)} total (${availablePercent.toFixed(1)}% free)`,
      state,
      stateLabel: state === 'warning'
        ? `Low free space · ${HOST_FILESYSTEM_WARNING_PERCENT}% threshold` : 'Available',
    };
  });
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

function factEvidenceDisplayStatus(value, now = Date.now()) {
  if (!value || value.fact_kind !== 'verification') {
    return value?.verification_status || 'stale/unknown';
  }
  const attestations = Array.isArray(value.evidence)
    ? value.evidence.map((reference) => reference?.attestation).filter(Boolean) : [];
  const evidenceIsCurrent = value.evidence.length > 0
    && value.evidence.every((reference) => {
      if (reference?.outcome !== 'passed' || !reference.attestation) return false;
      const observedAt = Date.parse(reference.attestation.observed_at);
      const validUntil = Date.parse(reference.attestation.valid_until);
      const revocationCheckedAt = Date.parse(reference.attestation.revocation_checked_at);
      return Number.isFinite(observedAt) && observedAt <= now
        && Number.isFinite(validUntil) && validUntil > now
        && Number.isFinite(revocationCheckedAt)
        && revocationCheckedAt >= observedAt && revocationCheckedAt <= now;
    });
  if (value.verification_status === 'verified_fact' && !evidenceIsCurrent) {
    return 'stale/unknown';
  }
  if (attestations.length > 0 && value.verification_status !== 'verified_fact') {
    // The backend rechecks the source when it reads this page. A formerly
    // attested fact that no longer verifies is historical, not current proof.
    return 'stale/unknown';
  }
  return value.verification_status;
}

function curatorError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function readConfiguredProjectId(projectRoot) {
  let descriptor;
  try {
    const configPath = path.join(projectRoot, '.curatormd-v2.toml');
    const noFollow = fs.constants.O_NOFOLLOW || 0;
    descriptor = fs.openSync(configPath, fs.constants.O_RDONLY | noFollow);
    const metadata = fs.fstatSync(descriptor);
    if (!metadata.isFile() || metadata.size > MAX_PROJECT_CONFIG_BYTES) {
      throw new Error('invalid project config file');
    }
    const sourceBuffer = Buffer.alloc(MAX_PROJECT_CONFIG_BYTES + 1);
    const bytesRead = fs.readSync(
      descriptor, sourceBuffer, 0, sourceBuffer.length, 0,
    );
    if (bytesRead > MAX_PROJECT_CONFIG_BYTES) {
      throw new Error('project config exceeds size limit');
    }
    const source = sourceBuffer.subarray(0, bytesRead).toString('utf8');
    let rootTable = true;
    let projectId = null;
    for (const line of source.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      if (trimmed.startsWith('[')) {
        rootTable = false;
        continue;
      }
      if (!rootTable || !/^project_id\s*=/.test(trimmed)) continue;
      if (projectId !== null) throw new Error('duplicate project id');
      const match = trimmed.match(/^project_id\s*=\s*(["'])([A-Za-z0-9][A-Za-z0-9._:-]{0,127})\1\s*(?:#.*)?$/);
      if (!match) throw new Error('invalid project id');
      projectId = match[2];
    }
    if (!projectId) throw new Error('missing project id');
    return projectId;
  } catch (_error) {
    throw curatorError(
      'status-project-invalid',
      'The Curator project file is missing, unreadable, or has an invalid project ID.',
    );
  } finally {
    if (descriptor !== undefined) fs.closeSync(descriptor);
  }
}

function resolveDatabasePath(projectId, databaseBindings, fallbackPath) {
  if (typeof projectId !== 'string' || !PROJECT_ID_PATTERN.test(projectId)) return null;
  const bindings = databaseBindings === undefined ? {} : databaseBindings;
  if (!bindings || typeof bindings !== 'object' || Array.isArray(bindings)) return null;
  const selected = Object.keys(bindings).length === 0
    ? fallbackPath
    : (Object.prototype.hasOwnProperty.call(bindings, projectId) ? bindings[projectId] : null);
  return typeof selected === 'string' && selected.trim() === selected
    && selected.length > 0 && path.isAbsolute(selected) ? selected : null;
}

function resolveEvidenceConfig(projectId, evidenceConfigBindings, fallbackPath) {
  let selected = fallbackPath;
  if (typeof projectId === 'string' && PROJECT_ID_PATTERN.test(projectId)
    && evidenceConfigBindings && typeof evidenceConfigBindings === 'object'
    && Object.prototype.hasOwnProperty.call(evidenceConfigBindings, projectId)) {
    selected = evidenceConfigBindings[projectId];
  }
  if (selected === '') return '';
  return typeof selected === 'string' && selected.trim() === selected
    && path.isAbsolute(selected) ? selected : null;
}

function validGoalText(value, limit) {
  return typeof value === 'string'
    && value.trim().length > 0
    && value.length <= limit
    && !/[\r\n]/.test(value);
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
  if (response && health
    && typeof response.project_id === 'string'
    && typeof health.project_id === 'string'
    && (response.project_id !== expectedProjectId || health.project_id !== expectedProjectId)) {
    throw curatorError('hermes-probe-project-mismatch', 'Hermes health belongs to another project.');
  }
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
        && Number.isSafeInteger(dependency.age_seconds)
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
    throw curatorError('hermes-probe-invalid', 'Hermes health response was incomplete.');
  }
  if (!healthObservationFresh || !dependencyObservationsFresh) {
    throw curatorError('hermes-probe-stale', 'Hermes health observations are outside the freshness limit.');
  }
  if (health.status === 'healthy'
    && (health.gate_codes.length > 0
      || dependencies.some((dependency) => dependency.status !== 'healthy'))) {
    throw curatorError('hermes-probe-unreconciled', 'Hermes healthy status contradicts its gates or dependencies.');
  }
  return health;
}

function parseCuratorQueueSnapshot(stdout, expectedProjectId) {
  if (typeof stdout !== 'string' || Buffer.byteLength(stdout, 'utf8') > HERMES_HEALTH_MAX_BYTES) {
    throw curatorError('curator-queue-invalid', 'Curator queue response exceeded its size limit.');
  }
  let snapshot;
  try {
    snapshot = JSON.parse(stdout);
  } catch {
    throw curatorError('curator-queue-invalid', 'Curator queue response was not valid JSON.');
  }
  if (snapshot && typeof snapshot.project_id === 'string'
    && snapshot.project_id !== expectedProjectId) {
    throw curatorError('curator-queue-project-mismatch', 'Curator queue data belongs to another project.');
  }
  const observedAt = snapshot && typeof snapshot.observed_at === 'string'
    ? Date.parse(snapshot.observed_at) : Number.NaN;
  const databaseObservedAt = snapshot && typeof snapshot.database_observed_at === 'string'
    ? Date.parse(snapshot.database_observed_at) : Number.NaN;
  const hasTimezone = (value) => typeof value === 'string'
    && /(?:Z|[+-][0-9]{2}:[0-9]{2})$/i.test(value);
  if (!hasTimezone(snapshot && snapshot.observed_at)
    || !hasTimezone(snapshot && snapshot.database_observed_at)) {
    throw curatorError('curator-queue-invalid', 'Curator queue timestamps must include a timezone.');
  }
  const isFresh = (timestamp) => {
    const age = (Date.now() - timestamp) / 1000;
    return Number.isFinite(timestamp)
      && age <= MAX_HEALTH_PROBE_AGE_SECONDS + MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS
      && age >= -MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS;
  };
  if ((Number.isFinite(observedAt) && !isFresh(observedAt))
    || (Number.isFinite(databaseObservedAt) && !isFresh(databaseObservedAt))) {
    throw curatorError('curator-queue-stale', 'Curator queue observation is outside the freshness limit.');
  }
  const count = (value) => Number.isSafeInteger(value) && value >= 0;
  const nullableCount = (value) => value === null || count(value);
  const operational = snapshot && snapshot.operational_counts;
  const operationalFields = [
    'pending_review_count', 'pending_purge_receipt_count',
    'pending_purge_artifact_count', 'pending_expiry_purge_receipt_count',
    'pending_expiry_purge_artifact_count',
  ];
  const eventFields = [
    'event_received_count', 'event_failed_count', 'event_quarantined_count',
    'event_claimed_count', 'event_expired_claim_count',
    'oldest_pending_event_age_seconds',
  ];
  if (!snapshot || snapshot.project_id !== expectedProjectId
    || !hasTimezone(snapshot.observed_at) || !Number.isFinite(observedAt)
    || !hasTimezone(snapshot.database_observed_at) || !Number.isFinite(databaseObservedAt)
    || snapshot.database_observation_complete !== true
    || !operational || !operationalFields.every((field) => count(operational[field]))
    || !eventFields.every((field) => nullableCount(snapshot[field]))) {
    throw curatorError('curator-queue-invalid', 'Curator queue snapshot is incomplete.');
  }
  return snapshot;
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

async function readHermesHealthWithRecovery(command, profileId, projectId, cwd, spawnProcess) {
  try {
    return await readHermesHealthProbe(command, profileId, projectId, cwd, spawnProcess);
  } catch (error) {
    if (error?.code !== 'hermes-probe-timeout') throw error;
    await new Promise((resolve) => setTimeout(resolve, HERMES_HEALTH_RETRY_DELAY_MS));
    return readHermesHealthProbe(command, profileId, projectId, cwd, spawnProcess);
  }
}

function projectFeedKey(projectRoot, databasePath, profileId, hermesProfileId, serverCommand,
  hermesCommand, evidenceConfig, projectId) {
  return createHash('sha256').update(JSON.stringify([
    projectRoot, databasePath, profileId, hermesProfileId, serverCommand, hermesCommand,
    evidenceConfig, projectId,
  ])).digest('hex');
}

function clearFeedFailureStates() {
  feedFailureStates.clear();
}

function feedFailureState(key, feed) {
  return feedFailureStates.get(`${key}:${feed}`) || null;
}

function feedIsCoolingDown(state) {
  const lastCheck = Date.parse(state?.checkedAt);
  return Boolean(state?.paused && Number.isFinite(lastCheck)
    && Date.now() - lastCheck < FEED_FAILURE_COOLDOWN_MS);
}

function recordFeedResult(key, feed, errorCode, checkedAt) {
  const stateKey = `${key}:${feed}`;
  if (!errorCode) {
    feedFailureStates.delete(stateKey);
    return null;
  }
  const previous = feedFailureStates.get(stateKey);
  const count = previous && previous.code === errorCode ? previous.count + 1 : 1;
  const state = { code: errorCode, count, checkedAt, paused: count >= MAX_IDENTICAL_FEED_FAILURES };
  feedFailureStates.set(stateKey, state);
  return state;
}

function readProjectFeeds({
  client, projectRoot, databasePath, profileId, serverCommand,
  hermesProfileId = profileId, hermesCommand, evidenceConfig, projectId, spawnProcess = spawn,
  trigger = 'automatic',
}) {
  const key = projectFeedKey(
    projectRoot, databasePath, profileId, hermesProfileId, serverCommand,
    hermesCommand, evidenceConfig, projectId,
  );
  if (trigger === 'manual') {
    feedFailureStates.delete(`${key}:health`);
    feedFailureStates.delete(`${key}:queue`);
  }
  const existing = feedRequestsInFlight.get(key);
  if (existing) return existing;

  const pending = (async () => {
    const priorHealthFailure = feedFailureState(key, 'health');
    const priorQueueFailure = feedFailureState(key, 'queue');
    const healthPaused = trigger !== 'manual' && feedIsCoolingDown(priorHealthFailure);
    const queuePaused = trigger !== 'manual' && feedIsCoolingDown(priorQueueFailure);
    const healthRequest = healthPaused
      ? Promise.resolve({ value: null, errorCode: 'feed-auto-paused', checkedAt: priorHealthFailure.checkedAt })
      : !hermesProfileId
        ? Promise.resolve({
          value: null,
          errorCode: 'hermes-probe-profile-binding',
          checkedAt: new Date().toISOString(),
        })
        : readHermesHealthWithRecovery(
          hermesCommand, hermesProfileId, projectId, projectRoot, spawnProcess,
        )
        .then((value) => ({ value, errorCode: null, checkedAt: value.observed_at }))
        .catch((error) => ({
          value: null,
          errorCode: error && typeof error.code === 'string' ? error.code : 'hermes-probe-invalid',
          checkedAt: new Date().toISOString(),
        }));
    const queueRequest = queuePaused
      ? Promise.resolve({ value: null, errorCode: 'feed-auto-paused', checkedAt: priorQueueFailure.checkedAt })
      : client.callTool('project_queue_snapshot', {})
        .then((wire) => parseCuratorQueueSnapshot(wire, projectId))
        .then((value) => ({ value, errorCode: null, checkedAt: value.observed_at }))
        .catch((error) => ({
          value: null,
          errorCode: error && typeof error.code === 'string'
            ? error.code : 'curator-queue-read',
          checkedAt: new Date().toISOString(),
        }));
    const [health, queue] = await Promise.all([healthRequest, queueRequest]);
    const healthState = healthPaused
      ? priorHealthFailure
      : recordFeedResult(key, 'health', health.errorCode, health.checkedAt);
    const queueState = queuePaused
      ? priorQueueFailure
      : recordFeedResult(key, 'queue', queue.errorCode, queue.checkedAt);
    return {
      health: health.value,
      healthProbeError: health.errorCode,
      healthLastFailureCode: healthPaused
        ? priorHealthFailure.code : health.errorCode,
      healthCheckedAt: health.checkedAt,
      healthAutoPaused: Boolean(healthState?.paused),
      queueSnapshot: queue.value,
      queueProbeError: queue.errorCode,
      queueLastFailureCode: queuePaused
        ? priorQueueFailure.code : queue.errorCode,
      queueCheckedAt: queue.checkedAt,
      queueAutoPaused: Boolean(queueState?.paused),
    };
  })();
  feedRequestsInFlight.set(key, pending);
  pending.finally(() => {
    if (feedRequestsInFlight.get(key) === pending) feedRequestsInFlight.delete(key);
  }).catch(() => {});
  return pending;
}

function dashboardErrorMessage(error) {
  if (error && typeof error.code === 'string'
    && (STARTUP_ERROR_CODES.has(error.code) || error.code === 'launcher-runtime')
    && Object.prototype.hasOwnProperty.call(STATUS_READ_FAILURES, error.code)) {
    return STATUS_READ_FAILURES[error.code];
  }
  switch (error && error.code) {
    case 'status-project-invalid':
      return 'This workspace has an invalid .curatormd-v2.toml project ID. Correct the project file before opening Curator.';
    case 'status-project-mismatch':
      return 'Curator opened a different project database than this workspace declares. Check curatormdV2.databaseBindings.';
    case 'status-database-binding-invalid':
      return 'No absolute Curator database is configured for this project. Set curatormdV2.databaseBindings in User settings.';
    case 'launcher-start':
      return 'Could not start Curator V2. Check the User setting serverCommand and the installed launcher.';
    case 'launcher-exit':
      return TRANSPORT_CLOSED_MESSAGE;
    case 'timeout':
      return 'Curator V2 did not respond within 15 seconds. Check the local backend and try again.';
    case 'read-denied':
      return 'Curator V2 denied this read. Check the configured project and its active local read grant.';
    case 'mcp-tool-error':
      return MCP_ERROR_MESSAGES[error.reasonCode]
        || 'Curator V2 rejected the request. Check the project grant and request details.';
    case 'mcp-request':
      return 'The Curator V2 MCP request failed. Check that the installed launcher and backend are compatible.';
    case 'invalid-response':
      return 'Curator V2 returned an invalid response. Check the installed launcher and backend.';
    case 'response-too-large':
      return 'Curator V2 returned an MCP line over the 4 MiB limit. Check the local launcher response size.';
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

function summarizeOperationalQueues(snapshot, projectId) {
  if (!snapshot || snapshot.project_id !== projectId) {
    return 'Operational queues: unknown. Curator queue snapshot unavailable or mismatched.';
  }
  if (snapshot.database_observation_complete !== true) {
    return 'Operational queues: unknown. Database observation is incomplete.';
  }
  const counts = snapshot.operational_counts;
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
    || !eventFields.every((field) => snapshot[field] === null || exactCount(snapshot[field]))) {
    return 'Operational queues: unknown. Curator queue snapshot is incomplete.';
  }
  const age = snapshot.oldest_pending_event_age_seconds === null
    ? 'none' : `${snapshot.oldest_pending_event_age_seconds}s`;
  return `Events received ${snapshot.event_received_count ?? 'unavailable'}, failed ${snapshot.event_failed_count ?? 'unavailable'}, quarantined ${snapshot.event_quarantined_count ?? 'unavailable'}, active claims ${snapshot.event_claimed_count ?? 'unavailable'}, expired claims ${snapshot.event_expired_claim_count ?? 'unavailable'}; oldest pending age ${age}. Reviews pending ${counts.pending_review_count}; purge pending ${counts.pending_purge_receipt_count} receipts / ${counts.pending_purge_artifact_count} artifacts; expiry pending ${counts.pending_expiry_purge_receipt_count} receipts / ${counts.pending_expiry_purge_artifact_count} artifacts.`;
}

function queueMetricRows(snapshot, projectId) {
  const unavailable = [{
    label: 'Queue snapshot',
    value: summarizeOperationalQueues(snapshot, projectId).replace(/^Operational queues: unknown\. /, ''),
    state: 'unknown',
  }];
  if (!snapshot || snapshot.project_id !== projectId
    || snapshot.database_observation_complete !== true) return unavailable;
  const counts = snapshot.operational_counts;
  const exactCount = (value) => Number.isSafeInteger(value) && value >= 0;
  const nullableText = (value) => exactCount(value) ? String(value) : 'unknown';
  if (!counts || ![
    'pending_review_count', 'pending_purge_receipt_count', 'pending_purge_artifact_count',
    'pending_expiry_purge_receipt_count', 'pending_expiry_purge_artifact_count',
  ].every((field) => exactCount(counts[field]))) return unavailable;
  const nullableState = (value, positiveState = 'warning') => (
    !exactCount(value) ? 'unknown' : value > 0 ? positiveState : 'healthy'
  );
  const age = snapshot.oldest_pending_event_age_seconds;
  const ageText = age === null
    ? snapshot.event_received_count === 0 && snapshot.event_failed_count === 0
      ? 'none' : 'unknown'
    : exactCount(age) ? `${age}s` : 'unknown';
  return [
    { label: 'Events received', value: nullableText(snapshot.event_received_count), state: nullableState(snapshot.event_received_count, 'review') },
    { label: 'Events failed', value: nullableText(snapshot.event_failed_count), state: nullableState(snapshot.event_failed_count, 'degraded') },
    { label: 'Events quarantined', value: nullableText(snapshot.event_quarantined_count), state: nullableState(snapshot.event_quarantined_count, 'degraded') },
    { label: 'Active claims', value: nullableText(snapshot.event_claimed_count), state: snapshot.event_claimed_count === null ? 'unknown' : 'neutral' },
    { label: 'Expired claims', value: nullableText(snapshot.event_expired_claim_count), state: nullableState(snapshot.event_expired_claim_count) },
    { label: 'Oldest pending age', value: ageText, state: ageText === 'unknown'
      || !exactCount(snapshot.event_received_count) || !exactCount(snapshot.event_failed_count)
      ? 'unknown' : snapshot.event_received_count || snapshot.event_failed_count ? 'review' : 'healthy' },
    { label: 'SDE reviews pending', value: String(counts.pending_review_count), state: counts.pending_review_count ? 'review' : 'healthy' },
    { label: 'Purge pending', value: `${counts.pending_purge_receipt_count} receipts · ${counts.pending_purge_artifact_count} artifacts`, state: counts.pending_purge_receipt_count || counts.pending_purge_artifact_count ? 'warning' : 'healthy' },
    { label: 'Expiry pending', value: `${counts.pending_expiry_purge_receipt_count} receipts · ${counts.pending_expiry_purge_artifact_count} artifacts`, state: counts.pending_expiry_purge_receipt_count || counts.pending_expiry_purge_artifact_count ? 'warning' : 'healthy' },
  ];
}

function healthComponentRows(snapshot, projectId, now = Date.now()) {
  const dependencies = snapshot && snapshot.project_id === projectId
    && Array.isArray(snapshot.dependencies) && snapshot.dependencies.length <= 32
    ? snapshot.dependencies : [];
  const byName = new Map(dependencies.map((dependency) => [dependency?.name, dependency]));
  return REQUIRED_HEALTH_PROBES.map((name) => {
    const dependency = byName.get(name);
    const observedAt = dependency && typeof dependency.observed_at === 'string'
      ? Date.parse(dependency.observed_at) : Number.NaN;
    const ageSeconds = (now - observedAt) / 1000;
    const validStatus = dependency
      && ['healthy', 'degraded', 'unknown'].includes(dependency.status)
      && Number.isSafeInteger(dependency.age_seconds)
      && dependency.age_seconds >= 0;
    const fresh = Number.isFinite(observedAt)
      && ageSeconds <= MAX_HEALTH_PROBE_AGE_SECONDS + MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS
      && ageSeconds >= -MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS
      && dependency.age_seconds <= MAX_HEALTH_PROBE_AGE_SECONDS;
    const label = name.replaceAll('_', ' ');
    if (!validStatus || !fresh) {
      return {
        label,
        value: fresh === false && validStatus ? 'Observation is stale' : 'Observation unavailable',
        state: 'unknown',
        stateLabel: fresh === false && validStatus ? 'Stale' : 'Unknown',
        ...healthRecoveryAction(name),
      };
    }
    return {
      label,
      value: `${dependency.status} · checked ${Math.max(0, Math.floor(ageSeconds))}s ago`,
      state: dependency.status,
      stateLabel: dependency.status,
      ...(dependency.status === 'healthy' ? {} : {
        ...healthRecoveryAction(name),
      }),
    };
  });
}

function healthHistoryStatus(snapshot, projectId) {
  if (!snapshot || snapshot.project_id !== projectId
    || !['healthy', 'degraded', 'unknown'].includes(snapshot.status)) return 'unknown';
  return snapshot.status === 'degraded'
    && Array.isArray(snapshot.gate_codes) && snapshot.gate_codes.length > 0
    && snapshot.gate_codes.every((gate) => gate === 'review_backlog')
    ? 'healthy' : snapshot.status;
}

function dashboardComponentRows({
  health,
  projectId,
  healthProbeError = null,
  queueSnapshot = null,
  queueProbeError = null,
  workspaceViewsUpdated = null,
  healthHistoryPersisted = false,
}) {
  const rows = healthComponentRows(health, projectId);
  const healthProbeValid = !healthProbeError && health
    && health.project_id === projectId
    && ['healthy', 'degraded', 'unknown'].includes(health.status);
  rows.push({
    label: 'Hermes profile probe',
    value: healthProbeValid
      ? `Fresh project-bound health read · ${health.status}`
      : healthProbeError ? healthProbeFailureMessage(healthProbeError) : 'Health read unavailable',
    state: healthProbeValid ? 'healthy' : 'unknown',
    stateLabel: healthProbeValid ? 'healthy' : 'unknown',
    ...(healthProbeValid ? {} : {
      action: 'retryRecoveryReads',
      actionLabel: 'Recheck',
    }),
  });
  const queueReadValid = !queueProbeError && queueSnapshot
    && queueSnapshot.project_id === projectId;
  rows.push({
    label: 'Curator MCP queue read',
    value: queueReadValid ? 'Fresh project-bound queue read'
      : queueProbeError ? queueProbeFailureMessage(queueProbeError) : 'Queue read unavailable',
    state: queueReadValid ? 'healthy' : 'unknown',
    stateLabel: queueReadValid ? 'healthy' : 'unknown',
    ...(queueReadValid ? {} : {
      action: 'retryRecoveryReads',
      actionLabel: 'Recheck',
    }),
  });
  rows.push({
    label: 'Inbox and review projections',
    value: workspaceViewsUpdated === true ? 'Both local views refreshed'
      : workspaceViewsUpdated === false
        ? 'Refresh failed or an open review has unsaved edits'
        : 'Not checked by this refresh',
    state: workspaceViewsUpdated === true ? 'healthy'
      : workspaceViewsUpdated === false ? 'degraded' : 'unknown',
    stateLabel: workspaceViewsUpdated === true ? 'healthy'
      : workspaceViewsUpdated === false ? 'degraded' : 'unknown',
    action: 'refreshQueueViews',
    actionLabel: 'Rebuild local views',
  });
  rows.push({
    label: 'Health history storage',
    value: healthHistoryPersisted ? 'Saved and read back by VS Code'
      : 'Persistent storage unavailable',
    state: healthHistoryPersisted ? 'healthy' : 'unknown',
    stateLabel: healthHistoryPersisted ? 'healthy' : 'unknown',
  });
  return rows;
}

async function updatePersistentHealthHistory(store, projectId, profileId, status, checkedAt) {
  const unavailable = { samples: [], persisted: false, scope: null };
  if (!store || typeof store.get !== 'function' || typeof store.update !== 'function'
    || typeof projectId !== 'string' || !PROJECT_ID_PATTERN.test(projectId)
    || typeof profileId !== 'string' || !profileId.trim() || profileId.length > 128) {
    return unavailable;
  }
  const scopeHash = createHash('sha256').update(`${projectId}\0${profileId}`, 'utf8').digest('hex');
  const scopedUnavailable = { ...unavailable, scope: scopeHash };
  const key = `curatormdV2.healthHistory.${scopeHash}`;
  const prior = healthHistoryWrites.get(key) || Promise.resolve();
  const write = prior.catch(() => {}).then(async () => {
    let stored = store.get(key, []);
    if (!Array.isArray(stored) || stored.length > HEALTH_HISTORY_LIMIT * 4) stored = [];
    const samples = stored.filter((sample) => sample
      && ['healthy', 'degraded', 'unknown'].includes(sample.status)
      && typeof sample.observed_at === 'string' && sample.observed_at.length <= 64
      && Number.isFinite(Date.parse(sample.observed_at)))
      .map((sample) => ({
        observed_at: new Date(Date.parse(sample.observed_at)).toISOString(),
        status: sample.status,
      }))
      .filter((sample) => Date.parse(sample.observed_at) >= (healthHistoryResetCutoffs.get(key) || 0))
      .sort((left, right) => Date.parse(left.observed_at) - Date.parse(right.observed_at))
      .filter((sample, index, all) => index === 0
        || sample.observed_at !== all[index - 1].observed_at)
      .slice(-HEALTH_HISTORY_LIMIT);
    const timestamp = typeof checkedAt === 'string' && checkedAt.length <= 64
      ? Date.parse(checkedAt) : Number.NaN;
    if (['healthy', 'degraded', 'unknown'].includes(status)
      && Number.isFinite(timestamp)
      && timestamp >= (healthHistoryResetCutoffs.get(key) || 0)) {
      const observedAt = new Date(timestamp).toISOString();
      if (!samples.some((sample) => sample.observed_at === observedAt)) {
        samples.push({ observed_at: observedAt, status });
        samples.sort((left, right) => Date.parse(left.observed_at) - Date.parse(right.observed_at));
        samples.splice(0, Math.max(0, samples.length - HEALTH_HISTORY_LIMIT));
      }
    }
    await store.update(key, samples);
    const saved = store.get(key, null);
    if (!Array.isArray(saved) || JSON.stringify(saved) !== JSON.stringify(samples)) {
      throw new Error('health history readback failed');
    }
    return samples;
  });
  healthHistoryWrites.set(key, write);
  try {
    return { samples: await write, persisted: true, scope: scopeHash };
  } catch (_) {
    return scopedUnavailable;
  } finally {
    if (healthHistoryWrites.get(key) === write) healthHistoryWrites.delete(key);
  }
}

async function resetPersistentHealthHistory(store, projectId, profileId) {
  if (!store || typeof store.get !== 'function' || typeof store.update !== 'function'
    || typeof projectId !== 'string' || !PROJECT_ID_PATTERN.test(projectId)
    || typeof profileId !== 'string' || !profileId.trim() || profileId.length > 128) {
    return false;
  }
  const scopeHash = createHash('sha256').update(`${projectId}\0${profileId}`, 'utf8').digest('hex');
  const key = `curatormdV2.healthHistory.${scopeHash}`;
  healthHistoryResetCutoffs.set(key, Date.now());
  const prior = healthHistoryWrites.get(key) || Promise.resolve();
  const reset = prior.catch(() => {}).then(async () => {
    await store.update(key, []);
    const saved = store.get(key, null);
    if (!Array.isArray(saved) || saved.length !== 0) {
      throw new Error('health history reset readback failed');
    }
    return true;
  });
  healthHistoryWrites.set(key, reset);
  try {
    return await reset;
  } catch (_) {
    return false;
  } finally {
    if (healthHistoryWrites.get(key) === reset) healthHistoryWrites.delete(key);
  }
}

const OPERATIONAL_ERROR_LABELS = Object.freeze({
  'health:probe': Object.freeze({
    component: 'Hermes health probe',
    category: 'health_read_failed',
    summary: 'Hermes health data could not be read.',
    recoveryHint: 'Check the selected Hermes profile and the configured Hermes command, then retry the recovery checks.',
  }),
  'queue:read': Object.freeze({
    component: 'Curator queue read',
    category: 'queue_read_failed',
    summary: 'Curator queue data could not be read.',
    recoveryHint: 'Check the project database binding and local project grant, then retry the recovery checks.',
  }),
  'health:degraded': Object.freeze({
    component: 'Hermes readiness',
    category: 'readiness_degraded',
    summary: 'Hermes reported one or more readiness gates that need attention.',
    recoveryHint: 'Review the health gate details above and repair the named component before retrying.',
  }),
  'events:evidence_rejected': Object.freeze({
    component: 'Curator event processing',
    category: 'evidence_rejected',
    summary: 'Event evidence was rejected by validation.',
    recoveryHint: 'Inspect failed event receipts in the inbox and correct the evidence source or request.',
  }),
  'events:evidence_adapter_error': Object.freeze({
    component: 'Curator event processing',
    category: 'evidence_adapter_error',
    summary: 'An evidence adapter failed while processing events.',
    recoveryHint: 'Check the configured evidence adapter and its local dependencies, then retry eligible events.',
  }),
  'events:other': Object.freeze({
    component: 'Curator event processing',
    category: 'event_processing_error',
    summary: 'One or more event receipts failed or were quarantined.',
    recoveryHint: 'Inspect failed and quarantined receipts in Recovery Manager to see the supported retry or review action.',
  }),
});

function operationalErrorsForSnapshot({
  health, projectId, healthProbeError, queueProbeError, queueSnapshot, metrics,
  healthCheckedAt, queueCheckedAt,
}) {
  const errors = [];
  const authoritativeComponents = [];
  const healthObservedAt = typeof healthCheckedAt === 'string' ? healthCheckedAt : health?.observed_at;
  const queueObservedAt = typeof queueCheckedAt === 'string' ? queueCheckedAt : queueSnapshot?.observed_at;
  const healthReadValid = health && health.project_id === projectId
    && ['healthy', 'degraded', 'unknown'].includes(health.status)
    && Array.isArray(health.gate_codes);
  const queueReadValid = queueSnapshot && queueSnapshot.project_id === projectId
    && queueSnapshot.database_observation_complete === true
    && Number.isSafeInteger(queueSnapshot.event_failed_count)
    && Number.isSafeInteger(queueSnapshot.event_quarantined_count);
  if (healthProbeError) errors.push({
    key: 'health:probe',
    observedAt: healthObservedAt,
    ...OPERATIONAL_ERROR_LABELS['health:probe'],
    summary: `${OPERATIONAL_ERROR_LABELS['health:probe'].summary} ${healthProbeFailureMessage(healthProbeError)}`,
  });
  if (queueProbeError) errors.push({
    key: 'queue:read',
    observedAt: queueObservedAt,
    ...OPERATIONAL_ERROR_LABELS['queue:read'],
    summary: `${OPERATIONAL_ERROR_LABELS['queue:read'].summary} ${queueProbeFailureMessage(queueProbeError)}`,
  });
  if (healthProbeError || healthReadValid) authoritativeComponents.push('Hermes health probe');
  if (queueProbeError || queueReadValid) authoritativeComponents.push('Curator queue read');
  if (healthReadValid && health.status === 'degraded'
    && health.gate_codes.some((code) => code !== 'review_backlog')) {
    const knownGateDescriptions = health.gate_codes
      .filter((code) => code !== 'review_backlog')
      .filter((code) => Object.prototype.hasOwnProperty.call(HEALTH_GATE_LABELS, code)
        || (() => {
          const match = /^dependency_(unknown|unavailable|degraded):([a-z][a-z0-9_]{0,63})$/.exec(code);
          return Boolean(match && Object.prototype.hasOwnProperty.call(HEALTH_DEPENDENCY_LABELS, match[2]));
        })())
      .slice(0, 12)
      .map(healthGateLabel);
    errors.push({
      key: 'health:degraded',
      observedAt: healthObservedAt,
      ...OPERATIONAL_ERROR_LABELS['health:degraded'],
      summary: knownGateDescriptions.length
        ? `Readiness needs attention: ${knownGateDescriptions.join(' ')}`
        : OPERATIONAL_ERROR_LABELS['health:degraded'].summary,
    });
  }
  if (!healthProbeError && healthReadValid) authoritativeComponents.push('Hermes readiness');
  if (queueReadValid) {
    const total = queueSnapshot.event_failed_count + queueSnapshot.event_quarantined_count;
    const categories = summarizeEventFailureCategories(metrics, projectId, total);
    if (total === 0 || categories) authoritativeComponents.push('Curator event processing');
    if (total > 0 && categories) {
      for (const category of ['evidence_rejected', 'evidence_adapter_error', 'other']) {
        const count = categories[category];
        if (count > 0) errors.push({
          key: `events:${category}`,
          observedAt: queueObservedAt,
          ...OPERATIONAL_ERROR_LABELS[`events:${category}`],
          summary: `${OPERATIONAL_ERROR_LABELS[`events:${category}`].summary} Current failed/quarantined count: ${count}.`,
        });
      }
    } else if (total > 0) {
      errors.push({
        key: 'events:other',
        observedAt: queueObservedAt,
        ...OPERATIONAL_ERROR_LABELS['events:other'],
        summary: `${OPERATIONAL_ERROR_LABELS['events:other'].summary} Current failed/quarantined count: ${total}; category details are unavailable.`,
      });
    }
  }
  errors.authoritativeComponents = authoritativeComponents;
  return errors;
}

async function updatePersistentOperationalErrorLog(store, projectId, profileId, currentErrors, checkedAt) {
  const unavailable = { entries: [], persisted: false, scope: null };
  if (!store || typeof store.get !== 'function' || typeof store.update !== 'function'
    || typeof projectId !== 'string' || !PROJECT_ID_PATTERN.test(projectId)
    || typeof profileId !== 'string' || !profileId.trim() || profileId.length > 128) return unavailable;
  const scope = createHash('sha256').update(`${projectId}\0${profileId}`, 'utf8').digest('hex');
  const key = `curatormdV2.operationalErrors.${scope}`;
  const prior = operationalErrorWrites.get(key) || Promise.resolve();
  const write = prior.catch(() => {}).then(async () => {
    const stored = store.get(key, []);
    const priorEntries = Array.isArray(stored) && stored.length <= OPERATIONAL_ERROR_LOG_LIMIT * 4
      ? stored.filter((entry) => entry && typeof entry.key === 'string'
        && Object.prototype.hasOwnProperty.call(OPERATIONAL_ERROR_LABELS, entry.key)
        && Number.isSafeInteger(entry.occurrences) && entry.occurrences > 0
        && typeof entry.firstSeenAt === 'string' && Number.isFinite(Date.parse(entry.firstSeenAt))
        && typeof entry.lastSeenAt === 'string' && Number.isFinite(Date.parse(entry.lastSeenAt))
        && typeof entry.active === 'boolean') : [];
    const byKey = new Map(priorEntries.map((entry) => [entry.key, {
      key: entry.key,
      ...OPERATIONAL_ERROR_LABELS[entry.key],
      firstSeenAt: new Date(Date.parse(entry.firstSeenAt)).toISOString(),
      lastSeenAt: new Date(Date.parse(entry.lastSeenAt)).toISOString(),
      occurrences: Math.min(entry.occurrences, Number.MAX_SAFE_INTEGER),
      active: entry.active,
      summary: typeof entry.summary === 'string' && entry.summary.length <= 500
        ? entry.summary : OPERATIONAL_ERROR_LABELS[entry.key].summary,
    }]));
    const timestamp = typeof checkedAt === 'string' && Number.isFinite(Date.parse(checkedAt))
      ? new Date(Date.parse(checkedAt)).toISOString() : new Date().toISOString();
    const activeKeys = new Set();
    for (const incident of Array.isArray(currentErrors) ? currentErrors : []) {
      if (!incident || typeof incident.key !== 'string'
        || !Object.prototype.hasOwnProperty.call(OPERATIONAL_ERROR_LABELS, incident.key)) continue;
      activeKeys.add(incident.key);
      const existing = byKey.get(incident.key);
      const observedAt = typeof incident.observedAt === 'string'
        && Number.isFinite(Date.parse(incident.observedAt))
        ? new Date(Date.parse(incident.observedAt)).toISOString() : timestamp;
      byKey.set(incident.key, {
        key: incident.key,
        ...OPERATIONAL_ERROR_LABELS[incident.key],
        firstSeenAt: existing?.firstSeenAt || observedAt,
        lastSeenAt: observedAt,
        occurrences: existing?.lastSeenAt === observedAt ? existing.occurrences
          : Math.min(Number.MAX_SAFE_INTEGER, (existing?.occurrences || 0) + 1),
        active: true,
        summary: typeof incident.summary === 'string'
          ? incident.summary.slice(0, 500) : OPERATIONAL_ERROR_LABELS[incident.key].summary,
      });
    }
    for (const [entryKey, entry] of byKey) {
      const authoritativeComponents = Array.isArray(currentErrors?.authoritativeComponents)
        ? currentErrors.authoritativeComponents : [];
      if (!activeKeys.has(entryKey) && authoritativeComponents.includes(entry.component)) {
        entry.active = false;
      }
    }
    const entries = [...byKey.values()].sort((left, right) =>
      Date.parse(right.lastSeenAt) - Date.parse(left.lastSeenAt)).slice(0, OPERATIONAL_ERROR_LOG_LIMIT);
    await store.update(key, entries);
    const saved = store.get(key, null);
    if (!Array.isArray(saved) || JSON.stringify(saved) !== JSON.stringify(entries)) {
      throw new Error('operational error log readback failed');
    }
    return entries;
  });
  operationalErrorWrites.set(key, write);
  try {
    return { entries: await write, persisted: true, scope };
  } catch (_) {
    return { ...unavailable, scope };
  } finally {
    if (operationalErrorWrites.get(key) === write) operationalErrorWrites.delete(key);
  }
}

function parsePurgeReceiptInspection(wire, expectedReceiptId) {
  let value;
  try { value = typeof wire === 'string' ? JSON.parse(wire) : wire; } catch (_) { value = null; }
  if (!Array.isArray(value) || value.length !== 2) {
    throw curatorError('invalid-response', 'Curator returned an invalid cleanup receipt.');
  }
  const [receipt, targets] = value;
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)
    || receipt.receipt_id !== expectedReceiptId
    || !['complete', 'purge_pending'].includes(receipt.purge_status)
    || !Array.isArray(targets) || targets.length > 500) {
    throw curatorError('invalid-response', 'Curator returned an invalid cleanup receipt.');
  }
  const allowedStatus = ['pending', 'purged', 'failed', 'held'];
  const allowedOutcome = ['deleted', 'already_absent', 'held', 'changed', 'failed'];
  const rows = targets.map((target) => {
    if (!target || typeof target !== 'object' || Array.isArray(target)
      || !target.artifact || typeof target.artifact.path !== 'string'
      || target.artifact.path.length > 1024
      || /[\u0000-\u001f\u007f]/.test(target.artifact.path)
      || !allowedStatus.includes(target.status)
      || !Number.isSafeInteger(target.attempts) || target.attempts < 0
      || typeof target.safe_recovery_action !== 'string'
      || !/^[a-z_]{1,64}$/.test(target.safe_recovery_action)
      || (target.outcome !== null && target.outcome !== undefined
        && !allowedOutcome.includes(target.outcome))
      || (target.error !== null && target.error !== undefined
        && (typeof target.error !== 'string' || !/^[a-z_]{1,64}$/.test(target.error)))
      || (target.next_attempt_in_seconds !== null && target.next_attempt_in_seconds !== undefined
        && (!Number.isSafeInteger(target.next_attempt_in_seconds)
          || target.next_attempt_in_seconds < 0))) {
      throw curatorError('invalid-response', 'Curator returned an invalid cleanup receipt.');
    }
    return {
      path: target.artifact.path,
      status: target.status,
      outcome: target.outcome || 'unknown',
      attempts: target.attempts,
      error: target.error || null,
      nextAttemptInSeconds: target.next_attempt_in_seconds ?? null,
      nextAction: target.safe_recovery_action,
      approvalStale: target.approval_stale === true,
    };
  });
  return {
    receiptId: receipt.receipt_id,
    purgeStatus: receipt.purge_status,
    canonicalPersisted: receipt.canonical_persisted === true,
    cleanupAuthorized: receipt.cleanup_authorized === true,
    cleanupCanonicalPersisted: receipt.cleanup_canonical_persisted === true,
    targetCount: rows.length,
    targets: rows.slice(0, 100),
    omittedTargetCount: Math.max(0, rows.length - 100),
  };
}

function parseTerminalEventInventory(wire, expectedProjectId) {
  let value;
  try { value = typeof wire === 'string' ? JSON.parse(wire) : wire; } catch (_) { value = null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.project_id !== expectedProjectId
    || !Number.isSafeInteger(value.count_after_cursor) || value.count_after_cursor < 0
    || typeof value.complete !== 'boolean'
    || !Array.isArray(value.events) || value.events.length > 100
    || (value.next_after_event_id !== null
      && (typeof value.next_after_event_id !== 'string'
        || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value.next_after_event_id)))) {
    throw curatorError('invalid-response', 'Curator returned an invalid terminal event inventory.');
  }
  const events = value.events.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)
      || typeof item.event_id !== 'string'
      || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(item.event_id)
      || !['failed', 'quarantined'].includes(item.status)
      || typeof item.payload_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.payload_sha256)
      || typeof item.source_id !== 'string'
      || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(item.source_id)
      || (item.source_sequence !== null && (!Number.isSafeInteger(item.source_sequence)
        || item.source_sequence < 1))) {
      throw curatorError('invalid-response', 'Curator returned an invalid terminal event inventory.');
    }
    return {
      eventId: item.event_id,
      status: item.status,
      payloadSha256: item.payload_sha256,
      sourceId: item.source_id,
      sourceSequence: item.source_sequence,
    };
  });
  if (!value.complete && (!events.length
    || value.next_after_event_id !== events.at(-1).eventId)) {
    throw curatorError('invalid-response', 'Curator returned an invalid terminal event cursor.');
  }
  return {
    projectId: value.project_id,
    countAfterCursor: value.count_after_cursor,
    complete: value.complete,
    nextAfterEventId: value.next_after_event_id,
    events,
  };
}

function parseEventCompactionProposal(wire, expectedProjectId, expectedOffset, expectedLimit) {
  let value;
  try { value = typeof wire === 'string' ? JSON.parse(wire) : wire; } catch (_) { value = null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.project_id !== expectedProjectId
    || !Number.isSafeInteger(value.eligible_count) || value.eligible_count < 0
    || value.offset !== expectedOffset || value.limit !== expectedLimit
    || typeof value.manifest_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.manifest_sha256)
    || !Array.isArray(value.items) || value.items.length > expectedLimit
    || value.offset + value.items.length > value.eligible_count) {
    throw curatorError('invalid-response', 'Curator returned an invalid event archive proposal.');
  }
  const items = value.items.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)
      || item.project_id !== expectedProjectId
      || typeof item.event_id !== 'string'
      || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(item.event_id)
      || typeof item.event_type !== 'string' || !/^[a-z][a-z0-9._-]{0,127}$/.test(item.event_type)
      || typeof item.payload_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.payload_sha256)
      || typeof item.received_at !== 'string' || item.received_at.length > 64
      || typeof item.processed_at !== 'string' || item.processed_at.length > 64
      || (item.source_id !== null && (typeof item.source_id !== 'string'
        || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(item.source_id)))
      || (item.source_sequence !== null && (!Number.isSafeInteger(item.source_sequence)
        || item.source_sequence < 1))
      || !['attempts', 'retry_audit_count', 'terminal_disposition_count',
        'consumer_drain_reference_count'].every((field) => Number.isSafeInteger(item[field])
          && item[field] >= 0)) {
      throw curatorError('invalid-response', 'Curator returned an invalid event archive proposal.');
    }
    return {
      eventId: item.event_id,
      eventType: item.event_type,
      payloadSha256: item.payload_sha256,
      receivedAt: item.received_at,
      processedAt: item.processed_at,
      sourceId: item.source_id,
      sourceSequence: item.source_sequence,
      attempts: item.attempts,
      retryAuditCount: item.retry_audit_count,
      terminalDispositionCount: item.terminal_disposition_count,
      consumerDrainReferenceCount: item.consumer_drain_reference_count,
    };
  });
  return {
    projectId: value.project_id,
    eligibleCount: value.eligible_count,
    offset: value.offset,
    limit: value.limit,
    manifestSha256: value.manifest_sha256,
    items,
  };
}

function parseProjectReconciliation(wire, expectedProjectId, expectedOffset, expectedLimit) {
  let value;
  try { value = typeof wire === 'string' ? JSON.parse(wire) : wire; } catch (_) { value = null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.project_id !== expectedProjectId
    || value.offset !== expectedOffset || value.limit !== expectedLimit
    || !Number.isSafeInteger(value.total_goals) || value.total_goals < 0
    || (value.next_offset !== null && (!Number.isSafeInteger(value.next_offset)
      || value.next_offset <= expectedOffset))
    || !Array.isArray(value.goals) || value.goals.length > expectedLimit
    || !Array.isArray(value.orphan_marker_sha256) || value.orphan_marker_sha256.length > 10000
    || !Array.isArray(value.malformed_marker_sha256) || value.malformed_marker_sha256.length > 10000
    || !Number.isSafeInteger(value.malformed_marker_count) || value.malformed_marker_count < 0
    || !Number.isSafeInteger(value.unrecognized_marker_count) || value.unrecognized_marker_count < 0
    || typeof value.inventory_complete !== 'boolean'
    || !Number.isSafeInteger(value.scanned_bytes) || value.scanned_bytes < 0) {
    throw curatorError('invalid-response', 'Curator returned an invalid Markdown reconciliation page.');
  }
  const goals = value.goals.map((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)
      || typeof item.goal_id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(item.goal_id)
      || !['synced', 'missing', 'divergent', 'malformed'].includes(item.status)
      || typeof item.expected_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.expected_sha256)
      || (item.actual_sha256 !== null
        && (typeof item.actual_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(item.actual_sha256)))) {
      throw curatorError('invalid-response', 'Curator returned an invalid Markdown reconciliation row.');
    }
    return {
      goalId: item.goal_id,
      status: item.status,
      expectedSha256: item.expected_sha256,
      actualSha256: item.actual_sha256,
    };
  });
  const validHashes = (items) => items.every((item) => typeof item === 'string'
    && /^[a-f0-9]{64}$/.test(item));
  if (!validHashes(value.orphan_marker_sha256)
    || !validHashes(value.malformed_marker_sha256)
    || value.malformed_marker_count < value.malformed_marker_sha256.length) {
    throw curatorError('invalid-response', 'Curator returned invalid Markdown marker digests.');
  }
  return {
    projectId: value.project_id,
    totalGoals: value.total_goals,
    offset: value.offset,
    limit: value.limit,
    nextOffset: value.next_offset,
    goals,
    orphanMarkerSha256: value.orphan_marker_sha256,
    malformedMarkerSha256: value.malformed_marker_sha256,
    malformedMarkerCount: value.malformed_marker_count,
    unrecognizedMarkerCount: value.unrecognized_marker_count,
    inventoryComplete: value.inventory_complete,
    scannedBytes: value.scanned_bytes,
  };
}

function parseGoalReconciliation(wire, expectedProjectId, expectedGoalId) {
  let value;
  try { value = typeof wire === 'string' ? JSON.parse(wire) : wire; } catch (_) { value = null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.project_id !== expectedProjectId || value.goal_id !== expectedGoalId
    || !['synced', 'missing', 'divergent', 'malformed'].includes(value.status)
    || typeof value.expected_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.expected_sha256)
    || (value.actual_sha256 !== null
      && (typeof value.actual_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(value.actual_sha256)))) {
    throw curatorError('invalid-response', 'Curator returned an invalid goal reconciliation result.');
  }
  return {
    projectId: value.project_id,
    goalId: value.goal_id,
    status: value.status,
    expectedSha256: value.expected_sha256,
    actualSha256: value.actual_sha256,
  };
}

function validateReconciliationTarget(target) {
  if (typeof target !== 'string') return null;
  const value = target.trim();
  if (!value || value.length > 512 || /[\\\u0000-\u001f\u007f]/.test(value)
    || value.startsWith('/') || value.split('/').some((segment) =>
      !segment || segment === '.' || segment === '..')) return null;
  return value;
}

function queuePanelState(snapshot, projectId) {
  const rows = queueMetricRows(snapshot, projectId);
  if (rows.length === 1 && rows[0].state === 'unknown') return 'unknown';
  if (rows.some((row) => row.state === 'unknown')) return 'unknown';
  if (snapshot.event_failed_count > 0 || snapshot.event_quarantined_count > 0) return 'degraded';
  if (snapshot.event_expired_claim_count > 0
    || snapshot.operational_counts.pending_purge_receipt_count > 0
    || snapshot.operational_counts.pending_purge_artifact_count > 0
    || snapshot.operational_counts.pending_expiry_purge_receipt_count > 0
    || snapshot.operational_counts.pending_expiry_purge_artifact_count > 0) return 'warning';
  if (snapshot.event_received_count > 0 || snapshot.operational_counts.pending_review_count > 0) return 'review';
  return 'healthy';
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

function summarizeOperationalAlerts(health, storage, metrics, projectId, queueSnapshot = health) {
  const alerts = [];
  const healthMatches = health && health.project_id === projectId;
  const healthComplete = healthMatches && health.database_observation_complete === true;
  const healthStatusValid = healthComplete
    && ['healthy', 'degraded', 'unknown'].includes(health.status)
    && Array.isArray(health.gate_codes)
    && health.gate_codes.every((gate) => typeof gate === 'string'
      && /^[a-z][a-z0-9_:.-]{0,127}$/.test(gate));
  if (!healthStatusValid) {
    alerts.push('Readiness unknown (Hermes health snapshot unavailable, incomplete, or mismatched).');
  } else {
    const gates = health.gate_codes.filter((gate) => gate !== 'review_backlog').slice(0, 20);
    const status = health.status === 'degraded' && health.gate_codes.length > 0
      && health.gate_codes.every((gate) => gate === 'review_backlog')
      ? 'healthy' : health.status;
    if (status !== 'healthy' || gates.length > 0) {
      alerts.push(`Readiness ${status}${gates.length ? `: ${gates.join(', ')}` : '.'}`);
    }
  }

  const queueComplete = queueSnapshot && queueSnapshot.project_id === projectId
    && queueSnapshot.database_observation_complete === true;
  if (!queueComplete) {
    alerts.push('Operational queues unknown (Curator queue snapshot unavailable, incomplete, or mismatched).');
  } else {
    const counts = queueSnapshot.operational_counts;
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
      || !eventFields.every((field) => queueSnapshot[field] === null || countValid(queueSnapshot[field]))) {
      alerts.push('Operational queues unknown (Curator queue snapshot is incomplete).');
    } else {
      if (queueSnapshot.event_received_count === null) {
        alerts.push('Event intake status unknown.');
      } else if (queueSnapshot.event_received_count > 0) {
        alerts.push(`${queueSnapshot.event_received_count} event receipt(s) waiting to process.`);
      }
      const failuresUnknown = queueSnapshot.event_failed_count === null
        || queueSnapshot.event_quarantined_count === null;
      const failed = queueSnapshot.event_failed_count;
      const quarantined = queueSnapshot.event_quarantined_count;
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
      if (queueSnapshot.event_expired_claim_count === null) {
        alerts.push('Expired event-claim status unknown.');
      } else if (queueSnapshot.event_expired_claim_count > 0) {
        alerts.push(`${queueSnapshot.event_expired_claim_count} expired event claim(s) need retry/reconciliation.`);
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
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true,
    });
    this.nextId = 1;
    this.profileId = profileId;
    this.sessionId = randomBytes(16).toString('hex');
    this.pending = new Map();
    this.buffer = '';
    this.startupStderr = Buffer.alloc(0);
    this.closed = false;
    this.exitHandled = false;
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', (chunk) => this._receive(chunk));
    if (this.child.stderr) {
      this.child.stderr.on('data', (chunk) => {
        const received = Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk), 'utf8');
        const remaining = MAX_STARTUP_DIAGNOSTIC_BYTES - this.startupStderr.length;
        if (remaining > 0) {
          this.startupStderr = Buffer.concat([
            this.startupStderr,
            received.subarray(0, remaining),
          ]);
        }
      });
    }
    this.child.on('error', () => this._failAll(curatorError(
      'launcher-start', 'Curator MCP process could not start.',
    )));
    const handleExit = () => {
      if (this.exitHandled) return;
      this.exitHandled = true;
      this.closed = true;
      const startupCode = startupFailureCode(this.startupStderr);
      this._failAll(startupCode
        ? curatorError(startupCode, 'Curator MCP startup was rejected.')
        : curatorError('launcher-exit', 'Curator MCP process exited before replying.'));
    };
    if (this.child.stderr) this.child.once('close', handleExit);
    else this.child.once('exit', handleExit);
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
      const errorText = (response.content || [])
        .find((item) => item && item.type === 'text' && typeof item.text === 'string')?.text;
      let reasonCode = 'internal_error';
      if (typeof errorText === 'string' && Buffer.byteLength(errorText, 'utf8') <= 1024) {
        try {
          const payload = JSON.parse(errorText);
          if (payload && payload.schema_version === 1
            && typeof payload.code === 'string' && MCP_ERROR_CODES.has(payload.code)) {
            reasonCode = payload.code;
          }
        } catch {}
      }
      const error = curatorError(
        'mcp-tool-error', `Curator rejected ${name} (${reasonCode}).`,
      );
      error.reasonCode = reasonCode;
      error.toolName = name;
      throw error;
    }
    const text = (response.content || [])
      .filter((item) => item && item.type === 'text' && typeof item.text === 'string')
      .map((item) => item.text)
      .join('\n');
    if (!text) throw new Error('Curator returned no readable result.');
    transportClosedAlertShown = false;
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
    if (this.closed) return;
    const incoming = `${this.buffer}${chunk}`;
    let start = 0;
    for (;;) {
      const newline = incoming.indexOf('\n', start);
      if (newline < 0) break;
      const rawLine = incoming.slice(start, newline);
      if (Buffer.byteLength(rawLine, 'utf8') > MAX_MCP_RESPONSE_LINE_BYTES) {
        this._failOversizedResponse();
        return;
      }
      const line = rawLine.trim();
      start = newline + 1;
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
    this.buffer = incoming.slice(start);
    if (Buffer.byteLength(this.buffer, 'utf8') > MAX_MCP_RESPONSE_LINE_BYTES) {
      this._failOversizedResponse();
    }
  }

  _failOversizedResponse() {
    this.closed = true;
    this.buffer = '';
    this.child.kill();
    this._failAll(curatorError(
      'response-too-large', 'Curator returned an MCP response over the 4 MiB line limit.',
    ));
  }

  _failAll(error) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}

function joinMarkdownParagraphLines(text) {
  const lines = text.split(/\r?\n/);
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const output = [];
  let fence = null;
  let structuredBlock = false;
  let previousProse = false;
  for (const line of lines) {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})/);
    if (fence) {
      output.push(line);
      if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null;
      previousProse = false;
      continue;
    }
    if (!line.trim()) structuredBlock = false;
    else if (/^ {0,3}(?:>|[-+*]\s|\d+[.)]\s|<(?:!--|[A-Za-z/!?]))/.test(line)) structuredBlock = true;
    if (structuredBlock) {
      output.push(line);
      previousProse = false;
      continue;
    }
    if (marker) {
      fence = marker[1];
      output.push(line);
      previousProse = false;
      continue;
    }
    const structural = !line.trim() || /^(?:\s{4}|\t| {0,3}(?:#{1,6}(?:\s|$)|\[[^\]]+\]:|\||<|(?:[-=*]\s*){3,}$))/.test(line)
      || line.includes('|');
    const hardBreak = /(?: {2,}|\\)$/.test(line);
    if (!structural && previousProse) {
      output[output.length - 1] += ` ${line.trim()}`;
    } else {
      output.push(line);
    }
    previousProse = !structural && !hardBreak;
  }
  return output.join(eol);
}

async function joinActiveMarkdownParagraphLines() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'markdown') {
    void vscode.window.showInformationMessage('Open a Markdown document to join wrapped paragraph lines.');
    return;
  }
  const document = editor.document;
  const text = document.getText();
  const joined = joinMarkdownParagraphLines(text);
  if (text === joined) return;
  await editor.edit((edit) => edit.replace(new vscode.Range(document.positionAt(0), document.positionAt(text.length)), joined));
}

function activate(context, spawnProcess = spawn) {
  healthHistoryStore = context?.globalState || null;
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
  const openHealingToolbox = vscode.commands.registerCommand(
    'curatormdV2.openHealingToolbox',
    () => showDashboard(spawn, { focusRecovery: true }),
  );
  const openPendingReview = vscode.commands.registerCommand(
    'curatormdV2.openPendingReview',
    () => openPendingReviewDocument(spawnProcess),
  );
  const joinMarkdown = vscode.commands.registerCommand(
    'curatormdV2.joinMarkdownParagraphLines', joinActiveMarkdownParagraphLines,
  );
  context.subscriptions.push(statusItem, openDashboard, openHealingToolbox, openPendingReview, joinMarkdown);
  if (vscode.languages && typeof vscode.languages.registerCodeLensProvider === 'function') {
    context.subscriptions.push(vscode.commands.registerCommand(
      'curatormdV2.reviewDocumentCandidate',
      (candidateId, decision) => launchDocumentReview(candidateId, decision),
    ));
    context.subscriptions.push(vscode.languages.registerCodeLensProvider(
      { scheme: 'file', language: 'markdown', pattern: '**/.curatormd-v2/sde-proposals/pending-review.md' },
      { provideCodeLenses: (document) => reviewDocumentActions(document) },
    ));
  }
  void refreshStatusBarHealthFromWorkspace();
  statusRefreshTimer = setInterval(() => {
    void refreshStatusBarHealthFromWorkspace();
  }, STATUS_REFRESH_INTERVAL_MS);
  if (typeof statusRefreshTimer.unref === 'function') statusRefreshTimer.unref();
  context.subscriptions.push({ dispose: () => clearInterval(statusRefreshTimer) });
  if (vscode.workspace && typeof vscode.workspace.onDidChangeWorkspaceFolders === 'function') {
    context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(() => {
      clearFeedFailureStates();
      resetStatusBarHealth();
      void refreshStatusBarHealthFromWorkspace(spawn, 'manual');
    }));
  }
  if (vscode.workspace && typeof vscode.workspace.onDidChangeConfiguration === 'function') {
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event || typeof event.affectsConfiguration !== 'function'
        || !event.affectsConfiguration('curatormdV2')) return;
      clearFeedFailureStates();
      resetStatusBarHealth();
      void refreshStatusBarHealthFromWorkspace(spawn, 'manual');
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
  healthHistoryStore = null;
  healthHistoryWrites.clear();
  healthHistoryResetCutoffs.clear();
  operationalErrorWrites.clear();
}

function updateStatusBarHealth(
  health, projectId, reviewItems = null, storage = null, readError = null,
) {
  if (!dashboardStatusItem) return 'unknown';
  const healthStatus = projectId
    && health?.project_id === projectId
    && ['healthy', 'degraded', 'unknown'].includes(health.status)
    ? health.status === 'degraded'
      && Array.isArray(health.gate_codes)
      && health.gate_codes.length > 0
      && health.gate_codes.every((gate) => gate === 'review_backlog')
      ? 'healthy' : health.status
    : 'unknown';
  const reviewsKnown = Array.isArray(reviewItems);
  const pendingReviews = reviewsKnown ? reviewItems.length : null;
  let displayStatus = healthStatus;
  if (healthStatus === 'healthy' && !reviewsKnown) displayStatus = 'unknown';
  const reviewSummary = !reviewsKnown
    ? 'pending SDE review count unavailable'
    : pendingReviews === 0
      ? 'no SDE reviews pending'
      : `${pendingReviews === REVIEW_QUEUE_SIZE ? 'At least ' : ''}${pendingReviews} pending SDE review${pendingReviews === 1 ? '' : 's'}`;
  const storageWarning = sqliteSizeWarning(storage, projectId);
  if (pendingReviews > 0) {
    const count = `${pendingReviews}${pendingReviews === REVIEW_QUEUE_SIZE ? '+' : ''}`;
    dashboardStatusItem.text = `$(checklist) CuratorMD V2: ${count} review${pendingReviews === 1 ? '' : 's'}`;
    dashboardStatusItem.color = STATUS_COLORS.action;
    dashboardStatusItem.command = 'curatormdV2.openPendingReview';
  } else {
    dashboardStatusItem.text = `$(circle-filled) CuratorMD V2: ${displayStatus}`
      + (storageWarning ? ' · SQLite size warning' : '');
    dashboardStatusItem.color = STATUS_COLORS[displayStatus];
    dashboardStatusItem.command = 'curatormdV2.openDashboard';
  }
  const clickAction = pendingReviews > 0
    ? 'Click to open pending-review.md.'
    : 'Click to open the project-scoped dashboard.';
  dashboardStatusItem.tooltip = statusTooltip(
    `${pendingReviews > 0 ? STATUS_COLOR_MEANINGS.action : statusColorMeaning(displayStatus)} Project health: ${healthStatus}.`
      + healthGateSummary(health, projectId)
      + (readError ? ` ${statusReadFailure(readError)}` : '')
      + ` ${reviewSummary}. `
      + (storageWarning ? `${storageWarning} ` : '')
      + clickAction,
  );
  return displayStatus;
}

async function openPendingReviewDocument(spawnProcess = spawn) {
  const workspace = vscode.workspace
    && vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!workspace) {
    vscode.window.showWarningMessage('Open a Curator-enabled project folder first.');
    return;
  }
  const projectRoot = workspace.uri.fsPath;
  if (!fs.existsSync(path.join(projectRoot, '.curatormd-v2.toml'))) {
    vscode.window.showWarningMessage('Open a Curator-enabled project to review pending SDE proposals.');
    return;
  }
  const approvalJson = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
  let workspaceViewsUpdated = false;
  let refreshError = null;
  try {
    workspaceViewsUpdated = await withReviewClient(
      projectRoot,
      (client, projectId) => refreshWorkspaceQueueViews(client, projectRoot, projectId),
      { spawnProcess },
    );
  } catch (error) {
    refreshError = error instanceof Error ? error.message : 'Curator review refresh failed.';
  }
  try {
    for (const directory of [
      path.dirname(path.dirname(approvalJson)), path.dirname(approvalJson),
    ]) {
      const directoryStat = fs.lstatSync(directory);
      if (!directoryStat.isDirectory() || directoryStat.isSymbolicLink()) {
        throw new Error('invalid approval projection directory');
      }
    }
    const metadata = fs.lstatSync(approvalJson);
    if (!metadata.isFile() || metadata.isSymbolicLink() || metadata.size > 1024 * 1024) {
      throw new Error('invalid approval projection');
    }
    const document = await vscode.workspace.openTextDocument(vscode.Uri.file(approvalJson));
    await vscode.window.showTextDocument(document);
    if (!workspaceViewsUpdated) {
      const reason = refreshError
        ? ` Curator refresh failed: ${refreshError}`
        : ' The current projection or inbox could not be verified, or the review document has unsaved edits.';
      vscode.window.showWarningMessage(
        `Opened the current pending review document, but its local queue projection may still be stale.${reason}`,
      );
    }
  } catch (error) {
    vscode.window.showWarningMessage(
      `The pending review document is unavailable. Curator refresh ${workspaceViewsUpdated ? 'completed' : 'did not complete'}; refresh CuratorMD V2 and try again.${error instanceof Error ? ` ${error.message}` : ''}`,
    );
    return;
  }
}

function reviewDocumentActions(document) {
  const workspace = vscode.workspace?.workspaceFolders?.[0];
  if (!workspace || document.uri.fsPath !== path.join(
    workspace.uri.fsPath, '.curatormd-v2', 'sde-proposals', 'pending-review.md',
  )) return [];
  const lenses = [];
  for (let line = 0; line < document.lineCount; line += 1) {
    const match = /^<!-- curator-v2-actions: ([A-Za-z0-9_-]{1,128}) -->$/.exec(document.lineAt(line).text);
    if (!match) continue;
    const range = new vscode.Range(line, 0, line, 0);
    for (const [title, decision] of [
      ['Accept', 'approve'], ['Reject', 'reject'], ['Withdraw', 'withdraw'],
      ['Refresh evidence', 'refresh-evidence'],
    ]) {
      lenses.push(new vscode.CodeLens(range, {
        title, command: 'curatormdV2.reviewDocumentCandidate', arguments: [match[1], decision],
      }));
    }
  }
  return lenses;
}

async function launchDocumentReview(
  candidateId, decision, spawnProcess = spawn, refreshAfterReview = refreshReviewConsumers,
) {
  let receiptId = null;
  let reviewProjectRoot = null;
  let reviewProjectId = null;
  try {
    if (typeof candidateId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(candidateId)
      || (decision !== undefined
        && !['approve', 'reject', 'withdraw', 'refresh-evidence'].includes(decision))) {
      throw new Error('invalid review action');
    }
    const workspace = vscode.workspace?.workspaceFolders?.[0];
    if (!workspace) throw new Error('missing workspace');
    const projectRoot = workspace.uri.fsPath;
    reviewProjectRoot = projectRoot;
    reviewProjectId = readConfiguredProjectId(projectRoot);
    const documentPath = path.join(projectRoot, '.curatormd-v2', 'sde-proposals', 'pending-review.md');
    for (const directory of [path.dirname(path.dirname(documentPath)), path.dirname(documentPath)]) {
      const metadata = fs.lstatSync(directory);
      if (!metadata.isDirectory() || metadata.isSymbolicLink()) throw new Error('invalid review directory');
    }
    const documentStat = fs.lstatSync(documentPath);
    if (!documentStat.isFile() || documentStat.isSymbolicLink() || documentStat.size > 1024 * 1024) {
      throw new Error('invalid review document');
    }
    let openDocument = vscode.workspace?.textDocuments?.find((item) => item.uri?.fsPath === documentPath);
    if (!openDocument) {
      openDocument = await vscode.workspace.openTextDocument(vscode.Uri.file(documentPath));
    }
    await vscode.window.showTextDocument(openDocument, { preview: false });
    if (openDocument?.isDirty && !await openDocument.save()) {
      vscode.window.showWarningMessage('Save the review document before continuing.');
      return;
    }
    const diskContent = fs.readFileSync(documentPath, 'utf8');
    if (openDocument?.isDirty || (openDocument && openDocument.getText() !== diskContent)
      || !isUnmodifiedReviewDocument(diskContent)) {
      vscode.window.showWarningMessage('The review document is stale or its generated sections changed. Your changes have been preserved.');
      return;
    }
    if (!diskContent.includes(`<!-- curator-v2-decision:${candidateId}:start -->`)) throw new Error('draft missing');
    if (!diskContent.includes(`<!-- curator-v2-candidate: ${candidateId} -->`)) throw new Error('candidate missing');
    let selectedDecision = decision;
    if (!selectedDecision) {
      const choice = await vscode.window.showQuickPick([
        { label: '$(check) Accept', value: 'approve' },
        { label: '$(circle-slash) Reject', value: 'reject' },
        { label: '$(trash) Withdraw stale proposal', value: 'withdraw' },
        { label: '$(sync) Refresh stale evidence', value: 'refresh-evidence' },
      ], { title: 'Curator V2 SDE review', placeHolder: 'Choose a decision' });
      if (!choice) return;
      selectedDecision = choice.value;
    }

    const outline = await withReviewClient(projectRoot, async (client, projectId) => {
      const outline = JSON.parse(await client.callTool('sde_review_outline', {
        candidate_id: candidateId,
      }));
      if (outline.project_id !== projectId || outline.candidate_id !== candidateId
        || outline.status !== 'pending_review') {
        throw new Error('The candidate is no longer pending in this project. Refresh the review document.');
      }
      return outline;
    }, { spawnProcess });

    if (selectedDecision === 'refresh-evidence') {
      if (outline.goal_status !== 'complete'
        || !Number.isSafeInteger(outline.lifecycle_revision)) {
        throw new Error('The source task is no longer eligible for an evidence refresh. Refresh the review document.');
      }
      if (outline.evidence_status === 'current_passing') {
        vscode.window.showInformationMessage(
          'This proposal already has passing evidence recorded at completion; no evidence refresh is needed.',
        );
        return;
      }
      const reason = await vscode.window.showInputBox({
        title: 'Refresh stale SDE evidence',
        prompt: 'Why does the source task need a new evidence pass?',
        ignoreFocusOut: true,
        validateInput: (value) => value.trim().length > 0 && value.length <= 1000
          ? null : 'Enter 1–1000 non-blank characters.',
      });
      if (reason === undefined) return;
      const nextAction = await vscode.window.showInputBox({
        title: 'Next action for the reopened task',
        prompt: 'Describe the fresh checks needed before creating a new proposal.',
        ignoreFocusOut: true,
        validateInput: (value) => value.trim().length > 0
          && reason.trim().length + value.trim().length + 18 <= 1000
          ? null : 'Enter a non-blank next action that keeps the combined reopen text within 1,000 characters.',
      });
      if (nextAction === undefined) return;
      const confirmation = await vscode.window.showWarningMessage(
        `Reopen “${outline.problem}” and withdraw stale proposal ${candidateId}?`,
        {
          modal: true,
          detail: 'The source task becomes active. Existing facts and receipts remain, and earlier verification is kept as historical evidence. Record the new outcome and any available checks; no terminal is opened.',
        },
        'Reopen task and withdraw proposal',
        'Cancel',
      );
      if (confirmation !== 'Reopen task and withdraw proposal') return;

      let reopenedGoalId = null;
      try {
        await withReviewClient(projectRoot, async (client, projectId) => {
          const current = JSON.parse(await client.callTool('sde_review_outline', {
            candidate_id: candidateId,
          }));
          if (current.project_id !== projectId || current.candidate_id !== candidateId
            || current.status !== 'pending_review' || current.goal_id !== outline.goal_id
            || current.goal_status !== 'complete'
            || current.lifecycle_revision !== outline.lifecycle_revision) {
            throw new Error('The proposal or source task changed; refresh the review document and try again.');
          }
          const result = JSON.parse(await client.callTool('goal_reopen', {
            event_id: randomBytes(16).toString('hex'),
            goal_id: current.goal_id,
            reason: reason.trim(),
            next_action: nextAction.trim(),
            expected_lifecycle_revision: current.lifecycle_revision,
          }));
          if (result.project_id !== projectId || result.status !== 'processed') {
            throw new Error('Curator did not confirm reopening the source task.');
          }
          reopenedGoalId = current.goal_id;
        }, { allowWrite: true, spawnProcess });

        const withdrawal = await withReviewClient(projectRoot, async (client, projectId) => {
          const current = JSON.parse(await client.callTool('sde_review_outline', {
            candidate_id: candidateId,
          }));
          if (current.project_id !== projectId || current.candidate_id !== candidateId
            || current.status !== 'pending_review' || current.goal_id !== reopenedGoalId
            || current.goal_status !== 'active') {
            throw new Error('The task reopened, but the proposal changed; refresh the review document before clearing it.');
          }
          return JSON.parse(await client.callTool('sde_withdraw_candidates', {
            candidate_ids: [candidateId],
            rationale: reason.trim(),
          }));
        }, { allowWrite: true, spawnProcess });
        if (!Array.isArray(withdrawal) || withdrawal.length !== 1
          || withdrawal[0]?.candidate_id !== candidateId
          || typeof withdrawal[0]?.withdrawal_id !== 'string') {
          throw new Error('The task reopened, but Curator did not confirm withdrawal of the stale proposal.');
        }
      } catch (error) {
        if (reopenedGoalId) {
          vscode.window.showWarningMessage(
            `Source task ${reopenedGoalId} was reopened, but stale proposal ${candidateId} was not confirmed withdrawn. Its facts and receipts remain; refresh the review document and withdraw the proposal before assessing a new one.`,
          );
          return;
        }
        throw error;
      }
      vscode.window.showInformationMessage(
        `Source task reopened and stale proposal withdrawn. Record fresh evidence for every criterion, finish the task, then create a new SDE proposal. Existing facts and receipts remain.`,
      );
      void refreshStatusBarHealthFromWorkspace();
      return;
    }

    if (selectedDecision === 'withdraw') {
      const rationale = await vscode.window.showInputBox({
        title: 'Curator V2 withdrawal rationale',
        prompt: 'Explain why this pending proposal is being cleared for retest (1–1000 characters).',
        ignoreFocusOut: true,
        validateInput: (value) => value.trim().length > 0 && value.length <= 1000
          ? null : 'Enter 1–1000 non-blank characters.',
      });
      if (rationale === undefined) return;
      const confirmed = await vscode.window.showWarningMessage(
        `Withdraw SDE proposal ${candidateId} from the pending review queue?`,
        {
          modal: true,
          detail: 'This clears only the pending proposal. Its task facts and evidence remain unchanged, and Curator records an owner-attributed withdrawal receipt. This does not approve or reject the proposed knowledge.',
        },
        'Confirm withdrawal',
      );
      if (confirmed !== 'Confirm withdrawal') return;
      const result = await withReviewClient(projectRoot, async (client, projectId) => {
        if (outline.project_id !== projectId) throw new Error('Project binding changed; no withdrawal was recorded.');
        const current = JSON.parse(await client.callTool('sde_review_outline', {
          candidate_id: candidateId,
        }));
        if (current.project_id !== projectId || current.candidate_id !== candidateId
          || current.status !== 'pending_review') {
          throw new Error('The candidate changed after confirmation; refresh the review document.');
        }
        const receipts = JSON.parse(await client.callTool('sde_withdraw_candidates', {
          candidate_ids: [candidateId], rationale,
        }));
        if (!Array.isArray(receipts) || receipts.length !== 1
          || receipts[0]?.candidate_id !== candidateId
          || typeof receipts[0]?.withdrawal_id !== 'string'
          || !/^[0-9a-f]{64}$/.test(receipts[0]?.candidate_sha256 || '')) {
          throw new Error('Curator did not return a valid withdrawal receipt.');
        }
        return receipts[0];
      }, { allowWrite: true, spawnProcess });
      vscode.window.showInformationMessage(
        `SDE proposal withdrawn from the pending queue; source facts retained. Receipt ${result.withdrawal_id}.`,
      );
      return;
    }

    let draft = readEditableReviewDraft(diskContent, candidateId);
    if (!draft) throw new Error('The editable decision JSON is missing or invalid.');
    const initial = await withReviewClient(projectRoot, async (client, projectId) => {
      const packet = JSON.parse(await client.callTool('sde_review_packet', {
        candidate_id: candidateId,
      }));
      if (outline.project_id !== projectId || packet.detail?.candidate?.candidate_id !== candidateId
        || packet.detail?.candidate?.status !== 'pending_review') {
        throw new Error('The candidate is no longer pending in this project. Refresh the review document.');
      }
      return { outline, packet };
    }, { spawnProcess });

    if (selectedDecision === 'approve') {
      const configuredDocuments = Array.isArray(initial.outline.persistence_documents)
        ? [...new Set(initial.outline.persistence_documents.filter(
          (item) => typeof item === 'string' && item.length > 0,
        ))] : [];
      if (configuredDocuments.length === 0) {
        throw new Error('This project has no configured persistence documents for an approved entry.');
      }
      if (!Array.isArray(draft.documents)) {
        vscode.window.showWarningMessage('The editable decision must list persistence destinations as a JSON array.');
        return;
      }
      const selectedDocuments = Array.isArray(draft.documents) && draft.documents.length > 0
        ? draft.documents : configuredDocuments;
      if (selectedDocuments.some((item) => typeof item !== 'string'
        || !configuredDocuments.includes(item))
        || new Set(selectedDocuments).size !== selectedDocuments.length) {
        vscode.window.showWarningMessage(
          'The editable decision lists an unavailable persistence document. Update it from the configured destinations and try again.',
        );
        return;
      }
      draft = { ...draft, documents: selectedDocuments };
      if (!await writeEditableReviewDraft(openDocument, diskContent, candidateId, draft)) {
        vscode.window.showWarningMessage(
          'Could not save the default persistence destinations. Your review decision was not recorded.',
        );
        return;
      }
      if (draft.significance === 5) {
        const confirmation = await vscode.window.showWarningMessage(
          'Significance 5 is the highest rating. Confirm this rating before acceptance.',
          { modal: true },
          'Confirm significance 5',
        );
        if (confirmation !== 'Confirm significance 5') return;
      }
    }

    const rationale = selectedDecision === 'approve'
      ? `Owner approved the SDE entry for ${draft.documents.join(', ')}.`
      : 'Owner rejected the pending SDE proposal.';
    const evidenceOverrideReason = null;
    const reviewDecision = reviewDecisionValue(selectedDecision);
    const inventoryComplete = initial.packet.artifact_inventory?.usage?.inventory_complete === true
      && typeof initial.packet.artifact_inventory.manifest_sha256 === 'string';
    const selectedArtifacts = inventoryComplete ? artifactsForAutomaticCleanup(initial.packet) : [];
    const reviewed = await withReviewClient(projectRoot, async (client, projectId) => {
      const packet = JSON.parse(await client.callTool('sde_review_packet', {
        candidate_id: candidateId,
        ...(inventoryComplete ? { review_artifacts: selectedArtifacts } : {}),
      }));
      if (packet.detail?.candidate?.candidate_id !== candidateId
        || packet.detail?.candidate?.status !== 'pending_review'
        || packet.artifact_inventory?.manifest_sha256 !== initial.packet.artifact_inventory.manifest_sha256
        || (packet.artifact_inventory?.usage?.inventory_complete === true) !== inventoryComplete) {
        throw new Error('The review packet changed. Refresh it and start again; no decision was recorded.');
      }
      const reviewDraftJson = JSON.stringify(draft);
      const binding = JSON.parse(await client.callTool('sde_prepare_review_binding', {
        candidate_id: candidateId,
        decision: reviewDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: inventoryComplete,
        dependency_map_sha256: inventoryComplete ? packet.dependency_map_sha256 : '0'.repeat(64),
        rationale,
        review_draft_json: reviewDraftJson,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
        evidence_override_reason: evidenceOverrideReason,
      }));
      if (typeof binding.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(binding.sha256)) {
        throw new Error('Curator did not return a valid review binding.');
      }
      return { packet, binding, reviewDraftJson, projectId };
    }, { spawnProcess });
    if (!reviewDraftMatchesDocument(openDocument, documentPath, candidateId, draft)) {
      vscode.window.showWarningMessage('The editable decision changed during review. Refresh and review it again; no decision was recorded.');
      return;
    }

    const decisionLabel = selectedDecision === 'approve' ? 'Accept' : 'Reject';
    const destinationSummary = selectedDecision === 'approve'
      ? `\nDestinations: ${draft.documents.join(', ')}` : '';
    const confirmed = await vscode.window.showWarningMessage(
      `${decisionLabel} SDE ${candidateId}?`,
      {
        modal: true,
        detail: [
          `Significance: ${draft.significance}/5`,
          initial.outline.evidence_status !== 'current_passing'
            ? 'Automated evidence is missing or stale; review the recorded facts before deciding.' : '',
          inventoryComplete
            ? 'Approval records this SDE decision. Accepted facts are written to the selected documents and verified; eligible transient artifacts then clear automatically. Retention holds and changed files stay visible for follow-up.'
            : 'The inventory is incomplete. The decision will be saved; cleanup remains pending and no artifacts are authorized for deletion.',
          destinationSummary,
        ].filter(Boolean).join('\n'),
      },
      `Confirm ${decisionLabel.toLowerCase()}`,
    );
    if (confirmed !== `Confirm ${decisionLabel.toLowerCase()}`) return;
    if (!reviewDraftMatchesDocument(openDocument, documentPath, candidateId, draft)) {
      vscode.window.showWarningMessage('The editable decision changed after confirmation. Refresh and review it again; no decision was recorded.');
      return;
    }

    const result = await withReviewClient(projectRoot, async (client, projectId) => {
      if (projectId !== reviewed.projectId) throw new Error('Project binding changed; no decision was recorded.');
      const currentPacket = JSON.parse(await client.callTool('sde_review_packet', {
        candidate_id: candidateId,
        ...(inventoryComplete ? { review_artifacts: selectedArtifacts } : {}),
      }));
      if (currentPacket.artifact_inventory?.manifest_sha256
        !== reviewed.packet.artifact_inventory.manifest_sha256
        || (inventoryComplete && currentPacket.dependency_map_sha256 !== reviewed.packet.dependency_map_sha256)
        || (currentPacket.artifact_inventory?.usage?.inventory_complete === true) !== inventoryComplete
        || currentPacket.detail?.candidate?.status !== 'pending_review') {
        throw new Error('The review packet changed after confirmation. Refresh it and try again.');
      }
      const currentBinding = JSON.parse(await client.callTool('sde_prepare_review_binding', {
        candidate_id: candidateId,
        decision: reviewDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: inventoryComplete,
        dependency_map_sha256: inventoryComplete ? currentPacket.dependency_map_sha256 : '0'.repeat(64),
        rationale,
        review_draft_json: reviewed.reviewDraftJson,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
        evidence_override_reason: evidenceOverrideReason,
      }));
      if (currentBinding.sha256 !== reviewed.binding.sha256) {
        throw new Error('The review binding changed after confirmation. Refresh it and try again.');
      }
      const receipt = JSON.parse(await client.callTool('sde_confirm', {
        candidate_id: candidateId,
        decision: reviewDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: inventoryComplete,
        dependency_map_sha256: inventoryComplete ? currentPacket.dependency_map_sha256 : '0'.repeat(64),
        rationale,
        review_draft_json: reviewed.reviewDraftJson,
        expected_review_binding_sha256: currentBinding.sha256,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
        evidence_override_reason: evidenceOverrideReason,
      }));
      if (typeof receipt.receipt_id !== 'string' || !receipt.receipt_id) {
        throw new Error('Curator did not return a decision receipt.');
      }
      receiptId = receipt.receipt_id;
      if (selectedDecision === 'approve') {
        for (const target of draft.documents) {
          await client.callTool('sde_project_review_target', {
            receipt_id: receiptId, target, prepare_only: true,
          });
        }
        for (const target of draft.documents) {
          await client.callTool('sde_project_review_target', {
            receipt_id: receiptId, target, prepare_only: false,
          });
        }
        const projections = JSON.parse(await client.callTool(
          'sde_review_projection_status', { receipt_id: receiptId },
        ));
        if (!Array.isArray(projections) || projections.length !== draft.documents.length
          || projections.some((item) => !Array.isArray(item) || item[1] === null || item[2] === null)) {
          throw new Error('The decision receipt was saved, but one or more document writes remain pending.');
        }
      }
      const finalReceipt = JSON.parse(await client.callTool(
        'sde_finalize_review_projection', { receipt_id: receiptId },
      ));
      const purge = JSON.parse(await client.callTool('artifact_purge_status', {
        receipt_id: receiptId,
      }));
      const workspaceViewsUpdated = await refreshWorkspaceQueueViews(
        client, projectRoot, projectId,
      );
      return { receipt: finalReceipt, purge, workspaceViewsUpdated };
    }, { allowWrite: true, spawnProcess });

    const purgeReceipt = Array.isArray(result.purge)
      ? result.purge[0] : (result.purge?.receipt || result.purge);
    const purgeStatus = purgeReceipt?.purge_status || result.receipt?.purge_status;
    await refreshAfterReview(projectRoot);
    let workspaceViewStatus = workspaceQueueViewsConfirmResolved(
      projectRoot, outline.project_id, candidateId,
    );
    if (!workspaceViewStatus.allResolved) {
      try {
        workspaceViewStatus = await retryWorkspaceQueueViewsAfterDecision(
          projectRoot, outline.project_id, candidateId, spawnProcess, refreshAfterReview,
        );
      } catch (_error) {
        // Keep the first refresh result visible; a failed retry cannot undo the receipt.
      }
    }
    const followUp = [];
    if (purgeStatus !== 'complete') {
      followUp.push(`cleanup status is ${purgeStatus || 'unknown'}`);
    }
    if (!workspaceViewStatus.reviewDocumentResolved) {
      followUp.push('the local pending-review.md document is stale, edited, or could not be refreshed');
    }
    if (!workspaceViewStatus.reviewQueueResolved) {
      followUp.push('the local pending.json proposal queue could not be confirmed current');
    }
    if (!workspaceViewStatus.inboxFresh) {
      followUp.push('the local inbox/status.json count view could not be confirmed fresh');
    }
    if (followUp.length > 0) {
      vscode.window.showWarningMessage(
        `SDE ${selectedDecision === 'approve' ? 'acceptance' : 'rejection'} recorded as receipt ${receiptId}; ${followUp.join('; ')}.`,
      );
    } else {
      vscode.window.showInformationMessage(
        `SDE ${selectedDecision === 'approve' ? 'accepted' : 'rejected'} and receipt ${receiptId} finalized.`,
      );
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected review failure.';
    if (receiptId) {
      let viewsRecovered = false;
      if (reviewProjectRoot && reviewProjectId) {
        try {
          const status = await retryWorkspaceQueueViewsAfterDecision(
            reviewProjectRoot, reviewProjectId, candidateId, spawnProcess, refreshAfterReview,
          );
          viewsRecovered = status.allResolved;
        } catch (_refreshError) {
          // Leave the durable receipt and local projections available for manual recovery.
        }
      }
      const recovery = viewsRecovered
        ? ' Local inbox and review views were refreshed and confirmed.'
        : ' Local inbox or review views still need attention; save any edits to pending-review.md, then use Recovery Manager > Rebuild local inbox and review views.';
      vscode.window.showWarningMessage(
        `Decision receipt ${receiptId} exists, but review finalization needs attention: ${message}.${recovery}`,
      );
    } else {
      vscode.window.showErrorMessage(`Curator V2 review was not recorded: ${message}`);
    }
  }
}

async function withReviewClient(
  projectRoot, operation, { allowWrite = false, spawnProcess = spawn } = {},
) {
  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  if (hasWorkspaceSettingOverride(configuration, [
    'databasePath', 'profileId', 'serverCommand', 'databaseBindings',
    'evidenceConfig', 'evidenceConfigBindings',
  ])) throw new Error('Set Curator project bindings in User settings, not workspace settings.');
  const projectId = readConfiguredProjectId(projectRoot);
  const database = resolveDatabasePath(
    projectId, configuration.get('databaseBindings', {}), configuration.get('databasePath', ''),
  );
  const evidence = resolveEvidenceConfig(
    projectId, configuration.get('evidenceConfigBindings', {}), configuration.get('evidenceConfig', ''),
  );
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  if (!database || evidence === null || typeof profileId !== 'string' || !profileId.trim()
    || typeof serverCommand !== 'string' || !serverCommand.trim()) {
    throw new Error('Curator project, database, evidence, or profile binding is unavailable.');
  }
  const args = [
    '--project-root', projectRoot,
    '--database', database,
    '--profile-id', profileId,
    ...hostEvidenceConfigArguments(evidence),
    '--allow-review',
  ];
  if (allowWrite) args.push('--allow-write');
  const client = new McpStdioClient(serverCommand, args, projectRoot, profileId, spawnProcess);
  try {
    await client.initialize();
    const page = JSON.parse(await client.callTool('goal_list_page', { offset: 0, limit: 1 }));
    if (page.project_id !== projectId) throw new Error('Curator returned a different project binding.');
    return await operation(client, projectId);
  } finally {
    client.close();
  }
}

function readEditableReviewDraft(content, candidateId) {
  const parts = reviewDraftParts(content);
  if (!parts) return null;
  const block = parts.drafts.get(candidateId);
  if (typeof block !== 'string') return null;
  const match = /^\s*(`{3,})json\s*\n([\s\S]*?)\n\1\s*$/.exec(block);
  if (!match) return null;
  try {
    const draft = JSON.parse(match[2]);
    return draft && typeof draft === 'object' && !Array.isArray(draft) ? draft : null;
  } catch (_) {
    return null;
  }
}

async function writeEditableReviewDraft(document, content, candidateId, draft) {
  if (document.isDirty || document.getText() !== content) return false;
  const startMarker = `<!-- curator-v2-decision:${candidateId}:start -->`;
  const endMarker = `<!-- curator-v2-decision:${candidateId}:end -->`;
  const startIndex = content.indexOf(startMarker);
  const endIndex = content.indexOf(endMarker, startIndex + startMarker.length);
  if (startIndex < 0 || endIndex < 0 || content.indexOf(startMarker, startIndex + 1) >= 0
    || content.indexOf(endMarker, endIndex + 1) >= 0) return false;
  const replaceStart = startIndex + startMarker.length;
  const replacement = `\n\`\`\`json\n${JSON.stringify(draft, null, 2)}\n\`\`\`\n`;
  const range = new vscode.Range(document.positionAt(replaceStart), document.positionAt(endIndex));
  const edit = new vscode.WorkspaceEdit();
  edit.replace(document.uri, range, replacement);
  if (!await vscode.workspace.applyEdit(edit)) return false;
  return document.save();
}

function reviewDraftMatchesDocument(document, documentPath, candidateId, draft) {
  try {
    if (document.isDirty) return false;
    const diskContent = fs.readFileSync(documentPath, 'utf8');
    if (document.getText() !== diskContent || !isUnmodifiedReviewDocument(diskContent)) return false;
    const currentDraft = readEditableReviewDraft(diskContent, candidateId);
    return JSON.stringify(currentDraft) === JSON.stringify(draft);
  } catch (_) {
    return false;
  }
}

function artifactsForAutomaticCleanup(packet) {
  const inventory = packet.artifact_inventory;
  if (!inventory?.usage?.inventory_complete || !Array.isArray(inventory.artifacts)) {
    throw new Error('The artifact inventory is incomplete.');
  }
  return inventory.artifacts.map((artifact) => {
    const dependency = (packet.artifact_dependencies || []).find(
      (item) => item.artifact?.path === artifact.path,
    );
    const action = artifact.retention_hold
      ? 'retain_under_hold'
      : (dependency?.evidence_dependencies || []).some((item) => item.criterion_status === 'open')
        ? 'reacquire_from_source' : 'not_required';
    return {
      path: artifact.path,
      sha256: artifact.sha256,
      ...(artifact.device_id === null || artifact.device_id === undefined ? {} : { device_id: artifact.device_id }),
      ...(artifact.inode_id === null || artifact.inode_id === undefined ? {} : { inode_id: artifact.inode_id }),
      ...(artifact.occurrence_id ? { occurrence_id: artifact.occurrence_id } : {}),
      ...(artifact.retention_hold ? { retention_hold: artifact.retention_hold } : {}),
      reacquisition_action: action,
    };
  });
}

function reviewDecisionValue(action) {
  if (action === 'approve') return 'approved';
  if (action === 'reject') return 'rejected';
  throw new Error('unsupported SDE review decision');
}

function resetStatusBarHealth() {
  if (!dashboardStatusItem) return;
  dashboardStatusItem.text = '$(circle-filled) CuratorMD V2';
  dashboardStatusItem.color = STATUS_COLORS.neutral;
  dashboardStatusItem.tooltip = statusTooltip(
    `${statusColorMeaning('neutral')} Click to open the project dashboard.`,
  );
}

async function refreshStatusBarHealthFromWorkspace(spawnProcess = spawn, trigger = 'automatic') {
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
  try {
    initializeWorkspaceAreas(projectRoot);
  } catch (_error) {
    updateStatusBarHealth(null, null, null, null, curatorError(
      'status-workspace-unavailable', 'Curator workspace areas are unavailable.',
    ));
    return 'unknown';
  }

  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  if (hasWorkspaceSettingOverride(configuration,
    ['databasePath', 'profileId', 'serverCommand', 'hermesCommand',
      'databaseBindings', 'hermesProfileBindings', 'evidenceConfig',
      'evidenceConfigBindings'])) {
    resetStatusBarHealth();
    return 'neutral';
  }
  let configuredProjectId;
  try {
    configuredProjectId = readConfiguredProjectId(projectRoot);
  } catch (error) {
    updateStatusBarHealth(null, null, null, null, error);
    return 'unknown';
  }
  const databasePath = resolveDatabasePath(
    configuredProjectId,
    configuration.get('databaseBindings', {}),
    configuration.get('databasePath', ''),
  );
  const profileId = configuration.get('profileId', '');
  const hermesProfileBindings = configuration.get('hermesProfileBindings', {});
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  const hermesCommand = configuration.get('hermesCommand', 'hermes');
  const evidenceConfig = resolveEvidenceConfig(
    configuredProjectId,
    configuration.get('evidenceConfigBindings', {}),
    configuration.get('evidenceConfig', ''),
  );
  if (!databasePath) {
    updateStatusBarHealth(null, null, null, null, curatorError(
      'status-database-binding-invalid', 'No valid absolute database path is configured.',
    ));
    return 'unknown';
  }
  if (evidenceConfig === null) {
    updateStatusBarHealth(null, null, null, null, curatorError(
      'status-evidence-binding-invalid', 'No valid host evidence config is mapped.',
    ));
    return 'unknown';
  }
  if (!profileId || !serverCommand || !hermesCommand) {
    resetStatusBarHealth();
    return 'neutral';
  }

  const client = new McpStdioClient(serverCommand, [
    '--project-root', projectRoot,
    '--database', databasePath,
    '--profile-id', profileId,
    ...hostEvidenceConfigArguments(evidenceConfig),
  ], projectRoot, profileId, spawnProcess);
  try {
    await client.initialize();
    const page = JSON.parse(await client.callTool('goal_list_page', { offset: 0, limit: 1 }));
    if (!page || typeof page.project_id !== 'string' || !page.project_id) {
      throw curatorError('status-project-invalid', 'Curator returned no project binding.');
    }
    if (page.project_id !== configuredProjectId) {
      throw curatorError('status-project-mismatch', 'Curator returned another project.');
    }
    const [reviewWire, feeds, storage, inboxWire] = await Promise.all([
      client.callTool('sde_review_queue_cards', { limit: REVIEW_QUEUE_SIZE })
        .then((wire) => JSON.parse(wire)),
      readProjectFeeds({
        client, projectRoot, databasePath, profileId, serverCommand,
        hermesCommand, evidenceConfig, projectId: page.project_id,
        hermesProfileId: resolveHermesProfileId(page.project_id, hermesProfileBindings),
        spawnProcess, trigger,
      }),
      client.callTool('project_storage_usage', {})
        .then((wire) => JSON.parse(wire))
        .catch(() => null),
      client.callTool('event_queue_status', {})
        .then((wire) => JSON.parse(wire))
        .catch(() => null),
    ]);
    const reviews = validateReviewQueue(reviewWire, page.project_id);
    if (generation !== statusRefreshGeneration
      || vscode.workspace?.workspaceFolders?.[0]?.uri?.fsPath !== projectRoot) {
      return 'unknown';
    }
    const displayHealth = updateStatusBarHealth(feeds.health, page.project_id, reviews, storage,
      feeds.healthProbeError ? { code: feeds.healthProbeError } : null);
    const { outlines, resolvedCandidateIds } = await readReviewOutlines(
      client, reviewWire, page.project_id, projectRoot,
    );
    if (generation !== statusRefreshGeneration
      || vscode.workspace?.workspaceFolders?.[0]?.uri?.fsPath !== projectRoot) return 'unknown';
    tryWriteWorkspaceQueueViews(
      projectRoot, page.project_id, inboxWire, reviewWire, outlines, resolvedCandidateIds,
    );
    await refreshOpenPendingReviewDocumentSafely(projectRoot);
    if (reviews === null) return 'unknown';
    if (!feeds.health) return 'unknown';
    if (displayHealth !== 'healthy') return displayHealth;
    return reviews.length > 0 ? 'review' : 'healthy';
  } catch (error) {
    if (generation === statusRefreshGeneration
      && vscode.workspace?.workspaceFolders?.[0]?.uri?.fsPath === projectRoot) {
      updateStatusBarHealth(null, null, null, null, error);
    }
    void notifyTransportClosed(error);
    return 'unknown';
  } finally {
    client.close();
  }
}

async function showDashboard(
  spawnProcess = spawn,
  { focusReviews = false, focusRecovery = false } = {},
) {
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
  if (fs.existsSync(workspace.uri.fsPath) && fs.existsSync(projectConfigPath)) {
    initializeWorkspaceAreas(workspace.uri.fsPath);
  }
  let configuredProjectId = null;
  if (fs.existsSync(projectConfigPath)) {
    try {
      configuredProjectId = readConfiguredProjectId(workspace.uri.fsPath);
    } catch (error) {
      resetStatusBarHealth();
      vscode.window.showErrorMessage(statusReadFailure(error));
      return;
    }
  }
  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  const workspaceOverride = hasWorkspaceSettingOverride(
    configuration,
    ['databasePath', 'profileId', 'serverCommand', 'hermesCommand',
      'databaseBindings', 'hermesProfileBindings', 'evidenceConfig',
      'evidenceConfigBindings'],
  );
  let databasePath = resolveDatabasePath(
    configuredProjectId,
    configuration.get('databaseBindings', {}),
    configuration.get('databasePath', ''),
  );
  if (!configuredProjectId && !databasePath) {
    const fallbackPath = configuration.get('databasePath', '');
    databasePath = typeof fallbackPath === 'string' && path.isAbsolute(fallbackPath)
      ? fallbackPath : null;
  }
  let profileId = configuration.get('profileId', '');
  let serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  let routerCommand = defaultRouterCommand(serverCommand);
  let evidenceConfig = resolveEvidenceConfig(
    configuredProjectId,
    configuration.get('evidenceConfigBindings', {}),
    configuration.get('evidenceConfig', ''),
  );
  let hermesCommand = configuration.get('hermesCommand', 'hermes');
  let hermesProfileBindings = configuration.get('hermesProfileBindings', {});
  if (workspaceOverride) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(
      'Curator launcher, database, profile, review CLI, and evidence config settings must be set in User settings, not the project.',
    );
    return;
  }
  if (!databasePath || !profileId || !serverCommand || !hermesCommand) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(
      'Set an absolute CuratorMD V2 database path and profileId in VS Code User settings; use databaseBindings for separate project databases.',
    );
    return;
  }
  if (evidenceConfig === null) {
    resetStatusBarHealth();
    vscode.window.showErrorMessage(STATUS_READ_FAILURES['status-evidence-binding-invalid']);
    return;
  }

  const panel = vscode.window.createWebviewPanel(
    'curatormdV2Dashboard',
    'CuratorMD V2',
    focusReviews || focusRecovery ? vscode.ViewColumn.Beside : vscode.ViewColumn.One,
    { enableScripts: true, localResourceRoots: [] },
  );
  panel.webview.html = dashboardHtml(panel.webview, focusReviews, focusRecovery);
  let panelDisposed = false;
  let goalIds = new Set();
  let candidateIds = new Set();
  let projectId = null;
  const reportRevisions = new Map();
  const reportFacts = new Map();
  const reportPages = new Map();
  const goalCards = new Map();
  let requestInProgress = false;
  let routerPassInProgress = false;
  let goalLoadInFlight = null;
  const schedulePanelReload = () => {
    const reload = () => panel.webview.postMessage({ type: 'reloadGoals' });
    return goalLoadInFlight ? goalLoadInFlight.then(reload, reload) : reload();
  };
  registerDashboardReloader(workspace.uri.fsPath, schedulePanelReload, panel);
  const settingsChangeListener = vscode.workspace
    && typeof vscode.workspace.onDidChangeConfiguration === 'function'
    ? vscode.workspace.onDidChangeConfiguration((event) => {
      if (!event || typeof event.affectsConfiguration !== 'function'
        || !event.affectsConfiguration('curatormdV2')) return;
      clearFeedFailureStates();
      const current = vscode.workspace.getConfiguration('curatormdV2');
      if (hasWorkspaceSettingOverride(current, [
        'databasePath', 'profileId', 'serverCommand', 'hermesCommand',
        'databaseBindings', 'hermesProfileBindings', 'evidenceConfig',
        'evidenceConfigBindings',
      ])) {
        panel.webview.postMessage({
          type: 'error',
          message: 'Curator connection settings must be set in User settings, not the project.',
        });
        return;
      }
      databasePath = resolveDatabasePath(
        configuredProjectId,
        current.get('databaseBindings', {}),
        current.get('databasePath', ''),
      );
      if (!configuredProjectId && !databasePath) {
        const fallbackPath = current.get('databasePath', '');
        databasePath = typeof fallbackPath === 'string' && path.isAbsolute(fallbackPath)
          ? fallbackPath : null;
      }
      profileId = current.get('profileId', '');
      serverCommand = current.get('serverCommand', 'curatormd-v2-mcp');
      routerCommand = defaultRouterCommand(serverCommand);
      evidenceConfig = resolveEvidenceConfig(
        configuredProjectId,
        current.get('evidenceConfigBindings', {}),
        current.get('evidenceConfig', ''),
      );
      hermesCommand = current.get('hermesCommand', 'hermes');
      hermesProfileBindings = current.get('hermesProfileBindings', {});
      if (!databasePath || !profileId || !serverCommand || !hermesCommand) {
        panel.webview.postMessage({
          type: 'error',
          message: 'Set an absolute CuratorMD V2 database path and profileId in User settings; use databaseBindings for separate project databases.',
        });
        return;
      }
      if (evidenceConfig === null) {
        panel.webview.postMessage({
          type: 'error',
          message: STATUS_READ_FAILURES['status-evidence-binding-invalid'],
        });
        return;
      }
      schedulePanelReload();
    }) : null;

  const withClient = async (operation, {
    allowWrite = false,
    allowEventRetry = false,
    allowRetentionHoldRelease = false,
    allowPurgeRetry = false,
  } = {}) => {
    if (requestInProgress) throw new Error('A Curator read is already in progress.');
    requestInProgress = true;
    updateStatusBarHealth(null, null);
    const args = [
      '--project-root', workspace.uri.fsPath,
      '--database', databasePath,
      '--profile-id', profileId,
      ...hostEvidenceConfigArguments(evidenceConfig),
    ];
    if (allowWrite) args.push('--allow-write');
    if (allowEventRetry) args.push('--allow-event-retry');
    if (allowRetentionHoldRelease) args.push('--allow-retention-hold-release');
    if (allowPurgeRetry) args.push('--allow-purge-retry');
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

  const readTerminalEventInventory = async (client, afterEventId = null) => {
    const args = { limit: 50 };
    if (afterEventId) args.after_event_id = afterEventId;
    return parseTerminalEventInventory(
      await client.callTool('event_terminal_inventory', args), projectId,
    );
  };
  const readEventArchiveProposal = async (client, offset = 0) => {
    const limit = 50;
    const wire = await client.callTool('event_receipt_compaction_propose', { offset, limit });
    return parseEventCompactionProposal(wire, projectId, offset, limit);
  };

  panel.webview.onDidReceiveMessage(async (message) => {
    try {
      if (!message || typeof message.type !== 'string') return;
      if (message.type === 'openPendingReview') {
        await openPendingReviewDocument(spawnProcess);
      } else if (message.type === 'refreshQueueViews') {
        if (typeof projectId !== 'string') {
          panel.webview.postMessage({
            type: 'queueViewsRefreshResult',
            status: {
              reviewQueueUpdated: false,
              reviewDocumentUpdated: false,
              inboxUpdated: false,
              reviewEditorOpen: false,
              reviewBufferUpdated: false,
            },
          });
          return;
        }
        const status = await withClient((client) => refreshWorkspaceQueueViews(
          client, workspace.uri.fsPath, projectId,
        ));
        panel.webview.postMessage({ type: 'queueViewsRefreshResult', status });
      } else if (message.type === 'resetHealthHistory') {
        if (typeof projectId !== 'string') {
          panel.webview.postMessage({
            type: 'healthHistoryResetSkipped',
            reason: 'Project binding is unavailable; saved samples were kept.',
          });
          return;
        }
        const historyProfileId = resolveHermesProfileId(projectId, hermesProfileBindings);
        if (!historyProfileId) {
          panel.webview.postMessage({
            type: 'healthHistoryResetSkipped',
            reason: 'Hermes profile mapping is unavailable; saved samples were kept.',
          });
          return;
        }
        const confirmation = await vscode.window.showWarningMessage(
          `Reset saved health graph history for project ${projectId}?`,
          {
            modal: true,
            detail: `This clears only the saved chart samples for Hermes profile ${historyProfileId}. Curator goals, events, receipts, evidence, and persistence documents remain unchanged. A fresh health read will follow.`,
          },
          'Reset graph history',
          'Cancel',
        );
        if (confirmation !== 'Reset graph history') {
          panel.webview.postMessage({ type: 'healthHistoryReset', success: false, cancelled: true });
          return;
        }
        const cleared = await resetPersistentHealthHistory(
          healthHistoryStore, projectId, historyProfileId,
        );
        panel.webview.postMessage({ type: 'healthHistoryReset', success: cleared });
      } else if (message.type === 'runEventRouter' && typeof projectId === 'string') {
        if (routerPassInProgress) {
          panel.webview.postMessage({
            type: 'eventRouterResult', success: false, ran: false,
            summary: 'An event-routing pass is already running for this project.',
          });
          return;
        }
        routerPassInProgress = true;
        try {
          const queue = await withClient(async (client) => JSON.parse(
            await client.callTool('event_queue_status', {}),
          ));
          const queueFields = [
            'received_count', 'failed_count', 'quarantined_count',
            'claimed_count', 'expired_claim_count',
          ];
          if (!queue || typeof queue !== 'object' || Array.isArray(queue)
            || queueFields.some((field) => !Number.isSafeInteger(queue[field]) || queue[field] < 0)) {
            throw curatorError('invalid-response', 'Curator returned invalid event queue counts.');
          }
          const eligibleCount = queue.received_count + queue.failed_count;
          if (eligibleCount === 0) {
            panel.webview.postMessage({
              type: 'eventRouterResult', success: true, ran: false,
              summary: `No received or failed events are queued. ${queue.quarantined_count} quarantined event(s) remain separate.`,
            });
            return;
          }
          const confirmation = await vscode.window.showWarningMessage(
            `Run one event-routing pass for project ${projectId}?`,
            {
              modal: true,
              detail: `Current queue: ${queue.received_count} received, ${queue.failed_count} failed, ${queue.quarantined_count} quarantined, ${queue.claimed_count} claimed, ${queue.expired_claim_count} expired claims. The pass processes at most 100 eligible received or failed events for this repository and database. It may apply their recorded goal and fact updates. Quarantined events are not included.`,
            },
            'Run one project pass',
            'Cancel',
          );
          if (confirmation !== 'Run one project pass') {
            panel.webview.postMessage({
              type: 'eventRouterResult', success: false, ran: false,
              summary: 'Event-routing pass cancelled; no action was taken.',
            });
            return;
          }
          const result = await runEventRouterPass(
            routerCommand, workspace.uri.fsPath, databasePath, spawnProcess, 100,
          );
          const summary = `Router pass attempted ${result.attempted}, processed ${result.processed}, failed ${result.failed}; ${result.pending} received/failed, ${result.quarantined} quarantined, ${result.claimed} claimed, ${result.expiredClaims} expired claims remain.`
            + (result.claimLost ? ` ${result.claimLost} claim(s) were lost during processing.` : '')
            + (result.exitCode === 1 ? ' Queue work remains; health stays gated.' : '');
          panel.webview.postMessage({
            type: 'eventRouterResult', success: true, ran: true, summary,
          });
          await reloadOpenDashboards(workspace.uri.fsPath);
          await refreshStatusBarHealthFromWorkspace();
        } catch (error) {
          panel.webview.postMessage({
            type: 'eventRouterResult', success: false, ran: false,
            summary: dashboardErrorMessage(error),
          });
        } finally {
          routerPassInProgress = false;
        }
      } else if (message.type === 'inspectEventArchive' && typeof projectId === 'string') {
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        panel.webview.postMessage({ type: 'eventArchiveLoading' });
        try {
          const proposal = await withClient((client) => readEventArchiveProposal(client, offset));
          panel.webview.postMessage({ type: 'eventArchiveProposal', proposal });
        } catch (error) {
          panel.webview.postMessage({
            type: 'eventArchiveError', message: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'archiveEventReceiptPage' && typeof projectId === 'string') {
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : -1;
        const inventorySha256 = typeof message.manifestSha256 === 'string'
          ? message.manifestSha256 : '';
        const requestedIds = Array.isArray(message.eventIds) ? message.eventIds : [];
        if (offset < 0 || !/^[a-f0-9]{64}$/.test(inventorySha256)
          || requestedIds.length < 1 || requestedIds.length > 50
          || requestedIds.some((id) => typeof id !== 'string'
            || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(id))) {
          panel.webview.postMessage({
            type: 'eventArchiveResult', success: false,
            summary: 'The archive proposal is invalid; no receipts were archived.',
          });
          return;
        }
        try {
          const proposal = await withClient((client) => readEventArchiveProposal(client, offset));
          const proposalIds = proposal.items.map((item) => item.eventId);
          if (proposal.manifestSha256 !== inventorySha256
            || JSON.stringify(proposalIds) !== JSON.stringify(requestedIds)
            || proposalIds.length === 0) {
            throw curatorError(
              'event-archive-stale',
              'The eligible receipt inventory changed; review a fresh proposal before archiving.',
            );
          }
          const rationale = await vscode.window.showInputBox({
            title: 'Reason for archiving processed event receipts',
            prompt: 'Record why this exact processed receipt page can leave the active inbox.',
            ignoreFocusOut: true,
            validateInput: (value) => typeof value === 'string'
              && value.trim().length > 0 && value.trim().length <= 1000
              && !/[\r\n]/.test(value)
              ? undefined : 'Enter a single-line rationale of at most 1,000 characters.',
          });
          if (!rationale || !rationale.trim()) {
            panel.webview.postMessage({
              type: 'eventArchiveResult', success: false,
              summary: 'Receipt archival cancelled; no action was taken.',
            });
            return;
          }
          const confirmation = await vscode.window.showWarningMessage(
            `Archive ${proposalIds.length} processed event receipt(s) from project ${projectId}?`,
            {
              modal: true,
              detail: `Inventory SHA-256: ${proposal.manifestSha256}\nOffset: ${proposal.offset}\nEvent IDs: ${proposalIds.join(', ')}\nThese processed receipts are payload-free and remain available for replay checks. Failed, quarantined, active, and unknown events are not eligible.\nRationale: ${rationale.trim()}`,
            },
            'Archive this receipt page',
            'Cancel',
          );
          if (confirmation !== 'Archive this receipt page') {
            panel.webview.postMessage({
              type: 'eventArchiveResult', success: false,
              summary: 'Receipt archival cancelled; no action was taken.',
            });
            return;
          }
          const archiveId = `event-archive-${randomBytes(16).toString('hex')}`;
          const receipt = await withClient(async (client) => {
            const current = await readEventArchiveProposal(client, offset);
            if (current.manifestSha256 !== proposal.manifestSha256
              || JSON.stringify(current.items.map((item) => item.eventId))
                !== JSON.stringify(proposalIds)) {
              throw curatorError(
                'event-archive-stale',
                'The eligible receipt inventory changed during confirmation; nothing was archived.',
              );
            }
            return JSON.parse(await client.callTool('event_receipt_compaction_archive', {
              archive_id: archiveId,
              event_ids: proposalIds,
              inventory_sha256: proposal.manifestSha256,
              offset,
              approval_reason: rationale.trim(),
            }));
          }, { allowWrite: true });
          if (!receipt || receipt.archive_id !== archiveId
            || receipt.project_id !== projectId
            || receipt.inventory_sha256 !== proposal.manifestSha256
            || receipt.offset !== offset
            || JSON.stringify(receipt.event_ids) !== JSON.stringify(proposalIds)) {
            throw curatorError('invalid-response', 'Curator did not confirm the exact receipt archive.');
          }
          let summary = `Archive receipt ${archiveId} recorded for ${proposalIds.length} processed event receipt(s).`;
          try {
            const updated = await withClient((client) => readEventArchiveProposal(client, offset));
            panel.webview.postMessage({ type: 'eventArchiveProposal', proposal: updated });
          } catch (refreshError) {
            summary += ` The archive succeeded, but the updated proposal could not be read: ${dashboardErrorMessage(refreshError)}`;
          }
          panel.webview.postMessage({ type: 'eventArchiveResult', success: true, summary });
          await reloadOpenDashboards(workspace.uri.fsPath);
        } catch (error) {
          panel.webview.postMessage({
            type: 'eventArchiveResult', success: false,
            summary: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'inspectProjectReconciliation'
        && typeof projectId === 'string') {
        const target = validateReconciliationTarget(message.target);
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : -1;
        const limit = 50;
        if (!target || offset < 0) {
          panel.webview.postMessage({
            type: 'projectReconciliationError',
            message: 'Enter a configured relative Markdown target and a valid page offset.',
          });
          return;
        }
        panel.webview.postMessage({ type: 'projectReconciliationLoading', target, offset });
        try {
          const reconciliation = await withClient(async (client) =>
            parseProjectReconciliation(
              await client.callTool('project_reconcile', { target, offset, limit }),
              projectId, offset, limit,
            ));
          panel.webview.postMessage({
            type: 'projectReconciliationResult', target, reconciliation,
          });
        } catch (error) {
          panel.webview.postMessage({
            type: 'projectReconciliationError',
            message: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'restoreMissingProjection'
        && typeof projectId === 'string') {
        const target = validateReconciliationTarget(message.target);
        const goalId = typeof message.goalId === 'string' ? message.goalId : '';
        const refreshOffset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        const expectedSha256 = typeof message.expectedSha256 === 'string'
          ? message.expectedSha256 : '';
        if (!target || !/^[A-Za-z0-9_-]{1,128}$/.test(goalId)
          || !/^[a-f0-9]{64}$/.test(expectedSha256)) {
          panel.webview.postMessage({
            type: 'projectionRepairResult', success: false,
            summary: 'The missing projection request is invalid; no write was attempted.',
          });
          return;
        }
        try {
          const preflight = await withClient(async (client) => parseGoalReconciliation(
            await client.callTool('goal_reconcile', { goal_id: goalId, target }),
            projectId, goalId,
          ));
          if (preflight.status !== 'missing'
            || preflight.expectedSha256 !== expectedSha256) {
            panel.webview.postMessage({
              type: 'projectionRepairResult', success: false,
              summary: 'The projection changed or is no longer missing. Inspect the current reconciliation page; no write was attempted.',
            });
            return;
          }
          const confirmation = await vscode.window.showWarningMessage(
            `Restore the missing goal block for ${goalId}?`,
            {
              modal: true,
              detail: `Project: ${projectId}\nConfigured target: ${target}\nGoal: ${goalId}\nExpected block SHA-256: ${expectedSha256}\nThe backend will recheck that this exact managed block is still missing, then write it from the current SQLite goal and evidence. This does not reset SQLite or overwrite a divergent block. An already-approved cleanup receipt may resume only after its existing gates pass.`,
            },
            'Restore this missing block',
            'Cancel',
          );
          if (confirmation !== 'Restore this missing block') {
            panel.webview.postMessage({
              type: 'projectionRepairResult', success: false,
              summary: 'Projection restoration cancelled; no write was made.',
            });
            return;
          }
          const reconciliation = await withClient(async (client) => {
            const current = parseGoalReconciliation(
              await client.callTool('goal_reconcile', { goal_id: goalId, target }),
              projectId, goalId,
            );
            if (current.status !== 'missing'
              || current.expectedSha256 !== expectedSha256) {
              throw curatorError(
                'projection-stale',
                'The goal projection changed during confirmation; no write was attempted.',
              );
            }
            const projection = JSON.parse(await client.callTool('goal_persist', {
              goal_id: goalId, target,
            }));
            if (!projection || projection.project_id !== projectId
              || projection.goal_id !== goalId
              || typeof projection.sha256 !== 'string'
              || !/^[a-f0-9]{64}$/.test(projection.sha256)) {
              throw curatorError('invalid-response', 'Curator did not confirm the goal projection write.');
            }
            const after = parseGoalReconciliation(
              await client.callTool('goal_reconcile', { goal_id: goalId, target }),
              projectId, goalId,
            );
            if (after.status !== 'synced'
              || after.actualSha256 !== after.expectedSha256) {
              throw curatorError(
                'projection-unverified',
                'The projection write returned, but read-back did not confirm a synced block.',
              );
            }
            return parseProjectReconciliation(
              await client.callTool('project_reconcile', { target, offset: refreshOffset, limit: 50 }),
              projectId, refreshOffset, 50,
            );
          }, { allowWrite: true });
          panel.webview.postMessage({
            type: 'projectReconciliationResult', target, reconciliation,
          });
          panel.webview.postMessage({
            type: 'projectionRepairResult', success: true,
            summary: `Goal ${goalId} was written and read-back verified as synced in ${target}.`,
          });
          await reloadOpenDashboards(workspace.uri.fsPath);
        } catch (error) {
          panel.webview.postMessage({
            type: 'projectionRepairResult', success: false,
            summary: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'inspectTerminalEvents' && typeof projectId === 'string') {
        const afterEventId = typeof message.afterEventId === 'string'
          && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(message.afterEventId)
          ? message.afterEventId : null;
        panel.webview.postMessage({ type: 'terminalEventLoading' });
        try {
          const inventory = await withClient(
            (client) => readTerminalEventInventory(client, afterEventId),
          );
          panel.webview.postMessage({ type: 'terminalEventInventory', inventory, afterEventId });
        } catch (error) {
          panel.webview.postMessage({
            type: 'terminalEventError', message: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'retryQuarantinedEvent' && typeof projectId === 'string') {
        const eventId = typeof message.eventId === 'string' ? message.eventId : '';
        const afterEventId = typeof message.afterEventId === 'string'
          && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(message.afterEventId)
          ? message.afterEventId : null;
        if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(eventId)) {
          panel.webview.postMessage({
            type: 'terminalEventRetryResult', success: false,
            summary: 'The event identifier is invalid; no retry was attempted.',
          });
          return;
        }
        try {
          const preflight = await withClient(async (client) => {
            const inventory = await readTerminalEventInventory(client, afterEventId);
            return inventory.events.find((item) => item.eventId === eventId) || null;
          });
          if (!preflight || preflight.status !== 'quarantined'
            || preflight.payloadSha256 !== message.payloadSha256) {
            panel.webview.postMessage({
              type: 'terminalEventRetryResult', success: false,
              summary: 'The event is no longer the same quarantined candidate. Refresh the inventory; no retry was attempted.',
            });
            return;
          }
          const confirmation = await vscode.window.showWarningMessage(
            `Retry quarantined event ${eventId}?`,
            {
              modal: true,
              detail: `Project: ${projectId}\nEvent: ${eventId}\nSource: ${preflight.sourceId}\nSource sequence: ${preflight.sourceSequence ?? 'unknown'}\nPayload SHA-256: ${preflight.payloadSha256}\nThis requeues only this exact quarantined event for automatic processing.`,
            },
            'Retry this event',
            'Cancel',
          );
          if (confirmation !== 'Retry this event') {
            panel.webview.postMessage({
              type: 'terminalEventRetryResult', success: false,
              summary: 'Event retry cancelled; no action was taken.',
            });
            return;
          }
          const receipt = await withClient(async (client) => {
            const currentInventory = await readTerminalEventInventory(client, afterEventId);
            const current = currentInventory.events.find((item) => item.eventId === eventId);
            if (!current || current.status !== 'quarantined'
              || current.payloadSha256 !== preflight.payloadSha256
              || current.sourceId !== preflight.sourceId
              || current.sourceSequence !== preflight.sourceSequence) {
              throw curatorError(
                'terminal-event-stale',
                'The quarantined event changed during confirmation; no retry was attempted.',
              );
            }
            return JSON.parse(await client.callTool('event_quarantine_retry', {
              event_id: eventId,
            }));
          }, { allowEventRetry: true });
          if (!receipt || receipt.project_id !== projectId || receipt.event_id !== eventId
            || receipt.status !== 'failed') {
            throw curatorError('invalid-response', 'Curator did not confirm the exact event retry.');
          }
          let summary = `Event ${eventId} was requeued for automatic processing. Its current state is failed until processing succeeds.`;
          try {
            const refreshed = await withClient(
              (client) => readTerminalEventInventory(client, afterEventId),
            );
            panel.webview.postMessage({
              type: 'terminalEventInventory', inventory: refreshed, afterEventId,
            });
          } catch (refreshError) {
            summary += ` The retry succeeded, but the updated inventory could not be read: ${dashboardErrorMessage(refreshError)}`;
          }
          panel.webview.postMessage({ type: 'terminalEventRetryResult', success: true, summary });
          await reloadOpenDashboards(workspace.uri.fsPath);
        } catch (error) {
          panel.webview.postMessage({
            type: 'terminalEventRetryResult', success: false,
            summary: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'inspectPurgeReceipt' && typeof projectId === 'string') {
        const receiptId = typeof message.receiptId === 'string' ? message.receiptId.trim() : '';
        if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(receiptId)) {
          panel.webview.postMessage({
            type: 'purgeReceiptError',
            message: 'Enter a receipt ID containing 1–128 letters, numbers, dots, underscores, colons, or hyphens.',
          });
          return;
        }
        panel.webview.postMessage({
          type: 'purgeReceiptLoading',
          receiptId,
        });
        try {
          const summary = await withClient(async (client) => parsePurgeReceiptInspection(
            await client.callTool('artifact_purge_status', { receipt_id: receiptId }),
            receiptId,
          ));
          panel.webview.postMessage({ type: 'purgeReceiptInspection', summary });
        } catch (error) {
          panel.webview.postMessage({
            type: 'purgeReceiptError',
            message: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'releaseArtifactHold' && typeof projectId === 'string') {
        const receiptId = typeof message.receiptId === 'string' ? message.receiptId.trim() : '';
        const artifactPath = typeof message.artifactPath === 'string' ? message.artifactPath : '';
        if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(receiptId)
          || !artifactPath || artifactPath.length > 1024
          || /[\u0000-\u001f\u007f]/.test(artifactPath)) {
          panel.webview.postMessage({ type: 'purgeReceiptError', message: 'Receipt or artifact reference is invalid.' });
          return;
        }
        const findHeldTarget = async (client) => {
          const status = parsePurgeReceiptInspection(
            await client.callTool('artifact_purge_status', { receipt_id: receiptId }),
            receiptId,
          );
          return status.targets.find((target) => target.path === artifactPath
            && target.status === 'held' && target.nextAction === 'release_artifact_hold'
            && !target.approvalStale);
        };
        try {
          const eligible = await withClient(findHeldTarget);
          if (!eligible) throw curatorError(
            'receipt-stale', 'The receipt no longer reports this artifact as eligible for hold release.',
          );
          const rationale = await vscode.window.showInputBox({
            title: 'Release one cleanup hold',
            prompt: `Why may Curator release the hold on ${artifactPath}?`,
            ignoreFocusOut: true,
            validateInput: (value) => typeof value === 'string'
              && value.trim().length > 0 && value.trim().length <= 1000
              ? undefined : 'Enter a single-line rationale of at most 1,000 characters.',
          });
          if (!rationale || !rationale.trim()) {
            panel.webview.postMessage({
              type: 'purgeReceiptHoldResult',
              receiptId,
              summary: 'Hold release cancelled; no action was taken.',
              success: false,
            });
            return;
          }
          const confirmation = await vscode.window.showWarningMessage(
            `Release the retention hold for ${artifactPath}?`,
            {
              modal: true,
              detail: `Project: ${projectId}\nReceipt: ${receiptId}\nCurator will resume only this receipt's already-authorized cleanup if its other gates pass. This does not approve cleanup for another artifact.\nRationale: ${rationale.trim()}`,
            },
            'Release this hold and retry',
            'Cancel',
          );
          if (confirmation !== 'Release this hold and retry') {
            panel.webview.postMessage({
              type: 'purgeReceiptHoldResult',
              receiptId,
              summary: 'Hold release cancelled; no action was taken.',
              success: false,
            });
            return;
          }
          const summary = await withClient(async (client) => {
            const currentTarget = await findHeldTarget(client);
            if (!currentTarget) throw curatorError(
              'receipt-stale', 'The receipt changed during confirmation; no hold was released.',
            );
            const released = JSON.parse(await client.callTool('release_artifact_hold', {
              receipt_id: receiptId,
              path: artifactPath,
              rationale: rationale.trim(),
            }));
            if (!released || released.receipt_id !== receiptId) throw curatorError(
              'invalid-response', 'Curator did not confirm the hold release.',
            );
            return parsePurgeReceiptInspection(
              await client.callTool('artifact_purge_status', { receipt_id: receiptId }),
              receiptId,
            );
          }, { allowRetentionHoldRelease: true });
          panel.webview.postMessage({
            type: 'purgeReceiptHoldResult',
            receiptId,
            summary: `Hold release recorded; current receipt state is ${summary.purgeStatus}.`,
            success: true,
          });
        } catch (error) {
          panel.webview.postMessage({
            type: 'purgeReceiptError',
            message: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'retryPendingPurges' && typeof projectId === 'string') {
        const confirmation = await vscode.window.showWarningMessage(
          `Retry only already-approved, canonically persisted cleanup work for project ${projectId}? This cannot approve any new deletion.`,
          { modal: true },
          'Retry authorized cleanup',
          'Cancel',
        );
        if (confirmation !== 'Retry authorized cleanup') {
          panel.webview.postMessage({
            type: 'purgeRetryResult',
            success: false,
            summary: 'Cleanup retry cancelled; no action was taken.',
          });
          return;
        }
        try {
          const wire = await withClient(
            (client) => client.callTool('retry_pending_purges', {}),
            { allowPurgeRetry: true },
          );
          const receipts = JSON.parse(wire);
          if (!Array.isArray(receipts) || receipts.length > 256
            || receipts.some((receipt) => !receipt || typeof receipt !== 'object')) {
            throw curatorError('invalid-response', 'Curator returned an invalid cleanup retry result.');
          }
          const completed = receipts.filter((receipt) => receipt.purge_status === 'complete').length;
          const pending = receipts.filter((receipt) => ['pending', 'purge_pending']
            .includes(receipt.purge_status)).length;
          const other = receipts.length - completed - pending;
          const summary = receipts.length === 0
            ? 'No already-authorized due cleanup work was pending.'
            : `Retried ${receipts.length} authorized receipt(s): ${completed} complete, ${pending} still pending, ${other} in another state. Rechecking project health and queues.`;
          panel.webview.postMessage({ type: 'purgeRetryResult', success: true, summary });
        } catch (error) {
          panel.webview.postMessage({
            type: 'purgeRetryResult',
            success: false,
            summary: dashboardErrorMessage(error),
          });
        }
      } else if (message.type === 'refreshHealth' && typeof projectId === 'string') {
        if (requestInProgress) {
          panel.webview.postMessage({ type: 'healthRefreshSkipped' });
          return;
        }
        const { feeds, views, metrics } = await withClient(async (client) => {
          const [feeds, views, metrics] = await Promise.all([
            readProjectFeeds({
              client,
              projectRoot: workspace.uri.fsPath,
              databasePath,
              profileId,
              serverCommand,
              hermesCommand,
              evidenceConfig,
              projectId,
              hermesProfileId: resolveHermesProfileId(projectId, hermesProfileBindings),
              spawnProcess,
              trigger: 'automatic',
            }),
            refreshWorkspaceQueueViews(client, workspace.uri.fsPath, projectId),
            client.callTool('project_metrics', {}).catch(() => null),
          ]);
          return { feeds, views, metrics };
        });
        const operationalErrorLog = await updatePersistentOperationalErrorLog(
          healthHistoryStore,
          projectId,
          resolveHermesProfileId(projectId, hermesProfileBindings),
          operationalErrorsForSnapshot({
            health: feeds.health,
            projectId,
            healthProbeError: feeds.healthProbeError,
            queueProbeError: feeds.queueProbeError,
            queueSnapshot: feeds.queueSnapshot,
            metrics,
            healthCheckedAt: feeds.healthCheckedAt,
            queueCheckedAt: feeds.queueCheckedAt,
          }),
          feeds.healthCheckedAt || feeds.queueCheckedAt,
        );
        const history = await updatePersistentHealthHistory(
          healthHistoryStore,
          projectId,
          resolveHermesProfileId(projectId, hermesProfileBindings),
          healthHistoryStatus(feeds.health, projectId),
          feeds.healthCheckedAt,
        );
        panel.webview.postMessage({
          type: 'healthSnapshot',
          projectId,
          operationalErrorLog,
          health: feeds.health,
          healthProbeError: feeds.healthProbeError,
          healthProbeFailure: feeds.healthProbeError
            ? feedFailureMessage(
              feeds.healthProbeError,
              feeds.healthLastFailureCode,
              feeds.healthAutoPaused,
              healthProbeFailureMessage,
            ) : null,
          healthCheckedAt: feeds.healthCheckedAt,
          healthComponentRows: dashboardComponentRows({
            health: feeds.health,
            projectId,
            healthProbeError: feeds.healthProbeError,
            queueSnapshot: feeds.queueSnapshot,
            queueProbeError: feeds.queueProbeError,
            workspaceViewsUpdated: views.allUpdated,
            healthHistoryPersisted: history.persisted,
          }),
          healthHistory: history.samples,
          healthHistoryPersisted: history.persisted,
          healthHistoryScope: history.scope,
        });
      } else if (message.type === 'loadGoals') {
        if (goalLoadInFlight) return;
        const loadGoals = (async () => {
        candidateIds.clear();
        reportRevisions.clear();
        reportFacts.clear();
        reportPages.clear();
        goalCards.clear();
        goalIds.clear();
        projectId = null;
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        const result = await withClient(async (client) => {
          const page = await client.callTool('goal_list_page', {
            offset,
            limit: GOAL_PAGE_SIZE,
          }).then((wire) => JSON.parse(wire));
          if (!page || typeof page.project_id !== 'string' || !page.project_id) {
            throw curatorError('status-project-invalid', 'Curator returned no project binding.');
          }
          if (configuredProjectId && page.project_id !== configuredProjectId) {
            throw curatorError('status-project-mismatch', 'Curator returned another project.');
          }
          const activityRequest = client.callTool('project_activity_status', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const storageRequest = client.callTool('project_storage_usage', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const metricsRequest = client.callTool('project_metrics', {})
            .catch(() => null);
          const reviewRequest = client.callTool('sde_review_queue_cards', {
            limit: REVIEW_QUEUE_SIZE,
          }).then((wire) => JSON.parse(wire)).catch(() => null);
          const inboxRequest = client.callTool('event_queue_status', {})
            .then((wire) => JSON.parse(wire)).catch(() => null);
          const [activity, storage, metrics, reviews, inbox] = await Promise.all([
            activityRequest,
            storageRequest,
            metricsRequest,
            reviewRequest,
            inboxRequest,
          ]);
          const { outlines, resolvedCandidateIds } = await readReviewOutlines(
            client, reviews, page.project_id, workspace.uri.fsPath,
          );
          const queueViewsUpdated = tryWriteWorkspaceQueueViews(
            workspace.uri.fsPath, page.project_id, inbox, reviews, outlines,
            resolvedCandidateIds,
          );
          const reviewBufferUpdated = await refreshOpenPendingReviewDocumentSafely(
            workspace.uri.fsPath,
          );
          const workspaceViewsUpdated = queueViewsUpdated && reviewBufferUpdated;
          const feeds = typeof page.project_id === 'string' && page.project_id
            ? await readProjectFeeds({
              client,
              projectRoot: workspace.uri.fsPath,
              databasePath,
              profileId,
              serverCommand,
              hermesCommand,
              evidenceConfig,
              projectId: page.project_id,
              hermesProfileId: resolveHermesProfileId(page.project_id, hermesProfileBindings),
              spawnProcess,
              trigger: message.manualRefresh === true ? 'manual' : 'automatic',
            })
            : {
              health: null, healthProbeError: 'hermes-probe-invalid',
              healthCheckedAt: new Date().toISOString(), healthAutoPaused: false,
              queueSnapshot: null, queueProbeError: 'curator-queue-invalid',
              queueCheckedAt: new Date().toISOString(), queueAutoPaused: false,
            };
          const history = await updatePersistentHealthHistory(
            healthHistoryStore,
            page.project_id,
            resolveHermesProfileId(page.project_id, hermesProfileBindings),
            healthHistoryStatus(feeds.health, page.project_id),
            feeds.healthCheckedAt,
          );
          return {
            ...feeds, activity, storage, metrics, page, reviews, inbox,
            hostFilesystemRows: hostFilesystemRows(workspace.uri.fsPath, databasePath),
            workspaceViewsUpdated,
            healthHistory: history.samples,
            healthHistoryPersisted: history.persisted,
            healthHistoryScope: history.scope,
          };
        });
        const operationalErrorLog = await updatePersistentOperationalErrorLog(
          healthHistoryStore,
          result.page.project_id,
          resolveHermesProfileId(result.page.project_id, hermesProfileBindings),
          operationalErrorsForSnapshot({
            health: result.health,
            projectId: result.page.project_id,
            healthProbeError: result.healthProbeError,
            queueProbeError: result.queueProbeError,
            queueSnapshot: result.queueSnapshot,
            metrics: result.metrics,
            healthCheckedAt: result.healthCheckedAt,
            queueCheckedAt: result.queueCheckedAt,
          }),
          result.healthCheckedAt || result.queueCheckedAt,
        );
        const {
          page, health, healthProbeError, healthLastFailureCode,
          healthCheckedAt, healthAutoPaused, queueSnapshot, queueProbeError,
          queueLastFailureCode, queueCheckedAt, queueAutoPaused,
          activity, storage, metrics, reviews,
          hostFilesystemRows: measuredFilesystemRows, workspaceViewsUpdated,
          healthHistory, healthHistoryPersisted, healthHistoryScope,
        } = result;
        if (page.project_id !== undefined && page.project_id !== '') {
          projectId = page.project_id;
          goalIds = new Set((page.goals || []).map((goal) => goal.goal_id));
          for (const goal of page.goals || []) goalCards.set(goal.goal_id, goal);
        }
        const reviewItems = validateReviewQueue(reviews, page.project_id);
        updateStatusBarHealth(
          health,
          page.project_id,
          reviewItems,
          storage,
          healthProbeError
            ? { code: healthLastFailureCode || healthProbeError } : null,
        );
        const healthFailureCode = healthLastFailureCode || healthProbeError;
        const queueFailureCode = queueLastFailureCode || queueProbeError;
        const healthGateDescriptions = !health
          ? [healthFailureCode
            ? healthProbeFailureMessage(healthFailureCode)
            : 'Health snapshot unavailable; refresh to retry.']
          : health.project_id !== page.project_id
            ? ['Health snapshot belongs to a different project.']
            : health.status === 'unknown'
              && health.gate_codes.every((gate) => gate === 'review_backlog')
              ? ['Hermes could not confirm local health.']
              : health.gate_codes.filter((gate) => gate !== 'review_backlog')
                .map(healthGateLabel);
        candidateIds = new Set((reviewItems || []).map((item) => item.candidate.candidate_id));
        panel.webview.postMessage({
          type: 'goals', page, health, activity, storage,
          operationalErrorLog,
          hostFilesystemRows: measuredFilesystemRows,
          reviews: reviewItems,
          healthComponentRows: dashboardComponentRows({
            health,
            projectId: page.project_id,
            healthProbeError,
            queueSnapshot,
            queueProbeError,
            workspaceViewsUpdated,
            healthHistoryPersisted,
          }),
          healthProbeError,
          healthProbeFailure: healthProbeError
            ? feedFailureMessage(
              healthProbeError,
              healthLastFailureCode,
              healthAutoPaused,
              healthProbeFailureMessage,
            ) : null,
          healthCheckedAt,
          healthHistory,
          healthHistoryPersisted,
          healthHistoryScope,
          healthAutoPaused,
          queueSnapshot,
          queueProbeError,
          queueProbeFailure: queueProbeError
            ? feedFailureMessage(
              queueProbeError,
              queueLastFailureCode,
              queueAutoPaused,
              queueProbeFailureMessage,
            ) : null,
          queueCheckedAt,
          queueAutoPaused,
          healthGateDescriptions,
          goalStatesSummary: summarizeGoalStates(activity, page.project_id),
          queueSummary: summarizeOperationalQueues(queueSnapshot, page.project_id),
          queueRows: queueMetricRows(queueSnapshot, page.project_id),
          queueState: queuePanelState(queueSnapshot, page.project_id),
          alertSummary: summarizeOperationalAlerts(
            health, storage, metrics, page.project_id, queueSnapshot,
          ),
          workspaceViewsUpdated,
          reviewAvailable: Boolean(profileId && serverCommand && databasePath && evidenceConfig !== null),
        });
        })();
        goalLoadInFlight = loadGoals;
        try {
          await loadGoals;
        } finally {
          if (goalLoadInFlight === loadGoals) goalLoadInFlight = null;
        }
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
        panel.webview.postMessage({
          type: 'evidence',
          evidence,
          factOffset: message.factOffset,
          displayStatus: factEvidenceDisplayStatus(evidence),
        });
      } else if (message.type === 'reopenGoal' && goalIds.has(message.goalId)) {
        const goal = goalCards.get(message.goalId);
        if (goal?.status !== 'complete' || !Number.isSafeInteger(goal.lifecycle_revision)) {
          throw curatorError('goal-not-reopenable', 'Refresh the goal list; this goal is no longer eligible to reopen.');
        }
        const reason = await vscode.window.showInputBox({
          title: 'Reopen completed Curator V2 task',
          prompt: 'Why does this completed task need a new evidence pass?',
          ignoreFocusOut: true,
          validateInput: (value) => validGoalText(value, 1000)
            ? undefined : 'Enter one line with at most 1,000 characters.',
        });
        if (!reason) return;
        const nextAction = await vscode.window.showInputBox({
          title: 'Next action for the reopened task',
          prompt: 'What is the next concrete step?',
          ignoreFocusOut: true,
          validateInput: (value) => validGoalText(value, 1000)
            ? undefined : 'Enter one line with at most 1,000 characters.',
        });
        if (!nextAction) return;
        const confirmation = await vscode.window.showWarningMessage(
          `Reopen “${goal.problem}”? Previous facts and evidence remain in history; current criteria return to open.`,
          { modal: true },
          'Reopen task',
          'Cancel',
        );
        if (confirmation !== 'Reopen task') return;
        const reopened = JSON.parse(await withClient(
          (client) => client.callTool('goal_reopen', {
            event_id: randomBytes(16).toString('hex'),
            goal_id: goal.goal_id,
            reason: reason.trim(),
            next_action: nextAction.trim(),
            expected_lifecycle_revision: goal.lifecycle_revision,
          }),
          { allowWrite: true },
        ));
        if (reopened.project_id !== projectId || reopened.status !== 'processed') {
          throw curatorError('goal-reopen-unconfirmed', 'Curator did not confirm the reopen action. Refresh to check the current goal state.');
        }
        panel.webview.postMessage({ type: 'goalReopened', goalId: goal.goal_id });
      } else if (message.type === 'openReview'
        && typeof message.candidateId === 'string'
        && (message.decision === undefined || message.decision === 'approve' || message.decision === 'reject')
        && candidateIds.has(message.candidateId)) {
        await launchDocumentReview(message.candidateId, message.decision);
      }
    } catch (error) {
      void notifyTransportClosed(error);
      goalIds.clear();
      candidateIds.clear();
      reportRevisions.clear();
      reportFacts.clear();
      reportPages.clear();
      projectId = null;
      updateStatusBarHealth(null, null);
      if (!panelDisposed) {
        panel.webview.postMessage({
          type: 'error',
          message: dashboardErrorMessage(error),
        });
      }
    }
  });

  panel.onDidDispose(() => {
    panelDisposed = true;
    if (settingsChangeListener && typeof settingsChangeListener.dispose === 'function') {
      settingsChangeListener.dispose();
    }
    goalIds.clear();
    candidateIds.clear();
  });
}

function dashboardHtml(webview, focusReviews = false, focusRecovery = false) {
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
    .dashboard { margin: .8rem 0; border: 1px solid var(--vscode-panel-border); border-radius: 6px; }
    .dashboard > summary { cursor: pointer; padding: .55rem .7rem; font-weight: 600; }
    .dashboard-content { padding: 0 .55rem .55rem; }
    .dashboard-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 360px), 1fr)); gap: .7rem; }
    .dashboard-card { min-width: 0; padding: .45rem .6rem; border: 1px solid var(--vscode-panel-border); border-radius: 5px; container: dashboard-card / inline-size; }
    .dashboard-card[data-state="healthy"] { border-top: 3px solid var(--vscode-testing-iconPassed, #73c991); }
    .dashboard-card[data-state="review"] { border-top: 3px solid var(--vscode-charts-purple, #b180d7); }
    .dashboard-card[data-state="degraded"] { border-top: 3px solid var(--vscode-errorForeground, #f48771); }
    .dashboard-card[data-state="warning"] { border-top: 3px solid var(--vscode-editorWarning-foreground, #cca700); }
    .dashboard-card[data-state="unknown"] { border-top: 3px solid #fce94f; }
    .dashboard-card[data-state="neutral"] { border-top: 3px solid var(--vscode-textLink-foreground, #4daafc); }
    .dashboard-card h2 { margin: .1rem 0 .35rem; font-size: 1em; }
    .dashboard-card p { margin: .3rem 0; font-size: .88em; line-height: 1.35; overflow-wrap: anywhere; }
    .metric-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 1rem; line-height: 1.35; }
    .metric-table th, .metric-table td { padding: .38rem .42rem; border-bottom: 1px solid var(--vscode-panel-border); text-align: left; vertical-align: top; overflow-wrap: normal; word-break: normal; }
    .metric-table th:first-child, .metric-table td:first-child { width: 28%; }
    .metric-table th:nth-child(2), .metric-table td:nth-child(2) { width: 42%; }
    .metric-table td:nth-child(2) { overflow-wrap: anywhere; }
    .metric-table th:last-child, .metric-table td:last-child { width: 30%; min-width: 8rem; }
    .metric-table td:last-child { white-space: nowrap; }
    .metric-table thead th { font-weight: 700; color: var(--vscode-foreground); }
    .metric-table tbody th { font-weight: 600; color: var(--vscode-descriptionForeground); }
    .metric-table tbody td[data-state] { font-weight: 600; }
    .metric-table [data-state="healthy"] { color: var(--vscode-testing-iconPassed, #73c991); }
    .metric-table [data-state="review"] { color: var(--vscode-charts-purple, #b180d7); }
    .metric-table [data-state="degraded"] { color: var(--vscode-errorForeground, #f48771); }
    .metric-table [data-state="warning"] { color: var(--vscode-editorWarning-foreground, #cca700); }
    .metric-table [data-state="unknown"] { color: #fce94f; }
    .metric-table tr[data-state="unknown"] td { color: #fce94f; }
    .metric-table [data-state="neutral"] { color: var(--vscode-textLink-foreground, #4daafc); }
    @media (max-width: 620px) {
      body { padding: .5rem; }
      .dashboard-content { padding: 0 .3rem .4rem; }
      .dashboard-card { padding: .35rem; }
      .metric-table th, .metric-table td { padding: .32rem .25rem; }
      .metric-table th:first-child, .metric-table td:first-child { width: 27%; }
      .metric-table th:nth-child(2), .metric-table td:nth-child(2) { width: 43%; }
      .metric-table th:last-child, .metric-table td:last-child { width: 30%; min-width: 5.25rem; }
    }
    @container dashboard-card (max-width: 32rem) {
      .metric-table, .metric-table thead, .metric-table tbody, .metric-table tr, .metric-table th, .metric-table td { display: block; }
      .metric-table thead { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
      .metric-table tbody tr { display: grid; grid-template-columns: minmax(0, 1fr) max-content; column-gap: .5rem; row-gap: .2rem; padding: .42rem 0; border-bottom: 1px solid var(--vscode-panel-border); }
      .metric-table tbody th, .metric-table tbody td { width: auto !important; min-width: 0 !important; padding: 0; border: 0; }
      .metric-table tbody th { grid-column: 1; grid-row: 1; }
      .metric-table tbody td:nth-child(2) { grid-column: 1 / -1; grid-row: 2; }
      .metric-table tbody td:last-child { grid-column: 2; grid-row: 1; justify-self: end; }
      .metric-table tbody td:nth-child(2)::before { content: 'Value: '; font-weight: 700; color: var(--vscode-descriptionForeground); }
      .metric-table tbody td:last-child::before { content: 'State: '; font-weight: 700; color: var(--vscode-descriptionForeground); }
    }
    #reviewsSection { margin: .9rem 0; padding: .55rem .7rem; border: 1px solid var(--vscode-panel-border); border-radius: 6px; }
    #reviewsSection h2 { margin: .1rem 0 .45rem; }
    #recoveryControls { display: flex; flex-wrap: wrap; align-items: center; gap: .2rem; }
    #operationalErrorEntries { margin: .35rem 0; padding-left: 1.4rem; }
    #operationalErrorEntries li { margin: .55rem 0; line-height: 1.4; }
    #purgeReceiptControls { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem; }
    #purgeReceiptControls input, #reconciliationControls input { color: var(--vscode-input-foreground); background: var(--vscode-input-background); border: 1px solid var(--vscode-input-border, var(--vscode-panel-border)); padding: .4rem .5rem; min-width: min(100%, 22rem); }
    #recoveryToolbox li { margin: .4rem 0; line-height: 1.4; }
    .health-history-chart { display: flex; align-items: stretch; gap: 2px; height: 7rem; border-bottom: 1px solid var(--vscode-panel-border); background: repeating-linear-gradient(to bottom, transparent 0, transparent 2.25rem, var(--vscode-panel-border) 2.3rem, transparent 2.35rem); }
    .health-history-point { display: block; flex: 1 1 0; min-width: 2px; max-width: 1rem; height: .35rem; border-radius: 2px; }
    .health-history-point[data-state="healthy"] { margin-top: .7rem; background: var(--vscode-testing-iconPassed, #73c991); }
    .health-history-point[data-state="degraded"] { margin-top: 3.25rem; background: var(--vscode-errorForeground, #f48771); }
    .health-history-point[data-state="unknown"] { margin-top: 5.8rem; background: #fce94f; }
    .health-history-axis { display: flex; justify-content: space-between; gap: .5rem; color: var(--vscode-descriptionForeground); font-size: .8em; }
    .health-history-legend { color: var(--vscode-descriptionForeground); font-size: .85em; }
    #goalControls { display: flex; flex-wrap: wrap; align-items: center; gap: .15rem; }
    #goalPage { color: var(--vscode-descriptionForeground); margin: .35rem 0; }
    #goals { display: flex; flex-wrap: wrap; gap: .3rem; margin: .8rem 0; }
    .goal-card { display: grid; text-align: left; max-width: 100%; min-width: min(100%, 260px); }
    .goal-title { overflow-wrap: anywhere; }
    .goal-disposition { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; opacity: .9; font-size: 1rem; line-height: 1.35; }
    .goal-state { border: 1px solid var(--vscode-panel-border); border-radius: 999px; padding: .05rem .4rem; }
    .goal-updated { font-variant-numeric: tabular-nums; }
    .goal-next-action { color: var(--vscode-descriptionForeground); }
    #report { white-space: pre-wrap; overflow-wrap: anywhere; font-family: var(--vscode-editor-font-family); line-height: 1.5; }
    #notice { color: var(--vscode-descriptionForeground); margin: .6rem 0; }
    #error { color: var(--vscode-errorForeground); }
  </style>
</head>
<body>
  <h1>CuratorMD V2</h1>
  <p id="notice">Reads are project-scoped and reauthorized by Curator on each request. Refresh replaces the current page; pages are never joined across reads.</p>
  <details class="dashboard" open>
    <summary>Project dashboard · health, activity, queues, storage</summary>
    <div class="dashboard-content">
      <div class="dashboard-grid">
      <section id="healthPanel" class="dashboard-card" data-state="unknown" aria-labelledby="healthHeading">
        <h2 id="healthHeading">Project health</h2>
        <p id="health" role="status">Loading authorized health status…</p>
        <table class="metric-table"><thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">State</th></tr></thead><tbody id="healthRows"></tbody></table>
      </section>
      <section id="activityPanel" class="dashboard-card" data-state="neutral" aria-labelledby="activityHeading">
        <h2 id="activityHeading">Retained activity</h2>
        <p id="activity" role="status">Loading authorized activity totals…</p>
        <table class="metric-table"><thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">State</th></tr></thead><tbody id="activityRows"></tbody></table>
      </section>
      <section id="queuesPanel" class="dashboard-card" data-state="unknown" aria-labelledby="queuesHeading">
        <h2 id="queuesHeading">Operational queues</h2>
        <p id="queues" role="status">Loading authorized queue counts…</p>
        <table class="metric-table"><thead><tr><th scope="col">Queue</th><th scope="col">Count</th><th scope="col">State</th></tr></thead><tbody id="queueRows"></tbody></table>
      </section>
      <section id="storagePanel" class="dashboard-card" data-state="unknown" aria-labelledby="storageHeading">
        <h2 id="storageHeading">Storage usage</h2>
        <p id="storage" role="status">Loading authorized storage totals…</p>
        <table class="metric-table"><thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">State</th></tr></thead><tbody id="storageRows"></tbody></table>
      </section>
      <section id="healthHistoryPanel" class="dashboard-card" data-state="unknown" aria-labelledby="healthHistoryHeading">
        <h2 id="healthHistoryHeading">Health history</h2>
        <p id="healthHistorySummary" role="status">Waiting for the first health check.</p>
        <p class="health-history-legend">Health state by check time · healthy high · degraded middle · unknown low</p>
        <div id="healthHistoryChart" class="health-history-chart" role="list" aria-label="Recent project health checks"></div>
        <div class="health-history-axis"><span id="healthHistoryStart">No samples</span><span>Older → newer</span><span id="healthHistoryEnd"></span></div>
        <p id="healthHistoryRetention">Restores the last ${HEALTH_HISTORY_LIMIT} checks for this project and Hermes profile. The dashboard checks once per minute while open.</p>
        <button id="resetHealthHistory" type="button">Reset saved graph history</button>
        <p id="healthHistoryResetStatus" role="status" aria-live="polite">Reset affects saved chart samples for this project and Hermes profile only.</p>
      </section>
      </div>
    </div>
  </details>
  <details id="recoveryToolbox" class="dashboard" open>
    <summary>CuratorMD V2 Recovery Manager</summary>
    <div class="dashboard-content">
      <p>Retry health, queue, activity, and storage reads; open attended review actions; or retry cleanup that was already approved and canonically persisted. A failed read stays unknown. Cleanup retry cannot approve a new deletion, change grants, or restore or replace the database.</p>
      <div id="recoveryControls">
        <button id="retryRecoveryReads" type="button">Retry recovery checks</button>
        <button id="refreshQueueViews" type="button">Rebuild local inbox and review views</button>
        <button id="runEventRouter" type="button" disabled>Run one event-routing pass</button>
        <button id="inspectTerminalEvents" type="button">Inspect failed and quarantined events</button>
        <button id="openReviewActions" type="button">Open pending review actions</button>
        <button id="retryPendingPurges" type="button" disabled>Retry approved cleanup</button>
      </div>
      <p id="queueViewsStatus" role="status" aria-live="polite">Generated inbox and review views can be rebuilt from a fresh authorized queue read.</p>
      <p>One routing pass processes at most 100 eligible received or failed events for this project. It may apply their recorded goal and fact updates. Quarantined events remain separate and require individual review.</p>
      <p id="eventRouterStatus" role="status" aria-live="polite">Event routing is available after the project connection is verified.</p>
      <h3>Recent operational errors</h3>
      <p id="operationalErrorLogStatus" role="status" aria-live="polite">Waiting for a project health and queue read.</p>
      <ul id="operationalErrorEntries"></ul>
      <h3>Inspect Markdown reconciliation</h3>
      <p>Compare a configured persistence target with bounded SQLite goal pages. This is read-only; divergent or malformed content needs an owner-reviewed recovery decision.</p>
      <div id="reconciliationControls">
        <label for="reconciliationTarget">Configured relative target</label>
        <input id="reconciliationTarget" type="text" maxlength="512" value="persistence/HISTORY.md" autocomplete="off" spellcheck="false">
        <button id="inspectProjectReconciliation" type="button">Inspect target</button>
      </div>
      <p id="projectReconciliationStatus" role="status" aria-live="polite">No Markdown reconciliation has been read.</p>
      <div id="projectReconciliationResult"></div>
      <p id="terminalEventStatus" role="status" aria-live="polite">Event inventory has not been read.</p>
      <div id="terminalEventInventory"></div>
      <h3>Archive processed event receipts</h3>
      <p>Review exact payload-free processed receipts before archiving a bounded page. Archiving removes them from the active receipt inventory; receipts remain available for replay checks.</p>
      <button id="inspectEventArchive" type="button">Review eligible receipt page</button>
      <p id="eventArchiveStatus" role="status" aria-live="polite">No receipt archive proposal is loaded.</p>
      <div id="eventArchiveProposal"></div>
      <p id="purgeRetryStatus" role="status" aria-live="polite">Cleanup retry is available after the project connection is verified.</p>
      <h3>Inspect cleanup receipt</h3>
      <p>Read the receipt and bounded per-artifact recovery state for this project. Inspection does not retry cleanup or change retention holds.</p>
      <div id="purgeReceiptControls">
        <label for="purgeReceiptId">Receipt ID</label>
        <input id="purgeReceiptId" type="text" maxlength="128" autocomplete="off" spellcheck="false">
        <button id="inspectPurgeReceipt" type="button" disabled>Inspect receipt</button>
      </div>
      <p id="purgeReceiptStatus" role="status" aria-live="polite">Enter a receipt ID to inspect its cleanup state.</p>
      <div id="purgeReceiptTargets"></div>
      <ul>
        <li><strong>No reviews waiting:</strong> complete a tracked goal with current passing evidence, then request historical SDE assessment. The resulting proposal appears below for the owner's decision.</li>
        <li><strong>Stale or missing SDE evidence:</strong> open the pending review document and choose <em>Refresh evidence</em> above the editable decision. This reopens the source task and withdraws the stale proposal while retaining its facts and receipts. Record fresh passing evidence, complete the task, then assess a new proposal.</li>
        <li><strong>Unknown or paused health and queue feeds:</strong> retry the checks once. If a feed remains unknown, inspect its displayed project and profile binding; do not treat missing counts as zero.</li>
        <li><strong><code>purge_pending</code> or expiry backlog:</strong> inspect the durable review and cleanup receipts first. Use the one-shot maintenance command only for already-authorized due work; never remove staged files by hand.</li>
        <li><strong>Database or Markdown disagreement:</strong> stop projection and purge for the affected target, preserve both copies and SQLite sidecars, then follow the owner-reviewed restore procedure. Restore only to a new path.</li>
      </ul>
    </div>
  </details>
  <section id="reviewsSection" aria-labelledby="reviewsHeading">
    <h2 id="reviewsHeading">Pending SDE review</h2>
    <p id="reviewNote" role="status">Loading authorized review queue…</p>
    <div id="reviews"></div>
  </section>
  <div id="goalControls"><button id="refresh">Refresh goals</button> <button id="previousGoals">Previous goals</button> <button id="nextGoals">Next goals</button><span id="goalPage"></span></div>
  <div id="goals"></div>
  <h2 id="selected"></h2>
  <button id="reopenGoal" hidden>Reopen completed task</button>
  <p id="actionStatus" role="status" aria-live="polite"></p>
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
    let reopenGoalAfterRefresh = null;
    let healthRefreshInFlight = false;
    let activeProjectId = null;
    const goals = document.getElementById('goals');
    const report = document.getElementById('report');
    const evidenceStatus = document.getElementById('evidenceStatus');
    const evidenceButtons = document.getElementById('evidenceButtons');
    const evidenceRefs = document.getElementById('evidenceRefs');
    const error = document.getElementById('error');
    const health = document.getElementById('health');
    const activitySummary = document.getElementById('activity');
    const queueSummary = document.getElementById('queues');
    const storageSummary = document.getElementById('storage');
    const reviewSummary = document.getElementById('reviewNote');
    const reviews = document.getElementById('reviews');
    const healthHistoryChart = document.getElementById('healthHistoryChart');
    const healthHistorySummary = document.getElementById('healthHistorySummary');
    const healthHistoryStart = document.getElementById('healthHistoryStart');
    const healthHistoryEnd = document.getElementById('healthHistoryEnd');
    const savedDashboardState = typeof api.getState === 'function' ? api.getState() : null;
    let healthHistoryProjectId = typeof savedDashboardState?.projectId === 'string'
      ? savedDashboardState.projectId : null;
    let healthHistoryScope = typeof savedDashboardState?.healthHistoryScope === 'string'
      ? savedDashboardState.healthHistoryScope : null;
    let healthHistory = Array.isArray(savedDashboardState?.healthHistory)
      && savedDashboardState.healthHistory.length <= ${HEALTH_HISTORY_LIMIT * 4}
      ? savedDashboardState.healthHistory.filter((sample) => sample
        && ['healthy', 'degraded', 'unknown'].includes(sample.status)
        && typeof sample.observed_at === 'string' && sample.observed_at.length <= 64
        && Number.isFinite(Date.parse(sample.observed_at))).slice(-${HEALTH_HISTORY_LIMIT}) : [];
    let healthHistoryResetAwaitingFreshCheck = false;
    let healthHistoryResetRetryCount = 0;
    function renderMetricRows(id, rows) {
      const body = document.getElementById(id);
      body.replaceChildren();
      for (const item of rows) {
        const row = document.createElement('tr');
        row.setAttribute('data-state', item.state);
        const label = document.createElement('th');
        label.setAttribute('scope', 'row');
        label.textContent = item.label;
        const value = document.createElement('td');
        value.textContent = item.value;
        if (item.action === 'refreshQueueViews') {
          const action = document.createElement('button');
          action.type = 'button';
          action.textContent = item.actionLabel || 'Rebuild local views';
          action.setAttribute('aria-label', 'Rebuild local inbox and review projections');
          action.addEventListener('click', requestQueueViewRefresh);
          value.appendChild(action);
        } else if (item.action === 'retryRecoveryReads') {
          const action = document.createElement('button');
          action.type = 'button';
          action.textContent = item.actionLabel || 'Recheck';
          action.setAttribute('aria-label', 'Recheck ' + item.label);
          action.addEventListener('click', () => {
            document.getElementById('retryRecoveryReads').click();
          });
          value.appendChild(action);
        } else if (['runEventRouter', 'retryPendingPurges', 'openReviewActions']
          .includes(item.action)) {
          const action = document.createElement('button');
          action.type = 'button';
          action.textContent = item.actionLabel;
          action.setAttribute('aria-label', item.actionLabel + ' for ' + item.label);
          action.addEventListener('click', () => {
            document.getElementById(item.action).click();
          });
          value.appendChild(action);
        }
        const state = document.createElement('td');
        state.textContent = item.stateLabel || item.state;
        state.setAttribute('data-state', item.state);
        row.appendChild(label);
        row.appendChild(value);
        row.appendChild(state);
        body.appendChild(row);
      }
    }
    function requestQueueViewRefresh() {
      const button = document.getElementById('refreshQueueViews');
      button.disabled = true;
      document.getElementById('queueViewsStatus').textContent = 'Reading the authorized queues and rebuilding local projections…';
      api.postMessage({ type: 'refreshQueueViews' });
    }
    function renderOperationalErrorLog(log) {
      const status = document.getElementById('operationalErrorLogStatus');
      const list = document.getElementById('operationalErrorEntries');
      list.replaceChildren();
      if (!log || log.persisted !== true || !Array.isArray(log.entries)) {
        status.textContent = 'Error log could not be saved and read back from VS Code local storage.';
        return;
      }
      const entries = log.entries.filter((entry) => entry
        && typeof entry.component === 'string' && entry.component.length <= 100
        && typeof entry.category === 'string' && entry.category.length <= 80
        && typeof entry.summary === 'string' && entry.summary.length <= 500
        && typeof entry.recoveryHint === 'string' && entry.recoveryHint.length <= 400
        && typeof entry.active === 'boolean'
        && Number.isSafeInteger(entry.occurrences) && entry.occurrences > 0
        && typeof entry.firstSeenAt === 'string' && Number.isFinite(Date.parse(entry.firstSeenAt))
        && typeof entry.lastSeenAt === 'string' && Number.isFinite(Date.parse(entry.lastSeenAt)))
        .slice(0, ${OPERATIONAL_ERROR_LOG_LIMIT});
      status.textContent = entries.length
        ? 'Saved locally for this project and Hermes profile · up to ${OPERATIONAL_ERROR_LOG_LIMIT} records retained. Raw exception text and event payloads are not stored.'
        : 'No operational errors were reported by the latest health and queue read.';
      for (const entry of entries) {
        const item = document.createElement('li');
        const heading = document.createElement('strong');
        heading.textContent = entry.component + ' · ' + entry.category + ' · '
          + (entry.active ? 'active' : 'resolved');
        const details = document.createElement('div');
        details.textContent = entry.summary + ' Seen ' + entry.occurrences + ' time(s); last observed '
          + new Date(entry.lastSeenAt).toLocaleString() + '.';
        const recovery = document.createElement('div');
        recovery.textContent = 'Next step: ' + entry.recoveryHint;
        item.append(heading, details, recovery);
        list.appendChild(item);
      }
    }
    function requestHealthHistoryReset() {
      const button = document.getElementById('resetHealthHistory');
      button.disabled = true;
      document.getElementById('healthHistoryResetStatus').textContent = 'Waiting for confirmation…';
      api.postMessage({ type: 'resetHealthHistory' });
    }
    function updateProjectionComponentRow(status) {
      const row = Array.from(document.getElementById('healthRows').children)
        .find((item) => item.children[0]?.textContent === 'Inbox and review projections');
      if (!row) return;
      const complete = status?.allUpdated === true;
      const state = complete ? 'healthy' : 'degraded';
      row.setAttribute('data-state', state);
      row.children[1].textContent = complete ? 'Both local views refreshed'
        : 'Refresh failed or an open review has unsaved edits';
      row.children[2].textContent = state;
      row.children[2].setAttribute('data-state', state);
    }
    function setPanelState(id, state) {
      document.getElementById(id + 'Panel').setAttribute('data-state', state);
    }
    function formatBytes(value) {
      if (value === null) return 'unavailable';
      if (value < 1024) return value + ' B';
      if (value < 1048576) return (value / 1024).toFixed(1) + ' KiB';
      return (value / 1048576).toFixed(1) + ' MiB';
    }
    function countLabel(value, singular) {
      return value + ' ' + singular + (value === 1 ? '' : 's');
    }
    function formatGoalUpdate(value) {
      if (typeof value !== 'string' || value.length === 0 || value.length > 64) {
        return 'Updated time unavailable';
      }
      const timestamp = Date.parse(value);
      if (!Number.isFinite(timestamp)) return 'Updated time unavailable';
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Ho_Chi_Minh',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
      }).formatToParts(new Date(timestamp));
      const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
      return 'Updated ' + fields.year + '-' + fields.month + '-' + fields.day
        + ' ' + fields.hour + ':' + fields.minute + ' +07';
    }
    function formatSnapshotCheck(value) {
      if (typeof value !== 'string' || value.length > 64) return 'Check time unavailable';
      const timestamp = Date.parse(value);
      if (!Number.isFinite(timestamp)) return 'Check time unavailable';
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Ho_Chi_Minh',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
      }).formatToParts(new Date(timestamp));
      const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
      return 'Checked ' + fields.year + '-' + fields.month + '-' + fields.day
        + ' ' + fields.hour + ':' + fields.minute + ' +07';
    }
    function renderHealthHistory() {
      healthHistoryChart.replaceChildren();
      for (const sample of healthHistory) {
        const point = document.createElement('span');
        point.className = 'health-history-point';
        point.setAttribute('data-state', sample.status);
        point.setAttribute('role', 'listitem');
        const checked = formatSnapshotCheck(sample.observed_at);
        point.setAttribute('title', sample.status + ' · ' + checked);
        point.setAttribute('aria-label', sample.status + ' · ' + checked);
        healthHistoryChart.appendChild(point);
      }
      if (!healthHistory.length) {
        healthHistorySummary.textContent = 'No health checks recorded for this project in this webview yet.';
        healthHistoryStart.textContent = 'No samples';
        healthHistoryEnd.textContent = '';
        setPanelState('healthHistory', 'unknown');
        return;
      }
      const first = healthHistory[0];
      const last = healthHistory[healthHistory.length - 1];
      healthHistorySummary.textContent = healthHistory.length + ' checks · '
        + formatSnapshotCheck(first.observed_at) + ' through ' + formatSnapshotCheck(last.observed_at)
        + ' · latest ' + last.status + '.';
      healthHistoryStart.textContent = formatSnapshotCheck(first.observed_at).replace(/^Checked /, '');
      healthHistoryEnd.textContent = formatSnapshotCheck(last.observed_at).replace(/^Checked /, '');
      setPanelState('healthHistory', last.status);
    }
    function loadPersistentHealthHistory(projectId, samples, persisted, scope) {
      if (typeof projectId !== 'string' || !projectId || projectId.length > 128) return;
      const nextScope = typeof scope === 'string' && /^[a-f0-9]{64}$/.test(scope)
        ? scope : projectId;
      if (healthHistoryProjectId !== projectId || healthHistoryScope !== nextScope) {
        healthHistoryProjectId = projectId;
        healthHistoryScope = nextScope;
        healthHistory = [];
      }
      if (persisted === true && Array.isArray(samples) && samples.length <= ${HEALTH_HISTORY_LIMIT}) {
        healthHistory = samples.filter((sample) => sample
          && ['healthy', 'degraded', 'unknown'].includes(sample.status)
          && typeof sample.observed_at === 'string' && sample.observed_at.length <= 64
          && Number.isFinite(Date.parse(sample.observed_at)))
          .map((sample) => ({
            observed_at: new Date(Date.parse(sample.observed_at)).toISOString(),
            status: sample.status,
          }))
          .sort((left, right) => Date.parse(left.observed_at) - Date.parse(right.observed_at))
          .filter((sample, index, all) => index === 0
            || sample.observed_at !== all[index - 1].observed_at);
      }
      const retention = document.getElementById('healthHistoryRetention');
      retention.textContent = persisted === true
        ? 'Saved by VS Code for this project and Hermes profile; up to ${HEALTH_HISTORY_LIMIT} checks are retained.'
        : 'Persistent history is unavailable; showing this webview’s samples only.';
      if (typeof api.setState === 'function') {
        api.setState({ projectId, healthHistoryScope: nextScope, healthHistory });
      }
      renderHealthHistory();
    }
    function recordHealthSnapshot(projectId, status, checkedAt) {
      const timestamp = typeof checkedAt === 'string' && checkedAt.length <= 64
        ? Date.parse(checkedAt) : Number.NaN;
      if (typeof projectId !== 'string' || !projectId || projectId.length > 128
        || !['healthy', 'degraded', 'unknown'].includes(status) || !Number.isFinite(timestamp)) return;
      if (healthHistoryProjectId !== projectId) {
        healthHistoryProjectId = projectId;
        healthHistoryScope = projectId;
        healthHistory = [];
      }
      const observedAt = new Date(timestamp).toISOString();
      if (healthHistory.at(-1)?.observed_at !== observedAt) {
        healthHistory.push({ observed_at: observedAt, status });
        healthHistory = healthHistory.slice(-${HEALTH_HISTORY_LIMIT});
        if (typeof api.setState === 'function') {
          api.setState({ projectId, healthHistoryScope, healthHistory });
        }
      }
      renderHealthHistory();
    }
    function renderHealthSnapshot(snapshot, projectId, message) {
      renderOperationalErrorLog(message.operationalErrorLog);
      const projectMatches = snapshot && snapshot.project_id === projectId;
      const validStatus = snapshot && ['healthy', 'degraded', 'unknown'].includes(snapshot.status);
      const status = projectMatches && validStatus
        ? snapshot.status === 'degraded' && Array.isArray(snapshot.gate_codes)
          && snapshot.gate_codes.length > 0
          && snapshot.gate_codes.every((gate) => gate === 'review_backlog')
          ? 'healthy' : snapshot.status
        : 'unknown';
      const probeFailure = typeof message.healthProbeFailure === 'string'
        ? message.healthProbeFailure : null;
      const gates = !snapshot ? ['Health snapshot unavailable.']
        : !projectMatches ? ['Health snapshot belongs to a different project.']
          : !validStatus || !Array.isArray(snapshot.gate_codes)
            ? ['Health observation is incomplete.']
            : snapshot.gate_codes.filter((gate) => typeof gate === 'string' && gate !== 'review_backlog');
      if (!snapshot && probeFailure) gates[0] = probeFailure;
      const gateDescriptions = Array.isArray(message.healthGateDescriptions)
        ? message.healthGateDescriptions : gates;
      health.textContent = 'Project health: ' + status + ' · '
        + (gates.length ? countLabel(gates.length, 'open gate') : 'no open gates')
        + (probeFailure ? '. ' + probeFailure : '.')
        + ' ' + formatSnapshotCheck(message.healthCheckedAt);
      const alertText = typeof message.alertSummary === 'string'
        ? message.alertSummary : status === 'healthy' ? 'No open health alerts.'
          : 'Health requires attention or its current state is unknown.';
      setPanelState('health', status);
      const healthRows = document.getElementById('healthRows');
      healthRows.setAttribute('data-project-id', projectMatches ? projectId : '');
      healthRows.setAttribute('data-observed-at', projectMatches && typeof snapshot.observed_at === 'string'
        ? snapshot.observed_at : '');
      renderMetricRows('healthRows', [
        { label: 'Project health', value: status, state: status, stateLabel: status },
        { label: 'Open gates', value: gateDescriptions.length
          ? gateDescriptions.join(' ') : 'None reported', state: status },
        { label: 'Operational alerts', value: probeFailure ? probeFailure + ' ' + alertText : alertText, state: status },
        ...(Array.isArray(message.healthComponentRows) ? message.healthComponentRows : []),
      ]);
      recordHealthSnapshot(projectId, status, message.healthCheckedAt);
    }
    function clearDashboard() {
      renderOperationalErrorLog(null);
      document.getElementById('healthRows').setAttribute('data-project-id', '');
      document.getElementById('healthRows').setAttribute('data-observed-at', '');
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
      health.textContent = 'Project health: unknown. Health snapshot unavailable; refresh to retry.';
      activitySummary.textContent = 'Retained activity: unknown. Refresh to retry the activity read.';
      queueSummary.textContent = 'Operational queues: unknown. Curator queue snapshot unavailable; refresh to retry.';
      storageSummary.textContent = 'Storage usage: unknown. Refresh to retry the storage read.';
      renderMetricRows('healthRows', [
        { label: 'Project health', value: 'unknown', state: 'unknown' },
        { label: 'Open gates', value: 'Health snapshot unavailable; refresh to retry.', state: 'unknown' },
        { label: 'Operational alerts', value: 'Health snapshot unavailable; refresh to retry.', state: 'unknown' },
      ]);
      renderMetricRows('activityRows', [{ label: 'Snapshot', value: 'Refresh required', state: 'unknown' }]);
      renderMetricRows('queueRows', [{ label: 'Snapshot', value: 'Refresh required', state: 'unknown' }]);
      renderMetricRows('storageRows', [{ label: 'Snapshot', value: 'Refresh required', state: 'unknown' }]);
      for (const panel of ['health', 'activity', 'queues', 'storage']) setPanelState(panel, 'unknown');
      setPanelState('healthHistory', 'unknown');
      if (healthHistory.length) {
        healthHistorySummary.textContent = 'Current health read unavailable; showing previous observations only.';
      }
      document.getElementById('selected').textContent = '';
      document.getElementById('reopenGoal').hidden = true;
      document.getElementById('actionStatus').textContent = '';
      document.getElementById('goalPage').textContent = '';
      document.getElementById('factPage').textContent = '';
      document.getElementById('previousGoals').disabled = true;
      document.getElementById('nextGoals').disabled = true;
      document.getElementById('previousFacts').disabled = true;
      document.getElementById('nextFacts').disabled = true;
    }
    function requestGoals(offset, manualRefresh = false) {
      document.getElementById('refresh').disabled = true;
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
      document.getElementById('reopenGoal').hidden = true;
      document.getElementById('factPage').textContent = '';
      document.getElementById('goalPage').textContent = 'Loading a fresh authorized goal page…';
      health.textContent = 'Loading an authorized health snapshot…';
      activitySummary.textContent = 'Loading authorized activity totals…';
      queueSummary.textContent = 'Loading the project-scoped Curator queue snapshot…';
      storageSummary.textContent = 'Loading authorized storage totals…';
      renderMetricRows('healthRows', [
        { label: 'Project health', value: 'Loading', state: 'neutral' },
        { label: 'Open gates', value: 'Awaiting health snapshot', state: 'neutral' },
        { label: 'Operational alerts', value: 'Health read in progress', state: 'neutral' },
      ]);
      for (const table of ['activityRows', 'queueRows', 'storageRows']) {
        renderMetricRows(table, [{ label: 'Snapshot', value: 'Loading', state: 'neutral' }]);
      }
      api.postMessage({ type: 'loadGoals', offset, manualRefresh });
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
    document.getElementById('reopenGoal').addEventListener('click', () => {
      if (selectedGoal) api.postMessage({ type: 'reopenGoal', goalId: selectedGoal });
    });
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
    function renderEvidence(value, displayStatus) {
      evidenceRefs.replaceChildren();
      const verificationStatus = typeof displayStatus === 'string'
        ? displayStatus : 'stale/unknown';
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
    document.getElementById('refresh').addEventListener('click', () => requestGoals(0, true));
    document.getElementById('retryRecoveryReads').addEventListener('click', () => requestGoals(0, true));
    document.getElementById('refreshQueueViews').addEventListener('click', requestQueueViewRefresh);
    document.getElementById('resetHealthHistory').addEventListener('click', requestHealthHistoryReset);
    document.getElementById('inspectTerminalEvents').addEventListener('click', () => {
      document.getElementById('terminalEventStatus').textContent = 'Reading failed and quarantined event inventory…';
      document.getElementById('terminalEventInventory').replaceChildren();
      api.postMessage({ type: 'inspectTerminalEvents' });
    });
    document.getElementById('runEventRouter').addEventListener('click', () => {
      document.getElementById('runEventRouter').disabled = true;
      document.getElementById('eventRouterStatus').textContent = 'Checking the project queue before routing…';
      api.postMessage({ type: 'runEventRouter' });
    });
    document.getElementById('inspectProjectReconciliation').addEventListener('click', () => {
      const target = document.getElementById('reconciliationTarget').value;
      document.getElementById('projectReconciliationResult').replaceChildren();
      document.getElementById('projectReconciliationStatus').textContent = 'Reading a bounded, read-only reconciliation page…';
      api.postMessage({ type: 'inspectProjectReconciliation', target, offset: 0 });
    });
    document.getElementById('inspectEventArchive').addEventListener('click', () => {
      document.getElementById('eventArchiveStatus').textContent = 'Reading eligible processed receipts…';
      document.getElementById('eventArchiveProposal').replaceChildren();
      api.postMessage({ type: 'inspectEventArchive', offset: 0 });
    });
    document.getElementById('retryPendingPurges').addEventListener('click', () => {
      document.getElementById('retryPendingPurges').disabled = true;
      document.getElementById('purgeRetryStatus').textContent = 'Waiting for attended confirmation…';
      api.postMessage({ type: 'retryPendingPurges' });
    });
    document.getElementById('inspectPurgeReceipt').addEventListener('click', () => {
      document.getElementById('inspectPurgeReceipt').disabled = true;
      const receiptId = document.getElementById('purgeReceiptId').value;
      document.getElementById('purgeReceiptTargets').replaceChildren();
      document.getElementById('purgeReceiptStatus').textContent = 'Reading the project-bound cleanup receipt…';
      api.postMessage({ type: 'inspectPurgeReceipt', receiptId });
    });
    document.getElementById('openReviewActions').addEventListener('click', () => {
      api.postMessage({ type: 'openPendingReview' });
    });
    document.getElementById('previousGoals').addEventListener('click', () => requestGoals(Math.max(0, goalOffset - ${GOAL_PAGE_SIZE})));
    document.getElementById('nextGoals').addEventListener('click', () => requestGoals(goalOffset + ${GOAL_PAGE_SIZE}));
    document.getElementById('previousFacts').addEventListener('click', () => requestReport(Math.max(0, factOffset - ${REPORT_PAGE_SIZE})));
    document.getElementById('nextFacts').addEventListener('click', () => requestReport(factOffset + ${REPORT_PAGE_SIZE}));
    renderHealthHistory();
    window.addEventListener('message', (event) => {
      const message = event.data;
      if (message.type === 'reloadGoals') {
        requestGoals(0);
        return;
      }
      if (message.type === 'queueViewsRefreshResult') {
        document.getElementById('refreshQueueViews').disabled = false;
        const status = message.status || {};
        const labels = [
          ['proposal JSON', status.reviewQueueUpdated],
          ['pending-review.md', status.reviewDocumentUpdated],
          ['inbox/status.json', status.inboxUpdated],
        ].map(([label, current]) => label + ': ' + (current ? 'current' : 'not confirmed'));
        labels.push('review editor: ' + (status.reviewEditorOpen
          ? status.reviewBufferUpdated ? 'synchronized' : 'not confirmed'
          : 'not open'));
        document.getElementById('queueViewsStatus').textContent = labels.join(' · ');
        updateProjectionComponentRow(status);
        return;
      }
      if (message.type === 'healthHistoryReset') {
        document.getElementById('resetHealthHistory').disabled = false;
        if (message.success !== true) {
          document.getElementById('healthHistoryResetStatus').textContent = message.cancelled
            ? 'History reset cancelled; saved samples were kept.'
            : 'History reset could not be verified; saved samples may still be present.';
          return;
        }
        healthHistory = [];
        if (typeof api.setState === 'function') {
          api.setState({ projectId: healthHistoryProjectId, healthHistoryScope, healthHistory });
        }
        renderHealthHistory();
        document.getElementById('healthHistoryResetStatus').textContent = 'Saved samples cleared; requesting a fresh health check…';
        healthHistoryResetAwaitingFreshCheck = true;
        healthHistoryResetRetryCount = 0;
        healthRefreshInFlight = true;
        api.postMessage({ type: 'refreshHealth' });
        return;
      }
      if (message.type === 'healthHistoryResetSkipped') {
        document.getElementById('resetHealthHistory').disabled = false;
        document.getElementById('healthHistoryResetStatus').textContent = message.reason;
        return;
      }
      if (message.type === 'error') {
        healthRefreshInFlight = false;
        document.getElementById('refresh').disabled = false;
        document.getElementById('refreshQueueViews').disabled = false;
        document.getElementById('runEventRouter').disabled = true;
        document.getElementById('retryPendingPurges').disabled = true;
        document.getElementById('inspectPurgeReceipt').disabled = true;
        activeProjectId = null;
        clearDashboard();
        document.getElementById('queueViewsStatus').textContent = message.message;
        error.textContent = message.message;
        return;
      }
      error.textContent = '';
      if (message.type === 'eventRouterResult') {
        document.getElementById('runEventRouter').disabled = false;
        document.getElementById('eventRouterStatus').textContent = message.summary;
        return;
      }
      if (message.type === 'projectReconciliationLoading') {
        document.getElementById('projectReconciliationResult').replaceChildren();
        document.getElementById('projectReconciliationStatus').textContent =
          'Reading ' + message.target + ' at goal offset ' + message.offset + '…';
        return;
      }
      if (message.type === 'projectReconciliationError') {
        document.getElementById('projectReconciliationStatus').textContent = message.message;
        document.getElementById('projectReconciliationResult').replaceChildren();
        return;
      }
      if (message.type === 'projectionRepairResult') {
        document.getElementById('projectReconciliationStatus').textContent = message.summary;
        return;
      }
      if (message.type === 'projectReconciliationResult') {
        const result = message.reconciliation;
        const target = document.getElementById('projectReconciliationResult');
        target.replaceChildren();
        const counts = { synced: 0, missing: 0, divergent: 0, malformed: 0 };
        for (const goal of result.goals) counts[goal.status] += 1;
        document.getElementById('projectReconciliationStatus').textContent =
          message.target + ' · goals ' + result.offset + '–'
          + (result.offset + result.goals.length) + ' of ' + result.totalGoals
          + ' · synced ' + counts.synced + ', missing ' + counts.missing
          + ', divergent ' + counts.divergent + ', malformed ' + counts.malformed
          + ' · scanned ' + result.scannedBytes + ' bytes'
          + (result.inventoryComplete ? '.' : ' · marker inventory incomplete.');
        const table = document.createElement('table');
        table.className = 'metric-table';
        const head = document.createElement('thead');
        const heading = document.createElement('tr');
        for (const label of ['Goal', 'Projection state', 'Expected SHA-256', 'Actual SHA-256', 'Recovery']) {
          const cell = document.createElement('th');
          cell.scope = 'col';
          cell.textContent = label;
          heading.appendChild(cell);
        }
        head.appendChild(heading);
        table.appendChild(head);
        const body = document.createElement('tbody');
        for (const goal of result.goals) {
          const row = document.createElement('tr');
          row.dataset.state = goal.status === 'synced' ? 'healthy'
            : goal.status === 'missing' ? 'warning' : 'degraded';
          for (const value of [goal.goalId, goal.status,
            goal.expectedSha256.slice(0, 16), goal.actualSha256?.slice(0, 16) || 'missing']) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
          }
          const actionCell = document.createElement('td');
          if (goal.status === 'missing') {
            const restore = document.createElement('button');
            restore.textContent = 'Restore missing block…';
            restore.addEventListener('click', () => {
              document.getElementById('projectReconciliationStatus').textContent =
                'Checking that the exact goal block is still missing…';
              api.postMessage({
                type: 'restoreMissingProjection', target: message.target,
                goalId: goal.goalId, expectedSha256: goal.expectedSha256,
                offset: result.offset,
              });
            });
            actionCell.appendChild(restore);
          } else {
            actionCell.textContent = goal.status === 'synced' ? '—'
              : 'Owner-reviewed recovery required';
          }
          row.appendChild(actionCell);
          body.appendChild(row);
        }
        table.appendChild(body);
        target.appendChild(table);
        const addDigestList = (label, digests, omittedCount = 0) => {
          if (digests.length === 0 && omittedCount === 0) return;
          const paragraph = document.createElement('p');
          paragraph.textContent = label + ': ' + digests.slice(0, 8)
            .map((digest) => digest.slice(0, 16)).join(', ')
            + (digests.length > 8 ? ' …' : '')
            + (omittedCount > 0 ? '; ' + omittedCount + ' additional marker(s) not listed' : '');
          target.appendChild(paragraph);
        };
        addDigestList('Orphan marker SHA-256', result.orphanMarkerSha256);
        addDigestList('Malformed marker SHA-256', result.malformedMarkerSha256,
          result.malformedMarkerCount - result.malformedMarkerSha256.length);
        if (result.unrecognizedMarkerCount > 0) {
          const note = document.createElement('p');
          note.textContent = result.unrecognizedMarkerCount + ' unrecognized managed marker(s) were found.';
          target.appendChild(note);
        }
        const pageControls = document.createElement('p');
        if (result.offset > 0) {
          const previous = document.createElement('button');
          previous.textContent = 'Previous reconciliation page';
          previous.addEventListener('click', () => api.postMessage({
            type: 'inspectProjectReconciliation', target: message.target,
            offset: Math.max(0, result.offset - result.limit),
          }));
          pageControls.appendChild(previous);
        }
        if (result.nextOffset !== null) {
          const next = document.createElement('button');
          next.textContent = 'Next reconciliation page';
          next.addEventListener('click', () => api.postMessage({
            type: 'inspectProjectReconciliation', target: message.target,
            offset: result.nextOffset,
          }));
          pageControls.appendChild(next);
        }
        target.appendChild(pageControls);
        return;
      }
      if (message.type === 'eventArchiveLoading') {
        document.getElementById('eventArchiveStatus').textContent = 'Reading eligible processed receipts…';
        document.getElementById('eventArchiveProposal').replaceChildren();
        return;
      }
      if (message.type === 'eventArchiveError') {
        document.getElementById('eventArchiveStatus').textContent = message.message;
        document.getElementById('eventArchiveProposal').replaceChildren();
        return;
      }
      if (message.type === 'eventArchiveResult') {
        document.getElementById('eventArchiveStatus').textContent = message.summary;
        if (message.success) requestGoals(0, true);
        return;
      }
      if (message.type === 'eventArchiveProposal') {
        const proposal = message.proposal;
        const target = document.getElementById('eventArchiveProposal');
        target.replaceChildren();
        const first = proposal.items.length ? proposal.offset + 1 : 0;
        const last = proposal.offset + proposal.items.length;
        document.getElementById('eventArchiveStatus').textContent =
          'Eligible processed receipts ' + first + '–' + last + ' of '
          + proposal.eligibleCount + '; inventory ' + proposal.manifestSha256 + '.';
        if (proposal.items.length) {
          const table = document.createElement('table');
          table.className = 'metric-table';
          const head = document.createElement('thead');
          const header = document.createElement('tr');
          for (const label of ['Event ID', 'Type', 'Received', 'Processed', 'Attempts', 'Retry audits', 'Dispositions', 'Drain refs', 'Payload SHA-256']) {
            const cell = document.createElement('th');
            cell.scope = 'col';
            cell.textContent = label;
            header.appendChild(cell);
          }
          head.appendChild(header);
          table.appendChild(head);
          const body = document.createElement('tbody');
          for (const item of proposal.items) {
            const row = document.createElement('tr');
            row.dataset.state = 'neutral';
            const values = [item.eventId, item.eventType, item.receivedAt, item.processedAt,
              String(item.attempts), String(item.retryAuditCount),
              String(item.terminalDispositionCount), String(item.consumerDrainReferenceCount),
              item.payloadSha256];
            for (const value of values) {
              const cell = document.createElement('td');
              cell.textContent = value;
              row.appendChild(cell);
            }
            body.appendChild(row);
          }
          table.appendChild(body);
          target.appendChild(table);
          const archive = document.createElement('button');
          archive.type = 'button';
          archive.textContent = 'Archive this exact page…';
          archive.addEventListener('click', () => {
            document.getElementById('eventArchiveStatus').textContent = 'Checking this exact archive proposal…';
            api.postMessage({
              type: 'archiveEventReceiptPage',
              offset: proposal.offset,
              manifestSha256: proposal.manifestSha256,
              eventIds: proposal.items.map((item) => item.eventId),
            });
          });
          target.appendChild(archive);
        } else {
          target.textContent = 'No eligible processed receipts on this page. Failed, quarantined, active, and unknown events are retained.';
        }
        if (proposal.offset + proposal.items.length < proposal.eligibleCount) {
          const next = document.createElement('button');
          next.type = 'button';
          next.textContent = 'Next receipt page';
          next.addEventListener('click', () => {
            document.getElementById('eventArchiveStatus').textContent = 'Reading the next eligible receipt page…';
            target.replaceChildren();
            api.postMessage({
              type: 'inspectEventArchive',
              offset: proposal.offset + proposal.items.length,
            });
          });
          target.appendChild(next);
        }
        return;
      }
      if (message.type === 'terminalEventLoading') {
        document.getElementById('terminalEventStatus').textContent = 'Reading failed and quarantined event inventory…';
        document.getElementById('terminalEventInventory').replaceChildren();
        return;
      }
      if (message.type === 'terminalEventError') {
        document.getElementById('terminalEventStatus').textContent = message.message;
        document.getElementById('terminalEventInventory').replaceChildren();
        return;
      }
      if (message.type === 'terminalEventRetryResult') {
        document.getElementById('terminalEventStatus').textContent = message.summary;
        if (message.success) requestGoals(0, true);
        return;
      }
      if (message.type === 'terminalEventInventory') {
        const inventory = message.inventory;
        const eventTarget = document.getElementById('terminalEventInventory');
        eventTarget.replaceChildren();
        document.getElementById('terminalEventStatus').textContent =
          inventory.events.length + ' event(s) shown; '
          + inventory.countAfterCursor + ' after this cursor; '
          + (inventory.complete ? 'inventory complete.' : 'more events are available.');
        if (!inventory.events.length) {
          eventTarget.textContent = 'No failed or quarantined events remain on this page.';
        } else {
          const table = document.createElement('table');
          table.className = 'metric-table';
          const head = document.createElement('thead');
          const header = document.createElement('tr');
          for (const label of ['Event ID', 'State', 'Source', 'Sequence', 'Payload SHA-256', 'Action']) {
            const cell = document.createElement('th');
            cell.scope = 'col';
            cell.textContent = label;
            header.appendChild(cell);
          }
          head.appendChild(header);
          table.appendChild(head);
          const body = document.createElement('tbody');
          for (const item of inventory.events) {
            const row = document.createElement('tr');
            row.dataset.state = item.status === 'quarantined' ? 'degraded' : 'warning';
            for (const value of [item.eventId, item.status, item.sourceId,
              item.sourceSequence === null ? 'unknown' : String(item.sourceSequence),
              item.payloadSha256]) {
              const cell = document.createElement('td');
              cell.textContent = value;
              row.appendChild(cell);
            }
            const action = document.createElement('td');
            if (item.status === 'quarantined') {
              const retry = document.createElement('button');
              retry.type = 'button';
              retry.textContent = 'Retry…';
              retry.addEventListener('click', () => {
                retry.disabled = true;
                document.getElementById('terminalEventStatus').textContent =
                  'Checking this exact quarantined event…';
                api.postMessage({
                  type: 'retryQuarantinedEvent',
                  eventId: item.eventId,
                  payloadSha256: item.payloadSha256,
                  afterEventId: message.afterEventId || null,
                });
              });
              action.appendChild(retry);
            } else {
              action.textContent = 'Automatic retry state';
            }
            row.appendChild(action);
            body.appendChild(row);
          }
          table.appendChild(body);
          eventTarget.appendChild(table);
        }
        if (!inventory.complete && inventory.nextAfterEventId) {
          const next = document.createElement('button');
          next.type = 'button';
          next.textContent = 'Next event page';
          next.addEventListener('click', () => {
            document.getElementById('terminalEventStatus').textContent = 'Reading the next event page…';
            eventTarget.replaceChildren();
            api.postMessage({
              type: 'inspectTerminalEvents', afterEventId: inventory.nextAfterEventId,
            });
          });
          eventTarget.appendChild(next);
        }
        return;
      }
      if (message.type === 'purgeRetryResult') {
        const retryButton = document.getElementById('retryPendingPurges');
        retryButton.disabled = false;
        document.getElementById('purgeRetryStatus').textContent = message.summary;
        if (message.success) requestGoals(0, true);
        return;
      }
      if (message.type === 'purgeReceiptLoading') {
        document.getElementById('purgeReceiptStatus').textContent = 'Reading receipt ' + message.receiptId + '…';
        document.getElementById('purgeReceiptTargets').replaceChildren();
        return;
      }
      if (message.type === 'purgeReceiptError') {
        document.getElementById('inspectPurgeReceipt').disabled = false;
        document.getElementById('purgeReceiptStatus').textContent = message.message;
        document.getElementById('purgeReceiptTargets').replaceChildren();
        return;
      }
      if (message.type === 'purgeReceiptHoldResult') {
        document.getElementById('purgeReceiptStatus').textContent = message.summary;
        if (message.success) {
          const targets = document.getElementById('purgeReceiptTargets');
          targets.replaceChildren();
          targets.textContent = 'Receipt state changed. Inspect it again for current artifact details.';
          requestGoals(0, true);
        } else {
          document.getElementById('inspectPurgeReceipt').disabled = false;
        }
        return;
      }
      if (message.type === 'purgeReceiptInspection') {
        document.getElementById('inspectPurgeReceipt').disabled = false;
        const summary = message.summary;
        const target = document.getElementById('purgeReceiptTargets');
        target.replaceChildren();
        document.getElementById('purgeReceiptStatus').textContent =
          'Receipt ' + summary.receiptId + ' · ' + summary.purgeStatus
          + ' · canonical persistence ' + (summary.canonicalPersisted ? 'confirmed' : 'not confirmed')
          + ' · cleanup authorization ' + (summary.cleanupAuthorized ? 'confirmed' : 'not confirmed')
          + ' · cleanup projection ' + (summary.cleanupCanonicalPersisted ? 'confirmed' : 'not confirmed')
          + ' · ' + summary.targetCount + ' artifact(s).';
        if (!summary.targets.length) {
          target.textContent = 'This receipt has no per-artifact cleanup targets.';
          return;
        }
        const table = document.createElement('table');
        table.className = 'metric-table';
        const head = document.createElement('thead');
        const header = document.createElement('tr');
        for (const label of ['Artifact', 'State', 'Outcome', 'Attempts', 'Next retry', 'Safe next action', 'Action']) {
          const cell = document.createElement('th');
          cell.scope = 'col';
          cell.textContent = label;
          header.appendChild(cell);
        }
        head.appendChild(header);
        table.appendChild(head);
        const body = document.createElement('tbody');
        for (const item of summary.targets) {
          const row = document.createElement('tr');
          row.dataset.state = item.status === 'failed' ? 'degraded'
            : item.status === 'held' || item.status === 'pending' ? 'warning' : 'healthy';
          const values = [item.path, item.status, item.outcome, String(item.attempts),
            item.nextAttemptInSeconds === null ? 'not scheduled' : item.nextAttemptInSeconds + 's',
            item.nextAction + (item.approvalStale ? ' · approval stale' : '')
              + (item.error ? ' · ' + item.error : '')];
          for (const [index, value] of values.entries()) {
            const cell = document.createElement(index === 0 ? 'th' : 'td');
            if (index === 0) cell.scope = 'row';
            cell.textContent = value;
            row.appendChild(cell);
          }
          const actionCell = document.createElement('td');
          if (item.status === 'held' && item.nextAction === 'release_artifact_hold'
            && !item.approvalStale) {
            const releaseButton = document.createElement('button');
            releaseButton.type = 'button';
            releaseButton.textContent = 'Release hold…';
            releaseButton.addEventListener('click', () => {
              releaseButton.disabled = true;
              document.getElementById('purgeReceiptStatus').textContent = 'Checking the current receipt before hold release…';
              api.postMessage({
                type: 'releaseArtifactHold',
                receiptId: summary.receiptId,
                artifactPath: item.path,
              });
            });
            actionCell.appendChild(releaseButton);
          } else {
            actionCell.textContent = '—';
          }
          row.appendChild(actionCell);
          body.appendChild(row);
        }
        table.appendChild(body);
        target.appendChild(table);
        if (summary.omittedTargetCount > 0) {
          const omitted = document.createElement('p');
          omitted.textContent = summary.omittedTargetCount + ' additional target(s) omitted from this view.';
          target.appendChild(omitted);
        }
        return;
      }
      if (message.type === 'healthSnapshot') {
        healthRefreshInFlight = false;
        activeProjectId = message.projectId;
        loadPersistentHealthHistory(
          message.projectId,
          message.healthHistory,
          message.healthHistoryPersisted,
          message.healthHistoryScope,
        );
        const resetStatus = document.getElementById('healthHistoryResetStatus');
        if (healthHistoryResetAwaitingFreshCheck) {
          const latest = Array.isArray(message.healthHistory) ? message.healthHistory.at(-1) : null;
          if (latest) {
            healthHistoryResetAwaitingFreshCheck = false;
            resetStatus.textContent = 'Reset complete; fresh ' + latest.status + ' check saved.';
          } else if (healthHistoryResetRetryCount < 1) {
            healthHistoryResetRetryCount += 1;
            resetStatus.textContent = 'The in-flight check began before the reset; requesting one fresh check…';
            healthRefreshInFlight = true;
            api.postMessage({ type: 'refreshHealth' });
          } else {
            healthHistoryResetAwaitingFreshCheck = false;
            resetStatus.textContent = 'Reset complete; no fresh health sample was available.';
          }
        }
        renderHealthSnapshot(message.health, message.projectId, message);
        return;
      }
      if (message.type === 'healthRefreshSkipped') {
        healthRefreshInFlight = false;
        return;
      }
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
        document.getElementById('refresh').disabled = false;
        const page = message.page;
        activeProjectId = page.project_id;
        const healthSnapshot = message.health;
        const activitySnapshot = message.activity;
        loadPersistentHealthHistory(
          page.project_id,
          message.healthHistory,
          message.healthHistoryPersisted,
          message.healthHistoryScope,
        );
        let alertText = typeof message.alertSummary === 'string'
          ? message.alertSummary : 'Operational alerts: unknown. Alert summary unavailable.';
        if (message.workspaceViewsUpdated === false) {
          alertText += ' Local inbox or review files could not be refreshed, or the review document has unsaved edits; database reads remain available.';
        }
        renderHealthSnapshot(healthSnapshot, page.project_id, { ...message, alertSummary: alertText });
        document.getElementById('retryPendingPurges').disabled = !message.reviewAvailable;
        document.getElementById('runEventRouter').disabled = !message.reviewAvailable;
        document.getElementById('inspectPurgeReceipt').disabled = false;
        const queueFailure = typeof message.queueProbeFailure === 'string'
          ? message.queueProbeFailure : null;
        queueSummary.textContent = (typeof message.queueSummary === 'string'
          ? message.queueSummary : 'Operational queues: unknown. Curator snapshot unavailable.')
          + (queueFailure ? ' ' + queueFailure : '')
          + ' ' + formatSnapshotCheck(message.queueCheckedAt);
        setPanelState('queues', ['healthy', 'review', 'warning', 'degraded', 'unknown']
          .includes(message.queueState) ? message.queueState : 'unknown');
        renderMetricRows('queueRows', Array.isArray(message.queueRows)
          ? message.queueRows : [{ label: 'Queue snapshot', value: 'Unavailable or invalid', state: 'unknown' }]);
        const goalStatesText = typeof message.goalStatesSummary === 'string'
          ? message.goalStatesSummary : 'Goal states unavailable.';
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
          setPanelState('activity', 'unknown');
          renderMetricRows('activityRows', [{ label: 'Activity snapshot', value: 'Unavailable', state: 'unknown' }]);
        } else if (activitySnapshot.project_id !== page.project_id) {
          activitySummary.textContent = 'Retained activity: unknown. Project mismatch.';
          setPanelState('activity', 'unknown');
          renderMetricRows('activityRows', [{ label: 'Activity snapshot', value: 'Project mismatch', state: 'unknown' }]);
        } else if (!activityValid) {
          activitySummary.textContent = 'Retained activity: unknown. Invalid activity snapshot.';
          setPanelState('activity', 'unknown');
          renderMetricRows('activityRows', [{ label: 'Activity snapshot', value: 'Invalid snapshot', state: 'unknown' }]);
        } else {
          activitySummary.textContent = 'Retained activity: ' + activitySnapshot.event_receipt_count
            + ' ' + (activitySnapshot.event_receipt_count === 1 ? 'receipt' : 'receipts')
            + ' · ' + countLabel(activitySnapshot.goal_count, 'goal') + ' · '
            + countLabel(activitySnapshot.fact_count, 'fact') + '.';
          setPanelState('activity', activitySnapshot.pending_sde_count ? 'review' : 'neutral');
          const countState = activitySnapshot.pending_sde_count ? 'review' : 'neutral';
          renderMetricRows('activityRows', [
            { label: 'SDE candidates', value: 'Pending ' + activitySnapshot.pending_sde_count + ' · Approved ' + activitySnapshot.approved_sde_count + ' · Rejected ' + activitySnapshot.rejected_sde_count, state: countState },
            { label: 'Goal states', value: goalStatesText.replace(/^Goal states:\s*/, ''), state: 'neutral' },
            { label: 'Receipts', value: activitySnapshot.event_receipt_count, state: 'neutral' },
            { label: 'Processed', value: activitySnapshot.processed_event_count, state: 'healthy' },
            { label: 'Received', value: activitySnapshot.received_event_count, state: activitySnapshot.received_event_count ? 'review' : 'healthy' },
            { label: 'Failed', value: activitySnapshot.failed_event_count, state: activitySnapshot.failed_event_count ? 'degraded' : 'healthy' },
            { label: 'Quarantined', value: activitySnapshot.quarantined_event_count, state: activitySnapshot.quarantined_event_count ? 'degraded' : 'healthy' },
            { label: 'Goals', value: activitySnapshot.goal_count, state: 'neutral' },
            { label: 'Facts', value: activitySnapshot.fact_count, state: 'neutral' },
          ]);
        }
        const storageSnapshot = message.storage;
        const expectedFilesystemLabels = ['Workspace filesystem', 'SQLite filesystem'];
        const hostFilesystemRows = expectedFilesystemLabels.map((label, index) => {
          const row = Array.isArray(message.hostFilesystemRows)
            ? message.hostFilesystemRows[index] : null;
          return row && row.label === label && typeof row.value === 'string'
            && row.value.length <= 256
            && ['healthy', 'warning', 'unknown'].includes(row.state)
            && typeof row.stateLabel === 'string' && row.stateLabel.length <= 80
            ? { label, value: row.value, state: row.state, stateLabel: row.stateLabel }
            : { label, value: 'Filesystem capacity unavailable', state: 'unknown', stateLabel: 'Unknown' };
        });
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
          setPanelState('storage', 'unknown');
          renderMetricRows('storageRows', [
            { label: 'Storage snapshot', value: 'Unavailable', state: 'unknown' },
            ...hostFilesystemRows,
          ]);
        } else if (storageSnapshot.project_id !== page.project_id) {
          storageSummary.textContent = 'Storage usage: unknown. Project mismatch.';
          setPanelState('storage', 'unknown');
          renderMetricRows('storageRows', [
            { label: 'Storage snapshot', value: 'Project mismatch', state: 'unknown' },
            ...hostFilesystemRows,
          ]);
        } else if (!storageValid) {
          storageSummary.textContent = 'Storage usage: unknown. Invalid storage snapshot.';
          setPanelState('storage', 'unknown');
          renderMetricRows('storageRows', [
            { label: 'Storage snapshot', value: 'Invalid snapshot', state: 'unknown' },
            ...hostFilesystemRows,
          ]);
        } else {
          const stagingLimit = storageSnapshot.staging_project_byte_limit;
          const sqliteBytes = storageSnapshot.global_database_bytes === null
            || storageSnapshot.global_wal_bytes === null
            ? null : storageSnapshot.global_database_bytes + storageSnapshot.global_wal_bytes;
          const sqliteState = sqliteBytes === null
            ? 'unknown' : sqliteBytes > ${SQLITE_WARNING_BYTES} ? 'warning' : 'healthy';
          const stagingState = !stagingSnapshot.inventory_complete
            ? 'unknown'
            : stagingLimit === null ? 'neutral'
              : stagingSnapshot.observed_file_bytes >= stagingLimit * 0.75 ? 'warning' : 'healthy';
          const hostDiskState = hostFilesystemRows.some((row) => row.state === 'warning')
            ? 'warning' : hostFilesystemRows.some((row) => row.state === 'unknown')
              ? 'unknown' : 'healthy';
          const storageState = sqliteState === 'warning' || stagingState === 'warning'
            || hostDiskState === 'warning'
            ? 'warning'
            : sqliteState === 'unknown' || stagingState === 'unknown'
              || hostDiskState === 'unknown' ? 'unknown' : 'healthy';
          storageSummary.textContent = 'SQLite ' + formatBytes(sqliteBytes)
            + ' · staging ' + formatBytes(stagingSnapshot.observed_file_bytes)
            + ' · workspace free ' + hostFilesystemRows[0].value
            + (stagingSnapshot.inventory_complete ? '' : ' or more; scan incomplete');
          setPanelState('storage', storageState);
          renderMetricRows('storageRows', [
            { label: 'Project logical records', value: formatBytes(storageSnapshot.logical_record_bytes), state: 'neutral' },
            { label: 'Retained event payload', value: formatBytes(storageSnapshot.event_payload_bytes_retained), state: 'neutral' },
            { label: 'Facts', value: storageSnapshot.fact_count + ' / ' + storageSnapshot.fact_count_limit, state: 'neutral' },
            { label: 'Fact record bytes', value: formatBytes(storageSnapshot.fact_record_bytes) + ' / ' + formatBytes(storageSnapshot.fact_record_bytes_limit), state: 'neutral' },
            { label: 'SQLite database', value: formatBytes(storageSnapshot.global_database_bytes), state: storageSnapshot.global_database_bytes === null ? 'unknown' : 'neutral' },
            { label: 'SQLite WAL', value: formatBytes(storageSnapshot.global_wal_bytes), state: storageSnapshot.global_wal_bytes === null ? 'unknown' : 'neutral' },
            { label: 'SQLite combined', value: formatBytes(sqliteBytes) + ' / ' + formatBytes(${SQLITE_WARNING_BYTES}), state: sqliteState, stateLabel: sqliteState === 'warning' ? 'Warning · writes allowed' : sqliteState === 'healthy' ? 'Below threshold' : 'Unknown' },
            { label: 'Staging files', value: stagingSnapshot.inventory_complete
              ? formatBytes(stagingSnapshot.observed_file_bytes) + (stagingLimit === null ? '' : ' / ' + formatBytes(stagingLimit))
              : 'At least ' + formatBytes(stagingSnapshot.observed_file_bytes) + ' · ' + stagingSnapshot.error_code,
            state: stagingState,
            stateLabel: stagingState === 'warning' ? 'Warning · writes allowed'
              : stagingState === 'unknown' ? 'Incomplete scan'
                : stagingLimit === null ? 'No threshold' : 'Below threshold' },
            { label: 'Model/token usage', value: 'Not reported', state: 'neutral' },
            ...hostFilesystemRows,
          ]);
        }
        goalTotal = page.total || 0;
        goalOffset = page.offset || 0;
        document.getElementById('goalPage').textContent = 'Goals ' + (goalTotal ? goalOffset + 1 : 0) + '–' + Math.min(goalOffset + (page.goals || []).length, goalTotal) + ' of ' + goalTotal;
        goals.replaceChildren();
        for (const goal of page.goals || []) {
          const button = document.createElement('button');
          button.className = 'goal-card';
          const title = document.createElement('span');
          title.className = 'goal-title';
          title.textContent = String(goal.problem || '')
            .replace(/\\b[0-9a-f]{8}-[0-9a-f-]{27,}\\b/gi, '')
            .replace(/^\\s*(?:planned|active|complete|open|blocked|deferred|cancelled|superseded)\\s*:\\s*/i, '')
            .replace(/\\bScheduled ACME renewal operation\\b/gi, '')
            .replace(/\\s+/g, ' ').replace(/\\s+([,.;:])/g, '$1').trim();
          const disposition = document.createElement('span');
          disposition.className = 'goal-disposition';
          const state = document.createElement('span');
          state.className = 'goal-state';
          state.textContent = 'Disposition: ' + goal.status;
          disposition.appendChild(state);
          const updatedAt = document.createElement('time');
          updatedAt.className = 'goal-updated';
          updatedAt.textContent = formatGoalUpdate(goal.updated_at);
          if (typeof goal.updated_at === 'string' && goal.updated_at.length <= 64) {
            updatedAt.setAttribute('datetime', goal.updated_at);
          }
          disposition.appendChild(updatedAt);
          if (goal.next_action) {
            const nextAction = document.createElement('span');
            nextAction.className = 'goal-next-action';
            nextAction.textContent = 'Next: ' + goal.next_action;
            disposition.appendChild(nextAction);
          }
          button.appendChild(title);
          button.appendChild(disposition);
          button.addEventListener('click', () => {
            selectedGoal = goal.goal_id;
            factOffset = 0;
            factTotal = 0;
            reportRevision = null;
            document.getElementById('selected').textContent = goal.problem;
            document.getElementById('reopenGoal').hidden = goal.status !== 'complete';
            requestReport(0);
          });
          goals.appendChild(button);
        }
        if (reopenGoalAfterRefresh) {
          const reopenedGoal = (page.goals || []).find(
            (goal) => goal.goal_id === reopenGoalAfterRefresh,
          );
          const reopenedId = reopenGoalAfterRefresh;
          reopenGoalAfterRefresh = null;
          if (reopenedGoal && reopenedGoal.status === 'active') {
            selectedGoal = reopenedId;
            document.getElementById('selected').textContent = reopenedGoal.problem;
            document.getElementById('reopenGoal').hidden = true;
            document.getElementById('actionStatus').textContent =
              'Task reopened. Prior facts remain in history; earlier verification is historical.';
            requestReport(0);
          } else {
            document.getElementById('actionStatus').textContent =
              'Reopen was submitted, but the refreshed page did not confirm an active task. Review the current task state.';
          }
        }
        reviews.replaceChildren();
        if (!Array.isArray(message.reviews)) {
          reviewSummary.textContent = 'Review queue: unavailable. Goal browsing remains available.';
        } else if (!message.reviews.length) {
          reviewSummary.textContent = 'No pending SDE candidates. Complete a tracked goal with current passing evidence, then request historical SDE assessment to prepare a proposal for owner review.';
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
            row.appendChild(label);
            for (const decision of ['approve', 'reject']) {
              const button = document.createElement('button');
              button.textContent = decision === 'approve' ? 'Accept' : 'Reject';
              button.title = 'Review and confirm in VS Code; no terminal is opened.';
              button.disabled = !message.reviewAvailable;
              button.addEventListener('click', () => api.postMessage({
                type: 'openReview', candidateId: candidate.candidate_id, decision,
              }));
              row.appendChild(button);
            }
            reviews.appendChild(row);
          }
          if (!message.reviewAvailable) {
            reviewSummary.textContent += ' Configure the Curator project, profile, database, and server in User settings; an invalid evidence binding also blocks review.';
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
        renderEvidence(message.evidence, message.displayStatus);
      } else if (message.type === 'goalReopened' && message.goalId === selectedGoal) {
        reopenGoalAfterRefresh = message.goalId;
        document.getElementById('actionStatus').textContent = 'Reopen saved. Refreshing the task and report…';
        requestGoals(goalOffset);
      }
    });
    // Opening the dashboard is an explicit retry after the status item points
    // the owner here from a paused health or queue feed.
    requestGoals(0, true);
    if (typeof window.setInterval === 'function') {
      const healthMonitorTimer = window.setInterval(() => {
        if (!activeProjectId || healthRefreshInFlight || document.getElementById('refresh').disabled) return;
        healthRefreshInFlight = true;
        api.postMessage({ type: 'refreshHealth' });
      }, ${STATUS_REFRESH_INTERVAL_MS});
      if (typeof window.addEventListener === 'function'
        && typeof window.clearInterval === 'function') {
        window.addEventListener('unload', () => window.clearInterval(healthMonitorTimer));
      }
    }
    if (${JSON.stringify(focusReviews)}) {
      document.getElementById('reviewsSection').scrollIntoView();
    }
    if (${JSON.stringify(focusRecovery)}) {
      document.getElementById('recoveryToolbox').scrollIntoView();
      document.getElementById('retryRecoveryReads').focus();
    }
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

function defaultRouterCommand(serverCommand) {
  if (path.basename(serverCommand) === 'curatormd-v2-mcp') {
    return path.join(path.dirname(serverCommand), 'curatormd-v2-router');
  }
  return 'curatormd-v2-router';
}

function parseRouterPassResult(stdout, exitCode) {
  if (typeof stdout !== 'string' || Buffer.byteLength(stdout, 'utf8') > 32768
    || ![0, 1].includes(exitCode)) {
    throw curatorError('router-result-invalid', 'The event router did not return a bounded result.');
  }
  let value;
  try { value = JSON.parse(stdout); } catch (_) { value = null; }
  const fields = [
    'attempted', 'claim_lost', 'failed', 'processed', 'project_count',
    'pending', 'quarantined', 'claimed', 'expired_claims',
  ];
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.project_count !== 1
    || fields.some((field) => !Number.isSafeInteger(value[field]) || value[field] < 0)) {
    throw curatorError('router-result-invalid', 'The event router did not return valid project counts.');
  }
  return {
    exitCode,
    attempted: value.attempted,
    claimLost: value.claim_lost,
    failed: value.failed,
    processed: value.processed,
    pending: value.pending,
    quarantined: value.quarantined,
    claimed: value.claimed,
    expiredClaims: value.expired_claims,
  };
}

function runEventRouterPass(
  routerCommand, projectRoot, databasePath, spawnProcess = spawn, batchLimit = 100,
) {
  if (typeof routerCommand !== 'string' || !routerCommand.trim()
    || typeof projectRoot !== 'string' || !path.isAbsolute(projectRoot)
    || typeof databasePath !== 'string' || !path.isAbsolute(databasePath)
    || !Number.isSafeInteger(batchLimit) || batchLimit < 1 || batchLimit > 1000) {
    return Promise.reject(curatorError('router-config-invalid', 'The event router binding is invalid.'));
  }
  return new Promise((resolve, reject) => {
    let child;
    try {
      child = spawnProcess(routerCommand, [
        '--database', databasePath,
        '--project-root', projectRoot,
        '--batch-limit', String(batchLimit),
        '--route-events',
      ], {
        cwd: projectRoot,
        shell: false,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (_) {
      reject(curatorError('router-start', 'The project event router did not start.'));
      return;
    }
    let stdout = '';
    let outputTooLarge = false;
    child.stdout?.on('data', (chunk) => {
      if (outputTooLarge) return;
      const text = String(chunk);
      if (Buffer.byteLength(stdout + text, 'utf8') > 32768) {
        outputTooLarge = true;
        child.kill();
        return;
      }
      stdout += text;
    });
    child.stderr?.on('data', () => {});
    const timer = setTimeout(() => {
      child.kill();
      reject(curatorError('router-timeout', 'The bounded event routing pass timed out; refresh queues before retrying.'));
    }, 120000);
    child.once('error', () => {
      clearTimeout(timer);
      reject(curatorError('router-start', 'The project event router did not start.'));
    });
    child.once('close', (code) => {
      clearTimeout(timer);
      if (outputTooLarge) {
        reject(curatorError('router-result-invalid', 'The event router output exceeded its limit.'));
        return;
      }
      try { resolve(parseRouterPassResult(stdout.trim(), code)); } catch (error) { reject(error); }
    });
  });
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
      || !['implementation', 'decision', 'recovery', 'verified_lesson', 'routine'].includes(candidate.materiality)
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
  joinMarkdownParagraphLines,
  deactivate,
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
  resolveHermesProfileId,
  readConfiguredProjectId,
  resolveDatabasePath,
  resolveEvidenceConfig,
  dashboardErrorMessage,
  factEvidenceDisplayStatus,
  initializeWorkspaceAreas,
  summarizeGoalStates,
  summarizeEventFailureCategories,
  summarizeOperationalQueues,
  healthComponentRows,
  dashboardComponentRows,
  healthHistoryStatus,
  updatePersistentHealthHistory,
  hostFilesystemRows,
  parsePurgeReceiptInspection,
  parseTerminalEventInventory,
  parseEventCompactionProposal,
  parseProjectReconciliation,
  validateReconciliationTarget,
  queueMetricRows,
  queuePanelState,
  summarizeOperationalAlerts,
  hasWorkspaceSettingOverride,
  hostEvidenceConfigArguments,
  quotePosixShellArgument,
  registerDashboardReloader,
  reloadOpenDashboards,
  refreshReviewConsumers,
  showDashboard,
  statusColorMeaning,
  sqliteSizeWarning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  reviewDocumentActions,
  launchDocumentReview,
  validateReviewQueue,
  writeWorkspaceQueueViewsDetailed,
  workspaceQueueViewsConfirmResolved,
  readReviewOutlines,
  writePendingReviewDocument,
  writeWorkspaceQueueViews,
  notifyTransportClosed,
};
