import { useCallback, useEffect, useState } from 'react'
import { generateSubmissionPackage, getAuditLog, getComplianceReport, getSubmissionPackage } from '../platformApi.js'
import { EmptyState, Spinner } from '../components/ui.jsx'

export default function GovernanceWorkspace() {
  const projectId = 1
  const [designId] = useState('res_demo')
  const [report, setReport] = useState(null)
  const [pkg, setPkg] = useState([])
  const [audit, setAudit] = useState([])
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([getSubmissionPackage(projectId), getAuditLog(projectId)])
      .then(([p, a]) => { setPkg(Array.isArray(p) ? p : p?.packages ?? []); setAudit(Array.isArray(a) ? a : a?.entries ?? a?.log ?? []); setErr(null) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [projectId])
  useEffect(() => { load() }, [load])

  const check = async () => {
    setBusy(true); setErr(null)
    try { setReport(await getComplianceReport(designId)) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const gen = async () => {
    setBusy(true); setErr(null)
    try { await generateSubmissionPackage(designId); load() } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const rows = report?.checks ?? report?.results ?? []
  const passed = rows.filter((c) => c.status === 'pass').length
  const warns = rows.filter((c) => c.status === 'warn').length
  const failed = rows.filter((c) => c.status === 'fail').length

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header"><h2>Governance &amp; Compliance</h2><span className="status-chip">Project #{projectId}</span></div>
        <p className="muted small">SBC 304 compliance status, municipality submission packages and the immutable audit trail.</p>
        {err && <div className="alert error" role="alert"><strong>Error:</strong> {err}</div>}
        <button className="btn primary" onClick={check} disabled={busy}>{busy ? 'Running…' : 'Run Compliance Check'}</button>
      </section>

      <section className="card">
        <h3>Compliance Status</h3>
        {report === null ? <EmptyState icon="🔬" title="No compliance report yet" hint="Run a check to see passed / failed / warning counts." />
          : (
            <div className="summary-grid four">
              <div className="stat"><span className="stat-label">Total</span><strong>{rows.length}</strong></div>
              <div className="stat"><span className="stat-label">Passed</span><strong style={{ color: 'var(--primary)' }}>{passed}</strong></div>
              <div className="stat"><span className="stat-label">Warnings</span><strong style={{ color: '#7A5A00' }}>{warns}</strong></div>
              <div className="stat"><span className="stat-label">Failed</span><strong style={{ color: 'var(--danger)' }}>{failed}</strong></div>
            </div>
          )}
      </section>

      <section className="card">
        <h3>Submission Package</h3>
        <p className="muted small">Combines calculation note, drawings, compliance report and project info into one municipality-ready PDF.</p>
        <button className="btn primary" onClick={gen} disabled={busy}>{busy ? 'Assembling…' : 'Generate Municipality Submission Package'}</button>
        {loading ? <Spinner label="Loading…" /> : pkg.length === 0
          ? <EmptyState icon="📦" title="No packages yet" hint="Generate the first submission package." />
          : (
            <ul className="saved-list">
              {pkg.map((p) => (
                <li key={p.id}>
                  <span>{p.file_path ?? p.file}</span>
                  <span className="badge success">{p.signed_by ? `Signed · ${p.signed_by}` : 'Pending'}</span>
                </li>
              ))}
            </ul>
          )}
      </section>

      <section className="card span-2">
        <h3>Audit Log</h3>
        {loading ? <Spinner label="Loading audit…" /> : audit.length === 0
          ? <EmptyState icon="🧾" title="No entries" hint="Actions are recorded here, append-only." />
          : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Action</th><th>User</th><th>Timestamp</th></tr></thead>
                <tbody>{audit.slice(-30).reverse().map((a, i) => (
                  <tr key={a.id ?? i}>
                    <td>{a.action ?? a.event}</td><td>{a.user_id ?? a.user}</td>
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