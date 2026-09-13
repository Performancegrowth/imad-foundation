// shadcn/ui Command palette (vendored) — Cmd+K / Ctrl+K navigation.
// Items: every sidebar route + quick actions (New Plan, Run Analysis,
// Generate BOQ). Styled to the IMAD theme; no cmdk dependency required.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { readStoredProject } from '../useProjectId.jsx'

function withPid(to, pid) {
  if (!to.includes(':projectId')) return to
  if (pid == null) return '/create-plan'
  return to.replace(':projectId', String(pid))
}

export function commandItems(pid) {
  return [
    { group: 'Workspaces', label: 'Home', hint: 'Landing', to: '/welcome' },
    { group: 'Workspaces', label: 'Create Plan', hint: 'New plan', to: '/create-plan' },
    { group: 'Workspaces', label: 'CAD Import', hint: 'DXF / IFC / image', to: '/cad' },
    { group: 'Workspaces', label: 'Generate Designs', hint: 'NSGA-II', to: '/generative' },
    { group: 'Project', label: 'Survey', to: withPid('/project/:projectId/survey', pid) },
    { group: 'Project', label: 'Analyze', hint: 'Run analysis', to: withPid('/project/:projectId/analyze', pid) },
    { group: 'Project', label: 'BOQ & BBS', hint: 'Generate BOQ', to: withPid('/project/:projectId/boq', pid) },
    { group: 'Project', label: 'Sustainability', to: withPid('/project/:projectId/carbon', pid) },
    { group: 'Project', label: 'Validation', to: withPid('/project/:projectId/validation', pid) },
    { group: 'Project', label: 'Building 3D', to: withPid('/project/:projectId/3d', pid) },
    { group: 'Project', label: 'Collaboration', to: withPid('/project/:projectId/collaboration', pid) },
    { group: 'Project', label: 'Ecosystem', to: withPid('/project/:projectId/ecosystem', pid) },
    { group: 'Project', label: 'Governance', to: withPid('/project/:projectId/governance', pid) },
    { group: 'Project', label: 'Review & Sign', to: withPid('/project/:projectId/review', pid) },
    { group: 'Project', label: 'Admin', to: withPid('/project/:projectId/admin', pid) },
    { group: 'Site', label: 'Pricing', to: '/pricing' },
    { group: 'Site', label: 'Blog', to: '/blog' },
    { group: 'Site', label: 'FAQ', to: '/faq' },
    { group: 'Site', label: 'Case Studies', to: '/case-studies' },
    { group: 'Actions', label: 'New Plan', hint: 'Create plan', to: '/create-plan' },
    { group: 'Actions', label: 'Run Analysis', hint: 'Analyze', to: withPid('/project/:projectId/analyze', pid) },
    { group: 'Actions', label: 'Generate BOQ', hint: 'BOQ', to: withPid('/project/:projectId/boq', pid) },
  ]
}

export function useCommandPalette() {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  return { open, setOpen }
}

export function CommandPalette({ open, onOpenChange }) {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const pid = (() => { try { return readStoredProject() } catch { return null } })()
  const items = useMemo(() => commandItems(pid), [pid])
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return items
    return items.filter((i) => `${i.label} ${i.hint || ''} ${i.group}`.toLowerCase().includes(needle))
  }, [items, q])

  useEffect(() => { if (open) { setQ(''); setActive(0) } }, [open ])
  useEffect(() => { setActive(0) }, [q])

  const go = useCallback((to) => {
    onOpenChange?.(false)
    if (to) navigate(to)
  }, [navigate, onOpenChange])

  if (!open) return null
  return (
    <div className="im-cmdk-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onOpenChange?.(false) }}>
      <div className="im-cmdk" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="im-cmdk-input-row">
          <span aria-hidden="true">⌘</span>
          <input
            autoFocus
            className="im-cmdk-input"
            placeholder="Type a command or search workspaces…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, filtered.length - 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
              if (e.key === 'Enter' && filtered[active]) go(filtered[active].to)
            }}
          />
          <kbd className="im-kbd">esc</kbd>
        </div>
        <div className="im-cmdk-list" role="listbox">
          {filtered.length === 0 && <div className="im-cmdk-empty">No matching commands.</div>}
          {filtered.map((it, i) => (
            <button
              key={`${it.group}-${it.label}`}
              role="option"
              aria-selected={i === active}
              className={`im-cmdk-item${i === active ? ' active' : ''}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(it.to)}
            >
              <span className="im-cmdk-group">{it.group}</span>
              <span className="im-cmdk-label">{it.label}</span>
              {it.hint && <span className="im-cmdk-hint">{it.hint}</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
