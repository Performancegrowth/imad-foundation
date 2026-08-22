import { useEffect, useRef } from 'react'
import { drawPlan } from '../planUtil.js'

/**
 * Reusable 2D engineering plan viewer. Renders a PlanData document on an
 * HTML5 canvas using the shared drawing pipeline in planUtil.js.
 */
export default function PlanViewer({ plan, height = 480 }) {
  const canvasRef = useRef(null)

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
    drawPlan(ctx, plan || {}, width, drawHeight)
  }, [plan, height])

  return (
    <div className="viewer" style={{ height }}>
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
      </div>
    </div>
  )
}