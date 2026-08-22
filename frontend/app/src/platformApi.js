// ─── Imad frontend · central API client (named exports) ───────────────────
// Base URL from VITE_APP_API_BASE env, else the local FastAPI /api/v1.
// JWT token is persisted in localStorage and attached as a Bearer header.
const BASE = (import.meta.env?.VITE_APP_API_BASE || '/api/v1')
const TOKEN_KEY = 'imad_token'
let _token = (() => { try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' } })()

export function setToken(t) {
  _token = t || ''; try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch {}
}
export function getToken() { return _token }

async function request(path, options = {}) {
  const headers = { Accept: 'application/json', ...(options.headers || {}) }
  if (_token) headers.Authorization = `Bearer ${_token}`
  let body = options.body
  if (body && !(body instanceof FormData)) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(body) }
  let res
  try { res = await fetch(BASE + path, { ...options, headers, body }) }
  catch { throw new Error('Network error reaching ' + BASE + path) }
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json())?.detail ?? detail } catch {}
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    err.status = res.status; throw err
  }
  return res.status === 204 ? null : res.json()
}
const get = (p) => request(p)
const post = (p, body) => request(p, { method: 'POST', body: body ?? {} })
const put = (p, body) => request(p, { method: 'PUT', body })
const patch = (p, body) => request(p, { method: 'PATCH', body })
const del = (p) => request(p, { method: 'DELETE' })

// ─── Auth ──────────────────────────────────────────────────────────────────
export const login = async (email, password) => {
  const data = await post('/auth/token', { email, password })
  if (data?.access_token) setToken(data.access_token)
  return data
}
export const register = (userData) => post('/auth/register', userData)
export const refreshToken = () => post('/auth/refresh', {})

// ─── Projects ──────────────────────────────────────────────────────────────
export const getProjects = () => get('/projects')
export const getProject = (id) => get(`/projects/${id}`)
export const createProject = (d) => post('/projects', d)
export const updateProject = (id, d) => put(`/projects/${id}`, d)
export const deleteProject = (id) => del(`/projects/${id}`)

// ─── Upload & CAD ──────────────────────────────────────────────────────────
export const uploadFile = (file) => { const fd = new FormData(); fd.append('file', file); return post('/files/upload', fd) }
export const processCad = (fileId) => post('/process-cad', { file_id: fileId })

// ─── Plans ─────────────────────────────────────────────────────────────────
export const generateFromQuestionnaire = (answers) => post('/plans/questionnaire', { answers })
export const generateFromTemplate = (templateId) => post('/plans/template', { template_id: templateId })
export const generateFromDescription = (text) => post('/plans/description', { text })
export const savePlan = (projectId, planData) => post('/plans/save', { project_id: projectId, plan: planData })
export const getPlan = (projectId) => get(`/plans/${projectId}`)

// ─── Survey ────────────────────────────────────────────────────────────────
export const saveManualSurvey = (projectId, surveyData) => post('/survey/manual', { project_id: projectId, ...surveyData })
export const uploadSurveyFile = (projectId, file) => {
  const fd = new FormData(); fd.append('file', file); fd.append('project_id', String(projectId))
  return post('/survey/upload', fd)
}

// ─── Analysis ──────────────────────────────────────────────────────────────
export const analyzeStructure = (designId) => post('/analyze', { design_id: designId })
export const getAnalysisStatus = (jobId) => get(`/jobs/${jobId}`)
export const getAnalysisResults = async (jobId) => {
  const r = await get(`/jobs/${jobId}`); const j = r?.job ?? r
  return { status: r?.status, ...(j?.result ?? j?.results ?? j) }
}

// ─── Generative Design ─────────────────────────────────────────────────────
export const generateDesigns = (projectId) => post('/generate-designs', { project_id: projectId })
export const getGenerativeStatus = (jobId) => get(`/generate-designs/status/${jobId}`)
export const getGenerativeResults = (jobId) => get(`/generate-designs/${jobId}/recommendation`)

// ─── BOQ ───────────────────────────────────────────────────────────────────
export const generateBoq = (designId) => post('/generate-boq', { design_id: designId })
export const getBoq = (designId) => get(`/generate-boq/${designId}`)

// ─── Carbon ────────────────────────────────────────────────────────────────
export const generateCarbonReport = (designId) => post('/carbon-report', { design_id: designId })

// ─── Validation ────────────────────────────────────────────────────────────
export const runValidation = () => post('/validation/run', {})
export const getValidationReport = () => get('/validation/report')

// ─── Agents ────────────────────────────────────────────────────────────────
export const generateSalesEmail = (prompt) => post('/agents/sales', { prompt })
export const generateMarketingContent = (prompt) => post('/agents/marketing', { prompt })
export const chatSupport = (message) => post('/support/chat', { message })

// ─── Billing & Subscription ────────────────────────────────────────────────
export const getPlans = () => get('/plans')
export const getCurrentSubscription = (email) => get(`/subscriptions/${encodeURIComponent(email || 'demo@imad.ai')}`)
export const upgradeSubscription = (planId) => post('/subscriptions/upgrade', { plan_id: planId })

// ─── Platform admin ────────────────────────────────────────────────────────
export const getAnalytics = () => get('/analytics')
export const getAuditLog = (projectId) => get(`/audit-log/${projectId}`)

// ─── Visualization (Sprint 9A) ─────────────────────────────────────────────
export const getVisualizationData = (designId) => post('/viz/building/scene', { design_id: designId })

// ─── Governance & review (Sprint 10) ───────────────────────────────────────
export const runComplianceCheck = (designId) => post('/compliance/check', { design_id: designId })
export const getComplianceReport = (designId) => post('/compliance/check', { design_id: designId })
export const requestSignature = (payload) => post('/signature/request', payload)
export const getSubmissionPackage = (projectId) => get(`/submission/${projectId}`)
export const generateSubmissionPackage = (designId) => post('/submission/generate', { design_id: designId })

// ─── Collaboration & BIM (Sprint 12) ───────────────────────────────────────
export const getComments = (projectId) => get(`/comments?project_id=${projectId}`)
export const addComment = (payload) => post('/comments', payload)
export const getTasks = (projectId) => get(`/tasks?project_id=${projectId}`)
export const createTask = (payload) => post('/tasks', payload)
export const updateTask = (id, state) => patch(`/tasks/${id}/move`, { state })

// ─── Ecosystem & marketplace (Sprint 13) ───────────────────────────────────
export const getSuppliers = () => get('/suppliers')
export const getConsultants = () => get('/consultants')
export const getCostData = (region) => get('/costs' + (region ? `?region=${encodeURIComponent(region)}` : ''))
export const requestConsultantReview = (payload) => post('/consultants/request-review', payload)

// ─── Legacy `pApi` object + PDF URL (Pricing & Validation workspaces) ────
export const validationPdfUrl = `${BASE}/validation/report/pdf`
export const pApi = {
  currentSubscription: (email) =>
    get(`/subscriptions/${encodeURIComponent(email || 'demo@imad.ai')}`),
  upgradeSubscription: (payload) => post('/subscriptions/upgrade', payload),
  runValidation: () => post('/validation/run', {}),
  validationReport: () => get('/validation/report'),
}