import { useCallback, useEffect, useState } from 'react'
import { getAuditLog, requestSignature, runComplianceCheck } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { EmptyState, ErrorState, Spinner } from '../components/ui.jsx'

const STATE = {
  pass: { label: 'Pass', cls: 'pill ok' },
  warn: { label: 'Warning', cls: 'pill warn' },
  fail: { label: 'Fail', cls: 'pill error-bad' },
}

export default function ReviewWorkspace() {
  const projectId = useProjectId()
  const [designId, setDesignId] = useState('res_demo')
  const [checks, setChecks] = useState(null)
  const [audit, setAudit] = useState([])
  const [sig, setSig] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadAudit = useCallback(() => {
    setLoading(true)
    getAuditLog(projectId).then((d) => setAudit(Array.isArray(d) ? d : d?.entries ?? d?.log ?? [])).catch(() => setAudit([])).finally(() => setLoading(false))
  }, [projectId])
  useEffect(() => { loadAudit() }, [loadAudit])

  const run = async () => {
    setBusy(true); setError(null)
    try { setChecks(await runComplianceCheck({ project_id: projectId })) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const sign = async () => {
    setBusy(true); setError(null)
    try { setSig(await requestSignature({ design_id: designId, project_id: projectId, engineer_name: 'Demo Engineer', license_number: 'SCE-1001' })); loadAudit() }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const rows = checks?.checks ?? checks?.results ?? []

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header">
          <h2>Review &amp; Compliance</h2>
          <span className="badge success">Design reviewed</span>
        </div>
        <p className="muted small">SBC 304 checklist, engineer signature and audit trail for project #{projectId}.</p>
        <div className="inline-controls">
          <label htmlFor="rd-design" className="sr-only">Design ID</label>
          <input id="rd-design" value={designId} onChange={(e) => setDesignId(e.target.value)} aria-label="Design ID" />
          <button className="btn primary" onClick={run} disabled={busy}>{busy ? 'Checking…' : 'Run Compliance Checklist'}</button>
        </div>
        {error && <ErrorState message={error} onRetry={run} />}
      </section>

      <section className="card span-2">
        <h3>Compliance Checklist</h3>
        {checks === null ? <EmptyState icon="📋" title="No compliance run yet" hint="Run the checklist to evaluate reinforcement, deflection, seismic and column capacity." />
          : rows.length === 0 ? <EmptyState icon="✓" title="All clear" hint="No failing checks were reported for this design." />
          : (
            <ul className="check-list" role="list">
              {rows.map((c, i) => {
                const s = STATE[c.status] ?? STATE.pass
                return (
                  <li key={c.check_name ?? i} role="listitem">
                    <span className="check-label">{c.check_name ?? `Check ${i + 1}`}</span>
                    <span className={s.cls}>{s.label}</span>
                    <span className="muted small">{typeof c.details === 'string' ? c.details : (c.details?.limit ? `limit ${c.details.limit}` : '')}</span>
                  </li>
                )
              })}
            </ul>
          )}
      </section>

      <section className="card">
        <h3>Signature Request</h3>
        <p className="muted small">Only licensed engineers may approve &amp; sign. Routed to the e-seal provider (placeholder).</p>
        <button className="btn primary" onClick={sign} disabled={busy}>{busy ? 'Requesting…' : 'Request Engineer Review &amp; Signature'}</button>
        {sig && (
          <div className={`alert ${sig.status === 'rejected' ? 'error' : 'info'}`} role="status">
            Signature <strong>{sig.status ?? sig.request?.status ?? 'pending'}</strong>{sig.request_id ? ` · ref ${sig.request_id}` : ''}
          </div>
        )}
      </section>

      <section className="card">
        <h3>Audit Log</h3>
        {loading ? <Spinner label="Loading…" /> : audit.length === 0
          ? <EmptyState icon="🧾" title="No entries" hint="Design and signing actions are recorded here." />
          : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Action</th><th>User</th><th>When</th></tr></thead>
                <tbody>{audit.slice(-25).reverse().map((a, i) => (
                  <tr key={a.id ?? i}>
                    <td>{a.action ?? a.event ?? '—'}</td><td>{a.user_id ?? a.user ?? '—'}</td>
                    <td className="small">{(a.timestamp ?? a.created_at ?? '').replace('T', ' ').slice(0, 19)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  )
}