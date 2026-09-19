// Sprint 8 — Sustainability dashboard: embodied-carbon breakdown, benchmark
// banding, green alternatives comparison and LCA report download.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { useProjectPlan } from '../useProjectPlan'
import { Button, Select, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { AreaChart, ProgressBar } from '../components/shadcn.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/shadcn.jsx'
import { EmptyState, StatCard, LoadingCard, NextStep } from '../components/ui.jsx'
import { WorkflowStepper } from '../components/WorkflowStepper.jsx'

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
  const { plan: currentPlan, loading: planLoading } = useProjectPlan()

  useEffect(() => {
    if (!projectId) return
    api.listPlans(projectId).then(setPlans).catch(() => setPlans([]))
  }, [projectId])

  // Auto-select the plan resolved from the project context on first load.
  useEffect(() => {
    if (!currentPlan || planName) return
    setPlanName(currentPlan.name || currentPlan.label || '')
  }, [currentPlan, planName])

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
        .map((r) => ({ name: r.code, kgCO2e: Number(r.co2e_kg) || 0 }))
    : []
  const complianceEntries = report ? Object.entries(report.compliance || {}) : []
  const metCount = complianceEntries.filter(([, v]) => !!v).length

  if (!projectId) return <NoProject />
  if (planLoading && !currentPlan && !report) return <LoadingCard label="Loading plan..." />

  return (
    <div className="workspace-grid">
      <WorkflowStepper projectId={projectId} currentKey="carbon" />
      <Card className="span-2" aria-labelledby="carbon-title">
                <h2 id="carbon-title">Sustainability &amp; Embodied Carbon</h2>
        {currentPlan && <Badge variant="default">{currentPlan.label || currentPlan.name}</Badge>
        }
        <p className="muted subtitle">
          Embodied carbon assessment and green material alternatives.
        </p>
        <div className="inline-controls wrap">
          <label htmlFor="carbon-plan" className="sr-only">Saved plan</label>
          <Select id="carbon-plan" value={planName} onChange={(e) => setPlanName(e.target.value)}>
            <option value="">— Select a saved plan —</option>
            {plans.map((p) => <option key={p.name} value={p.name}>{p.label}</option>)}
          </Select>
          <Button variant="primary" onClick={run} disabled={busy || !planName}>
            {busy ? 'Computing…' : 'Compute carbon & alternatives'}
          </Button>
          {report && (
            <Button onClick={download} disabled={downloading}>
              {downloading ? 'Preparing…' : '⬇ LCA report (PDF)'}
            </Button>
          )}
        </div>
        {!planName && plans.length === 0 && (
          <EmptyState icon="🌱" title="Nothing to assess yet"
                      hint="Generate a BOQ-able plan first — carbon is computed from its quantities." />
        )}
        {!planName && plans.length === 0 && (
          <div style={{ textAlign: 'center' }}>
            <a className="btn-primary on-light" href="/create-plan">Go to Create Plan</a>
          </div>
        )}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </Card>

      {report && (
        <>
          <Card className="span-2" aria-label="Carbon KPIs">
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
          </Card>

          <Card className="span-2" aria-label="Carbon breakdown">
            <CardHeader><CardTitle>Carbon by trade (kgCO₂e)</CardTitle></CardHeader>
            <AreaChart data={breakdownChart} categories={['kgCO2e']} index="name"
                       title="" subtitle="Cradle-to-gate kgCO₂e by item" />
            <Table>
              <TableHeader>
                <TableRow><TableHead>Item</TableHead><TableHead className="num">Qty</TableHead><TableHead className="num">EF</TableHead>
                    <TableHead className="num">kgCO₂e</TableHead><TableHead className="num">Share</TableHead><TableHead>Reference</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {report.carbon.breakdown.map((r) => (
                  <TableRow key={r.code}>
                    <TableCell>{r.description}</TableCell>
                    <TableCell className="num">{fmt(r.quantity)}</TableCell>
                    <TableCell className="num">{r.emission_factor}</TableCell>
                    <TableCell className="num">{fmt(r.co2e_kg)}</TableCell>
                    <TableCell className="num">{r.share_pct}%</TableCell>
                    <TableCell className="muted small">{r.reference}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <Card className="span-2" aria-label="Green alternatives">
            <CardHeader><CardTitle>Green alternatives</CardTitle></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>Option</TableHead><TableHead className="num">CO₂ cut</TableHead>
                    <TableHead className="num">Cost impact</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {report.alternatives.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell><strong>{a.name}</strong><br /><span className="muted small">{a.notes}</span></TableCell>
                    <TableCell className="num ok-text">−{a.total_cut_pct}%</TableCell>
                    <TableCell className={`num ${a.cost_delta_pct <= 0 ? 'ok-text' : 'warn-text'}`}>
                      {a.cost_delta_pct <= 0 ? '−' : '+'}{Math.abs(a.cost_delta_pct)}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          <Card className="span-2" aria-label="Compliance mapping">
            <CardHeader><CardTitle>Rating-system compliance snapshot</CardTitle></CardHeader>
            <ProgressBar value={metCount} max={Math.max(1, complianceEntries.length)}
                         label="LEED / Mostadam criteria met" />
            <ul className="check-list">
              {complianceEntries.map(([k, v]) => (
                <li key={k} className={v ? 'pass' : 'fail'}>
                  <span aria-hidden="true">{v ? '✓' : '✗'}</span> {k}
                  <span className="muted small"> — {v ? 'criterion likely met; confirm with documentation'
                                                    : 'requires the green alternatives above to qualify'}</span>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}

      {report && (
        <NextStep nextLabel="3D Model" nextHref={`/project/${projectId}/3d`} />
      )}
    </div>
  )
}