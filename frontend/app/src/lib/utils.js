// shadcn-style classnames helper (vendored: no clsx/tailwind-merge installed).
// Accepts strings, arrays, and { className: condition } objects.
export function cn(...parts) {
  const out = []
  const push = (v) => {
    if (!v) return
    if (typeof v === 'string') { if (v.trim()) out.push(v.trim()) }
    else if (Array.isArray(v)) v.forEach(push)
    else if (typeof v === 'object') {
      Object.entries(v).forEach(([k, cond]) => { if (cond && k.trim()) out.push(k.trim()) })
    }
  }
  parts.forEach(push)
  return out.join(' ')
}

export const IMAD = {
  green: '#0A5C36',
  greenDark: '#074428',
  gold: '#C9A227',
  ink: '#111827',
}
