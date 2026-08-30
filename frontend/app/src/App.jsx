import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
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
import AuthWorkspace from './views/AuthWorkspace.jsx'
import AuthActions from './components/AuthActions.jsx'
import { setToken } from './platformApi.js'
import { readStoredProject } from './useProjectId.jsx'

const NAV = [
  { id: 'welcome', label: 'Home', icon: '🏠', to: '/welcome' },
  { id: 'plan', label: 'Create Plan', icon: '🧱', to: '/create-plan' },
  { id: 'cad', label: 'CAD Import', icon: '📐', to: '/cad' },
  { id: 'generative', label: 'Generate Designs', icon: '🧬', to: '/generative' },
  { id: 'survey', label: 'Survey', icon: '🌍', to: '/project/:projectId/survey', scoped: true },
  { id: 'analysis', label: 'Analyze', icon: '📊', to: '/project/:projectId/analyze', scoped: true },
  { id: 'boq', label: 'BOQ & BBS', icon: '📋', to: '/project/:projectId/boq', scoped: true },
  { id: 'carbon', label: 'Sustainability', icon: '🌱', to: '/project/:projectId/carbon', scoped: true },
  { id: 'validation', label: 'Validation', icon: '🔬', to: '/project/:projectId/validation', scoped: true },
  { id: 'building3d', label: 'Building 3D', icon: '🏢', to: '/project/:projectId/3d', scoped: true },
  { id: 'collaboration', label: 'Collaboration', icon: '🤝', to: '/project/:projectId/collaboration', scoped: true },
  { id: 'ecosystem', label: 'Ecosystem', icon: '🌐', to: '/project/:projectId/ecosystem', scoped: true },
  { id: 'governance', label: 'Governance', icon: '🏛️', to: '/project/:projectId/governance', scoped: true },
  { id: 'review', label: 'Review & Sign', icon: '✍️', to: '/project/:projectId/review', scoped: true },
  { id: 'admin', label: 'Admin', icon: '🛡️', to: '/project/:projectId/admin', scoped: true },
  { id: 'pricing', label: 'Pricing', icon: '💳', to: '/pricing' },
  { id: 'blog', label: 'Blog', icon: '✍️', to: '/blog' },
  { id: 'faq', label: 'FAQ', icon: '❓', to: '/faq' },
  { id: 'case-studies', label: 'Case Studies', icon: '📁', to: '/case-studies' },
]

function currentPid(pathname) {
  const m = pathname.match(/^\/project\/(\d+)/)
  if (m) return m[1]
  const stored = readStoredProject()
  return stored != null ? String(stored) : null
}

function Sidebar() {
  const { pathname } = useLocation()
  const pid = currentPid(pathname)
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">ع</span>
        <div className="brand-text"><strong>Imad</strong><span>Engineering Engine</span></div>
      </div>
      <nav aria-label="Workspace">
        {pid == null && (
          <div className="sidebar-hint" role="status">
            <strong>No active project</strong>
            <span>Create or select a project to unlock Survey, Analyze, BOQ & more.</span>
          </div>
        )}
        {NAV.map((item) => {
          const scopedDisabled = item.scoped && pid == null
          const to = scopedDisabled
            ? '/create-plan'
            : item.to.replace(':projectId', pid == null ? '' : pid)
          return (
            <NavLink
              key={item.id}
              to={to}
              title={scopedDisabled ? 'Create or select a project first' : undefined}
              aria-disabled={scopedDisabled || undefined}
              className={({ isActive }) =>
                `nav-item ${isActive ? 'active' : ''} ${scopedDisabled ? 'locked' : ''}`}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}
              {scopedDisabled && <span className="nav-lock" aria-hidden="true">🔒</span>}
            </NavLink>
          )
        })}
      </nav>
      <div className="sidebar-footer"><span className="version">v0.9 · Sprints 0–14</span></div>
    </aside>
  )
}

function Shell() {
  const [authMode, setAuthMode] = useState('login')
  const [signedIn, setSignedIn] = useState(() => {
    try { return !!localStorage.getItem('imad_token') } catch { return false }
  })
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const pid = currentPid(pathname)

  useEffect(() => {
    const navLang = navigator.language || navigator.userLanguage || 'en'
    const isAr = String(navLang).toLowerCase().startsWith('ar')
    document.documentElement.lang = isAr ? 'ar' : 'en'
    document.documentElement.dir = isAr ? 'rtl' : 'ltr'
  }, [])

  const current = NAV.find((n) => pathname === n.to.replace(':projectId', pid == null ? '' : pid))
  const title = current?.label || 'Imad'
  const seo = ['welcome', 'pricing', 'blog', 'faq', 'case-studies'].includes(current?.id)
  const openAuth = (mode) => { setAuthMode(mode); navigate('/auth') }
  const handleAuthed = () => { setSignedIn(true); navigate('/create-plan') }
  const signOut = () => { setToken(''); setSignedIn(false); navigate('/') }
  const pathFor = (id) => {
    const item = NAV.find((n) => n.id === id)
    if (!item) return '/create-plan'
    if (item.scoped && pid == null) return '/create-plan'
    return item.to.replace(':projectId', pid == null ? '' : pid)
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="content">
        <header className="topbar">
          {seo ? <p className="topbar-title">{title}</p> : <h1>{title}</h1>}
          <AuthActions signedIn={signedIn} onOpen={openAuth} onSignOut={signOut} />
        </header>
        <section className="workspace">
          <Routes>
            <Route path="/" element={<Navigate to="/create-plan" replace />} />
            <Route path="/welcome" element={<LandingWorkspace onNav={(id) => navigate(pathFor(id))} onAuth={openAuth} />} />
            <Route path="/auth" element={<AuthWorkspace mode={authMode} key={authMode} onDone={handleAuthed} />} />
            <Route path="/create-plan" element={<CreatePlanWorkspace />} />
            <Route path="/cad" element={<CadWorkspace />} />
            <Route path="/generative" element={<GenerativeDesignWorkspace />} />
            <Route path="/project/:projectId/survey" element={<SurveyWorkspace />} />
            <Route path="/project/:projectId/analyze" element={<AnalysisWorkspace />} />
            <Route path="/project/:projectId/boq" element={<BoqWorkspace />} />
            <Route path="/project/:projectId/carbon" element={<CarbonWorkspace />} />
            <Route path="/project/:projectId/validation" element={<ValidationWorkspace />} />
            <Route path="/project/:projectId/3d" element={<Building3DWorkspace />} />
            <Route path="/project/:projectId/collaboration" element={<CollaborationWorkspace />} />
            <Route path="/project/:projectId/ecosystem" element={<EcosystemWorkspace />} />
            <Route path="/project/:projectId/governance" element={<GovernanceWorkspace />} />
            <Route path="/project/:projectId/review" element={<ReviewWorkspace />} />
            <Route path="/project/:projectId/admin" element={<AdminWorkspace />} />
            <Route path="/pricing" element={<PricingWorkspace />} />
            <Route path="/blog" element={<BlogWorkspace />} />
            <Route path="/faq" element={<FaqWorkspace />} />
            <Route path="/case-studies" element={<CaseStudiesWorkspace />} />
            <Route path="*" element={<Navigate to="/create-plan" replace />} />
          </Routes>
        </section>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}