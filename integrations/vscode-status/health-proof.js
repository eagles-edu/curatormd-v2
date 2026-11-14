#!/usr/bin/env node
'use strict';

// Fixed host-configured evidence command. Output is intentionally stable and
// contains no snapshot data: the evidence adapter reruns and hashes it.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');

const MAX_HEALTH_AGE_MS = 180000;
const [projectRoot, projectId, profileId, database, hermes, server] = process.argv.slice(2);
const required = ['event router', 'purge scheduler', 'database storage adapter',
  'host identity', 'human review', 'alert delivery', 'artifact producer inventory'];
const ownEvents = new Map([['hermes-health-proof-verification-20261109-1', 'fact.recorded'],
  ['hermes-health-proof-finish-20261109-1', 'goal.finish_requested']]);
const gateLabels = { event_backlog: 'Events are waiting to be processed.',
  event_failures: 'One or more events failed; check the inbox.' };
const deadline = Date.now() + 25000;
let temp;
let host;

function remaining() { return Math.max(1, deadline - Date.now()); }
function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function fail() { throw new Error('project health proof failed'); }

function run(command, args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: projectRoot, env, stdio: ['ignore', 'pipe', 'ignore'] });
    let output = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('probe timeout')); }, remaining());
    child.stdout.on('data', (chunk) => {
      output += chunk.toString();
      if (Buffer.byteLength(output) > 32768) child.kill();
    });
    child.once('error', (error) => { clearTimeout(timer); reject(error); });
    child.once('close', (code) => {
      clearTimeout(timer);
      if (code !== 0 || Buffer.byteLength(output) > 32768) reject(new Error('probe failed'));
      else resolve(output);
    });
  });
}

function expectedGate(events) {
  if (!Array.isArray(events) || events.length > 1) fail();
  if (!events.length) return null;
  const [event] = events;
  if (!event || ownEvents.get(event.event_id) !== event.event_type || event.source_id !== 'codex-local') fail();
  if (event.status === 'received') return 'event_backlog';
  if (event.status === 'failed') return 'event_failures';
  return fail();
}

function validateSnapshot(wire, expectedProjectId = projectId, gate = null) {
  const value = JSON.parse(wire);
  const health = value.health;
  const age = Date.now() - Date.parse(health?.observed_at);
  if (value.connected !== true || value.project_id !== expectedProjectId || health?.project_id !== expectedProjectId
    || health.status !== (gate ? 'degraded' : 'healthy') || !Array.isArray(health.gate_codes)
    || health.gate_codes.length !== (gate ? 1 : 0) || (gate && health.gate_codes[0] !== gate)
    || !Number.isFinite(age) || age < -5000 || age > MAX_HEALTH_AGE_MS
    || !Array.isArray(health.dependencies)) fail();
  const dependencies = new Map(health.dependencies.map((item) => [item.name, item]));
  for (const name of required.map((item) => item.replaceAll(' ', '_'))) {
    const dependency = dependencies.get(name);
    const dependencyAge = Date.now() - Date.parse(dependency?.observed_at);
    if (dependency?.status !== 'healthy' || !Number.isFinite(dependencyAge)
      || dependencyAge < -5000 || dependencyAge > MAX_HEALTH_AGE_MS) fail();
  }
}

async function evaluate(target) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    const timer = setTimeout(() => { socket.close(); reject(new Error('webview timeout')); }, 1500);
    socket.onopen = () => socket.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: {
      expression: `(() => {
        const d = document.querySelector('#active-frame')?.contentDocument;
        const rows = d?.querySelector('#healthRows');
        if (!rows) return null;
        return { project: rows.getAttribute('data-project-id'), observed: rows.getAttribute('data-observed-at'),
          rows: Array.from(rows.children, r => ({label: r.children[0]?.textContent,
            value: r.children[1]?.textContent, state: r.children[2]?.textContent})) };
      })()`, returnByValue: true,
    } }));
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== 1) return;
      clearTimeout(timer); socket.close();
      resolve(message.result?.result?.value || null);
    };
    socket.onerror = () => { clearTimeout(timer); reject(new Error('webview unavailable')); };
  });
}

function validDashboard(value, expectedProjectId = projectId, gate = null) {
  if (!value || value.project !== expectedProjectId || !Array.isArray(value.rows)) return false;
  const age = Date.now() - Date.parse(value.observed);
  if (!Number.isFinite(age) || age < -5000 || age > MAX_HEALTH_AGE_MS) return false;
  const rows = new Map(value.rows.map((row) => [row.label, row]));
  return ['Project health', 'Open gates', ...required, 'Hermes profile probe'].every((name) => {
    const row = rows.get(name);
    const state = gate && ['Project health', 'Open gates'].includes(name) ? 'degraded' : 'healthy';
    return row?.state === state
      && (name !== 'Open gates' || row.value === (gate ? gateLabels[gate] : 'None reported'));
  });
}

