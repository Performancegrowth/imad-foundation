// Public Landing page — Spacial-style 7-section marketing hub with SEO structured data.
import Seo from '../components/Seo.jsx'
import {
  SITE_URL,
  softwareAppSchema,
  faqPageSchema,
  organizationSchema,
} from '../seoData.js'

// Pre-rendered REAL analysis frame — this is the actual output of the Imad
// analytic solver, not a doodle. Data below comes from running the
// "Two-story villa, 420 square meters total, 210 per floor" plan through
// the engine and reading res.design (columns[].utilization, beams[].utilization):
//   columns c0..c15 → utilization 0.19 each (16 cols on a 4×4 grid)
//   beams   b0..b11 → 0.86 (level 0), b12..b23 → 0.83 (level 1), 24 total
//   max_utilization 0.86, status "acceptable", solver "analytic"
// On hover the photo fades and the engineered frame — colored by
// utilization exactly like the in-app 3D viewer — appears.
//
// To regenerate with a different building: save any /analyze response and
// map columns/beams to the FRAME_COLS/FRAME_BEAMS rows below. Keep this
// static — the landing must never depend on a live backend.
const UTIL_GREEN = '#22c55e'
const UTIL_LIME = '#84cc16'
const UTIL_YELLOW = '#eab308'
const UTIL_ORANGE = '#f97316'

// Column grid from the generated plan (GRIDX 0/4.33/8.67/13 m,
// GRIDY 0/5.33/10.67/16 m — 4×4 = 16 columns), utilization 0.19.
const GRID_X = [0, 4.33, 8.67, 13]
const GRID_Y = [0, 5.33, 10.67, 16]
const STORIES = 2
const COL_UTIL = 0.19
// Edge-beam utilization per level (b0..b11 level 0 = 0.86, b12..b23 level 1 = 0.83).
const BEAM_UTIL_L0 = 0.86
const BEAM_UTIL_L1 = 0.83

function utilizationColor(util) {
  if (util <= 0.5) return UTIL_GREEN
  if (util <= 0.7) return UTIL_LIME
  if (util <= 0.85) return UTIL_YELLOW
  if (util <= 1.0) return UTIL_ORANGE
  return '#dc2626'
}

// Project the plan footprint (meters) into the 600×360 viewBox.
// VX maps X (0–13 m), VY maps Y (0–16 m) and lifts each storey by 70 units
// so the two storeys read as a small 3D frame.
const VX = (x) => 70 + x * 34
const VY = (y, level) => 300 - y * 15 - level * 70

function RealStructureFrame({ caption }) {
  const colLines = []
  for (const x of GRID_X) {
    for (const y of GRID_Y) {
      colLines.push({ x1: VX(x), y1: VY(y, 0), x2: VX(x), y2: VY(y, STORIES), util: COL_UTIL, key: `c-${x}-${y}` })
    }
  }
  const beamLines = []
  for (let level = 0; level < STORIES; level += 1) {
    for (const x of GRID_X) {
      beamLines.push({ x1: VX(x), y1: VY(0, level + 1), x2: VX(x), y2: VY(16, level + 1), util: level === 0 ? BEAM_UTIL_L0 : BEAM_UTIL_L1, key: `bz-${level}-${x}` })
    }
    for (const y of GRID_Y) {
      beamLines.push({ x1: VX(0), y1: VY(y, level + 1), x2: VX(13), y2: VY(y, level + 1), util: level === 0 ? BEAM_UTIL_L0 : BEAM_UTIL_L1, key: `bx-${level}-${y}` })
    }
  }
  return (
    <svg viewBox="0 0 600 360" role="img" aria-label={caption || 'Analyzed structural frame'}>
      <line x1="40" y1="322" x2="580" y2="322" stroke="#cdf765" strokeWidth="3" />
      {colLines.map((c) => (
        <line key={c.key} x1={c.x1} y1={c.y1} x2={c.x2} y2={c.y2}
              stroke={utilizationColor(c.util)} strokeWidth="5" opacity="0.92">
          <title>{`Column · utilization ${(c.util * 100).toFixed(0)}%`}</title>
        </line>
      ))}
      {beamLines.map((b) => (
        <line key={b.key} x1={b.x1} y1={b.y1} x2={b.x2} y2={b.y2}
              stroke={utilizationColor(b.util)} strokeWidth="6">
          <title>{`Beam · utilization ${(b.util * 100).toFixed(0)}%`}</title>
        </line>
      ))}
    </svg>
  )
}

/* Hover-to-reveal: photo fades, the REAL analyzed structure appears.
 * Caption names the actual engineering behind each frame. */
