// ─── Imad API plumbing: base URL, JWT persistence, fetch wrapper ──────────
const BASE = (import.meta.env?.VITE_APP_API_BASE || '/api/v1')
const TOKEN_KEY = 'imad_token'
let _token = (() => { try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' } })()

export function setToken(t) {
  _token = t || ''; try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch {}
}
export function getToken() { return _token }

export async function request(path, options = {}) {
  const headers = { Accept: 'application/json', ...(options.headers || {}) }
  if (_token) headers.Authorization = `Bearer ${_token}`
  let body = options.body
  if (body && !(body instanceof FormData)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body) }
  // Default 120s timeout for slow AI generations; callers can override timeoutMs.
  const timeoutMs = options.timeoutMs ?? 120000
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res
  try { res = await fetch(BASE + path, { ...options, headers, body, signal: controller.signal }) }
  catch (err) {
    if (err.name === 'AbortError') { const e = new Error('Request timed out'); e.status = 408; throw e }
    throw new Error('Network error reaching ' + BASE + path)
  } finally { clearTimeout(timer) }
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json())?.detail ?? detail } catch {}
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    err.status = res.status; throw err
  }
  return res.status === 204 ? null : res.json()
}

export const BASE_URL = BASE
export const get = (p) => request(p)
export const post = (p, body) => request(p, { method: 'POST', body: body ?? {} })
export const put = (p, body) => request(p, { method: 'PUT', body })
export const patch = (p, body) => request(p, { method: 'PATCH', body })
export const del = (p) => request(p, { method: 'DELETE' })
