// Case Studies — data-driven engineering stories with a selector.
import { useState } from 'react'
import Seo from '../components/Seo.jsx'
import { SITE_URL } from '../seoData.js'

const CASES = [
  {
    id: 'riyadh-tower',
    title: '12-Storey Mixed-Use Tower — Riyadh',
    sector: 'Mixed-use · Saudi Arabia',
    story:
      "Using Imad's generative design, the team compared 1,400 structural schemes in a day, cutting material tonnage by 11% while meeting SBC 304 drift limits — and produced a complete BOQ + BBS ready for tender.",
    outcomes: [
      '1,400 options explored in one working day',
      '9% reduction in steel + concrete tonnage',
      'SBC 304-compliant, tender-ready BOQ & BBS',
    ],
  },
  {
    id: 'jeddah-villa',
    title: 'Low-Carbon Villa Cluster — Jeddah',
    sector: 'Residential · Saudi Arabia',
    story:
      "A developer used Imad's questionnaire-to-plan flow to generate 24 villa variants, then the LCA module ranked them by embodied carbon. The chosen scheme cut CO₂e/m² by 18% with no increase in construction cost.",
    outcomes: [
      '24 villa variants generated from a questionnaire in minutes',
      '18% embodied-carbon reduction via LCA-ranked alternatives',
      'Zero cost increase — selected scheme validated against BOQ',
    ],
  },
  {
    id: 'doha-office',
    title: 'Structural Conversion of an Office Block — Doha',
    sector: 'Commercial · Qatar',
    story:
      'A legacy reinforced-concrete frame was re-analysed in Imad with the saved survey data. The engine flagged two columns near their ACI capacity limit, and the concrete-design module suggested reinforcement that avoided a full retrofit.',
    outcomes: [
      'Existing frame re-analysed with field-survey inputs',
      'Two columns flagged close to capacity — proactively addressed',
      'Retrofit avoided, saving an estimated 40% vs. re-building',
    ],
  },
]

export default function CaseStudiesWorkspace() {
  const [active, setActive] = useState(0)
  const c = CASES[active] ?? CASES[0]
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
        <div className="card-header">
          <h1 id="cases-title">Case Studies</h1>
          <div className="inline-controls" role="group" aria-label="Choose a case study">
            {CASES.map((cs, i) => (
              <button
                key={cs.id}
                className={`btn small ${i === active ? 'primary' : ''}`}
                onClick={() => setActive(i)}
                aria-pressed={i === active}
              >
                {cs.sector.split(' · ')[1]}
              </button>
            ))}
          </div>
        </div>
        <p className="muted">
          Stories of engineering teams using Imad to design faster and build leaner.
        </p>
      </section>

      <article className="card span-2" key={c.id}>
        <div className="card-header">
          <h2>{c.title}</h2>
          <span className="badge success">{c.sector}</span>
        </div>
        <p>{c.story}</p>
        <ul className="feature-list">
          {c.outcomes.map((o) => (
            <li key={o}>✓ {o}</li>
          ))}
        </ul>
      </article>
    </div>
  )
}