// Public Engineering Blog placeholder — sample article cards.
import Seo from '../components/Seo.jsx'
import { SITE_URL } from '../seoData.js'

const POSTS = [
  {
    title: 'How Generative AI is Reshaping Structural Design',
    tag: 'AI Design',
    excerpt:
      'From single-scheme drafting to exploring thousands of valid structural systems in minutes.',
  },
  {
    title: 'ACI 318 vs Eurocode 2 vs SBC 304: A Practical Guide',
    tag: 'Codes',
    excerpt: 'Understand the design philosophy, load factors and limits across the three frameworks.',
  },
  {
    title: 'Cutting Steel Waste with an Optimised Bar Bending Schedule',
    tag: 'BOQ',
    excerpt: 'How smarter rebar scheduling targets under 2% waste and reduces project cost.',
  },
  {
    title: 'Sustainability by Default: LCA in Everyday Design',
    tag: 'Sustainability',
    excerpt: 'Embodied carbon that gets cheaper the more projects you run on an AI platform.',
  },
]

export default function BlogWorkspace() {
  return (
    <div className="workspace-grid">
      <Seo
        title="Engineering Blog – Imad (عِماد)"
        description="Insights on AI structural engineering, building codes, BOQ optimization, and sustainability."
        canonical={`${SITE_URL}/blog`}
        ogTitle="Engineering Blog – Imad (عِماد)"
        ogDescription="AI structural engineering guides: codes, generative design, BOQ and sustainability."
      />

      <section className="card span-2" aria-labelledby="blog-title">
        <h1 id="blog-title">Engineering Blog</h1>
        <p className="muted">
          Insights on AI structural engineering, building codes, BOQ optimization
          and sustainability.
        </p>
      </section>

      <div className="card-grid span-2">
        {POSTS.map((p) => (
          <article className="card" key={p.title}>
            <span className="badge success">{p.tag}</span>
            <h2>{p.title}</h2>
            <p className="muted small">{p.excerpt}</p>
            <button className="btn small">Read post</button>
          </article>
        ))}
      </div>
    </div>
  )
}