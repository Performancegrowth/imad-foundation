// Sprint 8 — Sustainability dashboard: embodied-carbon breakdown, benchmark
// banding, green alternatives comparison and LCA report download.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { BarChart, EmptyState, StatCard } from '../components/ui.jsx'

const fmt = (v, d = 1) => Number(v ?? 0).toLocaleString(undefined,
  { maximumFractionDigits: d })

export default function CarbonWorkspace() {
  const [plans, setPlans] = useState([])
  const [planName, setPlanName] = useState('')
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState(null)

  const projectId = useProjectId()

  useEffect(() => {
    if (!projectId) return
    api.listPlans(projectId).then(setPlans).catch(() => setPlans([]))
  }, [projectId])

  const run = useCallback(async () => {
    if (!planName) return
    setBusy(true); setError(null)
    try {
      setReport(await api.carbonReport({ project_id: projectId, plan_name: planName }))
    } catch (err) {
      setReport(null); setError(err.message || 'Carbon report failed.')
    } finally {
      setBusy(false)
    }
  }, [planName, projectId])

  const download = async () => {
    if (!report?.lca_pdf) return
    setDownloading(true)
    try {
      window.open(api.downloadUrl(report.lca_pdf), '_blank', 'noopener')
    } finally {
      setDownloading(false)
    }
  }

  const bandTone = { 'Best practice': 'ok', Typical: '', 'High impact': 'warn' }
  const breakdownChart = report
    ? report.carbon.breakdown.slice(0, 8)
        .map((r) => ({ label: r.code, value: r.co2e_kg }))
    : []

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <section className="card span-2" aria-labelledby="carbon-title">
        <h2 id="carbon-title">Sustainability & Embodied Carbon</h2>
        <p className="muted">
          Cradle-to-gate LCA from the BOQ using published emission factors
          (ICE v3.0, worldsteel), with green alternatives and LEED / Mostadam / Estidama mapping.
        </p>
        <div className="inline-controls wrap">
          <label htmlFor="carbon-plan" className="sr-only">Saved plan</label>
          <select id="carbon-plan" value={planName} onChange={(e) => setPlanName(e.target.value)}>
            <option value="">— Select a saved plan —</option>
            {plans.map((p) => <option key={p.name} value={p.name}>{p.label}</option>)}
          </select>
          <button className="btn primary" onClick={run} disabled={busy || !planName}>
            {busy ? 'Computing…' : 'Compute carbon & alternatives'}
          </button>
          {report && (
            <button className="btn" onClick={download} disabled={downloading}>
              {downloading ? 'Preparing…' : '⬇ LCA report (PDF)'}
            </button>
          )}
        </div>
        {!planName && plans.length === 0 && (
          <EmptyState icon="🌱" title="Nothing to assess yet"
                      hint="Generate a BOQ-able plan first — carbon is computed from its quantities." />
        )}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </section>

      {report && (
        <>
          <section className="card span-2" aria-label="Carbon KPIs">
            <div className="summary-grid four">
              <StatCard label="Embodied carbon"
                        value={fmt(report.carbon.total_co2e_tonnes)} unit="tCO₂e" />
              <StatCard label="Intensity"
                        value={fmt(report.carbon.intensity_kgco2e_m2)} unit="kgCO₂e/m²"
                        tone="gold" />
              <StatCard label="Benchmark band"
                        value={report.carbon.benchmark_band}
                        tone={bandTone[report.carbon.benchmark_band] ?? ''} />
              <StatCard label="Best alternative saving"
                        value={`${Math.max(0, ...report.alternatives.map((a) => a.total_cut_pct))}%`}
                        tone="ok" />
            </div>
          </section>

          <section className="card span-2" aria-label="Carbon breakdown">
            <div className="card-header"><h3>Carbon by trade (kgCO₂e)</h3></div>
            <BarChart data={breakdownChart} unit="kgCO₂e" height={210}
                      format={(v) => fmt(v, 0)} />
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Item</th><th className="num">Qty</th><th className="num">EF</th>
                      <th className="num">kgCO₂e</th><th className="num">Share</th><th>Reference</th></tr>
                </thead>
                <tbody>
                  {report.carbon.breakdown.map((r) => (
                    <tr key={r.code}>
                      <td>{r.description}</td>
                      <td className="num">{fmt(r.quantity)}</td>
                      <td className="num">{r.emission_factor}</td>
                      <td className="num">{fmt(r.co2e_kg)}</td>
                      <td className="num">{r.share_pct}%</td>
                      <td className="muted small">{r.reference}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card span-2" aria-label="Green alternatives">
            <div className="card-header"><h3>Green alternatives</h3></div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Option</th><th className="num">CO₂ cut</th>
                      <th className="num">Cost impact</th></tr>
                </thead>
                <tbody>
                  {report.alternatives.map((a) => (
                    <tr key={a.id}>
                      <td><strong>{a.name}</strong><br /><span className="muted small">{a.notes}</span></td>
                      <td className="num ok-text">−{a.total_cut_pct}%</td>
                      <td className={`num ${a.cost_delta_pct <= 0 ? 'ok-text' : 'warn-text'}`}>
                        {a.cost_delta_pct <= 0 ? '−' : '+'}{Math.abs(a.cost_delta_pct)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card span-2" aria-label="Compliance mapping">
            <div className="card-header"><h3>Rating-system compliance snapshot</h3></div>
            <ul className="check-list">
              {Object.entries(report.compliance).map(([k, v]) => (
                <li key={k} className={v ? 'pass' : 'fail'}>
                  <span aria-hidden="true">{v ? '✓' : '✗'}</span> {k}
                  <span className="muted small"> — {v ? 'criterion likely met; confirm with documentation'
                                                    : 'requires the green alternatives above to qualify'}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}