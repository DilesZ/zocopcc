const { timingSafeEqual } = require('node:crypto');

// Defaults preserve the original deployment. A copied project sets its own
// repository coordinates in Vercel Production.
const OWNER = process.env.GITHUB_OWNER || 'DilesZ';
const REPO = process.env.GITHUB_REPO || 'zocopcc';
const WORKFLOW = 'refresh-precios.yml';
const API = 'https://api.github.com';
const API_VERSION = '2026-03-10';

function reply(res, status, body) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.status(status).send(JSON.stringify(body));
}

function allowedOrigin(req) {
  const host = String(req.headers.host || '').toLowerCase();
  if (!host) return false;
  const origin = req.headers.origin;
  const isLocal = process.env.NODE_ENV !== 'production' &&
    ['http://localhost:3000', 'http://localhost:4173'].includes(origin);
  if (isLocal) return true;
  if (!origin) {
    if (req.headers['sec-fetch-site'] === 'same-origin') return true;
    try { return new URL(req.headers.referer || '').host.toLowerCase() === host; }
    catch { return false; }
  }
  try {
    const url = new URL(origin);
    return url.protocol === 'https:' && url.host.toLowerCase() === host;
  } catch {
    return false;
  }
}

function validCronSecret(req) {
  const expected = process.env.PRICE_CRON_SECRET || '';
  const authorization = req.headers.authorization || '';
  const prefix = 'Bearer ';
  if (!expected || !authorization.startsWith(prefix)) return false;
  const provided = Buffer.from(authorization.slice(prefix.length));
  const configured = Buffer.from(expected);
  return provided.length === configured.length && timingSafeEqual(provided, configured);
}

async function github(path, init = {}) {
  const token = process.env.GITHUB_ACTIONS_TOKEN;
  if (!token) throw new Error('Falta configurar GITHUB_ACTIONS_TOKEN en Vercel.');
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': API_VERSION,
      'User-Agent': 'zocopcc-vercel-refresh',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });
  const text = await response.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch {}
  if (!response.ok) {
    const detail = data.message || `GitHub respondió HTTP ${response.status}`;
    throw new Error(detail);
  }
  return { response, data };
}

async function getRun(runId) {
  const { data } = await github(`/repos/${OWNER}/${REPO}/actions/runs/${runId}`);
  return data;
}

async function getRuns() {
  const { data } = await github(
    `/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?branch=main&per_page=20`,
  );
  return data.workflow_runs || [];
}

module.exports = async function handler(req, res) {
  if (!['GET', 'POST'].includes(req.method)) {
    res.setHeader('Allow', 'GET, POST');
    return reply(res, 405, { error: 'Método no permitido.' });
  }
  const isAutomatic = req.method === 'POST' && req.query?.source === 'automatic';
  if (isAutomatic) {
    if (!process.env.PRICE_CRON_SECRET) {
      return reply(res, 503, { error: 'Falta configurar PRICE_CRON_SECRET en Vercel.' });
    }
    if (!validCronSecret(req)) return reply(res, 403, { error: 'Clave del programador no válida.' });
  } else if (!allowedOrigin(req)) {
    return reply(res, 403, { error: 'Origen no permitido.' });
  }

  try {
    if (req.method === 'POST') {
      const runs = await getRuns();
      const active = runs.find(run => ['queued', 'in_progress', 'waiting', 'requested'].includes(run.status));
      if (active) {
        return reply(res, 202, {
          run_id: active.id,
          html_url: active.html_url,
          status: active.status,
          already_running: true,
        });
      }
      const recent = runs.find(run => run.event === 'workflow_dispatch' &&
        Date.now() - Date.parse(run.created_at) < 10 * 60 * 1000);
      if (recent) {
        return reply(res, 429, { error: 'Se acaba de ejecutar una actualización. Espera 10 minutos antes de lanzar otra.' });
      }

      const skipSearch = req.query?.skip_search === '1' ? '1' : '0';
      const triggerType = req.query?.source === 'automatic' ? 'automatic' : 'manual';
      const requestedAt = new Date().toISOString();
      const { data } = await github(
        `/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
        {
          method: 'POST',
          body: JSON.stringify({
            ref: 'main',
            inputs: { limit: '0', skip_search: skipSearch, trigger_type: triggerType },
          }),
        },
      );
      return reply(res, 202, {
        run_id: data.workflow_run_id || null,
        html_url: data.html_url || null,
        requested_at: requestedAt,
        already_running: false,
      });
    }

    const runId = String(req.query?.run_id || '');
    if (/^\d+$/.test(runId)) {
      const run = await getRun(runId);
      return reply(res, 200, {
        run_id: run.id,
        status: run.status,
        conclusion: run.conclusion,
        html_url: run.html_url,
        updated_at: run.updated_at,
      });
    }

    const since = Date.parse(String(req.query?.since || ''));
    if (!Number.isFinite(since)) return reply(res, 400, { error: 'Falta run_id o since.' });
    const run = (await getRuns()).find(item =>
      item.event === 'workflow_dispatch' && Date.parse(item.created_at) >= since - 90_000,
    );
    if (!run) return reply(res, 200, { found: false, status: 'starting' });
    return reply(res, 200, {
      found: true,
      run_id: run.id,
      status: run.status,
      conclusion: run.conclusion,
      html_url: run.html_url,
      updated_at: run.updated_at,
    });
  } catch (error) {
    return reply(res, 502, { error: error.message || 'No se pudo contactar con GitHub.' });
  }
};
