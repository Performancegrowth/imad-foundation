// Sprint 6 — Generative design: launch an NSGA-II run, watch live progress,
// compare the top-3 Pareto options side by side and select one.
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { MiniStructure3D, ProgressBar, StatCard } from '../components/ui.jsx'

const fmt = (v, d = 0) => Number(v ?? 0).toLocaleString(undefined,
  { maximumFractionDigits: d })

export default function GenerativeDesignWorkspace() {
  const [form, setForm] = useState({ length_m: 24, width_m: 14, stories: 2 })
  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [recommendation, setRecommendation] = useState(null)
  const [selected, setSelected] = useState(null)
  const [selectState, setSelectState] = useState('idle') // idle|saving|saved|error
  const [error, setError] = useState(null)
  const timerRef = useRef(null)

  // Poll the job until it completes (or fails).
  useEffect(() => {
    if (!jobId || !['running', 'queued'].includes(job?.status ?? 'running')) return undefined
    timerRef.current = setInterval(async () => {
      try {
        const data = await api.generativeStatus(jobId)
        setJob(data)
        if (!['running', 'queued'].includes(data.status)) clearInterval(timerRef.current)
      } catch {
        /* transient poll errors are tolerated; next tick retries */
      }
    }, 700)
    return () => clearInterval(timerRef.current)
  }, [jobId, job?.status])

  useEffect(() => () => timerRef.current && clearInterval(timerRef.current), [])

  const start = useCallback(async (event) => {
    event.preventDefault()
    setError(null); setJob(null); setRecommendation(null)
    setSelected(null); setSelectState('idle')
    try {
      const res = await api.generateDesigns(form)
      setJobId(res.job_id)
      setJob({ status: 'running', progress: res.cached ? 1 : 0 })
    } catch (err) {
      setError(err.message || 'Could not start generation.')
    }
  }, [form])

  // Fetch the AI recommendation once results exist.
  useEffect(() => {
    if (job?.status !== 'completed' || recommendation) return
    api.generativeRecommendation(jobId)
      .then(setRecommendation)
      .catch(() => setRecommendation({ source: 'rule-based', recommendation: '' }))
  }, [job, jobId, recommendation])

  const selectOption = async (optionId) => {
    setSelected(optionId); setSelectState('saving')
    try {
      await api.selectGenerativeOption({ job_id: jobId, option_id: optionId })
      setSelectState('saved')
    } catch {
      setSelectState('error')
    }
  }

  const options = job?.result?.options ?? []
  const running = job && ['running', 'queued'].includes(job.status)

  return (
    <div className="workspace-grid">
      <section className="card span-2" aria-labelledby="gen-title">
        <h2 id="gen-title">Generate Design Options</h2>
        <p className="muted">
          An NSGA-II genetic algorithm evolves column grids, beam orientations and
          slab types, scoring each candidate on cost, embodied carbon, spatial
          flexibility and safety. The Pareto top-3 is returned in under a minute.
        </p>
        <form onSubmit={start} className="inline-controls wrap">
          <label htmlFor="gen-len">Length (m)</label>
          <input id="gen-len" type="number" min="6" max="120" step="0.5"
                 value={form.length_m}
                 onChange={(e) => setForm({ ...form, length_m: +e.target.value })} />
          <label htmlFor="gen-wid">Width (m)</label>
          <input id="gen-wid" type="number" min="6" max="120" step="0.5"
                 value={form.width_m}
                 onChange={(e) => setForm({ ...form, width_m: +e.target.value })} />
          <label htmlFor="gen-sto">Stories</label>
          <input id="gen-sto" type="number" min="1" max="40"
                 value={form.stories}
                 onChange={(e) => setForm({ ...form, stories: +e.target.value })} />
          <button className="btn primary" type="submit">
            {running ? 'Optimising…' : '⚙ Generate Design Options'}
          </button>
        </form>
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </section>

      {running && (
        <section className="card span-2" aria-live="polite" aria-label="Generation progress">
          <ProgressBar value={job.progress ?? 0} label="Evolving generations" />
          <p className="muted small">
            Population 50 · up to 100 generations · multi-objective
            (cost / carbon / flexibility / safety){job.progress > 0.05
              ? ` · ${Math.round((job.progress ?? 0) * 100)}%` : ''}
          </p>
        </section>
      )}

      {job?.status === 'failed' && (
        <div className="alert error span-2" role="alert">
          <strong>Optimisation failed:</strong> {job.error}
        </div>
      )}

      {job?.status === 'completed' && options.length > 0 && (
        <>
          <section className="card span-2" aria-label="Run summary">
            <div className="summary-grid four">
              <StatCard label="Options returned" value={options.length}
                        tone={job.result.cached ? 'gold' : ''} />
              <StatCard label="Envelope"
                        value={`${fmt(options[0].fitness.envelope_m2)} m²`} />
              <StatCard label="Best cost" tone="ok"
                        value={`${fmt(Math.min(...options.map((o) => o.fitness.cost)))}/m²`} />
              <StatCard label="Lowest carbon" tone="ok"
                        value={`${fmt(Math.min(...options.map((o) => o.fitness.carbon)))} kg/m²`} />
            </div>
            {job.result.cached && (
              <p className="badge ok cached-note">✓ served from optimisation cache</p>
            )}
          </section>

          <section className="card span-2" aria-label="Design option comparison">
            <div className="card-header"><h3>Pareto-optimal alternatives</h3></div>
            <div className="option-row three">
              {options.map((opt) => (
                <article key={opt.option_id}
                         className={`option-card ${selected === opt.option_id ? 'selected' : ''}`}
                         aria-label={`Option ${opt.option_id}`}>
                  <header>
                    <h4>{opt.summary.name}</h4>
                    <span className="badge">{opt.option_id}</span>
                  </header>
                  <MiniStructure3D plan={opt.plan} height={150}
                                   caption={`${opt.plan.stories}-storey · ${opt.genes.slab_type} slab`} />
                  <dl className="kv">
                    <div><dt>Cost</dt><dd>${fmt(opt.fitness.cost)}/m²</dd></div>
                    <div><dt>Carbon</dt><dd>{fmt(opt.fitness.carbon)} kg/m²</dd></div>
                    <div><dt>Flexibility</dt><dd>{fmt(100 - opt.fitness.flexibility)}/100</dd></div>
                    <div><dt>Safety margin</dt><dd>{fmt(opt.fitness.safety * 100)}%</dd></div>
                    <div><dt>Typical bay</dt><dd>{opt.genes.bay_x.toFixed(1)} × {opt.genes.bay_y.toFixed(1)} m</dd></div>
                  </dl>
                  <button className={`btn ${selected === opt.option_id ? 'primary' : ''}`}
                          onClick={() => selectOption(opt.option_id)}
                          disabled={selectState === 'saving'}>
                    {selected === opt.option_id
                      ? (selectState === 'saved' ? '✓ Saved as active plan'
                         : selectState === 'saving' ? 'Saving…' : '⚠ Retry save')
                      : 'Select this design'}
                  </button>
                </article>
              ))}
            </div>
          </section>

          {recommendation?.recommendation && (
            <section className="card span-2" aria-label="AI recommendation">
              <div className="card-header">
                <h3>Engineering recommendation</h3>
                <span className={`badge ${recommendation.source === 'ollama' ? 'ok' : ''}`}>
                  {recommendation.source === 'ollama' ? 'AI · local model' : 'rule-based'}
                </span>
              </div>
              <p>{recommendation.recommendation}</p>
            </section>
          )}
        </>
      )}
    </div>
  )
}