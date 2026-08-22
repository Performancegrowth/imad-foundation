import { useCallback, useEffect, useState } from 'react'
import { api, DEFAULT_PROJECT_ID } from '../api.js'

const EMPTY = {
  soil_bearing_capacity_kpa: '',
  groundwater_depth_m: '',
  terrain_slope_deg: '',
  latitude: '',
  longitude: '',
  soil_type: 'clay',
}

export default function SurveyWorkspace() {
  const [form, setForm] = useState(EMPTY)
  const [summary, setSummary] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [file, setFile] = useState(null)

  const refreshSummary = () => {
    api.getSurvey(DEFAULT_PROJECT_ID).then(setSummary).catch(() => setSummary(null))
  }
  useEffect(refreshSummary, [])

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submitManual = useCallback(async (e) => {
    e.preventDefault()
    setBusy(true); setError(null); setNotice(null)
    try {
      const body = Object.fromEntries(
        Object.entries(form)
          .filter(([, v]) => v !== '')
          .map(([k, v]) => (k === 'soil_type' ? [k, v] : [k, Number(v)])),
      )
      await api.saveSurveyManual(DEFAULT_PROJECT_ID, body)
      setNotice('Survey reading recorded.')
      refreshSummary()
    } catch (err) {
      setError(err.message || 'Could not save survey data')
    } finally {
      setBusy(false)
    }
  }, [form])

  const submitFile = useCallback(async () => {
    if (!file) { setError('Choose a geotechnical file first.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      const result = await api.uploadSurvey(DEFAULT_PROJECT_ID, file)
      setNotice(`Imported ${file.name}. ${result.message || ''}`)
      setFile(null)
      refreshSummary()
    } catch (err) {
      setError(err.message || 'Could not import file')
    } finally {
      setBusy(false)
    }
  }, [file])

  const num = (v) => (v === null || v === undefined || v === '' ? '—' : Number(v).toLocaleString())

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>Site Survey &amp; Geotechnics</h2>
        <p className="muted">Record site constraints that drive foundation selection and earthwork design.</p>

        {busy && <div className="alert info" role="status">Saving…</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        {notice && <div className="alert success" role="status">{notice}</div>}

        <form className="form-grid" onSubmit={submitManual}>
          <label>
            Soil bearing capacity (kPa)
            <input type="number" min="1" max="5000" value={form.soil_bearing_capacity_kpa} onChange={set('soil_bearing_capacity_kpa')} />
          </label>
          <label>
            Groundwater depth (m)
            <input type="number" min="0" step="0.1" value={form.groundwater_depth_m} onChange={set('groundwater_depth_m')} />
          </label>
          <label>
            Terrain slope (°)
            <input type="number" min="0" max="90" value={form.terrain_slope_deg} onChange={set('terrain_slope_deg')} />
          </label>
          <label>
            Latitude
            <input type="number" min="-90" max="90" step="0.0001" value={form.latitude} onChange={set('latitude')} />
          </label>
          <label>
            Longitude
            <input type="number" min="-180" max="180" step="0.0001" value={form.longitude} onChange={set('longitude')} />
          </label>
          <label>
            Soil type
            <select value={form.soil_type} onChange={set('soil_type')}>
              <option value="clay">Clay</option>
              <option value="sand">Sand</option>
              <option value="silt">Silt</option>
              <option value="gravel">Gravel</option>
              <option value="rock">Rock</option>
            </select>
          </label>
          <button type="submit" className="btn primary" disabled={busy}>Record Reading</button>
        </form>

        <hr className="divider" />
        <h3>Import geotechnical report</h3>
        <p className="muted small">PDF report, topographic CSV, contour DXF, or LAS point cloud.</p>
        <div className="inline-controls">
          <input
            type="file"
            accept=".pdf,.csv,.dxf,.las,.laz"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            aria-label="Choose geotechnical file"
          />
          <button className="btn primary" onClick={submitFile} disabled={busy || !file}>
            Upload &amp; Import
          </button>
        </div>
      </section>

      <section className="card span-2">
        <div className="card-header">
          <h3>Survey Summary</h3>
          {summary?.entries ? <span className="badge">{summary.entries} readout(s)</span> : null}
        </div>
        <div className="summary-grid">
          <div className="stat">
            <span className="stat-label">Soil bearing</span>
            <strong>{num(summary?.soil_bearing_capacity_kpa)} kPa</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Groundwater</span>
            <strong>{num(summary?.groundwater_depth_m)} m</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Slope</span>
            <strong>{num(summary?.terrain_slope_deg)} °</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Location</span>
            <strong>{summary?.location || 'Not set'}</strong>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 12 }}>
          {summary?.message || 'No survey data yet — record site inputs on the left.'}
        </p>
      </section>
    </div>
  )
}