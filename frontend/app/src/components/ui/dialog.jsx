import { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/utils.js'

// shadcn/ui Dialog (vendored) — controlled { open, onOpenChange } + parts.
export function Dialog({ open, onOpenChange, children }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape') onOpenChange?.(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])
  if (!open) return null
  return (
    <div
      ref={ref}
      className="im-dialog-overlay"
      role="presentation"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onOpenChange?.(false) }}
    >
      <div role="dialog" aria-modal="true" className="im-dialog">
        {children}
      </div>
    </div>
  )
}
export function DialogHeader({ className, ...props }) {
  return <div className={cn('im-dialog-header', className)} {...props} />
}
export function DialogTitle({ className, ...props }) {
  return <h3 className={cn('im-dialog-title', className)} {...props} />
}
export function DialogDescription({ className, ...props }) {
  return <p className={cn('muted', className)} {...props} />
}
export function DialogContent({ className, ...props }) {
  return <div className={cn('im-dialog-body', className)} {...props} />
}
export function DialogFooter({ className, ...props }) {
  return <div className={cn('im-dialog-footer', className)} {...props} />
}

// shadcn/ui Tabs (vendored) — controlled { value, onValueChange } + parts.
export function Tabs({ value, onValueChange, className, ...props }) {
  return <div className={cn('im-tabs', className)} data-value={value} {...props} />
}
export function TabsList({ className, ...props }) {
  return <div className={cn('tabs', 'im-tabs-list', className)} role="tablist" {...props} />
}
export function TabsTrigger({ value, active, className, onClick, ...props }) {
  return (
    <button
      role="tab"
      aria-selected={!!active}
      data-value={value}
      className={cn('tab', active && 'active', className)}
      onClick={onClick}
      {...props}
    />
  )
}
export function TabsContent({ className, ...props }) {
  return <div className={cn('im-tab-panel', className)} {...props} />
}

// shadcn/ui Table (vendored) — thin wrappers over .data-table styles.
export function Table({ className, ...props }) {
  return (
    <div className="table-wrap">
      <table className={cn('data-table', className)} {...props} />
    </div>
  )
}
export function TableHeader(props) { return <thead {...props} /> }
export function TableBody(props) { return <tbody {...props} /> }
export function TableRow(props) { return <tr {...props} /> }
export function TableHead(props) { return <th {...props} /> }
export function TableCell(props) { return <td {...props} /> }

// shadcn/ui DropdownMenu (vendored) — click-to-open menu.
export function DropdownMenu({ trigger, items = [], align = 'right' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open ])
  return (
    <div ref={ref} className={cn('im-dropdown', `im-dropdown-${align}`)}>
      <span className="im-dropdown-trigger" onClick={() => setOpen((v) => !v)}>{trigger}</span>
      {open && (
        <div className="im-dropdown-menu" role="menu">
          {items.map((it) => (
            <button
              key={it.label}
              role="menuitem"
              className="im-dropdown-item"
              onClick={() => { setOpen(false); it.onSelect?.() }}
            >
              {it.icon && <span aria-hidden="true">{it.icon} </span>}{it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function useDialogState(initial = false) {
  const [open, setOpen] = useState(initial)
  return { open, setOpen }
}
