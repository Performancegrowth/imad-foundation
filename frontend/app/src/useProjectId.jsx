import { useParams } from 'react-router-dom'

/** Last project the user worked on (set on plan save). */
export function readStoredProject() {
  try {
    const v = parseInt(localStorage.getItem('imad_last_project'), 10)
    return Number.isFinite(v) && v > 0 ? v : null
  } catch {
    return null
  }
}

/**
 * Project id from the URL (/project/:projectId/...), falling back to the
 * last-used project, then to an explicit fallback (or null).
 */
export function useProjectId(fallback = null) {
  const params = useParams()
  const raw = params.projectId
  if (raw != null) {
    const n = parseInt(raw, 10)
    if (Number.isFinite(n) && n > 0) return n
  }
  const stored = readStoredProject()
  return stored ?? fallback
}

/** Friendly empty state shown when no project context exists. */
export function NoProject() {
  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>No project selected</h2>
        <div className="empty">
          <span className="empty-icon" aria-hidden="true">🗂️</span>
          <p>Please create or select a project first.</p>
          <p className="muted small">
            Save a plan in “Create Plan” — Survey, Analysis, BOQ, Sustainability,
            Validation, Building 3D, Collaboration, Governance and Admin will then
            follow that project automatically.
          </p>
        </div>
      </section>
    </div>
  )
}
