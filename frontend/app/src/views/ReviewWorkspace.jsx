import { useCallback, useEffect, useState } from 'react'
import { getAuditLog, requestSignature, runComplianceCheck } from '../platformApi.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { useProjectPlan } from '../useProjectPlan'
import { EmptyState, ErrorState, Spinner } from '../components/ui.jsx'
import { WorkflowStepper } from '../components/WorkflowStepper.jsx'
import { LoadingCard, EmptyCard, NextStep } from '../components/ui.jsx'
import { Button, Input, Label, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/shadcn.jsx'

const STATE = {
  pass: { label: 'Pass', cls: 'pill ok' },
  warn: { label: 'Warning', cls: 'pill warn' },
  fail: { label: 'Fail', cls: 'pill error-bad' },
}

export default function ReviewWorkspace() {
    const projectId = useProjectId()
  const { plan, loading: planLoading } = useProjectPlan()
  const [designId, setDesignId] = useState('')
  const [checks, setChecks] = useState(null)
  const [audit, setAudit] = useState([])
  const [sig, setSig] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [engineerName, setEngineerName] = useState('')
  const [licenseNumber, setLicenseNumber] = useState('')

  const loadAudit = useCallback(() => {
    setLoading(true)
    getAuditLog(projectId).then((d) => setAudit(Array.isArray(d) ? d : d?.entries ?? d?.log ?? [])).catch(() => setAudit([])).finally(() => setLoading(false))
  }, [projectId])
  useEffect(() => { loadAudit() }, [loadAudit])

  // The design identifier derives from the saved plan (id/name) — never a
  // hardcoded placeholder.
  useEffect(() => {
    if (designId || !plan) return
    setDesignId(plan.design_id || plan.id || plan.name || plan.label || '')
  }, [plan, designId])

  const run = async () => {
    const planName = plan?.name || plan?.label
    if (!planName) { setError('No saved plan yet — create a plan first, then run the checklist.'); return }
    setBusy(true); setError(null)
    try { setChecks(await runComplianceCheck({ project_id: projectId, plan_name: planName })) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  // Auto-run the checklist once the saved plan resolves (mirrors Analyze).
  useEffect(() => {
    if (plan && checks === null) run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan])
  const sign = async () => {
    if (!engineerName.trim() || !licenseNumber.trim()) {
      setError('Enter your name and license number (e.g. Eng. Layla Hassan, SCE-20451) before requesting the signature. The demo values are gone for good.')
      return
    }
    setBusy(true); setError(null)
    try { setSig(await requestSignature({ design_id: designId || plan?.name || plan?.label || 'current', project_id: projectId, engineer_name: engineerName.trim(), license_number: licenseNumber.trim() })); loadAudit() }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const rows = checks?.checks ?? checks?.results ?? []

  if (!projectId) return <NoProject />
  if (loading && checks === null && audit.length === 0) {
    return <LoadingCard label="Loading review data..." />
  }

  return (
    <div className="workspace-grid">
      <WorkflowStepper projectId={projectId} currentKey="review" />
      <Card className="span-2">
                <CardHeader>
          <h2>Review &amp; Compliance</h2>
          <Badge variant="success">Design reviewed</Badge>
          {plan && <Badge variant="default">{plan.label || plan.name}</Badge>}
        </CardHeader>
        <p className="muted small">SBC 304 checklist, engineer signature and audit trail for project #{projectId}.</p>
        <div className="inline-controls">
          <label htmlFor="rd-design" className="sr-only">Design ID</label>
          <Input id="rd-design" value={designId} onChange={(e) => setDesignId(e.target.value)} placeholder="—" aria-label="Design ID" />
          <Button variant="primary" onClick={run} disabled={busy}>{busy ? 'Checking…' : 'Run Compliance Checklist'}</Button>
        </div>
        {error && <ErrorState message={error} onRetry={run} />}
      </Card>

      {!plan && checks === null && audit.length === 0 && (
        <Card className="span-2">
          <EmptyState icon="✍️" title="Nothing to review yet"
            hint="Run the compliance checklist after analysing a plan, then request the engineer signature." />
          <div style={{ textAlign: 'center' }}>
            <a className="btn-primary on-light" href="/create-plan">Go to Create Plan</a>
          </div>
        </Card>
      )}

      <Card className="span-2">
        <CardTitle>Compliance Checklist</CardTitle>
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
      </Card>

      <Card>
        <CardTitle>Signature Request</CardTitle>
        <p className="muted small">Only licensed engineers may approve &amp; sign. Your name and license number are stamped on the sealed review document.</p>
        <div className="field">
          <Label htmlFor="sig-name">Engineer name</Label>
          <Input id="sig-name" type="text" autoComplete="name" placeholder="Eng. Layla Hassan"
            value={engineerName} onChange={(e) => setEngineerName(e.target.value)} />
        </div>
        <div className="field">
          <Label htmlFor="sig-license">License number</Label>
          <Input id="sig-license" type="text" placeholder="SCE-20451"
            value={licenseNumber} onChange={(e) => setLicenseNumber(e.target.value)} />
        </div>
        <Button variant="primary" onClick={sign} disabled={busy}>{busy ? 'Requesting…' : 'Request Engineer Review &amp; Signature'}</Button>
        {sig && (
          <div className={`alert ${sig.status === 'rejected' ? 'error' : 'info'}`} role="status">
            Signature <strong>{sig.status ?? sig.request?.status ?? 'pending'}</strong>{sig.request_id ? ` · ref ${sig.request_id}` : ''}
          </div>
        )}
      </Card>

      <Card>
        <CardTitle>Audit Log</CardTitle>
        {loading ? <Spinner label="Loading…" /> : audit.length === 0
          ? <EmptyState icon="🧾" title="No entries" hint="Design and signing actions are recorded here." />
          : (
            <div className="table-wrap">
              <Table>
                <TableHeader><TableRow><TableHead>Action</TableHead><TableHead>User</TableHead><TableHead>When</TableHead></TableRow></TableHeader>
                <TableBody>{audit.slice(-25).reverse().map((a, i) => (
                  <TableRow key={a.id ?? i}>
                    <TableCell>{a.action ?? a.event ?? '—'}</TableCell><TableCell>{a.user_email || a.details?.user_email || a.user_id || a.user || a.actor_id || '—'}</TableCell>
                    <TableCell className="small">{(a.timestamp ?? a.created_at ?? '').replace('T', ' ').slice(0, 19)}</TableCell>
                  </TableRow>
                ))}</TableBody>
              </Table>
            </div>
          )}
      </Card>

      {/* End of workflow — final deliverable is the signed submission package. */}
      <div className="next-step">
        <span>End of workflow — the signed package is ready for submission.</span>
        <button type="button" className="btn-primary on-dark" onClick={() => window.print()}>
          Export PDF
        </button>
      </div>
    </div>
  )
}