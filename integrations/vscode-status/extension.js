'use strict';

const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const path = require('node:path');
const vscode = require('vscode');

const STATUS_LABEL = 'CuratorMD V2';
const REPORT_PAGE_SIZE = 16;
const GOAL_PAGE_SIZE = 20;
const REVIEW_QUEUE_SIZE = 100;
const REQUEST_TIMEOUT_MS = 15000;

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
    this.child.on('error', () => this._failAll(new Error('Curator MCP process could not start.')));
    this.child.on('exit', () => {
      this.closed = true;
      this._failAll(new Error('Curator MCP process exited before replying.'));
    });
  }

  async initialize() {
    await this._request('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'curatormd-v2-vscode-dashboard', version: '0.5.0' },
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
      throw new Error('Curator rejected the read. Check project access and retry.');
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
        reject(new Error('Curator did not respond within 15 seconds.'));
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
        this._failAll(new Error('Curator returned an invalid MCP response.'));
        continue;
      }
      const pending = this.pending.get(message.id);
      if (!pending) continue;
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error('Curator MCP request failed.'));
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
  const statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 20);
  statusItem.name = STATUS_LABEL;
  statusItem.text = STATUS_LABEL;
  statusItem.tooltip = 'Open the project-scoped CuratorMD V2 dashboard.';
  statusItem.command = 'curatormdV2.openDashboard';
  statusItem.show();

  const openDashboard = vscode.commands.registerCommand(
    'curatormdV2.openDashboard',
    () => showDashboard(),
  );
  context.subscriptions.push(statusItem, openDashboard);
}

function deactivate() {}

async function showDashboard(spawnProcess = spawn) {
  const workspace = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!workspace) {
    vscode.window.showWarningMessage('Open a Curator-enabled project folder first.');
    return;
  }
  const configuration = vscode.workspace.getConfiguration('curatormdV2');
  const workspaceOverride = hasWorkspaceSettingOverride(
    configuration,
    ['databasePath', 'profileId', 'serverCommand', 'reviewCommand'],
  );
  const databasePath = configuration.get('databasePath', '');
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  const configuredReviewCommand = configuration.get('reviewCommand', '');
  const reviewCommand = configuredReviewCommand || defaultReviewCommand(serverCommand);
  if (workspaceOverride) {
    vscode.window.showErrorMessage(
      'Curator launcher, database, profile, and review CLI settings must be set in User settings, not the project.',
    );
    return;
  }
  if (!databasePath || !profileId || !serverCommand) {
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
  const reportRevisions = new Map();
  let requestInProgress = false;

  const withClient = async (operation) => {
    if (requestInProgress) throw new Error('A Curator read is already in progress.');
    requestInProgress = true;
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
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        const result = await withClient(async (client) => {
          const healthRequest = client.callTool('project_health', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const activityRequest = client.callTool('project_activity_status', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const storageRequest = client.callTool('project_storage_usage', {})
            .then((wire) => JSON.parse(wire))
            .catch(() => null);
          const pageRequest = client.callTool('goal_list_page', {
            offset,
            limit: GOAL_PAGE_SIZE,
          }).then((wire) => JSON.parse(wire));
          const reviewRequest = client.callTool('sde_review_queue', {
            limit: REVIEW_QUEUE_SIZE,
          }).then((wire) => JSON.parse(wire)).catch(() => null);
          const [health, activity, storage, page, reviews] = await Promise.all([
            healthRequest,
            activityRequest,
            storageRequest,
            pageRequest,
            reviewRequest,
          ]);
          return { health, activity, storage, page, reviews };
        });
        const { page, health, activity, storage, reviews } = result;
        if (page.project_id !== undefined && page.project_id !== '') {
          goalIds = new Set((page.goals || []).map((goal) => goal.goal_id));
        }
        const reviewItems = validateReviewQueue(reviews, page.project_id);
        candidateIds = new Set((reviewItems || []).map((item) => item.candidate.candidate_id));
        panel.webview.postMessage({
          type: 'goals', page, health, activity, storage, reviews: reviewItems,
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
        if (factOffset > 0 && reportRevision) {
          const priorRevision = reportRevisions.get(message.goalId);
          if (priorRevision && priorRevision !== reportRevision) {
            panel.webview.postMessage({ type: 'reportStale', goalId: message.goalId });
            return;
          }
        }
        if (factOffset === 0 && reportRevision) {
          reportRevisions.set(message.goalId, reportRevision);
        }
        panel.webview.postMessage({
          type: 'report',
          goalId: message.goalId,
          factOffset,
          factTotal: match ? Number(match[1]) : 0,
          reportRevision,
          report,
        });
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
      panel.webview.postMessage({
        type: 'error',
        message: 'Curator read failed. Check User settings, the local project grant, and the launcher.',
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
  </section>
  <section aria-labelledby="activityHeading">
    <h2 id="activityHeading">Retained activity</h2>
    <p id="activity" role="status">Loading authorized activity totals…</p>
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
    const error = document.getElementById('error');
    const health = document.getElementById('health');
    const activitySummary = document.getElementById('activity');
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
      health.textContent = 'Project health: unknown. Refresh to retry the health read.';
      activitySummary.textContent = 'Retained activity: unknown. Refresh to retry the activity read.';
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
      goals.replaceChildren();
      reviews.replaceChildren();
      reviewSummary.textContent = 'Loading the authorized review queue…';
      document.getElementById('selected').textContent = '';
      document.getElementById('factPage').textContent = '';
      document.getElementById('goalPage').textContent = 'Loading a fresh authorized goal page…';
      health.textContent = 'Loading an authorized health snapshot…';
      activitySummary.textContent = 'Loading authorized activity totals…';
      storageSummary.textContent = 'Loading authorized storage totals…';
      api.postMessage({ type: 'loadGoals', offset });
      error.textContent = '';
    }
    function requestReport(offset) {
      if (!selectedGoal) return;
      factOffset = offset;
      report.textContent = 'Loading a fresh authorized report page…';
      document.getElementById('factPage').textContent = '';
      api.postMessage({ type: 'loadReport', goalId: selectedGoal, factOffset: offset });
      error.textContent = '';
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
        health.textContent = 'Project health: ' + healthStatus + '. Open gates: '
          + (healthGates.length ? healthGates.join(', ') : 'none reported') + '.';
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
            + '. ' + stagingText + ' Model/token usage is not reported here.';
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
        const revisionLabel = reportRevision ? ' Snapshot ' + reportRevision.slice(0, 12) + '.' : '';
        document.getElementById('factPage').textContent = 'Facts ' + (factTotal ? factOffset + 1 : 0) + '–' + Math.min(factOffset + ${REPORT_PAGE_SIZE}, factTotal) + ' of ' + factTotal + '.' + revisionLabel + ' This page is a fresh read; the previous page was cleared.';
        document.getElementById('previousFacts').disabled = factOffset === 0;
        document.getElementById('nextFacts').disabled = factOffset + ${REPORT_PAGE_SIZE} >= factTotal;
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
  if (!Array.isArray(value) || value.length > REVIEW_QUEUE_SIZE
    || typeof projectId !== 'string' || !projectId) return null;
  const candidateIds = new Set();
  for (const item of value) {
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
  return value.map(({ candidate, goal }) => ({
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
  hasWorkspaceSettingOverride,
  quotePosixShellArgument,
  showDashboard,
  validateReviewQueue,
};
