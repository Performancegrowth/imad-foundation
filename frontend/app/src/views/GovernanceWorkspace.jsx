import { useCallback, useEffect, useState } from 'react'
import { downloadExport, generateSBC304Package, getAuditLog, getComplianceReport, getSubmissionPackage, getSubmissionReadiness } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { EmptyState, Spinner } from '../components/ui.jsx'

export default function GovernanceWorkspace() {
  const projectId = useProjectId()
  const [report, setReport] = useState(null)
  const [pkg, setPkg] = useState([])
  const [audit, setAudit] = useState([])
  const [readiness, setReadiness] = useState(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      getSubmissionPackage(projectId),
      getAuditLog(projectId),
      getSubmissionReadiness(projectId).catch(() => null),
    ])
      .then(([p, a, r]) => {
        setPkg(Array.isArray(p) ? p : p?.packages ?? [])
        setAudit(Array.isArray(a) ? a : a?.entries ?? a?.log ?? [])
        setReadiness(r)
        setErr(null)
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [projectId])
  useEffect(() => { load() }, [load])

  const check = async () => {
    setBusy(true); setErr(null)
    try { setReport(await getComplianceReport({ project_id: projectId })) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const gen = async () => {
    setBusy(true); setErr(null)
    try { await generateSBC304Package({ project_id: projectId }); load() } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const rows = report?.checks ?? report?.results ?? []
  const passed = rows.filter((c) => c.status === 'pass').length
  const warns = rows.filter((c) => c.status === 'warn').length
  const failed = rows.filter((c) => c.status === 'fail').length

  if (!projectId) return <NoProject />

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
        <h3>Submission Readiness</h3>
        {loading || !readiness ? <Spinner label="Checking…" />
          : (
            <>
              <span className={`badge ${readiness.ready ? 'success' : 'warn'}`}>{readiness.status}</span>
              <ul className="saved-list" style={{ marginTop: 12 }}>
                {readiness.checks.map((c) => (
                  <li key={c.item}>
                    <span>{c.ready ? '✓' : '✗'} {c.item}</span>
                    <span className={`badge ${c.ready ? 'success' : 'warn'} small`}>{c.detail}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
      </section>

      <section className="card">
        <h3>SBC 304 Calculation Package</h3>
        <p className="muted small">Runs the analysis + compliance engines, assembles the preliminary calculation package (PDF) and records it for licensed-engineer review.</p>
        <button className="btn primary" onClick={gen} disabled={busy}>{busy ? 'Assembling…' : 'Generate SBC 304 Package'}</button>
        {loading ? <Spinner label="Loading…" /> : pkg.length === 0
          ? <EmptyState icon="📦" title="No packages yet" hint="Generate the first calculation package." />
          : (
            <ul className="saved-list">
              {pkg.map((p) => {
                const file = p.file_path ?? p.file
                return (
                  <li key={p.id}>
                    <span>{file ? String(file).split(/[\\/]/).pop() : p.id}</span>
                    <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="badge success">{p.signed_by ? `Signed · ${p.signed_by}` : 'Pending review'}</span>
                      {file && <button className="btn" onClick={() => downloadExport(file)}>Download</button>}
                    </span>
                  </li>
                )
              })}
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