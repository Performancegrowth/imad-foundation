import { useCallback, useEffect, useState } from 'react'
import { downloadExport, exportSubmissionDocx, generateSBC304Package, getAuditLog, getComplianceReport, getSubmissionPackage, getSubmissionReadiness, transitionSubmission } from '../platformApi.js'
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

  // Municipality-side tracking (roadmap #16): the caller records the real
  // outcome; nothing is inferred here.
  const [nextStatus, setNextStatus] = useState({})
  const STATUSES = ['generated', 'submitted', 'under_review', 'approved', 'revision_required', 'rejected', 'signed']
  const applyStatus = async (p) => {
    setBusy(true); setErr(null)
    try { await transitionSubmission(p.id, nextStatus[p.id] ?? 'submitted'); load() } catch (e) { setErr(e.message) } finally { setBusy(false) }
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
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="data-table">
                <thead><tr><th>Package</th><th>Status</th><th>Last tracking event</th><th>Actions</th></tr></thead>
                <tbody>
                  {pkg.map((p) => {
                    const file = p.file_path ?? p.file
                    const events = Array.isArray(p.tracking) ? p.tracking : []
                    const last = events[events.length - 1]
                    const status = p.status ?? (p.signed_by ? 'signed' : 'generated')
                    const badgeClass = ['signed', 'approved'].includes(status) ? 'success'
                      : ['rejected', 'revision_required'].includes(status) ? 'warn' : ''
                    return (
                      <tr key={p.id}>
                        <td className="small">{file ? String(file).split(/[\\/]/).pop() : p.id}</td>
                        <td>
                          <span className={`badge ${badgeClass}`}>{status.replace('_', ' ')}</span>
                          {p.signed_by && <div className="small muted">by {p.signed_by}</div>}
                        </td>
                        <td className="small">
                          {last
                            ? <>{last.status}{last.reference_number ? ` · ${last.reference_number}` : ''}{last.authority ? ` · ${last.authority}` : ''}<br /><span className="muted">{String(last.at || '').replace('T', ' ').slice(0, 19)}</span></>
                            : <span className="muted">—</span>}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            {file && <button className="btn" onClick={() => downloadExport(file)}>Download</button>}
                            {file && (
                              <button className="btn" disabled={busy}
                                title="Editable Word calculation note (roadmap #17)"
                                onClick={async () => {
                                  setBusy(true); setErr(null)
                                  try {
                                    const note = await exportSubmissionDocx(p.id)
                                    await downloadExport(note.file, note.filename)
                                  } catch (e) { setErr(e.message) } finally { setBusy(false) }
                                }}>Word</button>
                            )}
                            <select
                              className="btn"
                              value={nextStatus[p.id] ?? 'submitted'}
                              onChange={(e) => setNextStatus({ ...nextStatus, [p.id]: e.target.value })}
                              aria-label={`Next status for ${p.id}`}
                            >
                              {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                            </select>
                            <button className="btn" onClick={() => applyStatus(p)} disabled={busy}>Apply</button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
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