// ─── Imad API · extended endpoints (agents, billing, ops, marketplace) ──────
import { BASE_URL, get, post, patch } from './apiClient.js'

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
// Compliance/package endpoints resolve plan+analysis server-side from the
// project; callers pass { project_id } (optionally plan/plan_name/analysis).
export const runComplianceCheck = (payload) => post('/compliance/check', payload)
export const getComplianceReport = (payload) => post('/compliance/check', payload)
export const generateSBC304Package = (payload) => post('/compliance/sbc304-package', payload)
export const getSubmissionReadiness = (projectId) => get(`/compliance/sbc304-readiness/${projectId}`)
export const requestSignature = (payload) => post('/signature/request', payload)
export const getSubmissionPackage = (projectId) => get(`/submission/${projectId}`)
export const generateSubmissionPackage = (payload) => post('/submission/generate', payload)

// Download an exports-dir file (PDF etc.) served by GET /exports/download.
export const downloadExport = async (path, filename) => {
  const res = await fetch(`${BASE_URL}/exports/download?path=${encodeURIComponent(path)}`)
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || String(path).split(/[\\/]/).pop() || 'imad-export.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

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
export const validationPdfUrl = `${BASE_URL}/validation/report/pdf`
export const pApi = {
  currentSubscription: (email) =>
    get(`/subscriptions/${encodeURIComponent(email || 'demo@imad.ai')}`),
  upgradeSubscription: (payload) => post('/subscriptions/upgrade', payload),
  runValidation: () => post('/validation/run', {}),
  validationReport: () => get('/validation/report'),
}
