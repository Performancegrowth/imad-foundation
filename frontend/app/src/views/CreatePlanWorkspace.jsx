import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setActiveProject } from '../api.js'
import { readStoredProject } from '../useProjectId.jsx'
import PlanViewer from '../components/PlanViewer.jsx'
import { Button, Input, Textarea, Label, Select } from '../components/shadcn.jsx'
import { Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/shadcn.jsx'

const TABS = ['questionnaire', 'templates', 'description']

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
  const generateDescription = () => {
    if (description.trim().length < 5) {
      setError('Please describe the building (at least 5 characters).'); return
    }
    return run(() => api.generateDescription(description, floors))
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

  return (
    <div className="workspace-grid">
      <Card className="span-2">
        <h2>Create a Structural Plan</h2>
        <p className="muted">No CAD file? Build a plan from a questionnaire, a ready template, or a plain-language description.</p>
        {resolvingProject && <div className="alert info" role="status">Checking your projects…</div>}
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

        {busy && <div className="alert info" role="status">Generating layout…</div>}
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
            <Label className="full">
              Describe the building
              <Textarea
                rows="4"
                value={description}
                placeholder="e.g. A three-storey office tower, 24 by 15 metres, with a concrete frame on a 7.5 m grid…"
                onChange={(e) => setDescription(e.target.value)}
              />
            </Label>
            <div className="inline-controls">
              <Label>
                Floors
                <Input type="number" min="1" max="30" value={floors}
                  onChange={(e) => setFloors(Number(e.target.value) || 1)} />
              </Label>
              <Button variant="primary" onClick={generateDescription} disabled={busy}>
                {busy ? 'Generating…' : 'Generate Layout'}
              </Button>
            </div>
            <p className="muted small">Uses the local Ollama model if running (localhost:11434).</p>
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
    </div>
  )
}