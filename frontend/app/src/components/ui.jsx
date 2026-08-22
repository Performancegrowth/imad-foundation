// Shared UI primitives for Imad workspaces — charts, progress, empty/error
// states. Pure inline-SVG so no chart library dependency is required.
import { useState } from 'react'

export function ProgressBar({ value = 0, label }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100)
  return (
    <div className="progress-block" role="status" aria-label={label || 'Progress'}>
      {label && <span className="progress-label">{label}</span>}
      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="progress-value">{pct}%</span>
    </div>
  )
}

export function StatCard({ label, value, unit, tone = 'default' }) {
  return (
    <div className={`stat tone-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong>{value}<small>{unit ? ` ${unit}` : ''}</small></strong>
    </div>
  )
}

export function EmptyState({ icon = '📐', title, hint }) {
  return (
    <div className="empty-state" role="note">
      <span className="empty-icon" aria-hidden="true">{icon}</span>
      <h4>{title}</h4>
      {hint && <p className="muted">{hint}</p>}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="alert error" role="alert">
      <strong>Error:</strong> {message}
      {onRetry && <button className="btn small" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Spinner({ label = 'Working…' }) {
  return (
    <div className="spinner-row" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  )
}

// Horizontal bar chart (single series). Colors alternate brand green/gold.
export function BarChart({ data, unit = '', height = 220, format = (v) => Number(v).toLocaleString() }) {
  if (!data?.length) return null
  const max = Math.max(...data.map((d) => d.value), 1e-9)
  return (
    <div className="bar-chart" style={{ '--chart-h': `${height}px` }} role="img"
         aria-label={`Bar chart in ${unit || 'units'}`}>
      {data.map((d, i) => (
        <div className="bar-row" key={d.label}>
          <span className="bar-label" title={d.label}>{d.label}</span>
          <div className="bar-track">
            <div className={`bar-fill ${i % 2 ? 'alt' : ''}`}
                 style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
          <span className="bar-value">{format(d.value)}{unit && ` ${unit}`}</span>
        </div>
      ))}
    </div>
  )
}

// Donut chart for share-of-total breakdowns.
export function DonutChart({ data, size = 180 }) {
  const [hovered, setHovered] = useState(null)
  const palette = ['#0A5C36', '#C9A227', '#1B7A47', '#8A6D1D', '#667085',
                   '#2E90FA', '#DD524C', '#12B76A']
  const total = data.reduce((s, d) => s + d.value, 0) || 1
  let acc = 0
  const radius = size / 2 - 14
  const cx = size / 2
  const cy = size / 2
  const arcs = data.map((d, i) => {
    const frac = d.value / total
    const a0 = acc * 2 * Math.PI - Math.PI / 2
    acc += frac
    const a1 = acc * 2 * Math.PI - Math.PI / 2
    const large = frac > 0.5 ? 1 : 0
    const x0 = cx + radius * Math.cos(a0)
    const y0 = cy + radius * Math.sin(a0)
    const x1 = cx + radius * Math.cos(a1)
    const y1 = cy + radius * Math.sin(a1)
    return { d,
      path: `M ${cx} ${cy} L ${x0} ${y0} A ${radius} ${radius} 0 ${large} 1 ${x1} ${y1} Z`,
      color: palette[i % palette.length] }
  })
  return (
    <div className="donut-wrap">
      <svg width={size} height={size} role="img" aria-label="Share breakdown">
        {arcs.map((a, i) => (
          <path key={i} d={a.path} fill={a.color}
                opacity={hovered == null || hovered === i ? 1 : 0.35}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}>
            <title>{`${a.d.label}: ${(100 * a.d.value / total).toFixed(1)}%`}</title>
          </path>
        ))}
        <circle cx={cx} cy={cy} r={radius * 0.55} fill="#fff" />
        <text x={cx} y={cy - 2} textAnchor="middle" className="donut-center-num">
          {hovered != null ? `${(100 * arcs[hovered].d.value / total).toFixed(0)}%`
                           : data.length.toString()}
        </text>
        <text x={cx} y={cy + 13} textAnchor="middle" className="donut-center-cap">
          {hovered != null ? arcs[hovered].d.label : 'items'}
        </text>
      </svg>
      <ul className="legend" aria-hidden="true">
        {data.slice(0, 7).map((d, i) => (
          <li key={d.label}>
            <span className="swatch" style={{ background: palette[i % palette.length] }} />
            {d.label} · {(100 * d.value / total).toFixed(0)}%
          </li>
        ))}
      </ul>
    </div>
  )
}

// Lightweight isometric 3D thumbnail of a structural plan — pure SVG, no
// Three.js needed for option cards. Draws columns, beams and slab outline
// per storey with a slight isometric projection.
export function MiniStructure3D({ plan, height = 150, caption }) {
  const stories = Math.max(1, plan?.stories ?? 1)
  const bounds = plan?.bounds ? plan.bounds() : { min_x: 0, min_y: 0, max_x: 20, max_y: 12 }
  const w = Math.max(bounds.max_x - bounds.min_x, 1)
  const h = Math.max(bounds.max_y - bounds.min_y, 1)
  const W = 220
  const H = height
  const scale = Math.min((W - 60) / w, (H - 40) / (h + stories * 8))
  // isometric skew
  const px = (x, y, z) => [
    30 + (x - bounds.min_x) * scale + (y - bounds.min_y) * scale * 0.35,
    H - 14 - z * scale * 0.9 - (y - bounds.min_y) * scale * 0.5,
  ]
  const floors = []
  for (let s = 0; s <= stories; s += 1) {
    const z = s * 3.2
    const c = [
      px(bounds.min_x, bounds.min_y, z), px(bounds.max_x, bounds.min_y, z),
      px(bounds.max_x, bounds.max_y, z), px(bounds.min_x, bounds.max_y, z),
    ]
    floors.push(c.map((p) => p.join(',')).join(' '))
  }
  const colBoxes = (plan?.columns ?? []).slice(0, 24).map((col) => {
    const z0 = 0
    const z1 = 3.2 * stories
    const [x0, y0] = px(col.x - col.size_m / 2, col.y - col.size_m / 2, z1)
    const [x1, y1] = px(col.x + col.size_m / 2, col.y + col.size_m / 2, z0)
    return { x: x0, y: y0, w: Math.max(x1 - x0, 2), h: Math.max(y1 - y0, 2) }
  })
  const beams = (plan?.beams ?? []).slice(0, 40).map((b) => {
    const z = 3.2 * stories
    const [x0, y0] = px(b.x1, b.y1, z)
    const [x1, y1] = px(b.x2, b.y2, z)
    return { x0, y0, x1, y1 }
  })
  return (
    <figure className="mini3d">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={height} role="img"
           aria-label="Isometric structural thumbnail">
        {floors.map((pts, i) => (
          <polygon key={i} points={pts}
                   fill={i === floors.length - 1 ? 'rgba(201,162,39,0.18)' : 'rgba(10,92,54,0.06)'}
                   stroke="#0A5C36" strokeWidth="1" />
        ))}
        {beams.map((b, i) => (
          <line key={i} x1={b.x0} y1={b.y0} x2={b.x1} y2={b.y1}
                stroke="#C9A227" strokeWidth="1.4" strokeLinecap="round" />
        ))}
        {colBoxes.map((c, i) => (
          <rect key={i} x={c.x} y={c.y} width={c.w} height={c.h}
                fill="#0A5C36" opacity="0.85" rx="1" />
        ))}
      </svg>
      {caption && <figcaption className="muted small">{caption}</figcaption>}
    </figure>
  )
}
// Comparison radar (cost / carbon / flexibility / safety).
// axes: [{ name }] · series: [{ name, values: [frac per axis] }]
export function RadarChart({ axes, series, size = 240 }) {
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 36
  const n = axes.length
  const colors = ['#0A5C36', '#C9A227', '#2E90FA', '#DD524C']
  const clamp = (f) => Math.min(Math.max(f, 0.03), 1)
  const point = (i, frac) => {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2
    return `${cx + r * clamp(frac) * Math.cos(a)},${cy + r * clamp(frac) * Math.sin(a)}`
  }
  return (
    <svg width={size} height={size} role="img" aria-label="Option comparison radar">
      {[0.25, 0.5, 0.75, 1].map((g) => (
        <polygon key={g} points={axes.map((_, i) => point(i, g)).join(' ')}
                 fill="none" stroke="#E4E7EC" strokeWidth="1" />
      ))}
      {axes.map((axis, i) => (
        <g key={axis}>
          <line x1={cx} y1={cy}
                x2={point(i, 1).split(',')[0]} y2={point(i, 1).split(',')[1]}
                stroke="#E4E7EC" strokeWidth="1" />
          <text x={cx + (r + 20) * Math.cos((i / n) * 2 * Math.PI - Math.PI / 2)}
                y={cy + (r + 20) * Math.sin((i / n) * 2 * Math.PI - Math.PI / 2)}
                textAnchor="middle" dominantBaseline="middle"
                className="radar-axis-label">{axis}</text>
        </g>
      ))}
      {series.map((s, s_i) => (
        <polygon key={s.name}
                 points={s.values.map((f, i) => point(i, f)).join(' ')}
                 fill={colors[s_i % 4]} fillOpacity="0.18"
                 stroke={colors[s_i % 4]} strokeWidth="2" strokeLinejoin="round">
          <title>{s.name}</title>
        </polygon>
      ))}
    </svg>
  )
}