import { useEffect, useState } from 'react'
import CadWorkspace from './views/CadWorkspace.jsx'
import CreatePlanWorkspace from './views/CreatePlanWorkspace.jsx'
import SurveyWorkspace from './views/SurveyWorkspace.jsx'
import AnalysisWorkspace from './views/AnalysisWorkspace.jsx'
import GenerativeDesignWorkspace from './views/GenerativeDesignWorkspace.jsx'
import BoqWorkspace from './views/BoqWorkspace.jsx'
import CarbonWorkspace from './views/CarbonWorkspace.jsx'
import PricingWorkspace from './views/PricingWorkspace.jsx'
import ValidationWorkspace from './views/ValidationWorkspace.jsx'
import Building3DWorkspace from './views/Building3DWorkspace.jsx'
import ReviewWorkspace from './views/ReviewWorkspace.jsx'
import CollaborationWorkspace from './views/CollaborationWorkspace.jsx'
import EcosystemWorkspace from './views/EcosystemWorkspace.jsx'
import GovernanceWorkspace from './views/GovernanceWorkspace.jsx'
import AdminWorkspace from './views/AdminWorkspace.jsx'
import LandingWorkspace from './views/LandingWorkspace.jsx'
import BlogWorkspace from './views/BlogWorkspace.jsx'
import FaqWorkspace from './views/FaqWorkspace.jsx'
import CaseStudiesWorkspace from './views/CaseStudiesWorkspace.jsx'

// Public / marketing views render their own <h1>, so the topbar must not add one.
const SEO_VIEWS = ['landing', 'pricing', 'blog', 'faq', 'case-studies']

const NAV = [
  { id: 'landing', label: 'Home', icon: '🏠' },
  { id: 'cad', label: 'CAD Import', icon: '📐' },
  { id: 'plan', label: 'Create Plan', icon: '🧱' },
  { id: 'survey', label: 'Survey', icon: '🌍' },
  { id: 'analysis', label: 'Analyze', icon: '📊' },
  { id: 'generative', label: 'Generate Designs', icon: '🧬' },
  { id: 'boq', label: 'BOQ & BBS', icon: '📋' },
  { id: 'carbon', label: 'Sustainability', icon: '🌱' },
  { id: 'validation', label: 'Validation', icon: '🔬' },
  { id: 'building3d', label: 'Building 3D', icon: '🏢' },
  { id: 'collaboration', label: 'Collaboration', icon: '🤝' },
  { id: 'ecosystem', label: 'Ecosystem', icon: '🌐' },
  { id: 'governance', label: 'Governance', icon: '🏛️' },
  { id: 'review', label: 'Review & Sign', icon: '✍️' },
  { id: 'pricing', label: 'Pricing', icon: '💳' },
  { id: 'blog', label: 'Blog', icon: '✍️' },
  { id: 'faq', label: 'FAQ', icon: '❓' },
  { id: 'case-studies', label: 'Case Studies', icon: '📁' },
]

export default function App() {
  const [view, setView] = useState('landing')

  // Basic i18n for SEO: set <html> lang/dir from the browser language.
  useEffect(() => {
    const navLang = navigator.language || navigator.userLanguage || 'en'
    const isAr = String(navLang).toLowerCase().startsWith('ar')
    document.documentElement.lang = isAr ? 'ar' : 'en'
    document.documentElement.dir = isAr ? 'rtl' : 'ltr'
  }, [])

  const current = NAV.find((n) => n.id === view)
  const title = current?.label || 'Imad'

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">ع</span>
          <div className="brand-text">
            <strong>Imad</strong>
            <span>Engineering Engine</span>
          </div>
        </div>
        <nav aria-label="Workspace">
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${view === item.id ? 'active' : ''}`}
              onClick={() => setView(item.id)}
              aria-current={view === item.id ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="version">v0.9 · Sprints 0–14</span>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          {SEO_VIEWS.includes(view)
            ? <p className="topbar-title">{title}</p>
            : <h1>{title}</h1>}
          <div className="status-chip">Project #1 · Demo</div>
        </header>
        <section className="workspace">
          {view === 'landing' && <LandingWorkspace />}
          {view === 'cad' && <CadWorkspace />}
          {view === 'plan' && <CreatePlanWorkspace />}
          {view === 'survey' && <SurveyWorkspace />}
          {view === 'analysis' && <AnalysisWorkspace />}
          {view === 'generative' && <GenerativeDesignWorkspace />}
          {view === 'boq' && <BoqWorkspace />}
          {view === 'carbon' && <CarbonWorkspace />}
          {view === 'building3d' && <Building3DWorkspace />}
          {view === 'collaboration' && <CollaborationWorkspace />}
          {view === 'ecosystem' && <EcosystemWorkspace />}
          {view === 'governance' && <GovernanceWorkspace />}
          {view === 'review' && <ReviewWorkspace />}
          {view === 'admin' && <AdminWorkspace />}
          {view === 'validation' && <ValidationWorkspace />}
          {view === 'pricing' && <PricingWorkspace />}
          {view === 'blog' && <BlogWorkspace />}
          {view === 'faq' && <FaqWorkspace />}
          {view === 'case-studies' && <CaseStudiesWorkspace />}
        </section>
      </main>
    </div>
  )
}