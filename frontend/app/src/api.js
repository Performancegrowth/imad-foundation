// Imad frontend — API client.
// Uses the Vite dev proxy (see vite.config.js) so requests go to /api/... .
const BASE = import.meta.env.VITE_APP_API_BASE || '/api/v1'

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }
  // Default 120s request timeout so slow AI generations (Ollama description,
  // analysis, BOQ) don't hang the UI; callers can override via options.timeoutMs.
  const timeoutMs = options.timeoutMs ?? 120000
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError') {
      const e = new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s`)
      e.status = 408
      throw e
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = data.detail || detail
    } catch {
      /* keep statusText */
    }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  // Sprint 2 — CAD
  uploadFile: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/files/upload', { method: 'POST', body: fd })
  },
  processCad: (fileId) =>
    request('/process-cad', { method: 'POST', body: { file_id: fileId } }),

  // Sprint 3 — Plans
  listTemplates: () => request('/plans/templates'),
  generateQuestionnaire: (answers) =>
    request('/plans/questionnaire', { method: 'POST', body: { answers } }),
  generateTemplate: (templateId, floors) =>
    request('/plans/template', { method: 'POST', body: { template_id: templateId, floors } }),
  generateDescription: (text, floors) =>
    request('/plans/description', { method: 'POST', body: { text, floors } }),
  savePlan: (projectId, name, plan) =>
    request('/plans/save', { method: 'POST', body: { project_id: projectId, name, plan } }),
  listPlans: (projectId) => request(`/plans/${projectId}`),

  // Sprint 4 — Survey
  saveSurveyManual: (projectId, reading) =>
    request('/survey/manual', { method: 'POST', body: { project_id: projectId, reading } }),
  uploadSurvey: (projectId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('project_id', String(projectId))
    return request('/survey/upload', { method: 'POST', body: fd })
  },
  getSurvey: (projectId) => request(`/survey/${projectId}`),

  // Sprint 5 — Analysis
  analyze: (payload) => request('/analyze', { method: 'POST', body: payload }),

  // Sprint 6 — Generative design
  generateDesigns: (payload) =>
    request('/generate-designs', { method: 'POST', body: payload }),
  generationStatus: (jobId) => request(`/generate-designs/status/${jobId}`),
  generationRecommendation: (jobId) =>
    request(`/generate-designs/${jobId}/recommendation`),
  selectOption: (jobId, optionId, name) =>
    request('/generate-designs/select', {
      method: 'POST',
      body: { job_id: jobId, option_id: optionId, project_id: 1, name },
    }),
  // aliases used by the GenerativeDesignWorkspace component
  generativeStatus: (jobId) => request(`/generate-designs/status/${jobId}`),
  generativeRecommendation: (jobId) =>
    request(`/generate-designs/${jobId}/recommendation`),
  selectGenerativeOption: (payload) =>
    request('/generate-designs/select', { method: 'POST', body: payload }),

  // Sprint 7 — BOQ
  generateBoq: (payload) =>
    request('/generate-boq', { method: 'POST', body: payload }),
  exportBoqPdf: (resultId) =>
    request(`/generate-boq/${resultId}/export/pdf`, { method: 'POST' }),
  exportBoqXlsx: (resultId) =>
    request(`/generate-boq/${resultId}/export/xlsx`, { method: 'POST' }),
  downloadUrl: (file) =>
    `${BASE}/exports/download?path=${encodeURIComponent(file)}`,

  // Sprint 8 — Sustainability
  carbonReport: (payload) =>
    request('/carbon-report', { method: 'POST', body: payload }),

  // Sprint 9A — 3D building
  buildScene: (payload) =>
    request('/building/scene', { method: 'POST', body: payload }),
  exportGltf: (payload) =>
    request('/building/gltf', { method: 'POST', body: payload }),

  // Sprint 9B — AI agents
  agentSales: (payload) => request('/agents/sales', { method: 'POST', body: payload }),
  agentMarketing: (payload) => request('/agents/marketing', { method: 'POST', body: payload }),

  // Sprint 9C / 14 — billing & subscriptions
  listPlansPricing: () => request('/plans'),
  getSubscription: (userEmail) => request(`/subscriptions/${encodeURIComponent(userEmail)}`),
  upgradeSubscription: (payload) =>
    request('/subscriptions/upgrade', { method: 'POST', body: payload }),
  checkout: (payload) => request('/payments/checkout', { method: 'POST', body: payload }),

  // Sprint 10 — governance
  complianceCheck: (payload) =>
    request('/compliance/check', { method: 'POST', body: payload }),
  requestSignature: (payload) =>
    request('/signature/request', { method: 'POST', body: payload }),
  getSignature: (id) => request(`/signature/${id}`),
  completeSignature: (id) =>
    request(`/signature/${id}/complete`, { method: 'POST' }),
  generateSubmission: (payload) =>
    request('/submission/generate', { method: 'POST', body: payload }),
  getSubmissions: (projectId) => request(`/submission/${projectId}`),
  auditLog: (projectId) => request(`/audit-log/${projectId}`),

  // Sprint 11 — validation
  runValidation: (payload) =>
    request('/validation/run', { method: 'POST', body: payload }),
  validationReport: () => request('/validation/report'),
  validationReportPdf: () => request('/validation/report/pdf', { method: 'POST' }),

  // Sprint 12 — collaboration & BIM
  exportIfc: (payload) => request('/ifc/export', { method: 'POST', body: payload }),
  importIfc: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/ifc/import', { method: 'POST', body: fd })
  },
  listIssues: () => request('/bcf/issues'),
  addIssue: (payload) => request('/bcf/issues', { method: 'POST', body: payload }),
  updateIssue: (id, patch) =>
    request(`/bcf/issues/${id}`, { method: 'PATCH', body: patch }),
  listComments: (projectId) => request(`/comments?project_id=${projectId}`),
  addComment: (payload) => request('/comments', { method: 'POST', body: payload }),
  resolveComment: (id) => request(`/comments/${id}/resolve`, { method: 'PATCH' }),
  listApprovals: (projectId) => request(`/approvals?project_id=${projectId}`),
  createApproval: (payload) => request('/approvals', { method: 'POST', body: payload }),
  transitionApproval: (id, action, reviewer) =>
    request(`/approvals/${id}/transition`, { method: 'POST', body: { action, reviewer } }),
  listTasks: (projectId) => request(`/tasks?project_id=${projectId}`),
  addTask: (payload) => request('/tasks', { method: 'POST', body: payload }),
  moveTask: (id, state, order) =>
    request(`/tasks/${id}/move`, { method: 'PATCH', body: { state, order } }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
  listNotifications: () => request('/notifications'),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: 'POST' }),
  listWebhooks: () => request('/webhooks'),
  addWebhook: (payload) => request('/webhooks', { method: 'POST', body: payload }),
  deleteWebhook: (id) => request(`/webhooks/${id}`, { method: 'DELETE' }),

  // Sprint 13 — ecosystem
  saveSnapshot: (payload) =>
    request('/design-data/snapshot', { method: 'POST', body: payload }),
  designAnalytics: () => request('/analytics/design'),
  listCosts: () => request('/costs'),
  addCost: (payload) => request('/costs', { method: 'POST', body: payload }),
  importCosts: (rows) => request('/costs/import', { method: 'POST', body: { rows } }),
  listSuppliers: () => request('/suppliers'),
  registerSupplier: (payload) => request('/suppliers', { method: 'POST', body: payload }),
  listConsultants: () => request('/consultants'),
  registerConsultant: (payload) => request('/consultants', { method: 'POST', body: payload }),
  requestReview: (payload) =>
    request('/consultants/request-review', { method: 'POST', body: payload }),
  consultantRequests: (projectId) =>
    request(`/consultants/requests/${projectId}`),
  certificationQuiz: () => request('/certification/quiz'),
  completeCertification: (payload) =>
    request('/certification/complete', { method: 'POST', body: payload }),

  // Sprint 9 — 3D building & billing
  buildingScene: (payload) =>
    request('/building/scene', { method: 'POST', body: payload }),
  buildingGltf: (payload) =>
    request('/building/gltf', { method: 'POST', body: payload }),
  planCatalogue: () => request('/plans-catalogue').catch(() => request('/billing/plans')),
  getSubscription: (email) => request(`/subscriptions/${encodeURIComponent(email)}`),
  upgradeSubscription: (payload) =>
    request('/subscriptions/upgrade', { method: 'POST', body: payload }),
  createCheckout: (payload) =>
    request('/payments/checkout', { method: 'POST', body: payload }),

  // Sprint 14 — platform
  listJobs: () => request('/jobs'),
  getJob: (jobId) => request(`/jobs/${jobId}`),
  listTutorials: () => request('/tutorials'),
  supportChat: (message, history) =>
    request('/support/chat', { method: 'POST', body: { message, history } }),
  generateApiKey: (payload) =>
    request('/api-keys/generate', { method: 'POST', body: payload }),
  listApiKeys: (email) => request(`/api-keys/${encodeURIComponent(email)}`),
  revokeApiKey: (keyId) => request(`/api-keys/${keyId}`, { method: 'DELETE' }),
  getWhitelabel: (email) => request(`/whitelabel/${encodeURIComponent(email)}`),
  platformAnalytics: () => request('/analytics'),
  salesAgent: (payload) => request('/agents/sales', { method: 'POST', body: payload }),
  marketingAgent: (payload) => request('/agents/marketing', { method: 'POST', body: payload }),
  supportAgent: (payload) => request('/agents/support', { method: 'POST', body: payload }),
}

export const DEFAULT_PROJECT_ID = 1