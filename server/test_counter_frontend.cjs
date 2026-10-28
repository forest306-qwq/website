'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {randomUUID} = require('node:crypto');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/counter.js'), 'utf8');

function setup(fetch, hostname = 'nwuc.cn') {
  const fields = Object.fromEntries(['site_pv', 'site_uv'].flatMap(k => [
    ['busuanzi_value_' + k, {textContent: ''}], ['busuanzi_container_' + k, {style: {}}]
  ]));
  const visit = {dataset: {}};
  const context = {window: {}, location: {hostname, protocol: 'https:', pathname: '/'},
    crypto: {randomUUID}, AbortController, setTimeout, clearTimeout, setInterval() {}, fetch,
    document: {readyState: 'complete', querySelector() {return visit;}, getElementById(id) {return fields[id] || null;}}};
  vm.runInNewContext(source, context);
  return {context, fields, visit};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('same-path refresh does not increment; SPA events are serialized and display current totals', async () => {
  let calls = 0, running = 0, maximum = 0;
  const app = setup(async (url, options) => {
    calls++; running++; maximum = Math.max(maximum, running);
    assert.equal(url, '/api/site-counter');
    assert.equal(options.credentials, 'same-origin');
    assert.match(JSON.parse(options.body).event, /^[0-9a-f-]{36}$/);
    await flush();
    running--;
    return {ok: true, json: async () => ({success: true, data: {site_pv: calls, site_uv: 1}})};
  });
  app.context.window.__countReload();
  app.context.location.pathname = '/diary.html';
  app.context.window.__countReload();
  app.context.location.pathname = '/columns/song.html';
  app.context.window.__countReload();
  for (let i = 0; i < 10; i++) await flush();
  assert.equal(calls, 3);
  assert.equal(maximum, 1);
  assert.equal(app.fields.busuanzi_value_site_pv.textContent, 3);
  assert.equal(app.fields.busuanzi_value_site_uv.textContent, 1);
  assert.equal(app.visit.dataset.state, 'ready');
});
test('retry reuses the same event identifier', async () => {
  const events = [];
  const app = setup(async (_, options) => {
    events.push(JSON.parse(options.body).event);
    if (events.length === 1) throw new Error('network failure');
    return {ok: true, json: async () => ({success: true, data: {site_pv: 1, site_uv: 1}})};
  });
  await flush(); await flush();
  assert.equal(events.length, 2);
  assert.equal(events[0], events[1]);
  assert.equal(app.visit.dataset.state, 'ready');
});
test('failed requests show unavailable rather than zero or a fabricated count', async () => {
  const app = setup(async () => {throw new Error('offline');});
  await flush(); await flush();
  assert.equal(app.visit.dataset.state, 'error');
  assert.equal(app.fields.busuanzi_value_site_pv.textContent, '–');
});
test('local preview and former domains never submit visits', async () => {
  for (const host of ['localhost', 'forest306.cc.cd']) {
    let calls = 0;
    const app = setup(async () => {calls++;}, host);
    await flush();
    assert.equal(calls, 0);
    assert.equal(app.visit.dataset.state, 'preview');
  }
});
