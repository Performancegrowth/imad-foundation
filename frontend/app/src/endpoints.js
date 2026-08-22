// Sprints 9–14 — endpoint layer for the newer platform modules.
// Deliberately independent of ../api.js so platform features never break
// core workspaces; falls back across equivalent legacy paths where routers
// were mounted twice during development.
const BASE = (import.meta.env?.VITE_API_URL ?? '') + '/api/v1'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json())?.detail || detail } catch { /* ignore */ }
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

async function get(path) {
  return fetch(BASE + path, { headers: { Accept: 'application/json' } }).then(handle)
}

async function post(path, body) {
  return fetch(BASE + path, {
    method: 'POST',
    headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  }).then(handle)
}

/** Try candidate paths until one answers with something other than 404. */
async function postTry(paths, body) {
  let lastErr
  for (const p of paths) {
    try { return await post(p, body) } catch (e) {
      if (e.status === 404) { lastErr = e; continue }
      throw e
    }
  }
  throw lastErr ?? new Error('No endpoint available')
}

async function getTry(paths) {
  let lastErr
  for (const p of paths) {
    try { return await get(p) } catch (e) {
      if (e.status === 404) { lastErr = e; continue }
      throw e
    }
  }
  throw lastErr ?? new Error('No endpoint available')
}

/** Download link for files produced inside the backend exports directory. */
export function exportFileUrl(path) {
  return `${BASE}/generate-boq/exports/download?path=${encodeURIComponent(path)}`
}

// ── Sprint 9A · 3D building ────────────────────────────────────────────────
export const buildingViz = {
  scene: (payload) => postTry(
    ['/viz/building/scene', '/building/scene', '/viz/building'], payload),
  gltf: (payload) => postTry(
    ['/viz/building/gltf', '/building/gltf'], payload),
}

// ── Sprint 9B/9C · agents & billing ────────────────────────────────────────
export const agents = {
  sales: (payload) => post('/agents/sales', payload),
  marketing: (payload) => post('/agents/marketing', payload),
  support: (payload) => postTry(['/support/chat', '/agents/support'], payload),
}

export const billing = {
  plans: () => getTry(['/subscriptions/plans', '/billing/plans']),
  mine: () => getTry(['/subscriptions/me', '/subscriptions/current', '/billing/me']),
  upgrade: (payload) => postTry(['/subscriptions/upgrade', '/billing/upgrade'], payload),
  analytics: () => getTry(['/analytics/overview', '/billing/analytics', '/admin/analytics']),
}

// ── Sprint 10 · governance ─────────────────────────────────────────────────
export const governance = {
  compliance: (designId) => post('/compliance/check', { design_id: designId }),
  sign: (payload) => post('/signature/request', payload),
  submission: (payload) => post('/submission/generate', payload),
  auditLog: (projectId) => get(`/audit-log/${projectId}`),
}

// ── Sprint 11 · validation ─────────────────────────────────────────────────
export const validation = {
  run: () => postTry(['/validation/run', '/validation/suite'], {}),
  report: () => getTry(['/validation/report', '/validation/report/latest']),
}

// ── Sprint 12 · collaboration & BIM ────────────────────────────────────────
export const collab = {
  ifcExport: (payload) => post('/ifc/export', payload),
  ifcImport: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return post('/ifc/import', fd)
  },
  comments: (projectId) => get(`/comments?project_id=${projectId}`),
  addComment: (body) => post('/comments', body),
  approvals: (projectId) => get(`/approvals?project_id=${projectId}`),
  saveApproval: (body) => post('/approvals', body),
  tasks: (projectId) => get(`/tasks?project_id=${projectId}`),
  saveTask: (body) => post('/tasks', body),
  moveTask: (id, state) => postTry([`/tasks/${id}/state`, `/tasks/${id}`], { state }),
  notifications: () => get('/notifications'),
  markRead: (id) => postTry([`/notifications/${id}/read`, `/notifications/${id}`], {}),
}

// ── Sprint 13 · ecosystem & marketplace ────────────────────────────────────
export const ecosystem = {
  snapshot: (payload) => post('/design-data/snapshot', payload),
  analytics: () => get('/analytics/design'),
  costs: (region = '') =>
    get('/costs' + (region ? `?region=${encodeURIComponent(region)}` : '')),
  addCost: (payload) => post('/costs', payload),
  importCosts: (items) => post('/costs/import', { items }),
  suppliers: () => get('/suppliers'),
  addSupplier: (payload) => post('/suppliers', payload),
  consultants: () => getTry(['/consultants', '/consultants/list']),
  requestReview: (payload) => post('/consultants/request-review', payload),
  certification: (payload) => post('/certification/complete', payload),
  quiz: () => getTry(['/certification/quiz', '/certification/questions']),
}

// ── Sprint 14 · platform administration ────────────────────────────────────
export const platform = {
  jobs: () => getTry(['/jobs', '/jobs/list']),
  tutorials: () => getTry(['/tutorials', '/tutorials/list']),
  apiKeys: () => getTry(['/api-keys', '/keys']),
  createKey: (name, scopes) => post('/api-keys/generate', { name, scopes }),
  revokeKey: (id) => postTry([`/api-keys/${id}/revoke`, `/api-keys/${id}`], {}),
  whitelabel: () => getTry(['/whitelabel', '/settings/whitelabel']),
  saveWhitelabel: (payload) => postTry(['/whitelabel', '/settings/whitelabel'], payload),
}