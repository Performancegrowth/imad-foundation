// Public Landing page — main marketing hub with SEO structured data for AEO.
import Seo from '../components/Seo.jsx'
import {
  SITE_URL,
  FAQS,
  softwareAppSchema,
  faqPageSchema,
  organizationSchema,
} from '../seoData.js'

const FEATURES = [
  'Generative AI structural design',
  'BOQ and Bar Bending Schedule generation',
  'Carbon footprint calculation',
  'Multi-story building analysis',
  'IFC/BIM import/export',
  'Compliance with ACI 318, Eurocode 2, SBC 304',
]

export default function LandingWorkspace() {
  return (
    <div className="workspace-grid">
      <Seo
        title="Imad (عِماد) – AI Structural Engineering Platform"
        description="Imad is an autonomous AI-powered structural engineering platform. Generate structural designs, BOQ, and sustainability reports in minutes. Supports ACI, Eurocode, SBC 304."
        canonical={SITE_URL}
        ogTitle="Imad (عِماد) – AI Structural Engineering Platform"
        ogDescription="Generate structural designs, BOQ, and sustainability reports in minutes with AI. Supports ACI, Eurocode, SBC 304."
        schema={[softwareAppSchema(), faqPageSchema(), organizationSchema()]}
      />

      <section className="card span-2 hero-card" aria-label="Imad overview">
        <span className="badge success">The Autonomous Engineering Engine</span>
        <h1 className="hero-title">Imad (عِماد) – AI Structural Engineering Platform</h1>
        <p>
          Generate structural designs, Bills of Quantities, and sustainability
          reports in minutes. Imad is an autonomous AI platform for civil and
          structural engineers — supporting <strong>ACI 318</strong>,{' '}
          <strong>Eurocode 2</strong> and <strong>SBC 304</strong>.
        </p>
        <div className="inline-controls">
          <button className="btn primary">Start Free</button>
          <button className="btn">View Pricing</button>
        </div>
      </section>

      <section className="card span-2" aria-labelledby="landing-features">
        <div className="card-header">
          <h2 id="landing-features">What Imad does</h2>
          <span className="badge success">Generative design</span>
        </div>
        <ul className="feature-list">
          {FEATURES.map((f) => (
            <li key={f}>✓ {f}</li>
          ))}
        </ul>
      </section>

      <section className="card span-2" aria-labelledby="landing-pricing">
        <h2 id="landing-pricing">Simple, value-based pricing</h2>
        <p className="muted">
          Free to evaluate. Pay-Per-Project $99, Office $299/mo, Enterprise $999/mo.
        </p>
      </section>

      <section className="card span-2" aria-labelledby="landing-faq">
        <div className="card-header">
          <h2 id="landing-faq">Frequently asked questions</h2>
          <button className="btn small">View all FAQs</button>
        </div>
        <div className="faq-preview">
          {FAQS.slice(0, 5).map((f) => (
            <details className="faq-item" key={f.q}>
              <summary>{f.q}</summary>
              <p className="muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>
    </div>
  )
}