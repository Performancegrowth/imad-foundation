# Imad Frontend — Engineering Workspace (Sprints 2–5)

A professional React + Three.js single-page workspace for the Imad engineering
engine: CAD import/processing, plan creation (questionnaire / templates / AI),
site survey, and structural analysis with a 3D view.

## Stack

- **React 18** + **Vite 5**
- **Three.js** — 3D structural viewer
- **Native HTML5 Canvas** — 2D plan viewer (shared drawing in `src/planUtil.js`)

## Setup & Run

```bash
cd frontend/app
npm install
npm run dev
# → http://localhost:5173
```

The Vite dev server proxies `/api` to the FastAPI backend on `:8000`, so start
the backend first (see the repo-root README, or from `backend/`):

```bash
cd ../../backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Structure

```
src/
├── api.js                      # typed API client (CAD, plans, survey, analysis)
├── planUtil.js                 # shared 2D canvas drawing pipeline
├── App.jsx                     # shell + navigation
├── styles.css                  # design-system tokens & components
├── components/
│   ├── PlanViewer.jsx          # 2D plan canvas (walls/beams/columns/grid)
│   └── StructureViewer.jsx     # Three.js 3D colour-coded model
└── views/
    ├── CadWorkspace.jsx        # upload → process → extract
    ├── CreatePlanWorkspace.jsx # questionnaire / templates / AI description
    ├── SurveyWorkspace.jsx     # manual geotech form + file import + summary
    └── AnalysisWorkspace.jsx   # analyze → 3D model, forces, design, BOQ
```

## Design System

- Primary `#0A5C36`, secondary `#C9A227`, canvas `#F5F7FA`, dark `#111827`
- Inter + IBM Plex Sans Arabic web fonts
- Cards, data tables, badges, pills, empty/loading/error states, responsive grid

## Notes

- The "Analyze Demo Frame" button needs no saved plan, so the 3D viewer and
  results are exercisable immediately.
- Natural-language plan generation calls a local Ollama model at
  `localhost:11434` if running; otherwise the endpoint returns a clear 503.