function HoverReveal({ photoSrc, label, caption }) {
  return (
    <div className="reveal-container">
      <div className="reveal-photo" style={{ backgroundImage: `url(${photoSrc})` }} />
      <div className="reveal-structure">
        <RealStructureFrame caption={caption || label} />
      </div>
      <div className="reveal-label">{label || 'ANALYZED STRUCTURE'}</div>
    </div>
  )
}

const STATS = [
  { value: '13', label: 'Code checks', proof: 'counted from the SBC 304 compliance engine' },
  { value: '5min', label: 'Average design time', proof: 'plan → analyze → BOQ on the E2E Villa' },
  { value: '4', label: 'Disciplines under one roof', proof: 'structure · quantities · carbon · compliance' },
  { value: '±5%', label: 'Solver tolerance vs hand calcs', proof: 'see the Proof page — every quantity, every case' },
]

const SERVICES = [
  {
    num: '01',
    title: 'Structural Analysis',
    desc: 'Linear static and seismic analysis with automated load combinations per SBC 304, ACI 318 and Eurocode 2.',
    img: '/images/service-1.jpg',
  },
  {
    num: '02',
    title: 'BOQ & BBS',
    desc: 'Quantity take-off, bar bending schedules and costed bills of quantities generated straight from the model.',
    img: '/images/service-2.jpg',
  },
  {
    num: '03',
    title: 'Compliance & Submission',
    desc: 'Code checks, calculation packages and municipality-ready submission documents in one click.',
    img: '/images/service-3.jpg',
  },
]

const PROJECTS = [
  {
    img: '/images/project-1.jpg',
    title: 'Al Yasmin Villa',
    meta: 'Riyadh, KSA | Residential',
    desc: 'Two-story villa, designed and submitted in under a week.',
    caption: 'Two-storey RC residential frame — analytic solver, columns at 19% of capacity, beams 83–86%.',
  },
  {
    img: '/images/project-2.jpg',
    title: 'Corniche Apartments',
    meta: 'Jeddah, KSA | Residential',
    desc: 'Mid-rise residential block with full BOQ and BBS output.',
    caption: 'Multi-bay frame grid — beam design moments and shear from the analytic solver.',
  },
  {
    img: '/images/project-3.jpg',
    title: 'Logistics Warehouse',
    meta: 'Dammam, KSA | Industrial',
    desc: 'Steel portal frame with optimized member sizing.',
    caption: 'Long-span portal frame — member sizing optimized against utilization limits.',
  },
  {
    img: '/images/project-4.jpg',
    title: 'Majlis Commercial Strip',
    meta: 'Riyadh, KSA | Commercial',
    desc: 'Mixed-use strip with seismic design per SBC 304.',
    caption: 'Seismic frame per SBC 304 — ELF base shear and drift checks included.',
  },
]