async function main() {
  if (process.argv.length !== 8 || ![projectRoot, database, hermes, server].every(path.isAbsolute)
    || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(projectId)
    || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(profileId)) fail();
  const config = fs.readFileSync(path.join(projectRoot, '.curatormd-v2.toml'), 'utf8');
  const ids = [...config.matchAll(/^project_id\s*=\s*"([^"]+)"\s*$/gm)];
  if (ids.length !== 1 || ids[0][1] !== projectId) fail();
  const home = os.userInfo().homedir;
  const runtime = `/run/user/${process.getuid()}`;
  const env = { HOME: home, PATH: '/usr/local/bin:/usr/bin:/bin', LANG: 'C', LC_ALL: 'C',
    HERMES_HOME: path.join(home, '.hermes', 'profiles', profileId) };
  try {
    if (fs.statSync(path.join(runtime, 'bus')).isSocket()) {
      env.XDG_RUNTIME_DIR = runtime; env.DBUS_SESSION_BUS_ADDRESS = `unix:path=${runtime}/bus`;
    }
  } catch (_) { /* The probe will report missing host dependencies. */ }
  const inventoryCode = "import json,sqlite3,sys,urllib.parse; "
    + "c=sqlite3.connect('file:'+urllib.parse.quote(sys.argv[1])+'?mode=ro',uri=True,timeout=3); "
    + "r=c.execute(\"select event_id,status,event_type,source_id from event_inbox where project_id=? and status in ('received','failed','quarantined') order by event_id limit 2\",(sys.argv[2],)).fetchall(); "
    + "print(json.dumps([{'event_id':x[0],'status':x[1],'event_type':x[2],'source_id':x[3]} for x in r]))";
  const gate = expectedGate(JSON.parse(await run('/usr/bin/python3', ['-c', inventoryCode, database, projectId], env)));
  const probe = run(hermes, ['mcp', 'test', 'curator_v2', '--probe-curator-status', '--json'], env)
    .then((wire) => { try { validateSnapshot(wire, projectId, gate); return true; } catch (_) { return false; } }, () => false);
  temp = fs.mkdtempSync(path.join(os.tmpdir(), 'curator-health-proof-'));
  fs.mkdirSync(path.join(temp, 'User'), { mode: 0o700 });
  fs.writeFileSync(path.join(temp, 'User', 'settings.json'), JSON.stringify({
    'curatormdV2.databasePath': database, 'curatormdV2.profileId': profileId,
    'curatormdV2.hermesProfileBindings': { [projectId]: profileId },
    'curatormdV2.hermesCommand': hermes, 'curatormdV2.serverCommand': server,
    'security.workspace.trust.enabled': false,
  }), { mode: 0o600 });
  host = spawn('/usr/bin/xvfb-run', ['-a', '/usr/bin/code', '--wait', '--no-sandbox', '--disable-gpu',
    '--disable-workspace-trust', '--skip-welcome', '--skip-release-notes', '--remote-debugging-port=0',
    '--user-data-dir', temp, '--extensions-dir', path.join(temp, 'extensions'),
    '--extensionDevelopmentPath', __dirname, '--extensionTestsPath', path.join(__dirname, 'health-proof-test-host.js'),
    projectRoot], { cwd: projectRoot, env, stdio: 'ignore' });
  host.on('error', () => {});
  const portFile = path.join(temp, 'DevToolsActivePort');
  while (Date.now() < deadline) {
    if (host.exitCode !== null) fail();
    try {
      const port = Number(fs.readFileSync(portFile, 'utf8').split('\n')[0]);
      if (!Number.isInteger(port) || port < 1 || port > 65535) fail();
      const response = await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(1000) });
      const targets = await response.json();
      for (const target of targets) {
        if (target.type === 'iframe' && target.url.includes('extensionId=curatormd.curatormd-v2-status')
          && validDashboard(await evaluate(target), projectId, gate)) {
          if (!await probe) fail();
          process.stdout.write('curator-health-dashboard-proof-v1:pass\n');
          return;
        }
      }
    } catch (_) { /* Wait for the local development host and dashboard. */ }
    await delay(250);
  }
  fail();
}

function stopHostTree(rootPid) {
  const children = new Map();
  for (const entry of fs.readdirSync('/proc')) {
    if (!/^\d+$/.test(entry)) continue;
    try {
      const status = fs.readFileSync(`/proc/${entry}/status`, 'utf8');
      const parent = Number(/^PPid:\s*(\d+)$/m.exec(status)?.[1]);
      if (!children.has(parent)) children.set(parent, []);
      children.get(parent).push(Number(entry));
    } catch (_) { /* The process exited while the tree was read. */ }
  }
  const stop = (pid) => {
    for (const child of children.get(pid) || []) stop(child);
    try { process.kill(pid, 'SIGKILL'); } catch (_) { /* Already exited. */ }
  };
  stop(rootPid);
}

if (require.main === module) {
  main().catch(() => { process.exitCode = 1; }).finally(() => {
    if (host?.pid) { try { stopHostTree(host.pid); } catch (_) { host.kill('SIGKILL'); } }
    if (temp) { try { fs.rmSync(temp, { recursive: true, force: true }); } catch (_) { /* Temporary host cleanup. */ } }
  });
}

module.exports = { expectedGate, validateSnapshot, validDashboard };
