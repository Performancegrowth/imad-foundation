// Case Studies placeholder — one sample engineering project story.
import Seo from '../components/Seo.jsx'
import { SITE_URL } from '../seoData.js'

const CASE = {
  title: '12-Storey Mixed-Use Tower — Riyadh',
  sector: 'Mixed-use · Saudi Arabia',
  story:
    "Using Imad's generative design, the team compared 1,400 structural schemes in a day, cutting material tonnage by 11% while meeting SBC 304 drift limits — and produced a complete BOQ + BBS ready for tender.",
  outcomes: [
    '1,400 options explored in one working day',
    '9% reduction in steel + concrete tonnage',
    'SBC 304-compliant, tender-ready BOQ & BBS',
  ],
}

export default function CaseStudiesWorkspace() {
  return (
    <div className="workspace-grid">
      <Seo
        title="Case Studies – Imad (عِماد)"
        description="Real engineering projects delivered faster with Imad's autonomous AI structural design platform."
        canonical={`${SITE_URL}/case-studies`}
        ogTitle="Case Studies – Imad (عِماد)"
        ogDescription="How engineering teams use Imad's generative design to save time and material."
      />

      <section className="card span-2" aria-labelledby="cases-title">
        <h1 id="cases-title">Case Studies</h1>
        <p className="muted">
          Stories of engineering teams using Imad to design faster and build leaner.
        </p>
      </section>

      <article className="card span-2">
        <div className="card-header">
          <h2>{CASE.title}</h2>
          <span className="badge success">{CASE.sector}</span>
        </div>
        <p>{CASE.story}</p>
        <ul className="feature-list">
          {CASE.outcomes.map((o) => (
            <li key={o}>✓ {o}</li>
          ))}
        </ul>
      </article>
    </div>
  )
}