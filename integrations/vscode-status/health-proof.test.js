'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { expectedGate, validateSnapshot, validDashboard } = require('./health-proof');

const project = 'project-alpha';
const names = ['event_router', 'purge_scheduler', 'database_storage_adapter', 'host_identity',
  'human_review', 'alert_delivery', 'artifact_producer_inventory'];
function snapshot() {
  const now = new Date().toISOString();
  return { connected: true, project_id: project, health: {
    project_id: project, status: 'healthy', observed_at: now, gate_codes: [],
    dependencies: names.map((name) => ({ name, status: 'healthy', observed_at: now })),
  } };
}
function dashboard() {
  return { project, observed: new Date().toISOString(), rows: [
    { label: 'Project health', value: 'healthy', state: 'healthy' },
    { label: 'Open gates', value: 'None reported', state: 'healthy' },
    ...names.map((name) => ({ label: name.replaceAll('_', ' '), state: 'healthy' })),
    { label: 'Hermes profile probe', state: 'healthy' },
  ] };
}
test('project probe rejects failed, stale, mismatched, or incomplete snapshots', () => {
  const valid = snapshot();
  assert.doesNotThrow(() => validateSnapshot(JSON.stringify(valid), project));
  for (const mutate of [
    (x) => { x.connected = false; },
    (x) => { x.project_id = 'other'; },
    (x) => { x.health.gate_codes = ['event_failures']; },
    (x) => { x.health.observed_at = '2000-01-01T00:00:00Z'; },
    (x) => { x.health.dependencies.pop(); },
    (x) => { x.health.dependencies[0].status = 'unknown'; },
  ]) {
    const value = snapshot(); mutate(value);
    assert.throws(() => validateSnapshot(JSON.stringify(value), project));
  }
});
test('project probe tolerates delayed minute refreshes but still expires old health', () => {
  const delayed = snapshot();
  delayed.health.observed_at = new Date(Date.now() - 90000).toISOString();
  delayed.health.dependencies.forEach((dependency) => {
    dependency.observed_at = new Date(Date.now() - 90000).toISOString();
  });
  assert.doesNotThrow(() => validateSnapshot(JSON.stringify(delayed), project));
  const stale = snapshot();
  stale.health.observed_at = new Date(Date.now() - 181000).toISOString();
  assert.throws(() => validateSnapshot(JSON.stringify(stale), project));
});
test('rendered dashboard requires matching fresh project, every component, and no gates', () => {
  assert.equal(validDashboard(dashboard(), project), true);
  const delayed = dashboard();
  delayed.observed = new Date(Date.now() - 90000).toISOString();
  assert.equal(validDashboard(delayed, project), true);
  for (const mutate of [
    (x) => { x.project = 'other'; },
    (x) => { x.observed = '2000-01-01T00:00:00Z'; },
    (x) => { x.rows.pop(); },
    (x) => { x.rows[1].value = 'One open gate'; },
    (x) => { x.rows[3].state = 'unknown'; },
  ]) {
    const value = dashboard(); mutate(value);
    assert.equal(validDashboard(value, project), false);
  }
  const stale = dashboard();
  stale.observed = new Date(Date.now() - 181000).toISOString();
  assert.equal(validDashboard(stale, project), false);
});
test('only this task\'s own unfinished receipt can explain a degraded gate', () => {
  const own = 'hermes-health-proof-verification-20261109-1';
  const event = { event_id: own, event_type: 'fact.recorded', source_id: 'codex-local' };
  assert.equal(expectedGate([]), null);
  assert.equal(expectedGate([{ ...event, status: 'received' }]), 'event_backlog');
  assert.equal(expectedGate([{ ...event, status: 'failed' }]), 'event_failures');
  assert.throws(() => expectedGate([{ event_id: 'other', status: 'failed' }]));
  assert.throws(() => expectedGate([{ ...event, status: 'quarantined' }]));
  assert.throws(() => expectedGate([{ ...event, status: 'failed', source_id: 'other' }]));
  assert.throws(() => expectedGate([{ ...event, status: 'failed' }, { event_id: 'other', status: 'failed' }]));
  const health = snapshot();
  health.health.status = 'degraded';
  health.health.gate_codes = ['event_failures'];
  assert.doesNotThrow(() => validateSnapshot(JSON.stringify(health), project, 'event_failures'));
  assert.throws(() => validateSnapshot(JSON.stringify(health), project));
  const view = dashboard();
  view.rows[0].state = 'degraded';
  view.rows[1].state = 'degraded';
  view.rows[1].value = 'One or more events failed; check the inbox.';
  assert.equal(validDashboard(view, project, 'event_failures'), true);
  assert.equal(validDashboard(view, project), false);
});
