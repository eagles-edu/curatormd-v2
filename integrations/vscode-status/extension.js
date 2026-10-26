'use strict';

const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const vscode = require('vscode');

const STATUS_LABEL = 'CuratorMD V2';
const REPORT_PAGE_SIZE = 16;
const GOAL_PAGE_SIZE = 20;
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
      clientInfo: { name: 'curatormd-v2-vscode-dashboard', version: '0.2.0' },
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
    ['databasePath', 'profileId', 'serverCommand'],
  );
  const databasePath = configuration.get('databasePath', '');
  const profileId = configuration.get('profileId', '');
  const serverCommand = configuration.get('serverCommand', 'curatormd-v2-mcp');
  if (workspaceOverride) {
    vscode.window.showErrorMessage(
      'Curator launcher, database, and profile settings must be set in User settings, not the project.',
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
        const offset = Number.isSafeInteger(message.offset) && message.offset >= 0
          ? message.offset : 0;
        const page = await withClient(async (client) => {
          const wire = await client.callTool('goal_list_page', {
            offset,
            limit: GOAL_PAGE_SIZE,
          });
          return JSON.parse(wire);
        });
        if (page.project_id !== undefined && page.project_id !== '') {
          goalIds = new Set((page.goals || []).map((goal) => goal.goal_id));
        }
        panel.webview.postMessage({ type: 'goals', page });
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
      }
    } catch (error) {
      panel.webview.postMessage({
        type: 'error',
        message: 'Curator read failed. Check User settings, the local project grant, and the launcher.',
      });
    }
  });

  panel.onDidDispose(() => { goalIds.clear(); });
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
  <div><button id="refresh">Refresh goals</button> <button id="previousGoals">Previous goals</button> <button id="nextGoals">Next goals</button></div>
  <p id="goalPage"></p><div id="goals"></div>
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
    function clearDashboard() {
      selectedGoal = null;
      factOffset = 0;
      factTotal = 0;
      reportRevision = null;
      goals.replaceChildren();
      report.textContent = '';
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
      document.getElementById('selected').textContent = '';
      document.getElementById('factPage').textContent = '';
      document.getElementById('goalPage').textContent = 'Loading a fresh authorized goal page…';
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

module.exports = {
  activate,
  deactivate,
  McpStdioClient,
  dashboardHtml,
  hasWorkspaceSettingOverride,
  showDashboard,
};
