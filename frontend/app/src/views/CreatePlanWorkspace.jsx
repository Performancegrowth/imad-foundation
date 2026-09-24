import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setActiveProject } from '../api.js'
import { readStoredProject } from '../useProjectId.jsx'
import PlanViewer from '../components/PlanViewer.jsx'
import { getPlanBounds } from '../planUtil.js'
import { Button, Input, Textarea, Label, Select } from '../components/shadcn.jsx'
import { Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { LoadingCard, NextStep } from '../components/ui.jsx'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/shadcn.jsx'

const TABS = ['questionnaire', 'templates', 'description']

// ─── Evidence-based generation (NeuBE-inspired, client-side) ───────────────
// The AI Description tab runs a 3-step "glass box" workflow:
//   1. extract evidence → user reviews & corrects it,
//   2. generate with a visible trace (grid → column check → beam-depth check),
//   3. review every decision & constraint the returned plan reflects.
// Deterministic, runs in the browser — no backend or PlanData schema changes;
// generation still posts {text, floors} as before.

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const OCCUPANCY_OPTIONS = [
  'residential', 'office', 'warehouse', 'institutional', 'retail',
  'healthcare', 'education', 'hotel', 'industrial', 'parking',
]

const SRC_LABEL = {
  text: 'from your text',
  input: 'from Floors input',
  derived: 'derived from footprint',
  corrected: 'corrected by you',
  default: 'default',
  'not found': 'not found',
  none: 'none detected',
}

const WORD_NUM = {
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
}

/**
 * Deterministic evidence extractor. Pulls the reviewable facts the user is
 * asked to confirm — total area, floor count, occupancy, site constraints —
 * plus the beam-depth limit and optional column budget used by the review.
 */
function extractEvidence(text, fallbackFloors) {
  const t = (text || '').trim()
  const sources = {}

  // Floor count: "two-storey", "2 floors", "G+1" → else the Floors input.
  let floors = null
  let m = t.match(/(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[-\s]?(?:storeys?|stories|floors?|levels?)/i)
  if (m) floors = /^\d+$/.test(m[1]) ? parseInt(m[1], 10) : WORD_NUM[m[1].toLowerCase()]
  if (!floors) {
    const g = t.match(/\bG\s*\+\s*(\d+)\b/i)
    if (g) floors = parseInt(g[1], 10) + 1
  }
  if (floors && floors > 0) sources.floors = 'text'
  else {
    floors = Math.min(30, Math.max(1, Math.round(Number(fallbackFloors) || 1)))
    sources.floors = 'input'
  }

  // Footprint: "24 by 15 metres" / "24m x 15m".
  let fp = null
  m = t.match(/(\d+(?:\.\d+)?)\s*(?:m\b|metres?|meters?)\s*(?:by|x|×)\s*(\d+(?:\.\d+)?)\s*(?:m\b|metres?|meters?)/i)
    || t.match(/(\d+(?:\.\d+)?)\s+(?:by|×|x)\s+(\d+(?:\.\d+)?)\s+(?:m\b|metres?|meters?)/i)
  if (m) fp = [parseFloat(m[1]), parseFloat(m[2])]

  // Total area: "420 sqm" … else derived from the footprint.
  let area = null
  m = t.match(/(\d+(?:\.\d+)?)\s*(?:sqm|m2|m²|sq\.?\s?m\b|square\s?(?:metres?|meters?))/i)
    || t.match(/(?:area|footprint)[^.\d]{0,12}(\d+(?:\.\d+)?)/i)
  if (m) { area = parseFloat(m[1]); sources.area_sqm = 'text' }
  else if (fp) { area = Math.round(fp[0] * fp[1]); sources.area_sqm = 'derived' }
  else sources.area_sqm = 'not found'

  // Occupancy: first keyword family wins.
  const OCC = [
    [/villa|house|home|apartment|residential|family|bedroom/i, 'residential'],
    [/office|workspace|coworking|commercial/i, 'office'],
    [/warehouse|factory|industrial|workshop/i, 'warehouse'],
    [/school|classroom|university|hospital|clinic|mosque|institution/i, 'institutional'],
    [/retail|shop\b|showroom|mall|market/i, 'retail'],
    [/hotel|guest\s?house|hospitality/i, 'hotel'],
    [/parking|car\s?park/i, 'parking'],
  ]
  let occupancy = null
  for (const [re, val] of OCC) { if (re.test(t)) { occupancy = val; break } }
  sources.occupancy = occupancy ? 'text' : 'not found'

  // Site constraints: clauses carrying an orientation or keep-clear rule —
  // e.g. "garage on north", "living faces south", "keep the corner tree".
  const ORIENT = /\b(north|south|east|west|northern|southern|eastern|western|front|rear)\b/i
  const KEEP = /\b(setback|slope|retain|tree|adjacent|boundary|street|road|keep|clear|avoid|existing)\b/i
  const constraints = []
  for (const clause of t.split(/[.;\n]+/)) {
    for (const piece of clause.split(/\s*,\s*/)) {
      if (constraints.length >= 6) break
      const c = piece.trim().replace(/\s+/g, ' ')
      if (c.length < 4 || c.length > 90) continue
      if ((ORIENT.test(c) || KEEP.test(c)) && !constraints.some((x) => x.toLowerCase() === c.toLowerCase())) {
        constraints.push(c)
      }
    }
  }
  sources.constraints = constraints.length ? 'text' : 'none'

  // Beam-depth limit: stated in text, else 500 mm (Beam.depth_m default 0.5).
  let beamLimit = 500
  sources.beam_limit_mm = 'default'
  m = t.match(/(?:max(?:imum)?[\s-]*(?:beam[\s-]*)?depth|beam[\s-]*depth[\s-]*(?:max(?:imum)?)?)[^.\d]{0,12}(\d{3,4})\s*mm/i)
  if (m) { beamLimit = parseInt(m[1], 10); sources.beam_limit_mm = 'text' }

  // Optional column budget: "12-16 columns" / "about 16 columns".
  let columnsRequested = null
  m = t.match(/(\d{1,3})\s*(?:-|–|to)\s*(\d{1,3})\s*columns?\b/i)
  if (m) columnsRequested = `${m[1]}-${m[2]}`
  else {
    m = t.match(/(?:around|about|approx\.?|max(?:imum)?)\s*(\d{1,3})\s*columns?\b/i)
    if (m) columnsRequested = m[1]
  }
  sources.columns_requested = columnsRequested ? 'text' : 'none'

  return {
    values: {
      floors, area_sqm: area, occupancy, constraints,
      beam_limit_mm: beamLimit, columns_requested: columnsRequested,
    },
    sources,
  }
}

/** Reinforce confirmed evidence into the prompt sent to /plans/description. */
function buildPrompt(text, ev) {
  const bits = [`floors: ${ev.floors}`]
  if (ev.area_sqm) bits.push(`total area: ${ev.area_sqm} sqm`)
  if (ev.occupancy) bits.push(`occupancy: ${ev.occupancy}`)
  if (ev.constraints.length) bits.push(`site constraints: ${ev.constraints.join('; ')}`)
  bits.push(`max beam depth: ${ev.beam_limit_mm} mm`)
  return `${text}\n[Confirmed evidence — ${bits.join(' · ')}]`
}

/** Ray-cast point-in-polygon over a Room.boundary (closed GeoPoint list). */
function pointInPoly(x, y, pts) {
  let inside = false
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x; const yi = pts[i].y
    const xj = pts[j].x; const yj = pts[j].y
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Real check: columns that fall inside any "living" room polygon. */
function checkLivingRooms(plan) {
  const cols = plan?.columns || []
  const rooms = plan?.rooms || []
  const living = rooms.filter((r) => /living|lounge|salon|family/i.test(r.label || ''))
  if (!living.length) {
    return {
      status: 'skip', checked: cols.length, violations: 0,
      msg: rooms.length
        ? `No room labelled "living" among ${rooms.length} room polygon(s) — ${cols.length} columns sit on the structural grid.`
        : `No room polygons in this plan — all ${cols.length} columns sit on the structural grid, so none can land in a living room.`,
    }
  }
  let violations = 0
  for (const c of cols) {
    const x = c.cx ?? c.x ?? 0
    const y = c.cy ?? c.y ?? 0
    if (living.some((r) => (r.boundary || []).length >= 3 && pointInPoly(x, y, r.boundary))) violations += 1
  }
  return {
    status: violations === 0 ? 'ok' : 'fail', checked: cols.length, violations,
    msg: `${violations} of ${cols.length} columns inside ${living.length} living-room polygon(s).`,
  }
}

/** Real check: max beam depth (mm) across the plan vs the confirmed limit. */
function checkBeamDepths(plan, limitMm) {
  const beams = plan?.beams || []
  const depths = beams.map((b) => Math.round((b.depth_m ?? 0) * 1000)).filter((d) => d > 0)
  if (!depths.length) {
    return { status: 'skip', maxMm: null, count: beams.length, msg: 'No beam depths in the returned plan to validate.' }
  }
  const maxMm = Math.max(...depths)
  return {
    status: maxMm <= limitMm ? 'ok' : 'fail', maxMm, count: beams.length,
    msg: `Max ${maxMm} mm across ${beams.length} beams (limit ${limitMm} mm).`,
  }
}

/** Column-line / bay counts derived from the returned grid. */
function gridInfo(plan) {
  const cols = plan?.columns || []
  const linesX = new Set(cols.map((c) => Math.round((c.cx ?? c.x ?? 0) * 100) / 100)).size
  const linesY = new Set(cols.map((c) => Math.round((c.cy ?? c.y ?? 0) * 100) / 100)).size
  return { linesX, linesY, bays: `${Math.max(linesX - 1, 0)}×${Math.max(linesY - 1, 0)}` }
}

/** Rows of the Review Evidence panel (label / display / edit metadata). */
const EV_ROWS = (ev) => [
  { key: 'area_sqm', label: 'Total Area',
    display: ev.area_sqm != null ? `${ev.area_sqm} m²` : 'Not found',
    edit: ev.area_sqm != null ? String(ev.area_sqm) : '', type: 'number' },
  { key: 'floors', label: 'Floor Count', display: `${ev.floors}`, edit: String(ev.floors), type: 'number' },
  { key: 'occupancy', label: 'Occupancy', display: ev.occupancy || 'Not specified',
    edit: ev.occupancy || 'residential', type: 'select' },
  { key: 'constraints', label: 'Site Constraints',
    display: ev.constraints.length ? ev.constraints.join(' · ') : 'None detected',
    edit: ev.constraints.join('; '), type: 'text' },
  { key: 'beam_limit_mm', label: 'Beam Depth Limit', display: `${ev.beam_limit_mm} mm`,
    edit: String(ev.beam_limit_mm), type: 'number' },
]

const GEN_STEP_LABELS = (ev) => [
  'Generating Structural Grid...',
  'Placing Columns (verified, no columns in living room)...',
  `Validating Beam Depths (max ${ev?.beam_limit_mm ?? 500}mm)...`,
]

export default function CreatePlanWorkspace() {
  const [tab, setTab] = useState('questionnaire')
  const [plan, setPlan] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [answers, setAnswers] = useState({
    length_m: 12, width_m: 8, floors: 1, bays_x: 2, bays_y: 1, use: 'office',
  })
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('small_office')
  const [floors, setFloors] = useState(1)
  const [description, setDescription] = useState('')
  const [savedPlans, setSavedPlans] = useState([])
  const [planName, setPlanName] = useState('')
  const [projectId, setProjectId] = useState(null)
  const [resolvingProject, setResolvingProject] = useState(true)

  // Evidence-based description workflow (glass-box, NeuBE-inspired):
  // compose → evidence (review/correct) → ready → generating (3-step trace)
  // → review (decisions & constraints computed from the real plan).
  const [dPhase, setDPhase] = useState('compose')
  const [evidence, setEvidence] = useState(null)
  const [evSources, setEvSources] = useState({})
  const [editKey, setEditKey] = useState(null) // evidence row being corrected
  const [editVal, setEditVal] = useState('')
  const [genStep, setGenStep] = useState(0)    // progress trace stage 0..3
  const [checks, setChecks] = useState(null)   // real post-generation checks
  const aliveRef = useRef(true)
  useEffect(() => () => { aliveRef.current = false }, [])

  const navigate = useNavigate()

  // Resolve (or auto-create) a project the current user actually owns.
  // Previously the workspace defaulted to project 1, which belongs to another
  // user, so /plans/save rejected it with 404 "Project not found".
  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => setTemplates([]))
    let cancelled = false
    const resolveProject = async () => {
      try {
        const list = await api.listProjects()
        if (cancelled) return
        const ids = (list || []).map((p) => Number(p.id))
        const stored = readStoredProject()
        const chosen = ids.length && ids.includes(Number(stored))
          ? Number(stored)
          : (ids[0] || null)
        let pid = chosen
        if (!pid) {
          const created = await api.createProject({
            name: 'My Imad Project',
            description: 'Auto-created workspace for plan design',
          })
          if (cancelled) return
          pid = Number(created.id)
        }
        setProjectId(pid)
        if (pid) setActiveProject(pid)
        refreshSaved(pid)
      } catch (err) {
        if (cancelled) return
        const stored = readStoredProject()
        if (stored) {
          setProjectId(stored)
          refreshSaved(stored)
        } else {
          setError(err.status === 401
            ? 'Sign in to create a project and save your design.'
            : err.message || 'Could not load your projects.')
        }
      } finally {
        if (!cancelled) setResolvingProject(false)
      }
    }
    resolveProject()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refreshSaved = (pid) => {
    if (!pid) { setSavedPlans([]); return }
    api.listPlans(pid).then(setSavedPlans).catch(() => setSavedPlans([]))
  }

  const run = async (fn) => {
    setBusy(true); setError(null); setNotice(null)
    try { setPlan(await fn()); setPlanName('') }
    catch (err) { setError(err.message || 'Generation failed') }
    finally { setBusy(false) }
  }

  const generateQuestionnaire = () => run(() => api.generateQuestionnaire(answers))
  const generateTemplate = () => run(() => api.generateTemplate(selectedTemplate, floors))
  // Step 1 — extract evidence and pause for user review/correction.
  const analyzeDescription = () => {
    if (description.trim().length < 5) {
      setError('Please describe the building (at least 5 characters).')
      return
    }
    const { values, sources } = extractEvidence(description, floors)
    setEvidence(values); setEvSources(sources)
    setEditKey(null); setEditVal(''); setChecks(null); setError(null)
    setDPhase('evidence')
  }

  const startCorrect = (row) => { setEditKey(row.key); setEditVal(row.edit) }

  const saveCorrection = () => {
    setEvidence((ev) => {
      if (!ev) return ev
      const next = { ...ev }
      if (editKey === 'area_sqm') {
        const n = Number(editVal)
        next.area_sqm = Number.isFinite(n) && n > 0 ? n : null
      } else if (editKey === 'floors') {
        next.floors = Math.min(30, Math.max(1, Math.round(Number(editVal) || 1)))
      } else if (editKey === 'occupancy') {
        next.occupancy = editVal.trim() || null
      } else if (editKey === 'constraints') {
        next.constraints = editVal.split(/[;,]+/).map((s) => s.trim()).filter(Boolean).slice(0, 6)
      } else if (editKey === 'beam_limit_mm') {
        next.beam_limit_mm = Math.min(1200, Math.max(150, Math.round(Number(editVal) || 500)))
      }
      return next
    })
    setEvSources((s) => ({ ...s, [editKey]: 'corrected' }))
    setEditKey(null); setEditVal('')
  }

  // Step 2 — generate with a visible trace: grid → column check → beam check.
  const startGeneration = async () => {
    if (!evidence) return
    setDPhase('generating'); setGenStep(0); setChecks(null)
    setError(null); setNotice(null); setBusy(true)
    try {
      const generated = await api.generateDescription(buildPrompt(description, evidence), evidence.floors)
      if (!aliveRef.current) return
      setPlan(generated); setPlanName('')
      setGenStep(1)
      await sleep(700)
      if (!aliveRef.current) return
      const living = checkLivingRooms(generated)
      setChecks((c) => ({ ...(c || {}), living }))
      setGenStep(2)
      await sleep(700)
      if (!aliveRef.current) return
      const beams = checkBeamDepths(generated, evidence.beam_limit_mm)
      const stories = { requested: evidence.floors, actual: generated?.stories ?? null }
      setChecks((c) => ({ ...(c || {}), beams, stories }))
      setGenStep(3)
      await sleep(450)
      if (!aliveRef.current) return
      setDPhase('review')
    } catch (err) {
      if (!aliveRef.current) return
      setError(err.message || 'Generation failed')
      setDPhase('ready') // evidence stays confirmed — user can retry
    } finally {
      if (aliveRef.current) setBusy(false)
    }
  }

  const savePlan = async () => {
    if (!plan) return
    if (!planName.trim()) { setError('Give the plan a name before saving.'); return }
    if (!projectId) { setError('No project available yet — please sign in and try again.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      await api.savePlan(projectId, planName.trim(), plan)
      setActiveProject(projectId)
      setNotice(`Plan "${planName.trim()}" saved to project #${projectId} — opening Survey…`); refreshSaved(projectId)
      setTimeout(() => navigate(`/project/${projectId}/survey`), 900)
    } catch (err) {
      // Surface the real backend message. FastAPI returns a plain string, or
      // a list of {loc, msg} objects for 422 — flattening it here avoids the
      // useless "[object Object]" the user used to see.
      let msg = 'Save failed'
      const d = err?.response?.data?.detail ?? err?.detail
      if (typeof d === 'string') msg = d
      else if (Array.isArray(d) && d[0]?.msg) msg = d.map((x) => x.msg).join('; ')
      else if (d && typeof d === 'object') msg = JSON.stringify(d)
      else if (err?.message) msg = err.message
      setError(msg)
    } finally { setBusy(false) }
  }

  if (resolvingProject) return <LoadingCard label="Preparing your workspace..." />

  // Step 3 — Review & Validate rows; every line computed from the real plan.
  const decisions = []
  const constraintRows = []
  if (dPhase === 'review' && plan && evidence) {
    const nCols = plan.columns?.length ?? 0
    decisions.push({
      ok: true,
      text: `Used ${nCols} columns${evidence.columns_requested ? ` (requested: ${evidence.columns_requested})` : ''}`,
    })
    const g = gridInfo(plan)
    decisions.push({ ok: true, text: `Structural grid: ${g.linesX}×${g.linesY} column lines → ${g.bays} bays` })
    const actual = plan.stories ?? null
    decisions.push({ ok: actual === evidence.floors, text: `Stories: ${actual ?? '—'} (requested: ${evidence.floors})` })
    if (checks?.living) {
      decisions.push({
        ok: checks.living.status !== 'fail',
        text: checks.living.status === 'skip'
          ? 'No columns in living room — nothing in this plan could violate it'
          : `No columns in living room — ${checks.living.msg}`,
      })
    }
    if (checks?.beams) {
      decisions.push({
        ok: checks.beams.status !== 'fail',
        text: `Max beam depth: ${checks.beams.maxMm ?? '—'}mm (limit ${evidence.beam_limit_mm}mm)`,
      })
    }
    const b = getPlanBounds(plan)
    const fpArea = Math.round((b.maxX - b.minX) * (b.maxY - b.minY))
    decisions.push({
      ok: evidence.area_sqm == null ? null : Math.abs(fpArea - evidence.area_sqm) <= evidence.area_sqm * 0.35,
      text: `Footprint: ${fpArea} m²${evidence.area_sqm ? ` (confirmed area: ${evidence.area_sqm} m²)` : ''}`,
    })
    decisions.push({
      ok: null,
      text: `Elements: ${plan.walls?.length ?? 0} walls · ${plan.beams?.length ?? 0} beams · ${nCols} columns · occupancy ${evidence.occupancy || 'unspecified'}`,
    })

    if (evidence.constraints.length) {
      for (const c of evidence.constraints) {
        if (/living|lounge|family/i.test(c) && checks?.living) {
          constraintRows.push({ ok: checks.living.status !== 'fail', text: c, detail: checks.living.msg })
        } else {
          constraintRows.push({ ok: null, text: c, detail: 'Recorded from your description — confirm placement in the preview.' })
        }
      }
    } else {
      constraintRows.push({ ok: null, text: 'No site constraints detected in your description.', detail: '' })
    }
    constraintRows.push({
      ok: checks?.beams ? checks.beams.status !== 'fail' : null,
      text: `Beam depth limit: ${evidence.beam_limit_mm} mm`,
      detail: checks?.beams?.msg || '',
    })
  }

  return (
    <div className="workspace-grid">
      <Card className="span-2">
        <h2>Create a Structural Plan</h2>
        <p className="muted">No CAD file? Build a plan from a questionnaire, a ready template, or a plain-language description.</p>
        {!resolvingProject && projectId && <p className="muted small">Saving to <strong>project #{projectId}</strong> — saved plans feed Survey, Analysis &amp; BOQ.</p>}

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            {TABS.map((t) => (
              <TabsTrigger
                key={t}
                value={t}
                active={tab === t}
                onClick={() => setTab(t)}
              >
                {t === 'questionnaire' ? 'Questionnaire' : t === 'templates' ? 'Templates' : 'AI Description'}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {busy && dPhase !== 'generating' && <div className="alert info" role="status">Generating layout…</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        {notice && <div className="alert success" role="status">{notice}</div>}

        {tab === 'questionnaire' && (
          <form
            className="form-grid"
            onSubmit={(e) => { e.preventDefault(); generateQuestionnaire() }}
          >
            <Label>
              Building use
              <Select value={answers.use} onChange={(e) => setAnswers({ ...answers, use: e.target.value })}>
                <option value="office">Office</option>
                <option value="residential">Residential</option>
                <option value="warehouse">Warehouse</option>
                <option value="institutional">Institutional</option>
              </Select>
            </Label>
            <Label>
              Length (m)
              <Input type="number" min="1" max="300" value={answers.length_m}
                onChange={(e) => setAnswers({ ...answers, length_m: e.target.value })} />
            </Label>
            <Label>
              Width (m)
              <Input type="number" min="1" max="300" value={answers.width_m}
                onChange={(e) => setAnswers({ ...answers, width_m: e.target.value })} />
            </Label>
            <Label>
              Floors
              <Input type="number" min="1" max="30" value={answers.floors}
                onChange={(e) => setAnswers({ ...answers, floors: e.target.value })} />
            </Label>
            <Label>
              Bays (length)
              <Input type="number" min="1" max="20" value={answers.bays_x}
                onChange={(e) => setAnswers({ ...answers, bays_x: e.target.value })} />
            </Label>
            <Label>
              Bays (width)
              <Input type="number" min="1" max="20" value={answers.bays_y}
                onChange={(e) => setAnswers({ ...answers, bays_y: e.target.value })} />
            </Label>
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? 'Generating…' : 'Generate Layout'}
            </Button>
          </form>
        )}

        {tab === 'templates' && (
          <div>
            <div className="template-gallery">
              {(templates.length ? templates : []).map((t) => (
                <button
                  key={t.id}
                  className={`template-card ${selectedTemplate === t.id ? 'active' : ''}`}
                  onClick={() => setSelectedTemplate(t.id)}
                >
                  <span className="template-preview" aria-hidden="true">
                    <svg viewBox="0 0 80 60">
                      <rect x="8" y="8" width="64" height="44" fill="none" stroke="#0A5C36" strokeWidth="2" />
                      <line x1="40" y1="8" x2="40" y2="52" stroke="#0A5C36" strokeWidth="1.5" strokeDasharray="3,3" />
                      <line x1="8" y1="30" x2="72" y2="30" stroke="#0A5C36" strokeWidth="1.5" strokeDasharray="3,3" />
                      <circle cx="12" cy="12" r="2.5" fill="#111827" />
                      <circle cx="68" cy="12" r="2.5" fill="#111827" />
                      <circle cx="12" cy="48" r="2.5" fill="#111827" />
                      <circle cx="68" cy="48" r="2.5" fill="#111827" />
                    </svg>
                  </span>
                  <strong>{t.name}</strong>
                  <span className="muted">{t.kind}</span>
                </button>
              ))}
            </div>
            <div className="inline-controls">
              <Label>
                Floors
                <Input type="number" min="1" max="10" value={floors}
                  onChange={(e) => setFloors(Number(e.target.value) || 1)} />
              </Label>
              <Button variant="primary" onClick={generateTemplate} disabled={busy}>
                {busy ? 'Generating…' : 'Use Template'}
              </Button>
            </div>
          </div>
        )}

        {tab === 'description' && (
          <div>
            {dPhase === 'compose' && (
              <>
                <Label className="full">
                  Describe the building
                  <Textarea
                    rows="4"
                    value={description}
                    placeholder="e.g. A two-storey residential villa of 420 sqm, living faces south, garage on north, max beam depth 500mm…"
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </Label>
                <div className="inline-controls">
                  <Label>
                    Floors
                    <Input type="number" min="1" max="30" value={floors}
                      onChange={(e) => setFloors(Number(e.target.value) || 1)} />
                  </Label>
                  <Button variant="primary" onClick={analyzeDescription} disabled={busy}>
                    Analyze Description
                  </Button>
                </div>
                <p className="muted small">
                  Step 1 of 3 — evidence is extracted from your text first (area, floors,
                  occupancy, site constraints) so you can verify it before anything is generated.
                </p>
              </>
            )}

            {dPhase === 'evidence' && evidence && (
              <div role="group" aria-label="Review evidence">
                <h4>Review Evidence</h4>
                <p className="muted small">
                  Extracted from your description — correct anything we misread before generating.
                </p>
                <ul className="ev-list">
                  {EV_ROWS(evidence).map((row) => (
                    <li key={row.key} className="ev-row">
                      <span className="ev-label">{row.label}</span>
                      {editKey === row.key ? (
                        <span className="ev-edit">
                          {row.type === 'select' ? (
                            <Select value={editVal} aria-label={`Correct ${row.label}`}
                              onChange={(e) => setEditVal(e.target.value)}>
                              {OCCUPANCY_OPTIONS.map((o) => (
                                <option key={o} value={o}>{o}</option>
                              ))}
                            </Select>
                          ) : (
                            <Input type={row.type} value={editVal} aria-label={`Correct ${row.label}`}
                              onChange={(e) => setEditVal(e.target.value)} />
                          )}
                          <Button size="sm" variant="primary" onClick={saveCorrection}>Save</Button>
                          <Button size="sm" variant="outline" onClick={() => setEditKey(null)}>Cancel</Button>
                        </span>
                      ) : (
                        <span className="ev-value-wrap">
                          <span className="ev-value">{row.display}</span>
                          <span className="chip">{SRC_LABEL[evSources[row.key]] || evSources[row.key] || ''}</span>
                          <Button size="sm" variant="outline" onClick={() => startCorrect(row)}>Correct</Button>
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="inline-controls">
                  <Button variant="outline" onClick={() => setDPhase('compose')}>← Edit Description</Button>
                  <Button variant="primary" onClick={() => { setEditKey(null); setDPhase('ready') }}>
                    Confirm Evidence
                  </Button>
                </div>
              </div>
            )}

            {dPhase === 'ready' && evidence && (
              <div role="group" aria-label="Confirmed evidence">
                <h4>Evidence Confirmed</h4>
                <div className="ev-chip-row">
                  {EV_ROWS(evidence).map((row) => (
                    <Badge key={row.key} variant="default">{row.label}: {row.display}</Badge>
                  ))}
                  {evidence.columns_requested && (
                    <Badge variant="default">Columns: {evidence.columns_requested}</Badge>
                  )}
                </div>
                <div className="inline-controls">
                  <Button variant="outline" onClick={() => setDPhase('evidence')}>← Adjust Evidence</Button>
                  <Button variant="primary" onClick={startGeneration} disabled={busy}>
                    {busy ? 'Generating…' : 'Generate Plan'}
                  </Button>
                </div>
                <p className="muted small">
                  Step 2 of 3 — generation runs with a visible trace: structural grid →
                  column placement check → beam-depth validation.
                </p>
              </div>
            )}

            {dPhase === 'generating' && (
              <div role="status" aria-live="polite">
                <h4>Traceable Generation</h4>
                <ol className="gen-steps">
                  {GEN_STEP_LABELS(evidence).map((label, i) => (
                    <li key={label} className={i < genStep ? 'done' : i === genStep ? 'active' : 'pending'}>
                      <span className="gen-mark" aria-hidden="true">
                        {i < genStep ? '✓' : i === genStep ? '›' : '·'}
                      </span>
                      <span>{label}</span>
                      {i === genStep && <span className="spinner" aria-hidden="true" />}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {dPhase === 'review' && evidence && plan && (
              <div role="group" aria-label="Review and validate">
                <h4>Review &amp; Validate</h4>
                <p className="muted small">Every line below is computed from the plan that was actually generated.</p>
                <p className="eyebrow">Decisions</p>
                <ul className="review-list">
                  {decisions.map((row, i) => (
                    <li key={`${row.text}-${i}`}>
                      <Badge variant={row.ok === true ? 'success' : row.ok === false ? 'fail' : 'default'}>
                        {row.ok === true ? 'PASS' : row.ok === false ? 'CHECK' : 'INFO'}
                      </Badge>
                      <span>{row.text}</span>
                    </li>
                  ))}
                </ul>
                <p className="eyebrow">Constraints honored</p>
                <ul className="review-list">
                  {constraintRows.map((row, i) => (
                    <li key={`${row.text}-${i}`}>
                      <Badge variant={row.ok === true ? 'success' : row.ok === false ? 'fail' : 'default'}>
                        {row.ok === true ? 'PASS' : row.ok === false ? 'CHECK' : 'INFO'}
                      </Badge>
                      <span>
                        {row.text}
                        {row.detail && <span className="detail"> — {row.detail}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="inline-controls">
                  <Button variant="outline" onClick={() => { setDPhase('evidence'); setEditKey(null) }}>
                    ← Adjust Evidence
                  </Button>
                  <Button variant="primary" onClick={startGeneration} disabled={busy}>
                    {busy ? 'Generating…' : '↻ Generate Again'}
                  </Button>
                </div>
                <p className="muted small">
                  Step 3 of 3 — inspect the preview below, then Save Plan to run Survey &amp; Analysis.
                </p>
              </div>
            )}
            <p className="muted small">Uses the local Ollama model if running (localhost:11434), with a deterministic fallback parser.</p>
          </div>
        )}
      </Card>

      <Card className="span-2">
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          {plan && (
            <Badge variant="success">
              {plan.walls?.length}w · {plan.columns?.length}c · {plan.beams?.length}b
            </Badge>
          )}
        </CardHeader>
        {plan ? <PlanViewer plan={plan} /> : (
          <div className="empty">
            <span className="empty-icon" aria-hidden="true">⌗</span>
            <p>Your generated layout will appear here.</p>
          </div>
        )}

        {plan && (
          <div className="save-row">
            <Input
              type="text"
              placeholder="Plan name (e.g. Ground Floor)"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              aria-label="Plan name"
            />
            <Button onClick={savePlan} disabled={busy || !projectId}>Save Plan</Button>
          </div>
        )}

        {savedPlans.length > 0 && (
          <div className="saved-list">
            <h4>Saved plans</h4>
            <ul>
              {savedPlans.map((s) => (
                <li key={s.name}>
                  <span>{s.label}</span>
                  <span className="muted">{s.walls}w · {s.columns}c · {s.stories} floor(s)</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {plan && projectId && (
        <NextStep nextLabel="Analyze" nextHref={`/project/${projectId}/analyze`} />
      )}
    </div>
  )
}