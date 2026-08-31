#!/usr/bin/env node
/*
 * Contoso Events — Microsoft IQ orchestrator web client (local proxy)
 * ------------------------------------------------------------------
 * A tiny zero-dependency Node server that:
 *   1. Serves a branded chat page (public/index.html).
 *   2. Signs the user in interactively (device code).
 *   3. Proxies chat turns to a published Azure AI Foundry agent via the
 *      project Responses API. The agent routes each question to the right
 *      grounded source (Fabric Data Agent for numbers, Foundry IQ for
 *      knowledge) and cites which one it used.
 *
 * Invocation contract (verified):
 *   POST {account}/api/projects/{project}/openai/responses?api-version=2025-05-15-preview
 *   Authorization: Bearer <https://ai.azure.com/.default token>
 *   body: { "input": <question>,
 *           "agent": { "type": "agent_reference", "name": <AGENT_NAME> },
 *           "previous_response_id": <prior id> }   // optional, multi-turn
 *
 * The signed-in identity needs the "Cognitive Services OpenAI User" data-plane
 * role on the Foundry resource (API-key auth is typically disabled).
 *
 * Configure via a .env file (see .env.example). Run:  node server.js
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

// ---- minimal .env loader (zero-dependency) ---------------------------------
(function loadEnv() {
  const p = path.join(__dirname, '.env');
  if (!fs.existsSync(p)) return;
  for (const line of fs.readFileSync(p, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/i);
    if (m && !(m[1] in process.env)) {
      process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
    }
  }
})();

// ---- Configuration ---------------------------------------------------------
const PORT = process.env.PORT || 3000;
const BRAND = process.env.BRAND || 'Contoso Events';
// Azure AI Foundry project that hosts the orchestrator agent.
const FOUNDRY_ACCOUNT = process.env.FOUNDRY_ACCOUNT || 'https://YOUR-FOUNDRY.services.ai.azure.com';
const PROJECT = process.env.FOUNDRY_PROJECT || 'your-project';
const AGENT_NAME = process.env.FOUNDRY_AGENT || 'ConferenceIQ-Orchestrator';
const API_VERSION = process.env.FOUNDRY_API_VERSION || '2025-05-15-preview';
const RESPONSES_URL = FOUNDRY_ACCOUNT + '/api/projects/' + PROJECT +
  '/openai/responses?api-version=' + API_VERSION;

// Azure CLI public client — supports device-code and mints Foundry tokens.
const CLIENT_ID = process.env.AZURE_CLIENT_ID || '04b07795-8ddb-461a-bbee-02f9e1bf7b46';
const TENANT = process.env.AZURE_TENANT || 'organizations';
const AUTHORITY = 'https://login.microsoftonline.com/' + TENANT;
const SCOPE = 'https://ai.azure.com/.default offline_access openid profile';

// ---- In-memory state (single local user) -----------------------------------
let token = null;                // { access_token, expires_at, refresh_token, account }
let previousResponseId = null;   // chains multi-turn context
const pending = {};              // pollId -> device-code flow state

// ---- Auth helpers ----------------------------------------------------------
function form(obj) {
  return Object.entries(obj).map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
}
function decodeJwt(t) {
  try { return JSON.parse(Buffer.from(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8')); }
  catch (e) { return {}; }
}
function accountName(access) {
  const c = decodeJwt(access);
  return c.upn || c.unique_name || c.preferred_username || c.email || c.name || 'signed in';
}
async function startDeviceCode() {
  const r = await fetch(AUTHORITY + '/oauth2/v2.0/devicecode', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form({ client_id: CLIENT_ID, scope: SCOPE }),
  });
  const j = await r.json();
  if (!j.device_code) throw new Error('devicecode failed: ' + JSON.stringify(j));
  return j;
}
async function pollDeviceCode(device_code) {
  const r = await fetch(AUTHORITY + '/oauth2/v2.0/token', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form({ grant_type: 'urn:ietf:params:oauth:grant-type:device_code', client_id: CLIENT_ID, device_code }),
  });
  return { status: r.status, body: await r.json() };
}
async function refresh() {
  if (!token || !token.refresh_token) return false;
  const r = await fetch(AUTHORITY + '/oauth2/v2.0/token', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form({ grant_type: 'refresh_token', client_id: CLIENT_ID, scope: SCOPE, refresh_token: token.refresh_token }),
  });
  const j = await r.json();
  if (!j.access_token) return false;
  token = {
    access_token: j.access_token,
    refresh_token: j.refresh_token || token.refresh_token,
    expires_at: Date.now() + (j.expires_in - 120) * 1000,
    account: accountName(j.access_token),
  };
  return true;
}
async function getAccessToken() {
  if (!token) throw new Error('not_signed_in');
  if (Date.now() < token.expires_at) return token.access_token;
  if (await refresh()) return token.access_token;
  token = null;
  throw new Error('not_signed_in');
}

// ---- Foundry Agent (project Responses API) ---------------------------------
function extractText(resp) {
  if (resp.output_text) return resp.output_text;
  const out = resp.output;
  if (Array.isArray(out)) {
    const parts = [];
    for (const it of out) {
      if (it.type === 'message' && Array.isArray(it.content)) {
        for (const c of it.content) {
          if (typeof c.text === 'string' && c.text) parts.push(c.text);
          else if (c.type === 'output_text' && c.output_text) parts.push(c.output_text);
        }
      }
    }
    return parts.join('\n').trim();
  }
  return '';
}

async function askAgent(question) {
  const access = await getAccessToken();
  const body = {
    input: question,
    agent: { type: 'agent_reference', name: AGENT_NAME },
  };
  if (previousResponseId) body.previous_response_id = previousResponseId;

  const r = await fetch(RESPONSES_URL, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + access, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let j;
  try { j = await r.json(); } catch (e) { j = {}; }

  if (!r.ok || j.error) {
    const e = j.error || {};
    return { ok: false, error: e.message || e.code || ('HTTP ' + r.status) };
  }
  if (j.status && j.status !== 'completed') {
    const detail = (j.error && (j.error.code + ': ' + (j.error.message || ''))) ||
                   (j.incomplete_details && j.incomplete_details.reason) || j.status;
    return { ok: false, runState: j.status, error: detail };
  }
  previousResponseId = j.id || previousResponseId;
  return { ok: true, answer: extractText(j) || '(no answer returned)' };
}

// ---- HTTP plumbing ---------------------------------------------------------
function send(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(obj));
}
function readBody(req) {
  return new Promise((resolve) => {
    let d = '';
    req.on('data', (c) => (d += c));
    req.on('end', () => { try { resolve(d ? JSON.parse(d) : {}); } catch (e) { resolve({}); } });
  });
}

const server = http.createServer(async (req, res) => {
  try {
    const u = req.url.split('?')[0];

    if (req.method === 'GET' && (u === '/' || u === '/index.html')) {
      let html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');
      html = html.replace(/\{\{BRAND\}\}/g, BRAND);
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(html);
    }

    if (req.method === 'GET' && u === '/api/status') {
      let signedIn = false, account = null;
      if (token) { try { await getAccessToken(); signedIn = true; account = token.account; } catch (e) { signedIn = false; } }
      return send(res, 200, { signedIn, account, brand: BRAND });
    }

    if (req.method === 'POST' && u === '/api/login/start') {
      const dc = await startDeviceCode();
      const pollId = Math.random().toString(36).slice(2);
      pending[pollId] = { device_code: dc.device_code, interval: (dc.interval || 5), expires_at: Date.now() + dc.expires_in * 1000 };
      return send(res, 200, { pollId, user_code: dc.user_code, verification_uri: dc.verification_uri, interval: dc.interval || 5 });
    }

    if (req.method === 'POST' && u === '/api/login/poll') {
      const { pollId } = await readBody(req);
      const p = pending[pollId];
      if (!p) return send(res, 200, { status: 'error', error: 'unknown poll id' });
      if (Date.now() > p.expires_at) { delete pending[pollId]; return send(res, 200, { status: 'error', error: 'code expired' }); }
      const { body } = await pollDeviceCode(p.device_code);
      if (body.access_token) {
        token = {
          access_token: body.access_token, refresh_token: body.refresh_token,
          expires_at: Date.now() + (body.expires_in - 120) * 1000, account: accountName(body.access_token),
        };
        delete pending[pollId];
        return send(res, 200, { status: 'ok', account: token.account });
      }
      if (body.error === 'authorization_pending' || body.error === 'slow_down') return send(res, 200, { status: 'pending' });
      delete pending[pollId];
      return send(res, 200, { status: 'error', error: body.error_description || body.error || 'login failed' });
    }

    if (req.method === 'POST' && u === '/api/logout') { token = null; previousResponseId = null; return send(res, 200, { ok: true }); }
    if (req.method === 'POST' && u === '/api/reset') { previousResponseId = null; return send(res, 200, { ok: true }); }

    if (req.method === 'POST' && u === '/api/ask') {
      const { question } = await readBody(req);
      if (!question || !question.trim()) return send(res, 200, { ok: false, error: 'empty question' });
      try { return send(res, 200, await askAgent(question.trim())); }
      catch (e) {
        const msg = String(e.message || e);
        if (msg === 'not_signed_in') return send(res, 200, { ok: false, error: 'not_signed_in' });
        return send(res, 200, { ok: false, error: msg });
      }
    }

    res.writeHead(404); res.end('Not found');
  } catch (e) {
    send(res, 500, { error: String(e.message || e) });
  }
});

server.listen(PORT, () => {
  console.log('\n  ' + BRAND + ' Microsoft IQ client running:');
  console.log('    ->  http://localhost:' + PORT);
  console.log('    agent: ' + AGENT_NAME + '  (project ' + PROJECT + ')');
  if (FOUNDRY_ACCOUNT.includes('YOUR-FOUNDRY')) {
    console.log('\n  [!] Set FOUNDRY_ACCOUNT / FOUNDRY_PROJECT / FOUNDRY_AGENT in .env first.');
  }
  console.log('\n  Sign in with your Microsoft account when prompted.\n');
});
