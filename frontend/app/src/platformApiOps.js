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
export const validationPdfUrl = `${BASE_URL}/validation/report/pdf`
export const pApi = {
  currentSubscription: (email) =>
    get(`/subscriptions/${encodeURIComponent(email || 'demo@imad.ai')}`),
  upgradeSubscription: (payload) => post('/subscriptions/upgrade', payload),
  runValidation: () => post('/validation/run', {}),
  validationReport: () => get('/validation/report'),
}
