// Public Landing page — Spacial-style 7-section marketing hub with SEO structured data.
import Seo from '../components/Seo.jsx'
import {
  SITE_URL,
  softwareAppSchema,
  faqPageSchema,
  organizationSchema,
} from '../seoData.js'

/* Placeholder structural frame: 5 columns + 3 beams + pink node circles.
 * Used inside HoverReveal (the prop-driven 3D StructureViewer needs a live
 * plan, so the landing uses this lightweight SVG instead). */
function StructurePlaceholder() {
  const cols = [60, 180, 300, 420, 540]
  const beams = [80, 180, 280]
  return (
    <svg viewBox="0 0 600 360" role="img" aria-label="Structural frame preview">
      {beams.map((y) => (
        <line key={`b-${y}`} x1="40" y1={y} x2="560" y2={y} stroke="#3e68ff" strokeWidth="6" />
      ))}
      {cols.map((x) => (
        <line key={`c-${x}`} x1={x} y1="40" x2={x} y2="320" stroke="#ffffff" strokeWidth="5" opacity="0.85" />
      ))}
      {cols.map((x) =>
        beams.map((y) => (
          <circle key={`n-${x}-${y}`} cx={x} cy={y} r="7" fill="#ff2e79" />
        )),
      )}
      <line x1="20" y1="320" x2="580" y2="320" stroke="#cdf765" strokeWidth="3" />
    </svg>
  )
}

/* Hover-to-reveal: photo fades, structural model appears. */
function HoverReveal({ photoSrc, label }) {
  return (
    <div className="reveal-container">
      <div className="reveal-photo" style={{ backgroundImage: `url(${photoSrc})` }} />
      <div className="reveal-structure">
        <StructurePlaceholder />
      </div>
      <div className="reveal-label">{label || 'STRUCTURAL VIEW'}</div>
    </div>
  )
}

const STATS = [
  { value: '13', label: 'Code checks' },
  { value: '5min', label: 'Average design time' },
  { value: '4', label: 'Disciplines under one roof' },
  { value: '100%', label: 'AI-native workflow' },
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
  },
  {
    img: '/images/project-2.jpg',
    title: 'Corniche Apartments',
    meta: 'Jeddah, KSA | Residential',
    desc: 'Mid-rise residential block with full BOQ and BBS output.',
  },
  {
    img: '/images/project-3.jpg',
    title: 'Logistics Warehouse',
    meta: 'Dammam, KSA | Industrial',
    desc: 'Steel portal frame with optimized member sizing.',
  },
  {
    img: '/images/project-4.jpg',
    title: 'Majlis Commercial Strip',
    meta: 'Riyadh, KSA | Commercial',
    desc: 'Mixed-use strip with seismic design per SBC 304.',
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
        <HoverReveal photoSrc="/images/hero.jpg" label="STRUCTURAL VIEW" />
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
                <span className="stat-number">{s.value}</span>
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
                <HoverReveal photoSrc={p.img} label="STRUCTURAL VIEW" />
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
          <button type="button" className="sp-btn sp-btn-blue-text" onClick={go(onNav, 'plan')}>
            Start a Project
          </button>
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