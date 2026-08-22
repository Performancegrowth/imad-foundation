import { useCallback, useEffect, useState } from 'react'
import { addComment, createTask, getComments, getTasks, updateTask } from '../platformApi.js'
import { EmptyState, Spinner } from '../components/ui.jsx'

const fmt = (s) => String(s ?? '').replace('T', ' ').slice(0, 16)
const COLS = [
  { key: 'todo', label: 'To Do', icon: '▫' },
  { key: 'in_progress', label: 'In Progress', icon: '…' },
  { key: 'done', label: 'Done', icon: '✓' },
]
const NEXT = { todo: 'in_progress', in_progress: 'done', done: 'done' }

export default function CollaborationWorkspace() {
  const projectId = 1
  const [comments, setComments] = useState([])
  const [tasks, setTasks] = useState([])
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([getComments(projectId), getTasks(projectId)])
      .then(([c, t]) => { setComments(Array.isArray(c) ? c : c?.comments ?? []); setTasks(Array.isArray(t) ? t : t?.tasks ?? []); setErr(null) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [projectId])
  useEffect(() => { load() }, [load])

  const submitComment = async () => {
    if (!text.trim()) return
    try { await addComment({ project_id: projectId, text: text.trim(), author: 'Demo User' }); setText(''); load() } catch (e) { setErr(e.message) }
  }
  const submitTask = async () => {
    if (!title.trim()) return
    try { await createTask({ project_id: projectId, title: title.trim(), assignee: 'Demo User' }); setTitle(''); load() } catch (e) { setErr(e.message) }
  }
  const move = async (t) => {
    const state = NEXT[t.state || 'todo']
    if (state === (t.state || 'todo')) return
    try { await updateTask(t.id, state); load() } catch (e) { setErr(e.message) }
  }

  const byCol = (key) => tasks.filter((t) => t.state === key || (key === 'todo' && !t.state))

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <h2>Collaboration &amp; Task Board</h2>
        <p className="muted small">BIM coordination, comments and a lightweight kanban for project #{projectId}.</p>
        {err && <div className="alert error" role="alert"><strong>Error:</strong> {err}</div>}
      </section>

      <section className="card">
        <div className="card-header">
          <h3>Comments</h3>
          <span className="badge">{comments.length}</span>
        </div>
        <div aria-live="polite">
          {loading ? <Spinner label="Loading comments…" /> : comments.length === 0
            ? <EmptyState icon="💬" title="No comments" hint="Leave feedback on the shared model." />
            : comments.map((c, i) => (
              <div className="comment-item" key={c.id ?? i}>
                <p className="small">{c.text ?? c.body}</p>
                <div className="comment-meta">{c.author ?? c.user ?? '—'} · {fmt(c.created_at ?? c.timestamp)}</div>
              </div>
            ))}
        </div>
        <div className="save-row">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a comment…" aria-label="Comment text" />
          <button className="btn primary" onClick={submitComment}>Post</button>
        </div>
      </section>

      <section className="card">
        <div className="card-header"><h3>Tasks (Kanban)</h3><span className="badge">{tasks.length}</span></div>
        <div className="save-row">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task title…" aria-label="Task title" />
          <button className="btn primary" onClick={submitTask}>Add</button>
        </div>
        <div className="kanban">
          {COLS.map((col) => (
            <div className="kanban-col" key={col.key}>
              <div className="kanban-head">{col.icon} <span>{col.label}</span> <span className="badge">{byCol(col.key).length}</span></div>
              {loading ? <Spinner label="…" /> : byCol(col.key).length === 0
                ? <div className="kanban-card muted small">— none —</div>
                : byCol(col.key).map((t) => (
                  <div className="kanban-card" key={t.id} role="button" tabIndex="0" onClick={() => move(t)}
                       onKeyDown={(e) => { if (e.key === 'Enter') move(t) }} title="Click to advance status">
                    <strong>{t.title}</strong>
                    <span className="muted small">{t.assignee ?? '—'}</span>
                  </div>
                ))}
            </div>
          ))}
        </div>
        <p className="muted small">Click a card to advance it to the next state.</p>
      </section>
    </div>
  )
}