import { useCallback, useEffect, useState } from 'react'
import { downloadExport, exportSubmissionDocx, generateSBC304Package, getAuditLog, getComplianceReport, getSubmissionPackage, getSubmissionReadiness, transitionSubmission } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { useProjectPlan } from '../useProjectPlan'
import { EmptyState, Spinner } from '../components/ui.jsx'
import { Button, Select, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/shadcn.jsx'

export default function GovernanceWorkspace() {
    const projectId = useProjectId()
  const { plan, loading: planLoading } = useProjectPlan()
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
      <Card className="span-2">
                <CardHeader><h2>Governance &amp; Compliance</h2>
          <Badge variant="default">Project #{projectId}</Badge>
          {plan && <Badge variant="success">{plan.label || plan.name}</Badge>}
        </CardHeader>
        <p className="muted small">SBC 304 compliance status, municipality submission packages and the immutable audit trail.</p>
        {err && <div className="alert error" role="alert"><strong>Error:</strong> {err}</div>}
        <Button variant="primary" onClick={check} disabled={busy}>{busy ? 'Running…' : 'Run Compliance Check'}</Button>
      </Card>

      <Card>
        <CardTitle>Compliance Status</CardTitle>
        {report === null ? <EmptyState icon="🔬" title="No compliance report yet" hint="Run a check to see passed / failed / warning counts." />
          : (
            <div className="summary-grid four">
              <div className="stat"><span className="stat-label">Total</span><strong>{rows.length}</strong></div>
              <div className="stat"><span className="stat-label">Passed</span><strong style={{ color: 'var(--primary)' }}>{passed}</strong></div>
              <div className="stat"><span className="stat-label">Warnings</span><strong style={{ color: '#7A5A00' }}>{warns}</strong></div>
              <div className="stat"><span className="stat-label">Failed</span><strong style={{ color: 'var(--danger)' }}>{failed}</strong></div>
            </div>
          )}
      </Card>

      <Card>
        <CardTitle>Submission Readiness</CardTitle>
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
      </Card>

      <Card>
        <CardTitle>SBC 304 Calculation Package</CardTitle>
        <p className="muted small">Runs the analysis + compliance engines, assembles the preliminary calculation package (PDF) and records it for licensed-engineer review.</p>
        <Button variant="primary" onClick={gen} disabled={busy}>{busy ? 'Assembling…' : 'Generate SBC 304 Package'}</Button>
        {loading ? <Spinner label="Loading…" /> : pkg.length === 0
          ? <EmptyState icon="📦" title="No packages yet" hint="Generate the first calculation package." />
          : (
            <Table>
              <TableHeader>
                <TableRow><TableHead>Package</TableHead><TableHead>Status</TableHead><TableHead>Last tracking event</TableHead><TableHead>Actions</TableHead></TableRow>
              </TableHeader>
                <TableBody>
                  {pkg.map((p) => {
                    const file = p.file_path ?? p.file
                    const events = Array.isArray(p.tracking) ? p.tracking : []
                    const last = events[events.length - 1]
                    const status = p.status ?? (p.signed_by ? 'signed' : 'generated')
                    const badgeClass = ['signed', 'approved'].includes(status) ? 'success'
                      : ['rejected', 'revision_required'].includes(status) ? 'warn' : ''
                    return (
                      <TableRow key={p.id}>
                        <TableCell className="small">{file ? String(file).split(/[\\/]/).pop() : p.id}</TableCell>
                        <TableCell>
                          <Badge variant={badgeClass}>{status.replace('_', ' ')}</Badge>
                          {p.signed_by && <div className="small muted">by {p.signed_by}</div>}
                        </TableCell>
                        <TableCell className="small">
                          {last
                            ? <>{last.status}{last.reference_number ? ` · ${last.reference_number}` : ''}{last.authority ? ` · ${last.authority}` : ''}<br /><span className="muted">{String(last.at || '').replace('T', ' ').slice(0, 19)}</span></>
                            : <span className="muted">—</span>}
                        </TableCell>
                        <TableCell>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            {file && <Button onClick={() => downloadExport(file)}>Download</Button>}
                            {file && (
                              <Button disabled={busy}
                                title="Editable Word calculation note (roadmap #17)"
                                onClick={async () => {
                                  setBusy(true); setErr(null)
                                  try {
                                    const note = await exportSubmissionDocx(p.id)
                                    await downloadExport(note.file, note.filename)
                                  } catch (e) { setErr(e.message) } finally { setBusy(false) }
                                }}>Word</Button>
                            )}
                            <Select
                              value={nextStatus[p.id] ?? 'submitted'}
                              onChange={(e) => setNextStatus({ ...nextStatus, [p.id]: e.target.value })}
                              aria-label={`Next status for ${p.id}`}
                            >
                              {STATUSES.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                            </Select>
                            <Button onClick={() => applyStatus(p)} disabled={busy}>Apply</Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
            </Table>
          )}
      </Card>

      <Card className="span-2">
        <CardTitle>Audit Log</CardTitle>
        {loading ? <Spinner label="Loading audit…" /> : audit.length === 0
          ? <EmptyState icon="🧾" title="No entries" hint="Actions are recorded here, append-only." />
          : (
            <Table>
              <TableHeader><TableRow><TableHead>Action</TableHead><TableHead>User</TableHead><TableHead>Timestamp</TableHead></TableRow></TableHeader>
              <TableBody>{audit.slice(-30).reverse().map((a, i) => (
                <TableRow key={a.id ?? i}>
                  <TableCell>{a.action ?? a.event}</TableCell><TableCell>{a.user_id ?? a.user}</TableCell>
                  <TableCell className="small">{(a.timestamp ?? a.created_at ?? '').replace('T', ' ').slice(0, 19)}</TableCell>
                </TableRow>
              ))}</TableBody>
            </Table>
          )}
      </Card>
    </div>
  )
}