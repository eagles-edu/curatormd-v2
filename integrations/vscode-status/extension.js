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
  'read-denied': 'Curator denied the project read; check its local project access grant.',
  'mcp-tool-error': 'Curator rejected the request; check the project grant and request details.',
  'mcp-request': 'Curator could not complete the project read; refresh to try again.',
  'invalid-response': 'Curator returned an unreadable response; check the local installation.',
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
  'feed-auto-paused': 'Automatic checks paused after three identical failures. Click CuratorMD V2 to retry.',
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
const HERMES_HEALTH_MAX_BYTES = 32768;
const MAX_HEALTH_PROBE_AGE_SECONDS = 60;
const MAX_HEALTH_PROBE_CLOCK_SKEW_SECONDS = 5;
const STATUS_REFRESH_INTERVAL_MS = 60000;
const MAX_IDENTICAL_FEED_FAILURES = 3;
const MAX_PROJECT_CONFIG_BYTES = 16 * 1024;
const PROJECT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SQLITE_WARNING_BYTES = 250 * 1024 * 1024;
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

function feedFailureMessage(code, lastFailureCode, autoPaused, messageForCode) {
  const reasonCode = typeof lastFailureCode === 'string' && lastFailureCode
    ? lastFailureCode : code;
  const reason = messageForCode(reasonCode);
  return autoPaused && reasonCode !== 'feed-auto-paused'
    ? `${reason} Automatic checks paused after three identical failures; click CuratorMD V2 to retry.`
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
let transportClosedAlertShown = false;
const feedRequestsInFlight = new Map();
const feedFailureStates = new Map();

function statusTooltip(message) {
  return `${STATUS_LABEL} ${EXTENSION_VERSION}. ${message}`;
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
        if (JSON.stringify(stableExisting) === JSON.stringify(stableValue)) return false;
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

function writeWorkspaceQueueViews(projectRoot, projectId, inbox, reviewWire, outlines = new Map()) {
  const inboxFields = [
    'received_count', 'failed_count', 'quarantined_count',
    'claimed_count', 'expired_claim_count',
  ];
  const normalizedReviews = validateReviewQueue(reviewWire, projectId);
  const inboxValid = Boolean(inbox && inboxFields.every((field) => Number.isSafeInteger(inbox[field]) && inbox[field] >= 0)
      && (inbox.oldest_pending_age_seconds === null
        || (Number.isSafeInteger(inbox.oldest_pending_age_seconds)
          && inbox.oldest_pending_age_seconds >= 0)));
  if (normalizedReviews !== null) writeWorkspaceProjection(projectRoot, 'sde-proposals/pending.json', {
    project_id: projectId,
    generated_at: new Date(Date.now() + (7 * 60 * 60 * 1000)).toISOString().replace('Z', '+07:00'),
    source: 'Curator V2 SQLite review queue',
    canonical: false,
    queue_limit: REVIEW_QUEUE_SIZE,
    may_be_truncated: normalizedReviews.length === REVIEW_QUEUE_SIZE,
    review_action: 'Open pending-review.md to select a candidate for attended review.',
    candidates: normalizedReviews,
  });
  const reviewDocumentUpdated = normalizedReviews !== null
    && writePendingReviewDocument(projectRoot, projectId, normalizedReviews, outlines);
  if (inboxValid) writeWorkspaceProjection(projectRoot, 'inbox/status.json', {
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
  return inboxValid && normalizedReviews !== null && reviewDocumentUpdated;
}

function writePendingReviewDocument(projectRoot, projectId, reviews, outlines = new Map()) {
  const directory = ensureWorkspaceArea(projectRoot, 'sde-proposals');
  const destination = path.join(directory, 'pending-review.md');
  const openDocument = vscode.workspace?.textDocuments?.find(
    (document) => document.uri?.fsPath === destination,
  );
  if (openDocument?.isDirty) return false;
  let previousDrafts = new Map();
  let existingContent = null;
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
    if (hash(parts.normalized) !== marker.checksum && hash(oldBody) !== marker.checksum) return false;
    const currentIds = new Set(reviews.map(({ candidate }) => candidate.candidate_id));
    const removedIds = [...parts.drafts.keys()].filter((id) => !currentIds.has(id));
    if (removedIds.some((id) => !reviewDraftMatchesProposal(existing, id, parts.drafts.get(id)))) {
      return false;
    }
    previousDrafts = new Map([...parts.drafts].filter(([id]) => currentIds.has(id)));
  } catch (error) { if (!error || error.code !== 'ENOENT') throw error; }
  const safe = (value) => value.replace(/[\r\n]+/g, ' ').replace(/[\\`*_{}\[\]#+!<>|~\-]/g, '\\$&');
  const pushWrapped = (text, firstPrefix = '', continuationPrefix = '') => {
    const words = text.trim().split(/\s+/);
    let line = firstPrefix;
    for (const word of words) {
      const separator = line === firstPrefix || line === continuationPrefix ? '' : ' ';
      if (line.length + separator.length + word.length > 78 && line !== firstPrefix) {
        lines.push(line);
        line = `${continuationPrefix}${word}`;
      } else {
        line += `${separator}${word}`;
      }
    }
    if (line !== firstPrefix) lines.push(line);
  };
  const pushField = (label, value) => pushWrapped(`${label}: ${value}`, '- ', '  ');
  const pushFacts = (facts, fallback) => {
    if (facts.length === 0) {
      pushWrapped(fallback, '  - ', '    ');
      return;
    }
    for (const fact of facts) pushWrapped(safe(fact.bullet), '  - ', '    ');
  };
  const lines = [
    '# Pending SDE reviews', '',
  ];
  pushWrapped(`Project: ${safe(projectId)}`);
  lines.push('');
  pushWrapped('Review each proposal and its editable JSON copy. Accept and Reject open the attended reviewer. Withdraw clears a proposal while retaining its source facts and receipt. Refresh evidence reopens the source task for a new proof pass, then withdraws the stale proposal; it does not accept or delete facts.');
  lines.push('');
  if (reviews.length === REVIEW_QUEUE_SIZE) {
    pushWrapped('Only the first 100 candidates are shown.');
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
      && outline.successful_completion_evidence_current === true
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
      for (const document of outline.persistence_documents) pushWrapped(`\`${safe(document)}\``, '  - ', '    ');
    } else {
      pushWrapped('Choose one or more configured persistence documents in the editable copy.', '  - ', '    ');
    }

    lines.push('', `### ${candidateNumber}. Task and outcomes`, '');
    pushField('Problem / plan task', safe(goal.problem));
    lines.push('- Completed successfully:');
    if (verifiedCompletion) {
      pushFacts(verificationFacts, 'No successful work is recorded.');
      pushWrapped('The attended reviewer checks the current evidence before acceptance.', '  - ', '    ');
    } else {
      pushFacts([], 'No current passing verification supports a successful-completion claim.');
      if (taskSummaries.length > 0) {
        lines.push('- Completed task work, with verification still open:');
        pushFacts(taskSummaries, 'No task summary is recorded.');
      }
      for (const fact of verificationFacts) {
        pushWrapped(`Recorded verification, not current proof: ${safe(fact.bullet)}`, '  - ', '    ');
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
      if (changeFacts.length > 8) pushWrapped('Additional change facts are available in the attended review.', '  - ', '    ');
    }
    lines.push('', `<!-- curator-v2-actions: ${candidate.candidate_id} -->`);
    lines.push(`### ${candidateNumber}. Editable decision`, '');
    pushWrapped('Edit this JSON copy, choose a significance rating from 0 to 5, and list persistence documents for the accepted entry. Accept and Reject open the attended review in VS Code. Withdraw retains task facts and receipts. Refresh evidence reopens the source task; fresh proof and a new proposal are required. These actions do not open a terminal.');
    lines.push('',
      `<!-- curator-v2-decision:${candidate.candidate_id}:start -->`,
      draftBlock,
      `<!-- curator-v2-decision:${candidate.candidate_id}:end -->`, '');
  }
  const body = `${lines.join('\n').replace(/\n+$/, '')}\n`;
  if (Buffer.byteLength(body, 'utf8') > 1024 * 1024 - 128) return false;
  const generated = reviewDraftParts(body);
  if (!generated) return false;
  const checksum = createHash('sha256').update(generated.normalized, 'utf8').digest('hex');
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

function reviewDraftMatchesProposal(content, candidateId, draftBlock) {
  const marker = `<!-- curator-v2-candidate: ${candidateId} -->`;
  const candidateStart = content.indexOf(marker);
  if (candidateStart < 0) return false;
  const nextCandidate = content.indexOf('<!-- curator-v2-candidate:', candidateStart + marker.length);
  const section = content.slice(candidateStart, nextCandidate < 0 ? undefined : nextCandidate);
  const proposedMatch = section.match(/### \d+\. Proposed entry\s+(`{3,})json\s*\n([\s\S]*?)\n\1/);
  const editableMatch = typeof draftBlock === 'string'
    ? draftBlock.match(/^(`{3,})json\s*\n([\s\S]*?)\n\1$/) : null;
  if (!proposedMatch || !editableMatch) return false;
  try {
    return JSON.stringify(JSON.parse(proposedMatch[2]))
      === JSON.stringify(JSON.parse(editableMatch[2]));
  } catch (_) {
    return false;
  }
}

function pendingReviewChecksumMarker(content) {
  const match = /^<!-- (?:curator-v2-generated-sha256: |sha256:)([0-9a-f]{64}) -->\n/.exec(content);
  return match ? { checksum: match[1], length: match[0].length } : null;
}

function isUnmodifiedReviewDocument(content) {
  const marker = pendingReviewChecksumMarker(content);
  if (!marker) return false;
  const body = content.slice(marker.length);
  const parts = reviewDraftParts(body);
  if (!parts) return false;
  const hash = (value) => createHash('sha256').update(value, 'utf8').digest('hex');
  return hash(parts.normalized) === marker.checksum || hash(body) === marker.checksum;
}

function tryWriteWorkspaceQueueViews(projectRoot, projectId, inbox, reviewWire, outlines = new Map()) {
  try {
    return writeWorkspaceQueueViews(projectRoot, projectId, inbox, reviewWire, outlines);
  } catch (_error) {
    return false;
  }
}

async function readReviewOutlines(client, reviewWire, projectId) {
  const reviews = validateReviewQueue(reviewWire, projectId);
  const outlines = new Map();
  if (!reviews) return outlines;
  if (reviews.length === 0) return outlines;
  let next = 1;
  const firstId = reviews[0].candidate.candidate_id;
  try {
    outlines.set(firstId, JSON.parse(await client.callTool('sde_review_outline', { candidate_id: firstId })));
  } catch (_) {
    return outlines;
  }
  const worker = async () => {
    while (next < reviews.length) {
      const candidateId = reviews[next++].candidate.candidate_id;
      try {
        const value = JSON.parse(await client.callTool('sde_review_outline', { candidate_id: candidateId }));
        outlines.set(candidateId, value);
      } catch (_) { /* The document explicitly marks unavailable outlines. */ }
    }
  };
  await Promise.all(Array.from({ length: Math.min(4, reviews.length) }, () => worker()));
  return outlines;
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
  let selected = fallbackPath;
  if (databaseBindings && typeof databaseBindings === 'object'
    && Object.prototype.hasOwnProperty.call(databaseBindings, projectId)) {
    selected = databaseBindings[projectId];
  }
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
    const healthPaused = trigger !== 'manual' && priorHealthFailure?.paused;
    const queuePaused = trigger !== 'manual' && priorQueueFailure?.paused;
    const healthAttemptAt = new Date().toISOString();
    const queueAttemptAt = new Date().toISOString();
    const healthRequest = healthPaused
      ? Promise.resolve({ value: null, errorCode: 'feed-auto-paused', checkedAt: priorHealthFailure.checkedAt })
      : !hermesProfileId
        ? Promise.resolve({
          value: null,
          errorCode: 'hermes-probe-profile-binding',
          checkedAt: healthAttemptAt,
        })
        : readHermesHealthProbe(hermesCommand, hermesProfileId, projectId, projectRoot, spawnProcess)
        .then((value) => ({ value, errorCode: null, checkedAt: value.observed_at }))
        .catch((error) => ({
          value: null,
          errorCode: error && typeof error.code === 'string' ? error.code : 'hermes-probe-invalid',
          checkedAt: healthAttemptAt,
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
          checkedAt: queueAttemptAt,
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
      const error = curatorError('mcp-tool-error', 'Curator rejected the requested operation.');
      error.reasonCode = reasonCode;
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
  const openPendingReview = vscode.commands.registerCommand(
    'curatormdV2.openPendingReview',
    () => openPendingReviewDocument(),
  );
  context.subscriptions.push(statusItem, openDashboard, openPendingReview);
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

async function openPendingReviewDocument() {
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
  } catch (_) {
    vscode.window.showWarningMessage(
      'The pending review document is unavailable. Refresh CuratorMD V2 and try again.',
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

async function launchDocumentReview(candidateId, decision, spawnProcess = spawn) {
  let receiptId = null;
  try {
    if (typeof candidateId !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(candidateId)
      || (decision !== undefined
        && !['approve', 'reject', 'withdraw', 'refresh-evidence'].includes(decision))) {
      throw new Error('invalid review action');
    }
    const workspace = vscode.workspace?.workspaceFolders?.[0];
    if (!workspace) throw new Error('missing workspace');
    const projectRoot = workspace.uri.fsPath;
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
          'This proposal already has current passing evidence; no evidence refresh is needed.',
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
          detail: 'The source task becomes active and needs fresh passing evidence for every criterion. Existing facts and receipts remain. No evidence is fabricated and no terminal is opened. Finish the task and assess a new proposal after the checks pass.',
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

    if (selectedDecision === 'approve' && outline.evidence_status !== 'current_passing') {
      vscode.window.showWarningMessage(
        'Curator cannot accept this proposal because current passing evidence is missing or stale. Click Refresh evidence above Editable decision to reopen the source task, add fresh passing evidence, finish it, and assess a new proposal; this proposal can still be rejected or withdrawn.',
      );
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
      if (!packet.artifact_inventory?.usage?.inventory_complete
        || typeof packet.artifact_inventory.manifest_sha256 !== 'string') {
        throw new Error('The current artifact inventory is incomplete; no decision was recorded.');
      }
      return { outline, packet };
    }, { spawnProcess });

    if (selectedDecision === 'approve') {
      const configuredDocuments = Array.isArray(initial.outline.persistence_documents)
        ? initial.outline.persistence_documents.filter((item) => typeof item === 'string') : [];
      if (configuredDocuments.length === 0) {
        throw new Error('This project has no configured persistence documents for an approved entry.');
      }
      const documentChoices = await vscode.window.showQuickPick(
        configuredDocuments.map((item) => ({
          label: item,
          picked: Array.isArray(draft.documents) && draft.documents.includes(item),
        })),
        {
          canPickMany: true,
          title: 'Choose persistence documents',
          placeHolder: 'Select at least one destination for the accepted SDE',
        },
      );
      if (!documentChoices || documentChoices.length === 0) {
        vscode.window.showWarningMessage('Acceptance needs at least one persistence document.');
        return;
      }
      draft = { ...draft, documents: documentChoices.map((item) => item.label) };
      const updated = await writeEditableReviewDraft(openDocument, diskContent, candidateId, draft);
      if (!updated) {
        vscode.window.showWarningMessage('Could not save the selected destinations. Your review decision was not recorded.');
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

    const rationale = await vscode.window.showInputBox({
      title: `Curator V2 ${selectedDecision === 'approve' ? 'acceptance' : 'rejection'} rationale`,
      prompt: 'Enter the rationale to bind to this decision (1–1000 characters).',
      ignoreFocusOut: true,
      validateInput: (value) => value.trim().length > 0 && value.length <= 1000
        ? null : 'Enter 1–1000 non-blank characters.',
    });
    if (rationale === undefined) return;

    const selectedArtifacts = await selectReviewArtifacts(initial.packet);
    if (selectedArtifacts === null) return;
    const reviewed = await withReviewClient(projectRoot, async (client, projectId) => {
      const packet = JSON.parse(await client.callTool('sde_review_packet', {
        candidate_id: candidateId,
        review_artifacts: selectedArtifacts,
      }));
      if (packet.detail?.candidate?.candidate_id !== candidateId
        || packet.detail?.candidate?.status !== 'pending_review'
        || packet.artifact_inventory?.manifest_sha256 !== initial.packet.artifact_inventory.manifest_sha256
        || !packet.artifact_inventory?.usage?.inventory_complete) {
        throw new Error('The review packet changed. Refresh it and start again; no decision was recorded.');
      }
      const reviewDraftJson = JSON.stringify(draft);
      const binding = JSON.parse(await client.callTool('sde_prepare_review_binding', {
        candidate_id: candidateId,
        decision: selectedDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: true,
        dependency_map_sha256: packet.dependency_map_sha256,
        rationale,
        review_draft_json: reviewDraftJson,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
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

    const artifactList = selectedArtifacts.length === 0
      ? 'No staged artifacts are included.'
      : `${selectedArtifacts.length} staged artifact(s) and their allowed actions were reviewed one by one; the manifest digest is below.`;
    const decisionLabel = selectedDecision === 'approve' ? 'Accept' : 'Reject';
    const destinationSummary = selectedDecision === 'approve'
      ? `\nDestinations: ${draft.documents.join(', ')}` : '';
    const confirmed = await vscode.window.showWarningMessage(
      `${decisionLabel} SDE ${candidateId}?`,
      {
        modal: true,
        detail: [
          `Significance: ${draft.significance}/5`,
          artifactList,
          `Inventory SHA-256: ${reviewed.packet.artifact_inventory.manifest_sha256}`,
          `Dependency map SHA-256: ${reviewed.packet.dependency_map_sha256}`,
          `Review binding SHA-256: ${reviewed.binding.sha256}`,
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
        review_artifacts: selectedArtifacts,
      }));
      if (currentPacket.artifact_inventory?.manifest_sha256
        !== reviewed.packet.artifact_inventory.manifest_sha256
        || currentPacket.dependency_map_sha256 !== reviewed.packet.dependency_map_sha256
        || currentPacket.detail?.candidate?.status !== 'pending_review') {
        throw new Error('The review packet changed after confirmation. Refresh it and try again.');
      }
      const currentBinding = JSON.parse(await client.callTool('sde_prepare_review_binding', {
        candidate_id: candidateId,
        decision: selectedDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: true,
        dependency_map_sha256: currentPacket.dependency_map_sha256,
        rationale,
        review_draft_json: reviewed.reviewDraftJson,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
      }));
      if (currentBinding.sha256 !== reviewed.binding.sha256) {
        throw new Error('The review binding changed after confirmation. Refresh it and try again.');
      }
      const receipt = JSON.parse(await client.callTool('sde_confirm', {
        candidate_id: candidateId,
        decision: selectedDecision,
        artifacts: selectedArtifacts,
        artifact_inventory_complete: true,
        dependency_map_sha256: currentPacket.dependency_map_sha256,
        rationale,
        review_draft_json: reviewed.reviewDraftJson,
        expected_review_binding_sha256: currentBinding.sha256,
        confirm_significance_five: selectedDecision === 'approve' && draft.significance === 5,
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
      return { receipt: finalReceipt, purge };
    }, { allowWrite: true, spawnProcess });

    const purgeReceipt = Array.isArray(result.purge)
      ? result.purge[0] : (result.purge?.receipt || result.purge);
    const purgeStatus = purgeReceipt?.purge_status || result.receipt?.purge_status;
    if (purgeStatus !== 'complete') {
      vscode.window.showWarningMessage(
        `SDE ${selectedDecision === 'approve' ? 'acceptance' : 'rejection'} recorded as receipt ${receiptId}; cleanup status is ${purgeStatus || 'unknown'}.`,
      );
    } else {
      vscode.window.showInformationMessage(
        `SDE ${selectedDecision === 'approve' ? 'accepted' : 'rejected'} and receipt ${receiptId} finalized.`,
      );
    }
    void refreshStatusBarHealthFromWorkspace();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unexpected review failure.';
    if (receiptId) {
      vscode.window.showWarningMessage(`Decision receipt ${receiptId} exists, but review finalization needs attention: ${message}`);
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
  if (!await document.edit((builder) => builder.replace(range, replacement))) return false;
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

async function selectReviewArtifacts(packet) {
  const inventory = packet.artifact_inventory;
  if (!inventory?.usage?.inventory_complete || !Array.isArray(inventory.artifacts)) {
    throw new Error('The artifact inventory is incomplete.');
  }
  const selected = [];
  for (const [index, artifact] of inventory.artifacts.entries()) {
    const dependency = (packet.artifact_dependencies || []).find(
      (item) => item.artifact?.path === artifact.path,
    );
    const actions = artifact.retention_hold !== null && artifact.retention_hold !== undefined
      ? ['retain_under_hold']
      : (dependency?.evidence_dependencies || []).some((item) => item.criterion_status === 'open')
        ? ['reacquire_from_source'] : ['not_required', 'reacquire_from_source'];
    const dependencyDetails = (dependency?.evidence_dependencies || [])
      .map((item) => `${item.criterion_id}: ${item.criterion_status}`).join('\n');
    const choices = actions.map((value) => ({
      label: value.replaceAll('_', ' '),
      description: value === 'retain_under_hold' ? 'Required by the active retention hold' : undefined,
      detail: [
        `SHA-256: ${artifact.sha256}`,
        artifact.retention_hold ? `Retention hold: ${artifact.retention_hold}` : '',
        dependencyDetails,
      ].filter(Boolean).join('\n'),
      value,
    }));
    const choice = await vscode.window.showQuickPick(choices, {
      title: `Review staged artifact ${index + 1}/${inventory.artifacts.length}: ${artifact.path}`,
      placeHolder: 'Review its digest and dependencies, then choose the allowed action',
    });
    if (!choice) return null;
    const action = choice.value;
    selected.push({
      path: artifact.path,
      sha256: artifact.sha256,
      ...(artifact.device_id === null || artifact.device_id === undefined ? {} : { device_id: artifact.device_id }),
      ...(artifact.inode_id === null || artifact.inode_id === undefined ? {} : { inode_id: artifact.inode_id }),
      ...(artifact.occurrence_id ? { occurrence_id: artifact.occurrence_id } : {}),
      ...(artifact.retention_hold ? { retention_hold: artifact.retention_hold } : {}),
      reacquisition_action: action,
    });
  }
  return selected;
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
      || vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath !== projectRoot) {
      return 'unknown';
    }
    const displayHealth = updateStatusBarHealth(feeds.health, page.project_id, reviews, storage,
      feeds.healthProbeError ? { code: feeds.healthProbeError } : null);
    const outlines = await readReviewOutlines(client, reviewWire, page.project_id);
    if (generation !== statusRefreshGeneration
      || vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath !== projectRoot) return 'unknown';
    tryWriteWorkspaceQueueViews(projectRoot, page.project_id, inboxWire, reviewWire, outlines);
    if (reviews === null) return 'unknown';
    if (!feeds.health) return 'unknown';
    if (displayHealth !== 'healthy') return displayHealth;
    return reviews.length > 0 ? 'review' : 'healthy';
  } catch (error) {
    if (generation === statusRefreshGeneration
      && vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath === projectRoot) {
      updateStatusBarHealth(null, null, null, null, error);
    }
    void notifyTransportClosed(error);
    return 'unknown';
  } finally {
    client.close();
  }
}

async function showDashboard(spawnProcess = spawn, { focusReviews = false } = {}) {
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
    focusReviews ? vscode.ViewColumn.Beside : vscode.ViewColumn.One,
    { enableScripts: true, localResourceRoots: [] },
  );
  panel.webview.html = dashboardHtml(panel.webview, focusReviews);
  let goalIds = new Set();
  let candidateIds = new Set();
  let projectId = null;
  const reportRevisions = new Map();
  const reportFacts = new Map();
  const reportPages = new Map();
  const goalCards = new Map();
  let requestInProgress = false;
  let goalLoadInFlight = null;
  const schedulePanelReload = () => {
    const reload = () => panel.webview.postMessage({ type: 'reloadGoals' });
    if (goalLoadInFlight) void goalLoadInFlight.then(reload, reload);
    else reload();
  };
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

  const withClient = async (operation, { allowWrite = false } = {}) => {
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
          const outlines = await readReviewOutlines(client, reviews, page.project_id);
          const workspaceViewsUpdated = tryWriteWorkspaceQueueViews(
            workspace.uri.fsPath, page.project_id, inbox, reviews, outlines,
          );
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
          return {
            ...feeds, activity, storage, metrics, page, reviews, inbox,
            workspaceViewsUpdated,
          };
        });
        const {
          page, health, healthProbeError, healthLastFailureCode,
          healthCheckedAt, healthAutoPaused, queueSnapshot, queueProbeError,
          queueLastFailureCode, queueCheckedAt, queueAutoPaused,
          activity, storage, metrics, reviews, workspaceViewsUpdated,
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
          type: 'goals', page, health, activity, storage, reviews: reviewItems,
          healthProbeError,
          healthProbeFailure: healthProbeError
            ? feedFailureMessage(
              healthProbeError,
              healthLastFailureCode,
              healthAutoPaused,
              healthProbeFailureMessage,
            ) : null,
          healthCheckedAt,
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
      panel.webview.postMessage({
        type: 'error',
        message: dashboardErrorMessage(error),
      });
    }
  });

  panel.onDidDispose(() => {
    if (settingsChangeListener && typeof settingsChangeListener.dispose === 'function') {
      settingsChangeListener.dispose();
    }
    goalIds.clear();
    candidateIds.clear();
  });
}

function dashboardHtml(webview, focusReviews = false) {
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
      </div>
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
        const state = document.createElement('td');
        state.textContent = item.stateLabel || item.state;
        state.setAttribute('data-state', item.state);
        row.appendChild(label);
        row.appendChild(value);
        row.appendChild(state);
        body.appendChild(row);
      }
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
    document.getElementById('previousGoals').addEventListener('click', () => requestGoals(Math.max(0, goalOffset - ${GOAL_PAGE_SIZE})));
    document.getElementById('nextGoals').addEventListener('click', () => requestGoals(goalOffset + ${GOAL_PAGE_SIZE}));
    document.getElementById('previousFacts').addEventListener('click', () => requestReport(Math.max(0, factOffset - ${REPORT_PAGE_SIZE})));
    document.getElementById('nextFacts').addEventListener('click', () => requestReport(factOffset + ${REPORT_PAGE_SIZE}));
    window.addEventListener('message', (event) => {
      const message = event.data;
      if (message.type === 'reloadGoals') {
        requestGoals(0);
        return;
      }
      if (message.type === 'error') {
        document.getElementById('refresh').disabled = false;
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
        document.getElementById('refresh').disabled = false;
        const page = message.page;
        const healthSnapshot = message.health;
        const activitySnapshot = message.activity;
        const healthProjectMatches = healthSnapshot
          && healthSnapshot.project_id === page.project_id;
        const validHealthStatus = healthSnapshot
          && ['healthy', 'degraded', 'unknown'].includes(healthSnapshot.status);
        const healthStatus = healthProjectMatches && validHealthStatus
          ? healthSnapshot.status === 'degraded'
            && Array.isArray(healthSnapshot.gate_codes)
            && healthSnapshot.gate_codes.length > 0
            && healthSnapshot.gate_codes.every((gate) => gate === 'review_backlog')
            ? 'healthy' : healthSnapshot.status
          : 'unknown';
        const healthGates = !healthSnapshot
          ? ['health_read_unavailable']
          : !healthProjectMatches
            ? ['health_project_mismatch']
            : !validHealthStatus || !Array.isArray(healthSnapshot.gate_codes)
              ? ['health_observation_invalid']
              : healthSnapshot.gate_codes.filter((gate) => typeof gate === 'string'
                && gate !== 'review_backlog');
        const probeFailure = typeof message.healthProbeFailure === 'string'
          ? message.healthProbeFailure : null;
        const healthGateDescriptions = Array.isArray(message.healthGateDescriptions)
          ? message.healthGateDescriptions : healthGates;
        health.textContent = 'Project health: ' + healthStatus + ' · '
          + (healthGates.length ? countLabel(healthGates.length, 'open gate') : 'no open gates')
          + (probeFailure ? '. ' + probeFailure : '.')
          + ' ' + formatSnapshotCheck(message.healthCheckedAt);
        let alertText = typeof message.alertSummary === 'string'
          ? message.alertSummary : 'Operational alerts: unknown. Alert summary unavailable.';
        if (message.workspaceViewsUpdated === false) {
          alertText += ' Local inbox or review files could not be refreshed, or the review document has unsaved edits; database reads remain available.';
        }
        setPanelState('health', healthStatus);
        renderMetricRows('healthRows', [
          { label: 'Project health', value: healthStatus, state: healthStatus, stateLabel: healthStatus },
          {
            label: 'Open gates',
            value: !healthSnapshot && probeFailure
              ? 'Health check unavailable. ' + probeFailure
              : !healthSnapshot
                ? 'Health snapshot unavailable; refresh to retry.'
              : healthGateDescriptions.length ? healthGateDescriptions.join(' ') : 'None reported',
            state: healthStatus,
          },
          {
            label: 'Operational alerts',
            value: probeFailure ? probeFailure + ' ' + alertText : alertText,
            state: healthStatus,
          },
        ]);
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
          renderMetricRows('storageRows', [{ label: 'Storage snapshot', value: 'Unavailable', state: 'unknown' }]);
        } else if (storageSnapshot.project_id !== page.project_id) {
          storageSummary.textContent = 'Storage usage: unknown. Project mismatch.';
          setPanelState('storage', 'unknown');
          renderMetricRows('storageRows', [{ label: 'Storage snapshot', value: 'Project mismatch', state: 'unknown' }]);
        } else if (!storageValid) {
          storageSummary.textContent = 'Storage usage: unknown. Invalid storage snapshot.';
          setPanelState('storage', 'unknown');
          renderMetricRows('storageRows', [{ label: 'Storage snapshot', value: 'Invalid snapshot', state: 'unknown' }]);
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
          const storageState = sqliteState === 'warning' || stagingState === 'warning'
            ? 'warning'
            : sqliteState === 'unknown' || stagingState === 'unknown' ? 'unknown' : 'healthy';
          storageSummary.textContent = 'SQLite ' + formatBytes(sqliteBytes)
            + ' · staging ' + formatBytes(stagingSnapshot.observed_file_bytes)
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
              'Task reopened. Prior facts remain in history; current criteria need fresh evidence.';
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
    if (${JSON.stringify(focusReviews)}) {
      document.getElementById('reviewsSection').scrollIntoView();
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
  deactivate,
  McpStdioClient,
  dashboardHtml,
  defaultReviewCommand,
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
  queueMetricRows,
  queuePanelState,
  summarizeOperationalAlerts,
  hasWorkspaceSettingOverride,
  hostEvidenceConfigArguments,
  quotePosixShellArgument,
  showDashboard,
  statusColorMeaning,
  sqliteSizeWarning,
  updateStatusBarHealth,
  refreshStatusBarHealthFromWorkspace,
  reviewDocumentActions,
  launchDocumentReview,
  validateReviewQueue,
  writePendingReviewDocument,
  writeWorkspaceQueueViews,
  notifyTransportClosed,
};