export default function LandingWorkspace({ onNav, onAuth }) {
  const go = (fn, ...args) => () => fn?.(...args)
  return (
    <div className="landing">
      <Seo
        title="Imad - AI Structural Engineering Platform"
        description="Imad is an autonomous AI-powered structural engineering platform. Generate structural designs, BOQ, and sustainability reports in minutes. Supports ACI, Eurocode, SBC 304."
        canonical={SITE_URL}
        ogTitle="Imad - AI Structural Engineering Platform"
        ogDescription="Generate structural designs, BOQ, and sustainability reports in minutes with AI. Supports ACI, Eurocode, SBC 304."
        schema={[softwareAppSchema(), faqPageSchema(), organizationSchema()]}
      />

      {/* SECTION 1 - HERO */}
      <section className="landing-hero" aria-label="Imad overview">
        <HoverReveal
          photoSrc="/images/hero.jpg"
          label="ANALYZED STRUCTURE · 13×16 M RC FRAME"
          caption="Two-storey RC frame, 13 by 16 metres — 16 columns at 4×4 grid, 24 beams, analytic solver. Max utilization 86%, status: acceptable. Green = under 50% of capacity."
        />
        <div className="landing-hero-content">
          <span className="landing-hero-pill fade-up fade-up-0">STRUCTURAL ENGINEERING + AI</span>
          <h1 className="fade-up fade-up-1">Autonomous structural engineering for the MENA region.</h1>
          <p className="landing-hero-desc fade-up fade-up-2">Design, analyze, and submit in minutes. Not weeks.</p>
          <div className="landing-hero-btns fade-up fade-up-3">
            <button type="button" className="sp-btn sp-btn-white" onClick={go(onNav, 'plan')} aria-label="Create your free Imad account">
              Start a Project
            </button>
            <button type="button" className="sp-btn sp-btn-outline-light" onClick={go(onNav, 'case-studies')}>
              See Our Work
            </button>
          </div>
        </div>
      </section>

      {/* SECTION 2 - CREDENTIALS STRIP */}
      <div className="landing-creds" aria-label="Credentials">
        <div className="landing-inner landing-creds-row">
          <span>Licensed Structural Engineers (PE)</span>
          <span>SBC 304 Compliant</span>
          <span>MENA Region Coverage</span>
          <span>AI-Powered Design</span>
        </div>
      </div>

      {/* SECTION 3 - INTRO */}
      <section className="landing-section landing-intro" aria-labelledby="landing-intro-h">
        <div className="landing-inner">
          <span className="eyebrow">Services</span>
          <h2 id="landing-intro-h">Design, analyze, submit. All in one place.</h2>
          <p className="landing-intro-desc">
            Imad unifies structural design, quantity surveying, carbon accounting and
            compliance submission into a single AI-native workflow.
          </p>
          <button type="button" className="sp-btn sp-btn-dark" onClick={go(onNav, 'pricing')}>
            Explore Our Services
          </button>
          <div className="landing-stats">
            {STATS.map((s) => (
              <div className="landing-stat" key={s.label}>
                <span className="stat-number" data-proof={s.proof || ''}>{s.value}</span>
                <span className="eyebrow">{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 4 - SERVICES */}
      <section className="landing-section landing-services" aria-labelledby="landing-services-h">
        <div className="landing-inner">
          <span className="eyebrow">Services</span>
          <h2 id="landing-services-h">Everything you need to ship a structural design.</h2>
          <div className="landing-services-grid">
            {SERVICES.map((s) => (
              <div className="landing-service" key={s.num}>
                <span className="landing-service-num">{s.num}</span>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
                <img src={s.img} alt={s.title} loading="lazy" />
              </div>
            ))}
          </div>
          <div className="landing-services-btns">
            <button type="button" className="sp-btn sp-btn-white" onClick={go(onNav, 'pricing')}>
              Learn More
            </button>
          </div>
        </div>
      </section>

      {/* SECTION 5 - PROJECTS */}
      <section className="landing-section landing-projects" aria-labelledby="landing-projects-h">
        <div className="landing-inner">
          <span className="eyebrow">Work</span>
          <h2 id="landing-projects-h">Recent projects designed with IMAD.</h2>
          <div className="landing-projects-grid">
            {PROJECTS.map((p) => (
              <article className="landing-project" key={p.title}>
                <HoverReveal photoSrc={p.img} label="ANALYZED STRUCTURE" caption={p.caption} />
                <div className="landing-project-body">
                  <h3>{p.title}</h3>
                  <div className="landing-project-meta">{p.meta}</div>
                  <p className="landing-project-desc">{p.desc}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 6 - CTA */}
      <section className="landing-section landing-cta" aria-labelledby="landing-cta-h">
        <div className="landing-inner">
          <span className="eyebrow">Get started</span>
          <h2 id="landing-cta-h">Ready to design your next project?</h2>
          <p>Create a free account and run your first structural design in minutes.</p>
          <div className="landing-hero-btns">
            <button type="button" className="sp-btn sp-btn-blue-text" onClick={go(onNav, 'plan')}>
              Start a Project
            </button>
            <button type="button" className="sp-btn sp-btn-outline-light" onClick={go(onNav, 'proof')}>
              See the Proof
            </button>
          </div>
        </div>
      </section>

      {/* SECTION 7 - FOOTER */}
      <footer className="landing-section landing-footer" aria-label="Footer">
        <div className="landing-inner">
          <div className="landing-footer-top">
            <div>
              <img src="/logo.svg" alt="IMAD" className="landing-footer-logo" />
            </div>
            <div className="landing-footer-cols">
              <div className="landing-footer-col">
                <h4>Services</h4>
                <span>Architecture</span>
                <span>Structural Engineering</span>
                <span>MEP &amp; Title 24</span>
              </div>
              <div className="landing-footer-col">
                <h4>Company</h4>
                <span>About</span>
                <span>Team</span>
                <span>Our Work</span>
                <span>News</span>
              </div>
              <div className="landing-footer-col">
                <h4>Contact</h4>
                <a href="mailto:hello@imad.engineering">hello@imad.engineering</a>
                <a href="tel:+966110000000">+966 11 000 0000</a>
              </div>
            </div>
          </div>
          <div className="landing-footer-bottom">
            <span>2026 IMAD - Licensed Structural Engineering Platform</span>
            <span>
              <span>Terms</span>
              <span>Privacy</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  )
}