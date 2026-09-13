import { useMemo } from 'react'
import { ChartShell, AxisLabels, legendCats, niceCeil, PALETTE } from './charts.jsx'

export function BarChart({ data = [], categories, index = 'name', colors, title, subtitle, value, height = 220, layout = 'vertical' }) {
  const cats = useMemo(() => legendCats(data, categories, index), [data, categories, index])
  const sliced = (data || []).slice(0, 24)
  const max = useMemo(() => niceCeil(Math.max(0, ...sliced.flatMap((r) => cats.map((c) => Number(r[c]) || 0)))), [sliced, cats])
  if (layout === 'horizontal') {
    return (
      <ChartShell title={title} subtitle={subtitle} value={value}>
        <div className="im-bars-h">
          {sliced.map((r, i) => {
            const v = Number(r[cats[0]]) || 0
            return (
              <div className="im-bar-h-row" key={i}>
                <span className="im-bar-h-label" title={String(r[index])}>{String(r[index])}</span>
                <div className="im-bar-h-track">
                  <div className="im-bar-h-fill" style={{ width: `${Math.min(100, (v / max) * 100)}%`, background: colors?.[0] || PALETTE[0] }} />
                </div>
                <span className="im-num im-bar-h-val">{v.toLocaleString()}</span>
              </div>
            )
          })}
        </div>
      </ChartShell>
    )
  }
  return (
    <ChartShell title={title} subtitle={subtitle} value={value}>
      <div className="im-bars" style={{ height }}>
        {sliced.map((r, i) => (
          <div className="im-bar-group" key={i} title={`${r[index]}: ${cats.map((c) => `${c}=${r[c]}`).join(', ')}`}>
            <div className="im-bar-stack">
              {cats.map((c, j) => {
                const v = Number(r[c]) || 0
                return <div key={c} className="im-bar-seg" style={{ height: `${Math.max(0, (v / max) * 100)}%`, background: (colors && colors[j]) || PALETTE[j % PALETTE.length] }} />
              })}
            </div>
          </div>
        ))}
      </div>
      <AxisLabels labels={sliced.map((r) => String(r[index]))} />
    </ChartShell>
  )
}

export function LineChart({ data = [], categories, index = 'name', title, subtitle, value, height = 220 }) {
  const cats = legendCats(data, categories, index)
  const rows = data || []
  const w = 560; const h = height
  const max = niceCeil(Math.max(0, ...rows.flatMap((r) => cats.map((c) => Number(r[c]) || 0))))
  const lineFor = (c) => rows.map((r, i) => {
    const px = 26 + (i / Math.max(1, (rows.length - 1))) * (w - 52)
    const py = h - 26 - ((Number(r[c]) || 0) / max) * (h - 52)
    return `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`
  }).join(' ')
  return (
    <ChartShell title={title} subtitle={subtitle} value={value}>
      <svg viewBox={`0 0 ${w} ${h}`} className="im-svg" role="img">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1="26" x2={w - 10} y1={h - 26 - f * (h - 52)} y2={h - 26 - f * (h - 52)} className="im-grid" />
        ))}
        {cats.map((c, j) => <path key={c} d={lineFor(c)} fill="none" stroke={PALETTE[j % PALETTE.length]} strokeWidth="2.2" />)}
        {cats.map((c, j) => rows.map((r, i) => {
          const px = 26 + (i / Math.max(1, (rows.length - 1))) * (w - 52)
          const py = h - 26 - ((Number(r[c]) || 0) / max) * (h - 52)
          return <circle key={`${c}${i}`} cx={px} cy={py} r="3" fill={PALETTE[j % PALETTE.length]} />
        }))}
      </svg>
      <AxisLabels labels={rows.map((r) => String(r[index]))} />
    </ChartShell>
  )
}

export function AreaChart({ data = [], categories, index = 'name', title, subtitle, value, height = 220 }) {
  const cats = legendCats(data, categories, index)
  const rows = data || []
  const w = 560; const h = height
  const max = niceCeil(Math.max(0, ...rows.flatMap((r) => cats.map((c) => Number(r[c]) || 0))))
  const lineFor = (c) => rows.map((r, i) => {
    const px = 26 + (i / Math.max(1, (rows.length - 1))) * (w - 52)
    const py = h - 26 - ((Number(r[c]) || 0) / max) * (h - 52)
    return `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`
  }).join(' ')
  const lastX = 26 + (w - 52); const base = h - 26
  return (
    <ChartShell title={title} subtitle={subtitle} value={value}>
      <svg viewBox={`0 0 ${w} ${h}`} className="im-svg" role="img">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1="26" x2={w - 10} y1={h - 26 - f * (h - 52)} y2={h - 26 - f * (h - 52)} className="im-grid" />
        ))}
        {cats.map((c, j) => (
          <g key={c}>
            <path d={`${lineFor(c)} L${lastX},${base} L26,${base} Z`} fill={PALETTE[j % PALETTE.length]} opacity="0.18" />
            <path d={lineFor(c)} fill="none" stroke={PALETTE[j % PALETTE.length]} strokeWidth="2.2" />
          </g>
        ))}
      </svg>
      <AxisLabels labels={rows.map((r) => String(r[index]))} />
    </ChartShell>
  )
}
