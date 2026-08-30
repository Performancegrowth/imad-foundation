import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import StructureViewer from '../components/StructureViewer.jsx'

// Deterministic demo frame used when no plan has been saved yet, so the
// analysis workspace can be exercised immediately.
function makeDemoPlan() {
  const columns = []
  const beams = []
  const walls = []
  const grids = []
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 2; j++) {
      const cx = i * 6
      const cy = j * 6
      columns.push({ id: `c${i}${j}`, cx, cy, size_m: 0.3, height: 3.0 })
    }
  }
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 2; j++) {
      beams.push({ id: `bh${i}${j}`, x1: i * 6, y1: j * 6, x2: i * 6 + 6, y2: j * 6, width_m: 0.3, depth_m: 0.5 })
    }
  }
  for (let j = 0; j < 2; j++) {
    beams.push({ id: `bv${j}`, x1: 0, y1: j * 6, x2: 12, y2: j * 6, width_m: 0.3, depth_m: 0.5 })
  }
  walls.push({ id: 'w1', x1: 0, y1: 0, x2: 12, y2: 0, thickness_m: 0.15 })
  grids.push({ id: 'v1', orientation: 'vertical', position: 0, label: '1' })
  return {
    source: 'demo', units: 'm', stories: 1,
    columns, beams, walls, grids,
    materials: { concrete: 'C30', steel: 'A615 Gr60' },
  }
}

export default function AnalysisWorkspace() {
  const [plan, setPlan] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [savedPlans, setSavedPlans] = useState([])
  const [selectedName, setSelectedName] = useState('')

  const projectId = useProjectId()

  useEffect(() => {
    if (!projectId) return
    api.listPlans(projectId).then(setSavedPlans).catch(() => setSavedPlans([]))
  }, [projectId])

  const analyze = useCallback(async (payload) => {
    setBusy(true); setError(null); setResult(null)
    try {
      const data = await api.analyze(payload)
      setResult(data)
      setPlan(payload.plan || plan)
    } catch (err) {
      setError(err.message || 'Analysis failed')
    } finally {
      setBusy(false)
    }
  }, [plan])

  const analyzeDemo = () => {
    const p = makeDemoPlan()
    setPlan(p)
    analyze({ project_id: projectId, plan: p })
  }

  const analyzeSaved = () => {
    if (!selectedName) return
    analyze({ project_id: projectId, plan_name: selectedName })
  }

  const fmt = (v, unit) =>
    v === undefined || v === null ? '—' : `${Number(v).toLocaleString()} ${unit}`

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>Structural Analysis</h2>
        <p className="muted">Run a linear static + modal analysis (OpenSeesPy, analytic fallback) and a preliminary ACI 318 design + BOQ.</p>

        {busy && <div className="alert info" role="status">Running analysis…</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}

        <div className="inline-controls wrap">
          <button className="btn primary" onClick={analyzeDemo} disabled={busy}>
            {busy ? 'Analyzing…' : 'Analyze Demo Frame'}
          </button>
          {savedPlans.length > 0 && (
            <>
              <select value={selectedName} onChange={(e) => setSelectedName(e.target.value)} aria-label="Saved plan">
                <option value="">— Select saved plan —</option>
                {savedPlans.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
              </select>
              <button className="btn" onClick={analyzeSaved} disabled={busy || !selectedName}>
                Analyze Saved
              </button>
            </>
          )}
        </div>
      </section>

      {result && (
        <>
          <section className="card span-2">
            <div className="card-header">
              <h3>3D Model</h3>
              <span className="badge">{result.solver === 'opensees' ? 'OpenSeesPy' : 'Analytic solver'}</span>
            </div>
            <StructureViewer plan={plan || result.plan} forces={result.member_forces} />
            <p className="muted small">Drag to orbit · scroll to zoom · green = light load, gold = moderate, red = near/over capacity.</p>
          </section>

          <section className="card span-2">
            <div className="card-header"><h3>Summary of Forces</h3></div>
            <div className="summary-grid four">
              <div className="stat"><span className="stat-label">Max moment</span><strong>{fmt(result.summary?.max_moment_kNm, 'kN·m')}</strong></div>
              <div className="stat"><span className="stat-label">Max shear</span><strong>{fmt(result.summary?.max_shear_kN, 'kN')}</strong></div>
              <div className="stat"><span className="stat-label">Max axial</span><strong>{fmt(result.summary?.max_axial_kN, 'kN')}</strong></div>
              <div className="stat"><span className="stat-label">Max deflection</span><strong>{fmt(result.summary?.max_deflection_mm, 'mm')}</strong></div>
            </div>
            <table className="data-table">
              <thead>
                <tr><th>Element</th><th>Type</th><th>Moment (kN·m)</th><th>Shear (kN)</th><th>Axial (kN)</th></tr>
              </thead>
              <tbody>
                {(result.member_forces || []).map((f, idx) => (
                  <tr key={`${f.element_id}-${idx}`}>
                    <td>{f.element_id}</td>
                    <td>{f.kind}</td>
                    <td>{fmt(f.moment_kNm, '')}</td>
                    <td>{fmt(f.shear_kN, '')}</td>
                    <td>{fmt(f.axial_kN, '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card">
            <div className="card-header"><h3>Concrete Design (ACI 318)</h3></div>
            <p className="muted small">
              C{result.design?.concrete_strength_mpa || 30} · fy {result.design?.steel_yield_mpa || 460} MPa ·
              utilization <strong>{result.design?.max_utilization ?? '—'}</strong>
            </p>
            <p className={`pill ${result.design?.status === 'acceptable' ? 'ok' : 'warn'}`}>
              {result.design?.status || '—'}
            </p>
          </section>

          <section className="card">
            <div className="card-header"><h3>Preliminary BOQ</h3></div>
            <div className="summary-grid">
              <div className="stat"><span className="stat-label">Concrete</span><strong>{fmt(result.boq?.concrete_m3, 'm³')}</strong></div>
              <div className="stat"><span className="stat-label">Rebar</span><strong>{fmt(result.boq?.rebar_tonnes, 't')}</strong></div>
              <div className="stat"><span className="stat-label">Footprint</span><strong>{fmt(result.boq?.footprint_m2, 'm²')}</strong></div>
            </div>
          </section>
        </>
      )}

      {!result && !busy && (
        <section className="card span-2">
          <div className="empty">
            <span className="empty-icon" aria-hidden="true">≣</span>
            <p>Run an analysis to view the 3D model, forces, design checks and BOQ.</p>
          </div>
        </section>
      )}
    </div>
  )
}