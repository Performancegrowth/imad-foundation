// Workflow stepper — one shared nav across all project-scoped views.
// Paths MUST match App.jsx routes (`3d`, `governance`); do not invent slugs.
const STEPS = [
  { key: 'survey', label: 'Survey', path: 'survey' },
  { key: 'create-plan', label: 'Create Plan', path: null },
  { key: 'analyze', label: 'Analyze', path: 'analyze' },
  { key: 'boq', label: 'BOQ & BBS', path: 'boq' },
  { key: 'carbon', label: 'Sustainability', path: 'carbon' },
  { key: 'building3d', label: '3D Model', path: '3d' },
  { key: 'governance', label: 'Governance', path: 'governance' },
  { key: 'review', label: 'Review & Sign', path: 'review' },
]

export function WorkflowStepper({ projectId, currentKey }) {
  return (
    <nav className="workflow-stepper" aria-label="Project workflow">
      {STEPS.map((step, i) => {
        const isCurrent = step.key === currentKey
        const href = step.path && projectId ? `/project/${projectId}/${step.path}` : step.path ? '#' : '/create-plan'
        return (
          <a
            key={step.key}
            href={href}
            aria-current={isCurrent ? 'step' : undefined}
            className={`step${isCurrent ? ' current' : ''}`}
          >
            <span className="step-num">{i + 1}</span>
            <span className="step-label">{step.label}</span>
          </a>
        )
      })}
    </nav>
  )
}
