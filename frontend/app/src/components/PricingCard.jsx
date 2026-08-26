// Pricing plan data + reusable plan card (split out to keep PricingWorkspace small).
export const PLANS = [
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

export const money = (v) => `$${Number(v).toLocaleString()}`

export function StatLike({ label, value }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}

export default function PlanCard({ p, annual, busy, current, onUpgrade }) {
  const priceOf = (plan) => (annual && !plan.suffix ? Math.round(plan.price * 12 * 0.85) : plan.price)
  return (
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
              onClick={() => onUpgrade(p.id)}>
        {busy === p.id ? 'Processing…'
          : current?.plan === p.id ? 'Current plan' : p.price === 0 ? 'Switch to Free' : 'Upgrade'}
      </button>
    </article>
  )
}