/* Run with Node 24 and the generated app's dependencies available:
 * AEGIS_TEST_NODE_MODULES=/path/to/node_modules node --test skills/aegis-nextjs-frontend/tests/*.test.cjs
 * Loads the Markdown snippets and uses the real Aegis 4.2.0 client with fake fetch.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const vm = require('node:vm');
const {createHmac} = require('node:crypto');
const requireApp = createRequire(path.resolve(process.env.AEGIS_TEST_NODE_MODULES || 'node_modules', '../package.json'));
const ts = requireApp('typescript');
const refs = path.resolve(__dirname, '../references');
const site = '01900000-0000-7000-8000-000000000002';
const otherSite = '01900000-0000-7000-8000-000000000099';
const user = '01900000-0000-7000-8000-000000000003';

function load(file, heading, overrides = {}, globals = {}) {
  const source = readFileSync(path.join(refs, file), 'utf8').split(heading)[1].match(/```[^\n]*\n([\s\S]*?)\n```/)[1];
  const output = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  const exports = {};
  vm.runInNewContext(output, {
    exports, process, Buffer, Date, URL, console, ...globals,
    require: (name) => name === 'server-only' ? {} : overrides[name] || requireApp(name),
  }, {filename: file});
  return exports;
}
function withConfig(t) {
  const prior = {...process.env};
  process.env.AEGIS_API_URL = 'https://auth.example.com';
  process.env.AEGIS_SITE_ID = site;
  process.env.AEGIS_TENANT_API_KEY = 'test-only-tenant-key';
  t.after(() => {
    for (const key of ['AEGIS_API_URL', 'AEGIS_SITE_ID', 'AEGIS_TENANT_API_KEY', 'AEGIS_WEBHOOK_SECRET']) {
      if (prior[key] === undefined) delete process.env[key]; else process.env[key] = prior[key];
    }
  });
}
const request = () => ({headers: new Headers({Authorization: 'Bearer test-token'})});
const identity = (siteId = site) => ({uuid: user, site_uuid: siteId, email: 'u@example.com', role: 'user', is_verified: true, created_at: 1, updated_at: 1, deletion_protected: false});

test('server proxy preserves UUID, attaches key, ignores client state, and fails closed', async t => {
  withConfig(t);
  const helper = load('tenant-api-key-templates.md', '## 2. Server-Side');
  let count = 0;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    count++;
    assert.equal(new URL(url).pathname, '/api/auth/login');
    assert.equal(JSON.parse(options.body).site_id, site);
    assert.equal(options.headers['X-Tenant-Api-Key'], 'test-only-tenant-key');
    return new Response('{}', {status: 401, headers: {'Content-Type': 'application/json'}});
  });
  const first = helper.getServerAuthClient();
  assert.notEqual(first, helper.getServerAuthClient());
  await first.login('u@example.com', 'test-password');
  assert.equal(count, 1);
  process.env.AEGIS_SITE_ID = '42';
  assert.throws(helper.getServerAuthClient, /UUID/);
  delete process.env.AEGIS_TENANT_API_KEY;
  assert.throws(helper.getServerAuthClient);
});

test('backend verifies tenant, caches rejection, distinguishes outages, and validates lookup identity', async t => {
  withConfig(t);
  let response = identity();
  let status = 200;
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => {
    calls++;
    return new Response(JSON.stringify(response), {status, headers: {'Content-Type': 'application/json'}});
  });
  let helper = load('backend-auth-templates.md', '## Next.js helper:');
  assert.equal((await helper.authenticateRequest(request())).uuid, user);
  await helper.authenticateRequest(request());
  assert.equal(calls, 1);
  helper = load('backend-auth-templates.md', '## Next.js helper:');
  response = identity(otherSite);
  assert.equal(await helper.authenticateRequest(request()), null);
  await helper.authenticateRequest(request());
  assert.equal(calls, 2);
  for (const code of [400, 401, 403, 429, 500, 503]) {
    helper = load('backend-auth-templates.md', '## Next.js helper:');
    status = code; response = {error: 'simulated'};
    const before = calls;
    if (code === 429 || code >= 500) {
      await assert.rejects(helper.authenticateRequest(request()), /unavailable/);
      await assert.rejects(helper.authenticateRequest(request()), /unavailable/);
      assert.equal(calls - before, 2);
    } else {
      assert.equal(await helper.authenticateRequest(request()), null);
      assert.equal(await helper.authenticateRequest(request()), null);
      assert.equal(calls - before, 1);
    }
  }
  helper = load('backend-auth-templates.md', '## Next.js helper:');
  status = 200; response = identity();
  assert.equal((await helper.getAegisUser(user)).uuid, user);
  assert.equal(await helper.getAegisUser(otherSite), null); // API returned the wrong UUID.
  assert.equal(await helper.getAegisUser('42'), null);
  delete process.env.AEGIS_SITE_ID;
  await assert.rejects(helper.authenticateRequest(request()), /required/);
});

test('webhook verifies raw body, event binding, timestamps, and malformed signatures', () => {
  const {verifyWebhook} = load('webhook-templates.md', '## Node verifier:');
  const stamp = String(Math.floor(Date.now() / 1000));
  const payload = {event_id: user, event_type: 'user.verified', site_uuid: site, user_uuid: user, email: 'u@example.com', timestamp: 1};
  const body = JSON.stringify(payload);
  const sign = (raw, at = stamp) => 'sha256=' + createHmac('sha256', 'test-secret').update(`${at}.${raw}`).digest('hex');
  const verify = (sig, at = stamp, raw = body, event = 'user.verified') => verifyWebhook('test-secret', sig, at, raw, event);
  assert.equal(verify(sign(body)).event_id, user); // original event can be old
  assert.equal(verify(sign(body), stamp, body, 'user.deleted'), null);
  assert.equal(verify(sign(body), stamp, body + ' '), null);
  for (const signature of ['', 'sha256=x', 'sha256=' + 'z'.repeat(64), 'sha256=' + 'é'.repeat(64)]) {
    assert.equal(verify(signature), null);
  }
  const stale = String(Number(stamp) - 301);
  assert.equal(verify(sign(body, stale), stale), null);
  assert.equal(verify(sign(body, '1oops'), '1oops'), null);
  for (const raw of ['[]', 'null', 'invalid', JSON.stringify({...payload, user_uuid: 42})]) {
    assert.equal(verify(sign(raw), stamp, raw), null);
  }
});

test('Next receiver denies other sites, acknowledges unknown events, fails on missing persistence', async t => {
  withConfig(t);
  process.env.AEGIS_WEBHOOK_SECRET = 'test-secret';
  const verifier = load('webhook-templates.md', '## Node verifier:');
  const adapter = load('webhook-templates.md', '### Required adapter:');
  const route = load('webhook-templates.md', '## Next.js receiver:', {
    '@/lib/aegisWebhook': verifier, '@/lib/aegisIdentityStore': adapter,
  });
  const stamp = String(Math.floor(Date.now() / 1000));
  async function post(event, siteId = site) {
    const body = JSON.stringify({event_id: user, event_type: event, site_uuid: siteId, user_uuid: user, email: 'u@example.com', timestamp: 1});
    return route.POST({text: async () => body, headers: new Headers({
      'X-Aegis-Timestamp': stamp, 'X-Aegis-Event': event,
      'X-Aegis-Signature': 'sha256=' + createHmac('sha256', 'test-secret').update(`${stamp}.${body}`).digest('hex'),
    })});
  }
  assert.equal((await post('user.verified')).status, 503);
  assert.equal((await post('user.deleted')).status, 503);
  assert.equal((await post('future.event')).status, 200);
  assert.equal((await post('user.verified', otherSite)).status, 403);
  delete process.env.AEGIS_SITE_ID;
  assert.equal((await post('user.verified')).status, 503);
});


test('browser login keeps UUIDs and refresh updates the observable auth store', async t => {
  const storage = new Map();
  const events = [];
  const localStorage = {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  };
  const browser = load('auth-templates.md', '## lib/browserClient.ts', {}, {
    localStorage, window: {dispatchEvent: event => events.push(event.type)}, Event,
  });
  const future = Math.floor(Date.now() / 1000) + 3600;
  const login = {
    auth_token: {token: 'old-token', user_uuid: user, expires_at: future},
    refresh_token: {token: 'refresh', user_uuid: user, site_uuid: site, expires_at: future + 3600},
  };
  browser.initAuthClientFromLogin(login, site, 'Example App');
  assert.equal(storage.get('user_id'), user);
  assert.equal(storage.get('site_id'), site);
  assert.equal(browser.isTokenExpired(), false);
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({
    auth_token: {...login.auth_token, token: 'new-token'},
    refresh_token: login.refresh_token,
  }), {headers: {'Content-Type': 'application/json'}}));
  assert.equal((await browser.refreshAuthTokens()).success, true);
  assert.equal(storage.get('auth_token'), 'new-token');
  browser.clearAuthClient();
  assert.equal(storage.size, 0);
  assert.equal(browser.isTokenExpired(), true);
  assert.equal(events.length, 3);
});


test('refresh completion cannot resurrect logout or overwrite replacement login', async t => {
  const storage = new Map();
  const localStorage = {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key),
  };
  const browser = load('auth-templates.md', '## lib/browserClient.ts', {}, {
    localStorage, window: {dispatchEvent: () => {}}, Event,
  });
  const future = Math.floor(Date.now() / 1000) + 3600;
  const login = token => ({
    auth_token: {token, user_uuid: user, expires_at: future},
    refresh_token: {token: 'refresh-' + token, user_uuid: user, site_uuid: site, expires_at: future + 3600},
  });
  let release;
  t.mock.method(globalThis, 'fetch', () => new Promise(resolve => { release = resolve; }));
  const complete = () => release(new Response(JSON.stringify(login('stale-refresh')), {headers: {'Content-Type': 'application/json'}}));
  browser.initAuthClientFromLogin(login('old'), site, 'Example App');
  let pending = browser.refreshAuthTokens();
  browser.clearAuthClient();
  complete();
  assert.equal((await pending).superseded, true);
  assert.equal(storage.size, 0);
  browser.initAuthClientFromLogin(login('old'), site, 'Example App');
  pending = browser.refreshAuthTokens();
  browser.initAuthClientFromLogin(login('new-login'), site, 'Example App');
  complete();
  assert.equal((await pending).superseded, true);
  assert.equal(storage.get('auth_token'), 'new-login');
});
