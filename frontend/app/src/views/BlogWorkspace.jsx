// Public Engineering Blog — full readable articles, expanded inline.
import { useState } from 'react'
import Seo from '../components/Seo.jsx'
import { SITE_URL } from '../seoData.js'

const POSTS = [
  {
    title: 'How Generative AI is Reshaping Structural Design',
    tag: 'AI Design',
    minutes: 6,
    excerpt:
      'From single-scheme drafting to exploring thousands of valid structural systems in minutes.',
    body: [
      'Traditionally a designer produces one scheme, checks it, and iterates by hand — a workflow that rewards conservatism over exploration. Generative design flips this: the computer proposes many valid structural systems, and the engineer curates the best ones for cost, carbon and buildability.',
      'Imad runs an NSGA-II genetic algorithm that evolves column grids, beam orientations and slab types. Each candidate is analysed, costed and carbon-scored, and the Pareto-optimal top options are returned in under a minute.',
      'The result is not a replacement for engineering judgement — it is an amplifier. The engineer still sets the constraints, interrogates the assumptions and makes the final call.',
    ],
  },
  {
    title: 'ACI 318 vs Eurocode 2 vs SBC 304: A Practical Guide',
    tag: 'Codes',
    minutes: 8,
    excerpt: 'Understand the design philosophy, load factors and limits across the three frameworks.',
    body: [
      'ACI 318 and Eurocode 2 share the same underlying limit-state philosophy but differ in load combinations, material partial factors and detailing rules. SBC 304 is the Saudi national building code and closely follows ACI 318 with local amendments.',
      'For practitioners the three practical differences that matter most are the load-combination factors, the minimum-reinforcement rules and seismic detailing requirements. A design that passes ACI does not always pass SBC 304 without re-checking drift limits.',
      'Imad normalises these differences internally — you pick your design standard at the project level and every check, BOQ and submission is generated against that code.',
    ],
  },
  {
    title: 'Cutting Steel Waste with an Optimised Bar Bending Schedule',
    tag: 'BOQ',
    minutes: 5,
    excerpt: 'How smarter rebar scheduling targets under 2% waste and reduces project cost.',
    body: [
      'On a typical project, rebar waste runs between 5% and 10% because bars are cut without considering full stock lengths. A good bar bending schedule optimises the cutting plan across the whole order.',
      'Imad schedules bars in descending length, groups identical shapes, and applies a stock-length cutting algorithm with a waste target under 2%. Surplus lengths are tracked so the site can reuse off-cuts.',
      'On a 12-storey frame this alone typically saves 3–5% of the steel budget — often the difference between a winning and a losing tender price.',
    ],
  },
  {
    title: 'Sustainability by Default: LCA in Everyday Design',
    tag: 'Sustainability',
    minutes: 5,
    excerpt: 'Embodied carbon that gets cheaper the more projects you run on an AI platform.',
    body: [
      'Embodied carbon is now a first-order design driver in regional rating systems like LEED, Mostadam and Estidama — but measuring it per project used to require a separate LCA specialist model.',
      'Imad computes a cradle-to-gate LCA directly from the bill of quantities using published emission factors (ICE v3.0, worldsteel), then benchmarks the result and proposes green alternatives with their cost impact.',
      'Because the carbon model reuses the same quantities as the BOQ, the report is consistent, auditable and cheap to produce on every run — sustainability becomes a default, not an add-on.',
    ],
  },
]

export default function BlogWorkspace() {
  const [openIdx, setOpenIdx] = useState(null)
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
        {POSTS.map((p, i) => {
          const open = openIdx === i
          return (
            <article className={`card ${open ? 'span-2' : ''}`} key={p.title}>
              <div className="card-header">
                <span className="badge success">{p.tag}</span>
                <span className="muted small">{p.minutes} min read</span>
              </div>
              <h2>{p.title}</h2>
              <p className="muted small">{p.excerpt}</p>
              {open && (
                <div className="blog-body">
                  {p.body.map((para) => <p key={para.slice(0, 24)}>{para}</p>)}
                </div>
              )}
              <button
                className="btn small"
                onClick={() => setOpenIdx(open ? null : i)}
                aria-expanded={open}
              >
                {open ? 'Close article' : 'Read post'}
              </button>
            </article>
          )
        })}
      </div>
    </div>
  )
}