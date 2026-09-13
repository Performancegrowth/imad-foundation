// Sprint 7 — BOQ workspace: generate quantities + BBS, view tables & charts,
// download branded PDF / Excel exports.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { Button, Select, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/shadcn.jsx'
import { DonutChart, BarChart } from '../components/shadcn.jsx'
import { EmptyState, StatCard } from '../components/ui.jsx'

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

  const chartData = (boq?.items || []).map((i) => ({ name: i.code, Amount: Number(i.amount_usd) || 0 })) || []
  const tradeData = (boq?.trade_totals || []).map((t) => ({ name: t.trade ?? t.code, Total: Number(t.amount_usd ?? t.total) || 0 }))
  const donutData = chartData.slice(0, 8).map((d) => ({ name: d.name, value: d.Amount }))

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <Card className="span-2" aria-labelledby="boq-title">
        <h2 id="boq-title">Bill of Quantities & Bar Schedule</h2>
        <p className="muted">
          Detailed take-off across concrete, rebar, formwork, earthworks and
          waterproofing — with a cutting-optimised bar bending schedule (waste target &lt; 2%).
        </p>
        <div className="inline-controls wrap">
          <label htmlFor="boq-plan" className="sr-only">Saved plan</label>
          <Select id="boq-plan" value={planName} onChange={(e) => setPlanName(e.target.value)}>
            <option value="">— Select a saved plan —</option>
            {plans.map((p) => <option key={p.name} value={p.name}>{p.label}</option>)}
          </Select>
          <Button variant="primary" onClick={generate} disabled={busy || !planName}>
            {busy ? 'Generating…' : 'Generate BOQ'}
          </Button>
          {boq && (
            <div className="inline-controls">
              <Button onClick={() => doExport('pdf')} disabled={exporting !== null}>
                {exporting === 'pdf' ? 'Rendering…' : '⬇ PDF report'}
              </Button>
              <Button onClick={() => doExport('xlsx')} disabled={exporting !== null}>
                {exporting === 'xlsx' ? 'Writing…' : '⬇ Excel workbook'}
              </Button>
            </div>
          )}
        </div>
        {!planName && plans.length === 0 && (
          <EmptyState icon="📋" title="No saved plans yet"
                      hint="Create a plan first (CAD import or Create Plan), then generate its BOQ here." />
        )}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </Card>

      {boq && (
        <>
          <Card className="span-2" aria-label="BOQ summary">
            <div className="summary-grid four">
              <StatCard label="Total estimate" value={money(boq.totals.amount_usd)} />
              <StatCard label="Cost / m² GFA" value={money(boq.totals.amount_per_m2)} tone="gold" />
              <StatCard label="Rebar" value={Number(boq.bbs.rebar_total_kg).toLocaleString()} unit="kg" />
              <StatCard label="Cutting waste"
                        value={`${boq.bbs.waste_percent}%`}
                        tone={boq.bbs.within_target ? 'ok' : 'warn'} />
            </div>
          </Card>

          <Card aria-label="Cost breakdown donut">
            <CardHeader><CardTitle>Cost breakdown</CardTitle>
              <Badge variant="default">{money(boq.totals.amount_usd)}</Badge>
            </CardHeader>
            <DonutChart data={donutData} category="value" index="name" title="" />
          </Card>

          <Card aria-label="Trade totals">
            <CardHeader><CardTitle>Trade totals</CardTitle></CardHeader>
            {tradeData.length > 0 ? (
              <BarChart data={tradeData} categories={['Total']} index="name" layout="horizontal"
                        title="" subtitle="Amount (USD)" />
            ) : (
              <BarChart data={chartData} categories={['Amount']} index="name" layout="horizontal"
                        title="" subtitle="Amount (USD)" />
            )}
          </Card>

          <Card className="span-2" aria-label="BOQ table">
            <CardHeader><CardTitle>Bill of Quantities</CardTitle><Badge variant="default">{boq.currency}</Badge></CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>Code</TableHead><TableHead>Description</TableHead><TableHead>Unit</TableHead><TableHead className="num">Qty</TableHead>
                    <TableHead className="num">Rate</TableHead><TableHead className="num">Amount</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {boq.items.map((i) => (
                  <TableRow key={i.code}>
                    <TableCell className="mono">{i.code}</TableCell>
                    <TableCell>{i.description}</TableCell>
                    <TableCell>{i.unit}</TableCell>
                    <TableCell className="num">{Number(i.quantity).toLocaleString()}</TableCell>
                    <TableCell className="num">{money(i.rate)}</TableCell>
                    <TableCell className="num">{money(i.amount_usd)}</TableCell>
                  </TableRow>
                ))}
                <TableRow className="total-row">
                  <TableCell colSpan={5}>TOTAL</TableCell>
                  <TableCell className="num">{money(boq.totals.amount_usd)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <details className="assumptions">
              <summary>Measurement assumptions</summary>
              <ul>{boq.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </details>
          </Card>

          <Card className="span-2" aria-label="Bar bending schedule">
            <CardHeader>
              <CardTitle>Bar Bending Schedule</CardTitle>
              <Badge variant={boq.bbs.within_target ? 'success' : 'warn'}>
                waste {boq.bbs.waste_percent}% vs ≤{boq.bbs.target_waste_percent}%
              </Badge>
            </CardHeader>
            <Table>
              <TableHeader>
                <TableRow><TableHead>Mark</TableHead><TableHead>Element</TableHead><TableHead>Shape</TableHead><TableHead className="num">Ø mm</TableHead>
                    <TableHead className="num">Cut (m)</TableHead><TableHead className="num">Qty</TableHead>
                    <TableHead className="num">Weight (kg)</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {boq.bbs.bars.slice(0, 40).map((b) => (
                  <TableRow key={b.mark}>
                    <TableCell className="mono">{b.mark}</TableCell>
                    <TableCell>{b.element}</TableCell>
                    <TableCell>{b.shape}</TableCell>
                    <TableCell className="num">{b.dia_mm}</TableCell>
                    <TableCell className="num">{b.cut_length_m.toFixed(2)}</TableCell>
                    <TableCell className="num">{b.qty}</TableCell>
                    <TableCell className="num">{Number(b.weight_kg).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {boq.bbs.bars.length > 40 && (
              <p className="muted small">Showing first 40 of {boq.bbs.bars.length} marks — full list in the Excel export.</p>
            )}
          </Card>
        </>
      )}
    </div>
  )
}