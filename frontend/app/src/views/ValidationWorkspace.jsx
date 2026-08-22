// Sprint 11 — Engineering validation: hand-calculation benchmarks vs Imad engine.
import { useCallback, useEffect, useState } from 'react'
import { pApi, validationPdfUrl } from '../platformApi.js'

export default function ValidationWorkspace() {
  const [report, setReport] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Show any previously generated report immediately.
    pApi.validationReport().then(setReport).catch(() => setReport(null))
  }, [])

  const run = useCallback(async () => {
    setRunning(true); setError(null)
    try {
      await pApi.runValidation()
      setReport(await pApi.validationReport())
    } catch (err) {
      setError(err.message || 'Validation run failed.')
    } finally {
      setRunning(false)
    }
  }, [])

  const overall = report?.overall
  const benchmarks = report?.benchmarks ?? []

  return (
    <div className="workspace-grid">
      <section className="card span-2" aria-labelledby="val-title">
        <div className="card-header">
          <h2 id="val-title">Engineering Validation</h2>
          <div className="inline-controls">
            <button className="btn primary" onClick={run} disabled={running}>
              {running ? 'Running benchmarks…' : '▶ Run validation suite'}
            </button>
            {report && (
              <a className="btn" href={validationPdfUrl} target="_blank" rel="noopener noreferrer">
                ⬇ Report PDF
              </a>
            )}
          </div>
        </div>
        <p className="muted">
          Imad&rsquo;s results are compared against closed-form hand calculations (beam bending,
          column buckling/axial shortening, portal-frame moment distribution, multi-storey
          equivalent-lateral-force seismic shear) with a ±5% tolerance. Methodology and formulas:
          see <code>docs/validation.md</code>.
        </p>
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </section>

      {!report && !running && (
        <section className="card span-2"><p className="muted">No validation report yet — run the suite to populate this page.</p></section>
      )}
      {running && (
        <section className="card span-2" aria-busy="true">
          <p className="progress-line">Executing benchmark cases…<span className="spinner" aria-hidden="true" /></p>
        </section>
      )}

      {overall && (
        <section className="card" aria-label="Accuracy score">
          <h3>Accuracy score</h3>
          <p className="score-value">{Number(overall.accuracy_score ?? 0).toFixed(1)}%</p>
          <span className={`badge ${overall.passed ? 'ok' : 'warn'}`}>
            {overall.passed ? `All cases within ±${overall.tolerance_pct}%` : 'Tolerance exceeded'}
          </span>
          <p className="muted small" style={{ marginTop: 8 }}>
            {report.generated_at ? `Generated ${new Date(report.generated_at).toLocaleString()}` : ''}
          </p>
        </section>
      )}

      {report?.warnings?.length > 0 && (
        <section className="card" aria-label="Conservative warnings">
          <h3>Conservative-default warnings</h3>
          <ul className="warning-list">
            {report.warnings.map((w, i) => <li key={i}>{typeof w === 'string' ? w : w.message}</li>)}
          </ul>
        </section>
      )}

      {benchmarks.length > 0 && (
        <section className="card span-2" aria-label="Benchmark comparison">
          <div className="card-header"><h3>Benchmark comparison</h3><span className="badge">{benchmarks.length} cases</span></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>Case</th><th>Quantity</th><th className="num">Hand calc</th>
                    <th className="num">Imad</th><th className="num">Δ %</th><th>Status</th></tr>
              </thead>
              <tbody>
                {benchmarks.map((b, i) => (
                  <tr key={`${b.name}-${i}`}>
                    <td>{b.name}{b.description && <><br /><span className="muted small">{b.description}</span></>}</td>
                    <td>{b.quantity ?? b.metric ?? '—'}</td>
                    <td className="num">{fmt(b.expected)}</td>
                    <td className="num">{fmt(b.imad)}</td>
                    <td className="num">{b.diff_pct != null ? `${Number(b.diff_pct).toFixed(2)}%` : '—'}</td>
                    <td><span className={`badge ${b.passed ? 'ok' : 'warn'}`}>{b.passed ? 'PASS' : 'REVIEW'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

function fmt(v) {
  if (v == null) return '—'
  const n = Number(v)
  return Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 3 }) : String(v)
}