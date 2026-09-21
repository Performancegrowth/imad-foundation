// Public Proof page — "Imad vs. hand calculations".
// Shows the engineering validation benchmark suite (closed-form reference
// vs the solver) to any visitor, no login required. The report is fetched
// from the latest stored suite run; numbers come from the backend —
// nothing here is hand-written marketing copy.
import { useEffect, useState } from 'react'
import Seo from '../components/Seo.jsx'
import { SITE_URL } from '../seoData.js'
import { getPublicValidationReport } from '../platformApi.js'
import { Card } from '../components/shadcn.jsx'
import { LoadingCard, EmptyCard } from '../components/ui.jsx'

const METHOD = [
  { qty: 'Simply supported beam', how: 'M = wL²/8 · V = wL/2 · δ = 5wL⁴/(384EI)', ref: 'ACI 318 · mechanics of materials' },
  { qty: 'Short column', how: 'N = q·A_floor/n_cols · σ = N/A', ref: 'Tributary-area takedown' },
  { qty: 'Two-storey frame', how: 'V_b = C_s·W · T ≈ 0.085·H^0.75', ref: 'SBC 301 ELF · empirical period' },
]

function StatusPill({ status }) {
  const tone = status === 'pass' ? 'success' : status === 'warn' ? 'warn' : 'fail'
  return <span className={`badge ${tone}`}>{String(status || '—').toUpperCase()}</span>
}

export default function ProofWorkspace() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    let alive = true
    getPublicValidationReport()
      .then((r) => { if (alive) setReport(r) })
      .catch(() => { if (alive) setMissing(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  if (loading) return <LoadingCard label="Loading benchmark report..." />
  if (missing || !report) {
    return (
      <div className="landing">
        <Seo title="Imad — Proof" description="Solver vs hand calculations." canonical={`${SITE_URL}/proof`} />
        <section className="landing-section" aria-label="Engineering proof">
          <div className="landing-inner">
            <span className="eyebrow">Proof, not promises</span>
            <h2>Imad vs. hand calculations.</h2>
            <EmptyCard
              title="No benchmark published yet"
              description="The suite runs inside the app. The latest published report appears here automatically."
              ctaLabel="Open the app"
              ctaHref="/create-plan"
            />
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="landing">
      <Seo
        title="Imad — Proof: solver vs hand calculations"
        description="Imad's structural solver benchmarked against closed-form hand calculations: beam, column and frame cases with pass/fail per quantity."
        canonical={`${SITE_URL}/proof`}
      />
      <section className="landing-section" aria-label="Engineering proof">
        <div className="landing-inner">
          <span className="eyebrow">Proof, not promises</span>
          <h2>Imad vs. hand calculations.</h2>
          <p className="landing-intro-desc">
            Every release is benchmarked against closed-form solutions with identical
            load assumptions — any difference isolates solver error, not input
            mismatch. Pass band ±5%, conservative warning 5–10%.
          </p>

          <div className="summary-grid four" style={{ margin: '24px 0' }}>
            <div className="stat">
              <span className="stat-label">Accuracy score</span>
              <strong>{report.accuracy_score_pct}%</strong>
            </div>
            <div className="stat">
              <span className="stat-label">Verdict</span>
              <strong>{String(report.verdict || '').toUpperCase()}</strong>
            </div>
            <div className="stat">
              <span className="stat-label">Tolerance</span>
              <strong>±{report.tolerance_pct}%</strong>
            </div>
            <div className="stat">
              <span className="stat-label">Ran at</span>
              <strong>{String(report.ran_at || '').replace('T', ' ').slice(0, 19)}</strong>
            </div>
          </div>

          {(report.cases || []).map((c) => (
            <Card className="span-2" key={c.case} style={{ marginBottom: 16 }}>
              <div className="card-header">
                <h3>{c.case} — {c.description}</h3>
                <StatusPill status={c.status} />
              </div>
              <p className="muted small">Solver: {c.solver || 'analytic'}</p>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Quantity</th><th>Formula</th><th>Hand</th>
                      <th>Imad</th><th>Diff %</th><th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(c.quantities || []).map((q) => (
                      <tr key={q.quantity}>
                        <td>{q.quantity}</td>
                        <td className="mono">{q.formula}</td>
                        <td>{q.hand} {q.unit}</td>
                        <td>{q.engine} {q.unit}</td>
                        <td>{q.diff_pct}%</td>
                        <td><StatusPill status={q.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ))}

          <Card className="span-2" style={{ marginTop: 8 }}>
            <h3>Method, in the open</h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Case</th><th>Closed form</th><th>Reference</th></tr>
                </thead>
                <tbody>
                  {METHOD.map((m) => (
                    <tr key={m.qty}>
                      <td>{m.qty}</td><td className="mono">{m.how}</td><td>{m.ref}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small" style={{ marginTop: 12 }}>
              Full methodology: <span className="mono">docs/validation.md</span> in the
              repository. Signed PDF of this report downloads from the Governance tab.
            </p>
          </Card>
        </div>
      </section>
    </div>
  )
}
