// Sprint 9C/14 — Pricing & subscription management.
import { useEffect, useState } from 'react'
import { pApi } from '../platformApi.js'
import Seo from '../components/Seo.jsx'
import PlanCard, { PLANS, StatLike } from '../components/PricingCard.jsx'
import { SITE_URL } from '../seoData.js'

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

  return (
    <div className="workspace-grid">
      <Seo
        title="Pricing – Imad (عِماد)"
        description="Simple pricing for AI structural design, BOQ generation, and sustainability reporting. Free tier available."
        canonical={`${SITE_URL}/pricing`}
      />
      <section className="card span-2" aria-labelledby="pricing-title">
        <div className="card-header">
          <h1 id="pricing-title">Plans &amp; Pricing</h1>
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
          <PlanCard key={p.id} p={p} annual={annual} busy={busy} current={current} onUpgrade={upgrade} />
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