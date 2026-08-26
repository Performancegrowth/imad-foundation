// Public FAQ page backed by the shared FAQPage JSON-LD content.
import Seo from '../components/Seo.jsx'
import { SITE_URL, FAQS, faqPageSchema } from '../seoData.js'

export default function FaqWorkspace() {
  return (
    <div className="workspace-grid">
      <Seo
        title="FAQ – Imad (عِماد)"
        description="Answers on Imad's AI structural design: code compliance, pricing, BOQ & BBS, safety and generative design."
        canonical={`${SITE_URL}/faq`}
        ogTitle="FAQ – Imad (عِماد)"
        ogDescription="How Imad works, what it costs, and how AI structural design keeps you safe and compliant."
        schema={faqPageSchema()}
      />

      <section className="card span-2" aria-labelledby="faq-title">
        <h1 id="faq-title">Frequently Asked Questions</h1>
        <p className="muted">
          Answers to the most common questions about Imad's AI structural design.
        </p>
      </section>

      <section className="card span-2" aria-label="FAQ list">
        {FAQS.map((f) => (
          <details className="faq-item" key={f.q}>
            <summary>{f.q}</summary>
            <p className="muted">{f.a}</p>
          </details>
        ))}
      </section>
    </div>
  )
}