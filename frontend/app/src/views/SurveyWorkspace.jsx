import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { NoProject, useProjectId } from '../useProjectId.jsx'
import { Button, Input, Label, Select, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'

const EMPTY = {
  soil_bearing_capacity_kpa: '',
  groundwater_depth_m: '',
  terrain_slope_deg: '',
  latitude: '',
  longitude: '',
  soil_type: 'clay',
  // Lateral-load parameters (SBC 301 §12.8 seismic + ch. 27 wind)
  ss_mps2: '', s1_mps2: '', site_class: 'D', r_factor: '',
  basic_wind_speed_mps: '', wind_exposure: 'B',
}

export default function SurveyWorkspace() {
  const [form, setForm] = useState(EMPTY)
  const [summary, setSummary] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [file, setFile] = useState(null)

  const projectId = useProjectId()

  const refreshSummary = () => {
    if (!projectId) return
    api.getSurvey(projectId).then(setSummary).catch(() => setSummary(null))
  }
  useEffect(refreshSummary, [projectId])

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
      await api.saveSurveyManual(projectId, body)
      setNotice('Survey reading recorded.')
      refreshSummary()
    } catch (err) {
      setError(err.message || 'Could not save survey data')
    } finally {
      setBusy(false)
    }
  }, [form, projectId])

  const submitFile = useCallback(async () => {
    if (!file) { setError('Choose a geotechnical file first.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      const result = await api.uploadSurvey(projectId, file)
      setNotice(`Imported ${file.name}. ${result.message || ''}`)
      setFile(null)
      refreshSummary()
    } catch (err) {
      setError(err.message || 'Could not import file')
    } finally {
      setBusy(false)
    }
  }, [file, projectId])

  const num = (v) => (v === null || v === undefined || v === '' ? '—' : Number(v).toLocaleString())

  if (!projectId) return <NoProject />

  return (
    <div className="workspace-grid">
      <Card className="span-2">
        <h2>Site Survey &amp; Geotechnics</h2>
        <p className="muted">Record site constraints that drive foundation selection and earthwork design.</p>

        {busy && <div className="alert info" role="status">Saving…</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
        {notice && <div className="alert success" role="status">{notice}</div>}

        <form className="form-grid" onSubmit={submitManual}>
          <Label>
            Soil bearing capacity (kPa)
            <Input type="number" min="1" max="5000" value={form.soil_bearing_capacity_kpa} onChange={set('soil_bearing_capacity_kpa')} />
          </Label>
          <Label>
            Groundwater depth (m)
            <Input type="number" min="0" step="0.1" value={form.groundwater_depth_m} onChange={set('groundwater_depth_m')} />
          </Label>
          <Label>
            Terrain slope (°)
            <Input type="number" min="0" max="90" value={form.terrain_slope_deg} onChange={set('terrain_slope_deg')} />
          </Label>
          <Label>
            Latitude
            <Input type="number" min="-90" max="90" step="0.0001" value={form.latitude} onChange={set('latitude')} />
          </Label>
          <Label>
            Longitude
            <Input type="number" min="-180" max="180" step="0.0001" value={form.longitude} onChange={set('longitude')} />
          </Label>
          <Label>
            Soil type
            <Select value={form.soil_type} onChange={set('soil_type')}>
              <option value="clay">Clay</option>
              <option value="sand">Sand</option>
              <option value="silt">Silt</option>
              <option value="gravel">Gravel</option>
              <option value="rock">Rock</option>
            </Select>
          </Label>
          <Button type="submit" variant="primary" disabled={busy}>Record Reading</Button>
        </form>

        <hr className="divider" />
        <h3>Seismic &amp; Wind (SBC 301)</h3>
        <p className="muted small">Lateral-load parameters. Defaults apply for Saudi Arabia when blank.</p>
        <form className="form-grid" onSubmit={submitManual}>
          <Label>
            Ss (short-period, g)
            <Input type="number" min="0" max="3" step="0.01" value={form.ss_mps2} onChange={set('ss_mps2')} placeholder="0.35" />
          </Label>
          <Label>
            S1 (1-sec, g)
            <Input type="number" min="0" max="2" step="0.01" value={form.s1_mps2} onChange={set('s1_mps2')} placeholder="0.12" />
          </Label>
          <Label>
            Site class
            <Select value={form.site_class} onChange={set('site_class')}>
              <option value="A">A — Hard rock</option>
              <option value="B">B — Rock</option>
              <option value="C">C — Very dense soil</option>
              <option value="D">D — Stiff soil (default)</option>
              <option value="E">E — Soft soil</option>
              <option value="F">F — Requires site study</option>
            </Select>
          </Label>
          <Label>
            R factor (response mod.)
            <Input type="number" min="1" max="8" step="0.5" value={form.r_factor} onChange={set('r_factor')} placeholder="5.0" />
          </Label>
          <Label>
            Basic wind speed (m/s)
            <Input type="number" min="0" max="100" step="1" value={form.basic_wind_speed_mps} onChange={set('basic_wind_speed_mps')} placeholder="32" />
          </Label>
          <Label>
            Wind exposure
            <Select value={form.wind_exposure} onChange={set('wind_exposure')}>
              <option value="B">B — Suburban/urban</option>
              <option value="C">C — Open terrain</option>
              <option value="D">D — Flat, unobstructed</option>
            </Select>
          </Label>
        </form>

        <hr className="divider" />
        <h3>Import geotechnical report</h3>
        <p className="muted small">PDF report, topographic CSV, contour DXF, or LAS point cloud.</p>
        <div className="inline-controls">
          <Input
            type="file"
            accept=".pdf,.csv,.dxf,.las,.laz"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            aria-label="Choose geotechnical file"
          />
          <Button variant="primary" onClick={submitFile} disabled={busy || !file}>
            Upload &amp; Import
          </Button>
        </div>
      </Card>

      <Card className="span-2">
        <CardHeader>
          <CardTitle>Survey Summary</CardTitle>
          {summary?.entries ? <Badge variant="default">{summary.entries} readout(s)</Badge> : null}
        </CardHeader>
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
        <div className="summary-grid" style={{ marginTop: 12 }}>
          <div className="stat">
            <span className="stat-label">Ss / S1</span>
            <strong>{summary?.ss_mps2 || '—'} / {summary?.s1_mps2 || '—'} g</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Site class</span>
            <strong>{summary?.site_class || 'D'}</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Wind speed</span>
            <strong>{summary?.basic_wind_speed_mps || '—'} m/s</strong>
          </div>
          <div className="stat">
            <span className="stat-label">Exposure</span>
            <strong>{summary?.wind_exposure || 'B'}</strong>
          </div>
        </div>
        <p className="muted small" style={{ marginTop: 12 }}>
          {summary?.message || 'No survey data yet — record site inputs on the left.'}
        </p>
      </Card>
    </div>
  )
}