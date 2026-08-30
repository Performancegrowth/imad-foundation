import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setActiveProject } from '../api.js'
import { useProjectId } from '../useProjectId.jsx'
import PlanViewer from '../components/PlanViewer.jsx'

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
  const projectId = useProjectId(1)
  const navigate = useNavigate()

  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => setTemplates([]))
    refreshSaved()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const refreshSaved = () => {
    api.listPlans(projectId).then(setSavedPlans).catch(() => setSavedPlans([]))
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
    setBusy(true); setError(null); setNotice(null)
    try {
      await api.savePlan(projectId, planName.trim(), plan)
      setActiveProject(projectId)
      setNotice(`Plan "${planName.trim()}" saved — opening Survey…`); refreshSaved()
      setTimeout(() => navigate(`/project/${projectId}/survey`), 900)
    } catch (err) { setError(err.message || 'Save failed') }
    finally { setBusy(false) }
  }

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>Create a Structural Plan</h2>
        <p className="muted">No CAD file? Build a plan from a questionnaire, a ready template, or a plain-language description.</p>

        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              className={`tab ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t === 'questionnaire' ? 'Questionnaire' : t === 'templates' ? 'Templates' : 'AI Description'}
            </button>
          ))}
        </div>

        {busy && <div className="alert info" role="status">Generating layout…</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        {notice && <div className="alert success" role="status">{notice}</div>}

        {tab === 'questionnaire' && (
          <form
            className="form-grid"
            onSubmit={(e) => { e.preventDefault(); generateQuestionnaire() }}
          >
            <label>
              Building use
              <select value={answers.use} onChange={(e) => setAnswers({ ...answers, use: e.target.value })}>
                <option value="office">Office</option>
                <option value="residential">Residential</option>
                <option value="warehouse">Warehouse</option>
                <option value="institutional">Institutional</option>
              </select>
            </label>
            <label>
              Length (m)
              <input type="number" min="1" max="300" value={answers.length_m}
                onChange={(e) => setAnswers({ ...answers, length_m: e.target.value })} />
            </label>
            <label>
              Width (m)
              <input type="number" min="1" max="300" value={answers.width_m}
                onChange={(e) => setAnswers({ ...answers, width_m: e.target.value })} />
            </label>
            <label>
              Floors
              <input type="number" min="1" max="30" value={answers.floors}
                onChange={(e) => setAnswers({ ...answers, floors: e.target.value })} />
            </label>
            <label>
              Bays (length)
              <input type="number" min="1" max="20" value={answers.bays_x}
                onChange={(e) => setAnswers({ ...answers, bays_x: e.target.value })} />
            </label>
            <label>
              Bays (width)
              <input type="number" min="1" max="20" value={answers.bays_y}
                onChange={(e) => setAnswers({ ...answers, bays_y: e.target.value })} />
            </label>
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Generating…' : 'Generate Layout'}
            </button>
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
              <label>
                Floors
                <input type="number" min="1" max="10" value={floors}
                  onChange={(e) => setFloors(Number(e.target.value) || 1)} />
              </label>
              <button className="btn primary" onClick={generateTemplate} disabled={busy}>
                {busy ? 'Generating…' : 'Use Template'}
              </button>
            </div>
          </div>
        )}

        {tab === 'description' && (
          <div>
            <label className="full">
              Describe the building
              <textarea
                rows="4"
                value={description}
                placeholder="e.g. A three-storey office tower, 24 by 15 metres, with a concrete frame on a 7.5 m grid…"
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <div className="inline-controls">
              <label>
                Floors
                <input type="number" min="1" max="30" value={floors}
                  onChange={(e) => setFloors(Number(e.target.value) || 1)} />
              </label>
              <button className="btn primary" onClick={generateDescription} disabled={busy}>
                {busy ? 'Generating…' : 'Generate Layout'}
              </button>
            </div>
            <p className="muted small">Uses the local Ollama model if running (localhost:11434).</p>
          </div>
        )}
      </section>

      <section className="card span-2">
        <div className="card-header">
          <h3>Preview</h3>
          {plan && (
            <span className="badge success">
              {plan.walls?.length}w · {plan.columns?.length}c · {plan.beams?.length}b
            </span>
          )}
        </div>
        {plan ? <PlanViewer plan={plan} /> : (
          <div className="empty">
            <span className="empty-icon" aria-hidden="true">⌗</span>
            <p>Your generated layout will appear here.</p>
          </div>
        )}

        {plan && (
          <div className="save-row">
            <input
              type="text"
              placeholder="Plan name (e.g. Ground Floor)"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              aria-label="Plan name"
            />
            <button className="btn" onClick={savePlan} disabled={busy}>Save Plan</button>
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
      </section>
    </div>
  )
}