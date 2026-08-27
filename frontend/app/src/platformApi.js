// ─── Imad frontend · central API client (named exports) ───────────────────
// Plumbing lives in ./apiClient.js; extended domain endpoints live in
// ./platformApiOps.js and are re-exported below, so every view keeps
// importing from '../platformApi' unchanged.
import { get, post, put, del, setToken, getToken } from './apiClient.js'

export { setToken, getToken }

// ─── Auth ──────────────────────────────────────────────────────────────────
// Backend serves these at the router root (no /auth prefix) and wraps the JWT
// as { token: { access_token, ... }, user } — normalized below for callers.
const extractToken = (d) => d?.token?.access_token ?? d?.access_token ?? ''
export const login = async (email, password) => {
  const data = await post('/token', { email, password })
  const t = extractToken(data); if (t) setToken(t)
  return { ...data, access_token: t }
}
export const register = async (userData) => {
  const data = await post('/register', userData)
  const t = extractToken(data); if (t) setToken(t)
  return { ...data, access_token: t }
}
export const refreshToken = () => post('/refresh', { refresh_token: getToken() })

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


// ─── Extended domains (re-exported) ────────────────────────────────────────
// Agents, billing/subscriptions, platform admin, visualization, governance &
// review, collaboration/BIM, ecosystem/marketplace and the legacy `pApi`
// object all live in ./platformApiOps.js and are re-exported unchanged:
export * from './platformApiOps.js'