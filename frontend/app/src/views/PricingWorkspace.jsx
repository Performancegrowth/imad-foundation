// Sprint 9C/14 — Pricing & subscription management.
import { useEffect, useState } from 'react'
import { pApi } from '../platformApi.js'

const PLANS = [
  {
    id: 'free', name: 'Free', price: 0, blurb: 'Evaluate Imad on a single project.',
    features: ['1 project', 'Plan creation & CAD import', 'Survey input',
               'Watermarked exports'],
    locked: ['Structural analysis', 'Generative design', 'BOQ & reports', 'PDF/Excel export', '3D without watermark'],
  },
  {
    id: 'payg', name: 'Pay-Per-Project', price: 99, suffix: '/project',
    blurb: 'Occasional projects without a subscription.',
    features: ['Everything in Free, unlocked per project', 'Full structural analysis',
               'Generative design (top 3)', 'BOQ + BBS exports'],
    locked: ['White-label', 'API access'],
  },
  {
    id: 'office', popular: true, name: 'Office', price: 299, suffix: '/month',
    blurb: 'For engineering offices running live projects.',
    features: ['Unlimited projects', 'All analysis & generative tools',
               'Unlimited PDF/Excel/LCA exports', 'Collaboration & approvals',
               'Consultant marketplace', 'API access (fair use)'],
    locked: [],
  },
  {
    id: 'enterprise', name: 'Enterprise', price: 999, suffix: '/month',
    blurb: 'Multi-team deployments with compliance needs.',
    features: ['Everything in Office', 'White-label domain & branding',
               'Priority queue & dedicated support', 'SSO / RBAC management',
               'On-prem Ollama agent hosting'],
    locked: [],
  },
]

const money = (v) => `$${Number(v).toLocaleString()}`

export default function PricingWorkspace() {
  const [annual, setAnnual] = useState(false)
  const [current, setCurrent] = useState(null)
  const [busy, setBusy] = useState(null)
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    pApi.currentSubscription().then(setCurrent).catch(() => setCurrent(null))
  }, [])

  const upgrade = async (planId) => {
    setBusy(planId); setError(null); setNotice(null)
    try {
      const res = await pApi.upgradeSubscription({ plan: planId, cycle: annual ? 'annual' : 'monthly' })
      setNotice(res?.checkout_url
        ? 'Redirecting to Stripe checkout…'
        : 'Plan recorded (Stripe sandbox placeholder — no payment taken). Refresh later to see entitlements.')
      setCurrent(await pApi.currentSubscription())
    } catch (err) {
      setError(err.message || 'Upgrade failed.')
    } finally {
      setBusy(null)
    }
  }

  const priceOf = (p) => (annual && !p.suffix ? Math.round(p.price * 12 * 0.85) : p.price)

  return (
    <div className="workspace-grid">
      <section className="card span-2" aria-labelledby="pricing-title">
        <div className="card-header">
          <h2 id="pricing-title">Plans &amp; Pricing</h2>
          <label className="inline-controls" htmlFor="cycle-toggle">
            <span className={annual ? 'muted' : 'strong'}>Monthly</span>
            <input id="cycle-toggle" type="checkbox" checked={annual}
                   onChange={(e) => setAnnual(e.target.checked)} />
            <span className={annual ? 'strong' : 'muted'}>Annual <span className="badge ok">−15%</span></span>
          </label>
        </div>
        <p className="muted">Value-based pricing: unlock the full engineering pipeline — analysis,
          generative design, BOQ, LCA and municipality-ready submissions.</p>
        {notice && <div className="alert ok" role="status">{notice}</div>}
        {error && <div className="alert error" role="alert"><strong>Error:</strong> {error}</div>}
      </section>

      {current && (
        <section className="card span-2" aria-label="Current subscription">
          <h3>Current subscription</h3>
          <div className="summary-grid">
            <StatLike label="Plan" value={String(current.plan ?? 'free').toUpperCase()} />
            <StatLike label="Status" value={String(current.status ?? 'active')} />
            <StatLike label="Renews" value={String(current.renews_at ?? '—')} />
          </div>
        </section>
      )}

      <div className="pricing-grid span-2">
        {PLANS.map((p) => (
          <article key={p.id} className={`card pricing-card${p.popular ? ' featured' : ''}`}
                   aria-label={`${p.name} plan`}>
            {p.popular && <span className="badge gold">Most popular</span>}
            <h3>{p.name}</h3>
            <p className="price"><strong>{money(priceOf(p))}</strong>
              <span className="muted">{p.suffix ?? (annual ? '/year' : '/month')}</span></p>
            <p className="muted small">{p.blurb}</p>
            <ul className="feature-list">
              {p.features.map((f) => <li key={f}>✓ {f}</li>)}
              {p.locked.map((f) => <li key={f} className="locked">✕ {f}</li>)}
            </ul>
            <button className={`btn ${p.popular ? 'primary' : ''}`} disabled={busy !== null}
                    onClick={() => upgrade(p.id)}>
              {busy === p.id ? 'Processing…'
                : current?.plan === p.id ? 'Current plan' : p.price === 0 ? 'Switch to Free' : 'Upgrade'}
            </button>
          </article>
        ))}
      </div>

      <section className="card span-2" aria-label="Payment note">
        <p className="muted small">
          Payments run through a <strong>Stripe sandbox placeholder</strong> — upgrades are
          recorded instantly for evaluation and no card is charged. Production keys drop in
          via <code>STRIPE_SECRET_KEY</code> (see docs/monetization.md).
        </p>
      </section>
    </div>
  )
}

function StatLike({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}