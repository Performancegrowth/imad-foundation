import { useCallback, useRef, useState } from 'react'
import { api } from '../api.js'
import PlanViewer from '../components/PlanViewer.jsx'

const STATUS_IDLE = 'idle'
const STATUS_UPLOADING = 'uploading'
const STATUS_PROCESSING = 'processing'
const STATUS_READY = 'ready'
const STATUS_ERROR = 'error'

export default function CadWorkspace() {
  const [status, setStatus] = useState(STATUS_IDLE)
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState(null)
  const [fileInfo, setFileInfo] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const fileInputRef = useRef(null)

  const onFileSelected = useCallback(async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setPlan(null)
    setFileInfo(null)
    setStatus(STATUS_UPLOADING)
    setUploading(true)
    try {
      // Simulated progress while real upload runs
      const timer = setInterval(() => setProgress((p) => Math.min(p + 12, 90)), 120)
      const uploadMeta = await api.uploadFile(file)
      clearInterval(timer)
      setProgress(100)
      setFileInfo(uploadMeta)
      setStatus(STATUS_PROCESSING)
      setProgress(10)
      const result = await api.processCad(uploadMeta.file_id)
      setPlan(result.plan)
      setProgress(100)
      setStatus(STATUS_READY)
    } catch (err) {
      setError(err.message || 'Processing failed')
      setStatus(STATUS_ERROR)
    } finally {
      setUploading(false)
    }
  }, [])

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>CAD &amp; Image Import</h2>
        <p className="muted">
          Upload a structural DXF, or a scanned sheet (PNG/JPG/PDF) and Imad will
          extract walls, columns, beams and grid lines.
        </p>

        <div className="dropzone">
          <input
            ref={fileInputRef}
            type="file"
            accept=".dxf,.dwg,.ifc,.obj,.png,.jpg,.jpeg,.tiff,.pdf"
            onChange={onFileSelected}
            id="cad-file"
            className="sr-only"
            aria-label="Choose a design file"
          />
          <label htmlFor="cad-file" className="dropzone-label">
            <span className="dropzone-icon" aria-hidden="true">├</span>
            <strong>Click to choose or drop a design file</strong>
            <span className="muted">DXF, DWG, IFC, PNG, JPG, TIFF, PDF · up to 128 MB</span>
          </label>
        </div>

        {(status === STATUS_UPLOADING || status === STATUS_PROCESSING) && (
          <div className="progress-block" role="status">
            <div className="progress-label">{status === STATUS_UPLOADING ? 'Uploading…' : 'Processing & extracting structure…'}</div>
            <div className="progress-track">
              <div className="progress-bar" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {fileInfo && status === STATUS_PROCESSING && (
          <p className="muted">Analysing {fileInfo.original_name} ({fileInfo.size_bytes} bytes)…</p>
        )}

        {status === STATUS_ERROR && (
          <div className="alert error" role="alert">
            <strong>Processing error:</strong> {error}
            <button className="link" onClick={() => setStatus(STATUS_IDLE)}>Dismiss</button>
          </div>
        )}
      </section>

      <section className="card span-2">
        <div className="card-header">
          <h3>Extracted Structure</h3>
          {status === STATUS_READY && (
            <span className="badge success">
              {plan?.walls?.length} walls · {plan?.columns?.length} columns · {plan?.beams?.length} beams
            </span>
          )}
        </div>
        {status === STATUS_READY ? (
          <PlanViewer plan={plan} />
        ) : (
          <div className="empty">
            <span className="empty-icon" aria-hidden="true">✥</span>
            <p>No structure extracted yet. Upload a file to begin.</p>
          </div>
        )}
      </section>
    </div>
  )
}