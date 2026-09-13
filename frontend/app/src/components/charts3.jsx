import { ChartShell, PALETTE } from './charts.jsx'

export function DonutChart({ data = [], category = 'value', index = 'name', title, subtitle, value }) {
  const rows = data || []
  const total = rows.reduce((s, r) => s + (Number(r[category]) || 0), 0) || 1
  let acc = 0
  const R = 70; const C = 2 * Math.PI * R
  const compact = total >= 1e6 ? `${(total / 1e6).toFixed(1)}M` : total >= 1e3 ? `${(total / 1e3).toFixed(1)}k` : String(Math.round(total))
  return (
    <ChartShell title={title} subtitle={subtitle} value={value ?? total.toLocaleString()}>
      <div className="im-donut-row">
        <svg viewBox="0 0 180 180" className="im-donut" role="img">
          {rows.map((r, i) => {
            const frac = (Number(r[category]) || 0) / total
            const el = (
              <circle
                key={i}
                cx="90" cy="90" r={R} fill="none"
                stroke={PALETTE[i % PALETTE.length]} strokeWidth="22"
                strokeDasharray={`${(frac * C).toFixed(1)} ${C.toFixed(1)}`}
                strokeDashoffset={(-acc * C).toFixed(1)}
                transform="rotate(-90 90 90)"
              />
            )
            acc += frac
            return el
          })}
          <text x="90" y="86" textAnchor="middle" className="im-donut-total">{compact}</text>
          <text x="90" y="104" textAnchor="middle" className="im-donut-sub">{category}</text>
        </svg>
        <ul className="im-legend">
          {rows.map((r, i) => (
            <li key={i}>
              <span className="swatch" style={{ background: PALETTE[i % PALETTE.length] }} />
              {String(r[index])}
              <span className="im-num im-legend-val">{(Number(r[category]) || 0).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartShell>
  )
}

export function ScatterChart({ data = [], x = 'x', y = 'y', title, subtitle, value, height = 240, color }) {
  const w = 560; const h = height
  const rows = data || []
  const xs = rows.map((d) => Number(d[x]) || 0)
  const ys = rows.map((d) => Number(d[y]) || 0)
  const x0 = Math.min(0, ...xs); const x1 = Math.max(1, ...xs)
  const y1 = Math.max(1, ...ys)
  const pts = rows.map((d, i) => ({
    i,
    cx: 26 + ((Number(d[x]) - x0) / (x1 - x0 || 1)) * (w - 52),
    cy: h - 26 - (Number(d[y]) / y1) * (h - 52),
    d,
  }))
  return (
    <ChartShell title={title} subtitle={subtitle} value={value}>
      <svg viewBox={`0 0 ${w} ${h}`} className="im-svg" role="img">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line key={f} x1="26" x2={w - 10} y1={h - 26 - f * (h - 52)} y2={h - 26 - f * (h - 52)} className="im-grid" />
        ))}
        <line x1="26" x2={w - 10} y1={h - 26} y2={h - 26} className="im-grid" />
        <line x1="26" x2="26" y1="10" y2={h - 26} className="im-grid" />
        {pts.map((p) => (
          <circle key={p.i} cx={p.cx} cy={p.cy} r="5" fill={color || PALETTE[0]} opacity="0.8">
            <title>{`${x}=${p.d[x]}, ${y}=${p.d[y]}`}</title>
          </circle>
        ))}
      </svg>
      <div className="muted small im-chart-foot">{x} → · {y} ↑ · {pts.length} points</div>
    </ChartShell>
  )
}

export function ProgressBar({ value = 0, max = 100, label, color }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / (Number(max) || 100)) * 100))
  const barColor = color || (pct >= 80 ? '#0A5C36' : pct >= 50 ? '#C9A227' : '#B42318')
  return (
    <div className="im-progress">
      {label && <div className="im-progress-label"><span>{label}</span><span className="im-num">{pct.toFixed(0)}%</span></div>}
      <div className="im-progress-track" role="progressbar" aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100">
        <div className="im-progress-fill" style={{ width: `${pct}%`, background: barColor }} />
      </div>
    </div>
  )
}

export function Metric({ label, value, unit, delta, hint }) {
  return (
    <div className="stat im-metric">
      <span className="stat-label">{label}</span>
      <strong className="im-num">{value}{unit && <span className="im-unit"> {unit}</span>}</strong>
      {delta && <span className="im-delta">{delta}</span>}
      {hint && <span className="muted small">{hint}</span>}
    </div>
  )
}
