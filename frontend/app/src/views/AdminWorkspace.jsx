import { useEffect, useState } from 'react'
import { getAnalytics, getCurrentSubscription, getPlans } from '../platformApi.js'
import { BarChart, EmptyState, Spinner, StatCard } from '../components/ui.jsx'

export default function AdminWorkspace() {
  const [analytics, setAnalytics] = useState(null)
  const [plans, setPlans] = useState([])
  const [subscription, setSubscription] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([getAnalytics(), getPlans(), getCurrentSubscription()])
      .then(([a, p, s]) => { setAnalytics(a); setPlans(Array.isArray(p) ? p : p?.plans ?? []); setSubscription(s); setErr(null) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  const an = analytics ?? {}
  const metric = (keys, fb) => keys.reduce((v, k) => v ?? an[k], null) ?? fb
  const chartData = Array.isArray(an.projects_by_plan)
    ? an.projects_by_plan.map((p) => ({ label: p.plan, value: p.count }))
    : plans.map((p) => ({ label: p.name ?? p.plan, value: Number(p.projects ?? 0) }))

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header"><h2>Admin Dashboard</h2><span className="status-chip">Enterprise</span></div>
        <p className="muted small">Platform analytics, subscription plans, users and system health.</p>
        {err && <div className="alert error" role="alert"><strong>Error:</strong> {err}</div>}
      </section>

      <section className="card span-2">
        <h3>Analytics Overview</h3>
        {loading ? <Spinner label="Loading analytics…" /> : (
          <>
            <div className="summary-grid four">
              <StatCard label="Total projects" value={metric(['total_projects', 'projects'], 0)} />
              <StatCard label="Total users" value={metric(['total_users', 'users_count'], 0)} />
              <StatCard label="Revenue" unit="SAR" value={metric(['total_revenue', 'revenue'], '—')} />
              <StatCard label="Active subscriptions" value={metric(['active_subscriptions', 'subscriptions'], 0)} />
            </div>
            <BarChart data={chartData} height={180} format={(v) => Number(v).toLocaleString()} />
          </>
        )}
      </section>

      <section className="card">
        <h3>Subscription Plans</h3>
        {loading ? <Spinner label="Loading plans…" /> : plans.length === 0
          ? <EmptyState icon="💳" title="No plans" hint="Plans defined by the billing service appear here." />
          : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Plan</th><th>Price</th><th>Features</th></tr></thead>
                <tbody>{plans.map((p) => (
                  <tr key={p.name ?? p.plan}>
                    <td>{p.name ?? p.plan} <span className="badge success">{subscription?.plan === (p.name ?? p.plan) ? 'active' : '—'}</span></td>
                    <td>{p.price != null ? `${p.price} ${p.currency ?? 'SAR'}` : 'Free'}</td>
                    <td className="small">{Array.isArray(p.features) ? p.features.join(', ') : '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </section>

      <section className="card">
        <h3>User Management</h3>
        {Array.isArray(an.users) && an.users.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>User</th><th>Role</th><th>Status</th></tr></thead>
              <tbody>{an.users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email ?? u.username}</td><td>{u.role ?? 'user'}</td>
                  <td><span className={`badge ${u.active === false ? 'error-badge' : 'success'}`}>{u.active === false ? 'disabled' : 'active'}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="👥" title="User list unavailable" hint="Role-based access management requires an admin users endpoint." />
        )}
      </section>

      <section className="card span-2">
        <h3>System Health</h3>
        {loading ? <Spinner label="…" /> : (
          <div className="health-grid">
            <div className="health-card"><span className="stat-label">API</span><div className="badge success">Operational</div><span className="muted small">v0.5.0</span></div>
            <div className="health-card"><span className="stat-label">Database</span><div className="badge success">{err ? 'Degraded' : 'Operational'}</div><span className="muted small">SQLite</span></div>
            <div className="health-card"><span className="stat-label">Queue</span><div className="badge">Configured</div><span className="muted small">worker profile</span></div>
            <div className="health-card"><span className="stat-label">Monitoring</span><div className="badge">Placeholder</div><span className="muted small">Sentry / Cloudflare</span></div>
          </div>
        )}
      </section>
    </div>
  )
}