// Sprint 7 — BOQ workspace: generate quantities + BBS, view tables & charts,
// download branded PDF / Excel exports.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { BarChart, EmptyState, StatCard } from '../components/ui.jsx'

const money = (v) => `$${Number(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`

export default function BoqWorkspace() {
  const [plans, setPlans] = useState([])
  const [planName, setPlanName] = useState('')
  const [boq, setBoq] = useState(null)
  const [resultId, setResultId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [error, setError] = useState(null)

  const projectId = useProjectId()

  useEffect(() => {
    if (!projectId) return
    api.listPlans(projectId).then(setPlans).catch(() => setPlans([]))
  }, [projectId])

  const generate = useCallback(async () => {
    if (!planName) return
    setBusy(true); setError(null)
    try {
      const data = await api.generateBoq({
        project_id: projectId,
        project_name: planName,
        plan_name: planName,
      })
      setBoq(data)
      setResultId(data.result_id)
    } catch (err) {
      setBoq(null); setError(err.message || 'BOQ generation failed.')
    } finally {
      setBusy(false)
    }
  }, [planName, projectId])

  const doExport = async (kind) => {
    if (!resultId) return
    setExporting(kind)
    try {
      const res = kind === 'pdf' ? await api.exportBoqPdf(resultId)
                                 : await api.exportBoqXlsx(resultId)
      window.open(api.downloadUrl(res.file), '_blank', 'noopener')
    } catch (err) {
      setError(err.message || `${kind.toUpperCase()} export failed.`)
    } finally {
      setExporting(null)
    }
  }

  const chartData = boq?.items.map((i) => ({ label: i.code, value: i.amount_usd })) || []

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <section className="card span-2" aria-labelledby="boq-title">
        <h2 id="boq-title">Bill of Quantities & Bar Schedule</h2>
        <p className="muted">
          Detailed take-off across concrete, rebar, formwork, earthworks and
          waterproofing — with a cutting-optimised bar bending schedule (waste target &lt; 2%).
        </p>
        <div className="inline-controls wrap">
          <label htmlFor="boq-plan" className="sr-only">Saved plan</label>
          <select id="boq-plan" value={planName} onChange={(e) => setPlanName(e.target.value)}>
            <option value="">— Select a saved plan —</option>
            {plans.map((p) => <option key={p.name} value={p.name}>{p.label}</option>)}
          </select>
          <button className="btn primary" onClick={generate} disabled={busy || !planName}>
            {busy ? 'Generating…' : 'Generate BOQ'}
          </button>
          {boq && (
            <div className="inline-controls">
              <button className="btn" onClick={() => doExport('pdf')} disabled={exporting !== null}>
                {exporting === 'pdf' ? 'Rendering…' : '⬇ PDF report'}
              </button>
              <button className="btn" onClick={() => doExport('xlsx')} disabled={exporting !== null}>
                {exporting === 'xlsx' ? 'Writing…' : '⬇ Excel workbook'}
              </button>
            </div>
          )}
        </div>
        {!planName && plans.length === 0 && (
          <EmptyState icon="📋" title="No saved plans yet"
                      hint="Create a plan first (CAD import or Create Plan), then generate its BOQ here." />
        )}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </section>

      {boq && (
        <>
          <section className="card span-2" aria-label="BOQ summary">
            <div className="summary-grid four">
              <StatCard label="Total estimate" value={money(boq.totals.amount_usd)} />
              <StatCard label="Cost / m² GFA" value={money(boq.totals.amount_per_m2)} tone="gold" />
              <StatCard label="Rebar" value={Number(boq.bbs.rebar_total_kg).toLocaleString()} unit="kg" />
              <StatCard label="Cutting waste"
                        value={`${boq.bbs.waste_percent}%`}
                        tone={boq.bbs.within_target ? 'ok' : 'warn'} />
            </div>
          </section>

          <section className="card span-2" aria-label="Cost breakdown chart">
            <div className="card-header"><h3>Cost breakdown by trade</h3></div>
            <BarChart data={chartData} unit="USD" height={200}
                      format={(v) => `$${Math.round(v).toLocaleString()}`} />
          </section>

          <section className="card span-2" aria-label="BOQ table">
            <div className="card-header"><h3>Bill of Quantities</h3><span className="badge">{boq.currency}</span></div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Code</th><th>Description</th><th>Unit</th><th className="num">Qty</th>
                      <th className="num">Rate</th><th className="num">Amount</th></tr>
                </thead>
                <tbody>
                  {boq.items.map((i) => (
                    <tr key={i.code}>
                      <td className="mono">{i.code}</td>
                      <td>{i.description}</td>
                      <td>{i.unit}</td>
                      <td className="num">{Number(i.quantity).toLocaleString()}</td>
                      <td className="num">{money(i.rate)}</td>
                      <td className="num">{money(i.amount_usd)}</td>
                    </tr>
                  ))}
                  <tr className="total-row">
                    <td colSpan={5}>TOTAL</td>
                    <td className="num">{money(boq.totals.amount_usd)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <details className="assumptions">
              <summary>Measurement assumptions</summary>
              <ul>{boq.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </details>
          </section>

          <section className="card span-2" aria-label="Bar bending schedule">
            <div className="card-header">
              <h3>Bar Bending Schedule</h3>
              <span className={`badge ${boq.bbs.within_target ? 'ok' : 'warn'}`}>
                waste {boq.bbs.waste_percent}% vs ≤{boq.bbs.target_waste_percent}%
              </span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Mark</th><th>Element</th><th>Shape</th><th className="num">Ø mm</th>
                      <th className="num">Cut (m)</th><th className="num">Qty</th>
                      <th className="num">Weight (kg)</th></tr>
                </thead>
                <tbody>
                  {boq.bbs.bars.slice(0, 40).map((b) => (
                    <tr key={b.mark}>
                      <td className="mono">{b.mark}</td>
                      <td>{b.element}</td>
                      <td>{b.shape}</td>
                      <td className="num">{b.dia_mm}</td>
                      <td className="num">{b.cut_length_m.toFixed(2)}</td>
                      <td className="num">{b.qty}</td>
                      <td className="num">{Number(b.weight_kg).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {boq.bbs.bars.length > 40 && (
              <p className="muted small">Showing first 40 of {boq.bbs.bars.length} marks — full list in the Excel export.</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}