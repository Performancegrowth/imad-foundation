import { useEffect, useMemo, useState } from 'react'
import { getConsultants, getCostData, getSuppliers, requestConsultantReview } from '../platformApi.js'
import { EmptyState, Spinner } from '../components/ui.jsx'

const toArr = (d, k) => (Array.isArray(d) ? d : d?.[k] ?? [])

export default function EcosystemWorkspace() {
  const [suppliers, setSuppliers] = useState([])
  const [consultants, setConsultants] = useState([])
  const [costs, setCosts] = useState([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([getSuppliers(), getConsultants(), getCostData('')])
      .then(([s, c, co]) => { setSuppliers(toArr(s, 'suppliers')); setConsultants(toArr(c, 'consultants')); setCosts(toArr(co, 'costs')); setErr(null) })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(
    () => suppliers.filter((s) => `${s.name ?? ''} ${s.region ?? ''} ${s.type ?? ''}`.toLowerCase().includes(q.toLowerCase())),
    [suppliers, q])

  const review = async (c) => {
    try { const r = await requestConsultantReview({ consultant_id: c.id, project_id: 1 }); alert(`Review request sent — ${r.status ?? 'pending'}`) }
    catch (e) { setErr(e.message) }
  }

  return (
    <div className="workspace-grid">
      <section className="card span-2">
        <div className="card-header">
          <h2>Marketplace &amp; Ecosystem</h2>
          <input className="search-box" placeholder="Filter suppliers…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search suppliers" />
        </div>
        <p className="muted small">Supplier directory, licensed consultant network and the live regional cost database.</p>
        {err && <div className="alert error" role="alert"><strong>Error:</strong> {err}</div>}
      </section>

      <section className="card span-2">
        <h3>Supplier Directory</h3>
        {loading ? <Spinner label="Loading suppliers…" /> : filtered.length === 0
          ? <EmptyState icon="🏭" title="No suppliers found" hint="Adjust the search or register a supplier." />
          : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Supplier</th><th>Type</th><th>Region</th><th>Contact</th></tr></thead>
                <tbody>{filtered.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td><td>{s.type ?? s.category ?? '—'}</td><td>{s.region ?? '—'}</td><td>{s.contact ?? s.email ?? '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </section>

      <section className="card span-2">
        <h3>Consultant Network</h3>
        {loading ? <Spinner label="Loading consultants…" /> : consultants.length === 0
          ? <EmptyState icon="🧑‍🏭" title="No licensed consultants" hint="Book a licensed engineer to review and stamp your design." />
          : (
            <div className="consult-grid">
              {consultants.map((c) => (
                <div className="market-card" key={c.id}>
                  <strong>{c.name ?? c.full_name}</strong>
                  <span className="rating" aria-label={`Rating ${c.rating ?? 0} out of 5`}>★ {c.rating ?? '—'} / 5</span>
                  <span className="muted small">{c.specialty ?? c.title ?? 'Structural Engineer'} · {c.region ?? '—'}</span>
                  <button className="btn small" onClick={() => review(c)}>Request Review</button>
                </div>
              ))}
            </div>
          )}
      </section>

      <section className="card span-2">
        <h3>Regional Cost Database</h3>
        {loading ? <Spinner label="Loading cost data…" /> : costs.length === 0
          ? <EmptyState icon="💲" title="No cost records" hint="Material unit prices by region and date appear here." />
          : (
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Material</th><th>Unit</th><th>Price</th><th>Region</th><th>Date</th></tr></thead>
                <tbody>{costs.map((c) => (
                  <tr key={c.id}>
                    <td>{c.material}</td><td>{c.unit ?? '—'}</td><td>{c.price ?? c.rate}</td><td>{c.region ?? '—'}</td><td>{c.date ?? c.recorded_at ?? '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </section>
    </div>
  )
}