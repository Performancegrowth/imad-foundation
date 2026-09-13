// Tremor-style charts (vendored, zero-dependency SVG).
// Same component names/props as @tremor/react so views read like Tremor code:
//   <BarChart data category index colors /> <LineChart ... />
//   <AreaChart ... /> <DonutChart ... /> <ScatterChart data x y />
//   <ProgressBar value max />  <Metric label value unit />
// Numbers render in tabular monospace per the IMAD engineering aesthetic.
import { useMemo } from 'react'

export const PALETTE = ['#0A5C36', '#C9A227', '#0E7A4C', '#7FB3D5', '#B42318', '#5B6472', '#E8B93C']

export function niceCeil(v) {
  if (!v || v <= 0) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  const n = v / p
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10
  return m * p
}

export function ChartShell({ title, subtitle, value, right, children }) {
  return (
    <div className="im-chart">
      {(title || value) && (
        <div className="im-chart-head">
          <div>
            {title && <div className="im-chart-title">{title}</div>}
            {subtitle && <div className="muted small">{subtitle}</div>}
          </div>
          <div className="im-chart-side">
            {value != null && <span className="im-num im-chart-value">{value}</span>}
            {right}
          </div>
        </div>
      )}
      {children}
    </div>
  )
}

export function AxisLabels({ labels }) {
  return (
    <div className="im-axis">
      {labels.map((l, i) => <span key={i} className="im-axis-label">{l}</span>)}
    </div>
  )
}

export function legendCats(data, categories, index) {
  if (categories?.length) return categories
  const keys = Object.keys(data?.[0] || {})
  return keys.filter((k) => k !== index)
}
