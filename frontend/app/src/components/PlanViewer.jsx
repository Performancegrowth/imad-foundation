import { useEffect, useMemo, useRef, useState } from 'react'
import { drawPlan, getPlanLevels } from '../planUtil.js'

/**
 * Reusable 2D engineering plan viewer. Renders a PlanData document on an
 * HTML5 canvas using the shared drawing pipeline in planUtil.js.
 *
 * IFC/BIM-aware: multi-storey plans get a storey filter, polygonised rooms
 * are rendered as translucent fills with area labels, and the legend reports
 * the floor footprint computed by the backend geometry service.
 */
export default function PlanViewer({ plan, height = 480 }) {
  const canvasRef = useRef(null)
  const levels = useMemo(() => getPlanLevels(plan || {}), [plan])
  const [level, setLevel] = useState(null)

  // Reset the storey filter whenever a new plan document arrives.
  useEffect(() => {
    setLevel(null)
  }, [plan])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const width = canvas.clientWidth
    const drawHeight = height
    canvas.width = width * dpr
    canvas.height = drawHeight * dpr
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)
    drawPlan(ctx, plan || {}, width, drawHeight, { level })
  }, [plan, height, level])

  const rooms = plan?.rooms || []
  const geometry = plan?.original?.geometry || {}
  const isBim = plan?.source === 'ifc'
  const floorArea = geometry.floor_area_m2

  return (
    <div className="viewer" style={{ height }}>
      {(levels.length > 1 || isBim) && (
        <div className="viewer-toolbar" role="toolbar" aria-label="Storey filter">
          {isBim && <span className="chip chip-static">BIM · IFC</span>}
          {levels.length > 1 && (
            <>
              <button
                type="button"
                className={level === null ? 'chip active' : 'chip'}
                onClick={() => setLevel(null)}
              >
                All storeys ({plan?.stories || levels.length})
              </button>
              {levels.map((l) => (
                <button
                  key={l}
                  type="button"
                  className={level === l ? 'chip active' : 'chip'}
                  onClick={() => setLevel(l)}
                >
                  Storey {l}
                </button>
              ))}
            </>
          )}
        </div>
      )}
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height }}
        role="img"
        aria-label="Extracted structural plan drawing"
      />
      <div className="viewer-legend">
        <span><i className="swatch wall" /> Walls</span>
        <span><i className="swatch beam" /> Beams</span>
        <span><i className="swatch column" /> Columns</span>
        {rooms.length > 0 && (
          <span><i className="swatch room" /> Rooms ({rooms.length})</span>
        )}
        {typeof floorArea === 'number' && floorArea > 0 && (
          <span className="legend-stat">Floor {floorArea.toFixed(1)} m²</span>
        )}
      </div>
    </div>
  )
}