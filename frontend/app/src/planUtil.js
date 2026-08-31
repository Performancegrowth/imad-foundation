// Shared rendering helpers that draw a PlanData document on a 2D canvas.
// Colours follow the Imad design system (green walls, gold beams, ink columns).
export const COLORS = {
  grid: '#CBD5DC',
  wall: '#0A5C36',
  beam: '#C9A227',
  column: '#111827',
  columnFill: '#E8EEF2',
  annotation: '#5B6472',
  room: 'rgba(127, 179, 213, 0.16)',
  roomStroke: '#4A78A0',
  roomLabel: '#41576B',
}

// Collect the distinct storey levels present in the plan geometry (IFC/BIM
// plans are multi-storey; every element carries a `level` attribute).
export function getPlanLevels(plan) {
  const levels = new Set()
  ;(plan.walls || []).forEach((w) => levels.add(w.level ?? 0))
  ;(plan.columns || []).forEach((c) => levels.add(c.level ?? 0))
  ;(plan.beams || []).forEach((b) => levels.add(b.level ?? 0))
  return [...levels].sort((a, b) => a - b)
}

function atLevel(el, level) {
  if (level === null || level === undefined) return true
  return (el.level ?? 0) === level
}

// Area-weighted centroid of a closed polygon (points: [{x, y}, ...]).
function polygonCentroid(points) {
  let a = 0
  let cx = 0
  let cy = 0
  for (let i = 0; i < points.length - 1; i++) {
    const p = points[i]
    const q = points[i + 1]
    const cross = p.x * q.y - q.x * p.y
    a += cross
    cx += (p.x + q.x) * cross
    cy += (p.y + q.y) * cross
  }
  if (Math.abs(a) < 1e-9) return null
  a *= 0.5
  return { x: cx / (6 * a), y: cy / (6 * a) }
}

export function getPlanBounds(plan) {
  const xs = [0]
  const ys = [0]
  ;(plan.walls || []).forEach((w) => {
    xs.push(w.x1, w.x2)
    ys.push(w.y1, w.y2)
  })
  ;(plan.beams || []).forEach((b) => {
    xs.push(b.x1, b.x2)
    ys.push(b.y1, b.y2)
  })
  ;(plan.columns || []).forEach((c) => {
    xs.push(c.cx)
    ys.push(c.cy)
  })
  let minX = Math.min(...xs)
  let maxX = Math.max(...xs)
  let minY = Math.min(...ys)
  let maxY = Math.max(...ys)
  if (maxX - minX < 1e-6) {
    maxX = minX + 1
  }
  if (maxY - minY < 1e-6) {
    maxY = minY + 1
  }
  return { minX, minY, maxX, maxY }
}

// transform world (m) coords -> canvas px with padding, preserving aspect.
export function fitTransform(bounds, width, height, pad = 40) {
  const usableW = Math.max(width - pad * 2, 10)
  const usableH = Math.max(height - pad * 2, 10)
  const scale = Math.min(usableW / (bounds.maxX - bounds.minX), usableH / (bounds.maxY - bounds.minY))
  const offX = (width - (bounds.maxX - bounds.minX) * scale) / 2 - bounds.minX * scale
  const offY = (height - (bounds.maxY - bounds.minY) * scale) / 2 - bounds.minY * scale
  return { scale, offX, offY }
}

export function drawPlan(ctx, plan, width, height, options = {}) {
  const level = options.level ?? null
  const walls = (plan.walls || []).filter((w) => atLevel(w, level))
  const beams = (plan.beams || []).filter((b) => atLevel(b, level))
  const columns = (plan.columns || []).filter((c) => atLevel(c, level))
  const rooms = (plan.rooms || []).filter((r) => atLevel(r, level))

  ctx.clearRect(0, 0, width, height)
  const bounds = getPlanBounds(plan)
  const { scale, offX, offY } = fitTransform(bounds, width, height)
  const px = (x) => x * scale + offX
  const py = (y) => y * scale + offY

  // Grid lines (dashed)
  ctx.save()
  ctx.strokeStyle = COLORS.grid
  ctx.setLineDash([4, 4])
  ctx.lineWidth = 1
  ;(plan.grids || []).forEach((g) => {
    if (g.orientation === 'vertical') {
      const x = px(g.position)
      ctx.beginPath()
      ctx.moveTo(x, py(bounds.minY))
      ctx.lineTo(x, py(bounds.maxY))
      ctx.stroke()
    } else {
      const y = py(g.position)
      ctx.beginPath()
      ctx.moveTo(px(bounds.minX), y)
      ctx.lineTo(px(bounds.maxX), y)
      ctx.stroke()
    }
  })
  ctx.restore()

  // Rooms — translucent fills + area labels (populated for IFC/BIM plans
  // by the Shapely room-polygonisation step in the geometry service).
  if (rooms.length) {
    ctx.save()
    rooms.forEach((r) => {
      const pts = (r.boundary || []).map((p) => ({ x: p.x, y: p.y }))
      if (pts.length < 3) return
      ctx.beginPath()
      pts.forEach((p, idx) => {
        const X = px(p.x)
        const Y = py(p.y)
        if (idx === 0) ctx.moveTo(X, Y)
        else ctx.lineTo(X, Y)
      })
      ctx.closePath()
      ctx.fillStyle = COLORS.room
      ctx.fill()
      ctx.strokeStyle = COLORS.roomStroke
      ctx.lineWidth = 1
      ctx.stroke()
      if (r.area_m2) {
        const c = polygonCentroid(pts)
        if (c) {
          ctx.fillStyle = COLORS.roomLabel
          ctx.font = '11px Inter, sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(`${r.area_m2.toFixed(1)} m²`, px(c.x), py(c.y))
        }
      }
    })
    ctx.restore()
  }

  // Beams — gold lines
  ctx.save()
  ctx.strokeStyle = COLORS.beam
  ctx.lineWidth = 5
  ctx.lineCap = 'round'
  beams.forEach((b) => {
    ctx.beginPath()
    ctx.moveTo(px(b.x1), py(b.y1))
    ctx.lineTo(px(b.x2), py(b.y2))
    ctx.stroke()
  })
  ctx.restore()

  // Walls — green thick lines
  ctx.save()
  ctx.strokeStyle = COLORS.wall
  ctx.lineWidth = 8
  ctx.lineCap = 'round'
  walls.forEach((w) => {
    ctx.beginPath()
    ctx.moveTo(px(w.x1), py(w.y1))
    ctx.lineTo(px(w.x2), py(w.y2))
    ctx.stroke()
  })
  ctx.restore()

  // Columns — filled squares
  ctx.save()
  columns.forEach((c) => {
    const r = Math.max((c.size_m || 0.3) * scale * 0.5, 4)
    const x = px(c.cx)
    const y = py(c.cy)
    ctx.fillStyle = COLORS.columnFill
    ctx.strokeStyle = COLORS.column
    ctx.lineWidth = 2
    ctx.fillRect(x - r, y - r, r * 2, r * 2)
    ctx.strokeRect(x - r, y - r, r * 2, r * 2)
  })
  ctx.restore()

  // Empty-state overlay when nothing meaningful is drawn
  if (!walls.length && !columns.length && !beams.length) {
    ctx.fillStyle = '#9AA4B0'
    ctx.font = '13px Inter, sans-serif'
    ctx.textAlign = 'center'
    const msg = level === null
      ? 'No geometry — run a process or generate a plan'
      : `No geometry on storey ${level}`
    ctx.fillText(msg, width / 2, height / 2)
  }
}