// Code-compliance checking has moved to the Governance tab, where the
// SBC 304 compliance engine runs the real checks (punching, shear,
// development length, the structuralcodes cross-check, …) against the
// actual analysis results. This page now only redirects.
import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { readStoredProject } from '../useProjectId.jsx'
import { Card } from '../components/shadcn.jsx'

export default function ValidationWorkspace() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const pid = pathname.match(/^\/project\/(\d+)/)?.[1] || readStoredProject()

  useEffect(() => {
    // Redirect to the Governance tab, which now hosts the compliance engine.
    const to = pid ? `/project/${pid}/governance` : '/create-plan'
    navigate(to, { replace: true })
  }, [navigate, pid])

  return (
    <div className="workspace-grid">
      <Card className="span-2">
        <h2>Validation moved</h2>
        <p className="muted">
          Code-compliance checking now runs from the <strong>Governance</strong> tab,
          driven by the SBC 304 compliance engine (real checks against your analysis:
          punching shear, beam shear, development length, the structuralcodes cross-check, …).
        </p>
        <p className="muted small">Redirecting…</p>
      </Card>
    </div>
  )
}