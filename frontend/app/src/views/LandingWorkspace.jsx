// Public Landing page — main marketing hub with SEO structured data for AEO.
import Seo from '../components/Seo.jsx'
import {
  SITE_URL,
  FAQS,
  softwareAppSchema,
  faqPageSchema,
  organizationSchema,
} from '../seoData.js'
import { Button, Card, CardHeader, CardTitle, Badge } from '../components/shadcn.jsx'

const FEATURES = [
  'Generative AI structural design',
  'BOQ and Bar Bending Schedule generation',
  'Carbon footprint calculation',
  'Multi-story building analysis',
  'IFC/BIM import/export',
  'Compliance with ACI 318, Eurocode 2, SBC 304',
]

export default function LandingWorkspace({ onNav, onAuth }) {
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

      <Card className="span-2 hero-card" aria-label="Imad overview">
        <Badge variant="success">The Autonomous Engineering Engine</Badge>
        <h1 className="hero-title">Imad (عِماد) – AI Structural Engineering Platform</h1>
        <p>
          Generate structural designs, Bills of Quantities, and sustainability
          reports in minutes. Imad is an autonomous AI platform for civil and
          structural engineers — supporting <strong>ACI 318</strong>,{' '}
          <strong>Eurocode 2</strong> and <strong>SBC 304</strong>.
        </p>
        <div className="inline-controls">
          <Button variant="primary" onClick={() => onAuth?.('register')} aria-label="Create your free Imad account">
            Start Free — Sign Up
          </Button>
          <Button onClick={() => onAuth?.('login')} aria-label="Log in to your Imad account">
            Login
          </Button>
          <Button onClick={() => onNav?.('pricing')}>View Pricing</Button>
        </div>
      </Card>

      <Card className="span-2" aria-labelledby="landing-features">
        <CardHeader>
          <h2 id="landing-features">What Imad does</h2>
          <Badge variant="success">Generative design</Badge>
        </CardHeader>
        <ul className="feature-list">
          {FEATURES.map((f) => (
            <li key={f}>✓ {f}</li>
          ))}
        </ul>
      </Card>

      <Card className="span-2" aria-labelledby="landing-pricing">
        <h2 id="landing-pricing">Simple, value-based pricing</h2>
        <p className="muted">
          Free to evaluate. Pay-Per-Project $99, Office $299/mo, Enterprise $999/mo.
        </p>
      </Card>

      <Card className="span-2" aria-labelledby="landing-faq">
        <CardHeader>
          <h2 id="landing-faq">Frequently asked questions</h2>
          <Button size="sm" onClick={() => onNav?.('faq')}>View all FAQs</Button>
        </CardHeader>
        <div className="faq-preview">
          {FAQS.slice(0, 5).map((f) => (
            <details className="faq-item" key={f.q}>
              <summary>{f.q}</summary>
              <p className="muted">{f.a}</p>
            </details>
          ))}
        </div>
      </Card>
    </div>
  )
}