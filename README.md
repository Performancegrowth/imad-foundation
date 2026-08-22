# Imad · عِماد — The Autonomous Engineering Engine

> A professional, web-based structural-engineering SaaS: from CAD scans, questionnaires,
> templates or plain text, Imad produces validated structural designs, costed BOQs,
> sustainability reports, compliance packages and a live 3D model — with full audit,
> collaboration and marketplace features.

## Features

**Input & Modelling**
- CAD import (DXF) and image/PDF plan extraction (walls, columns, beams, grids)
- Non-CAD plan builder: guided questionnaire, template library, natural-language layout (Ollama), 2D editor
- Survey integration: manual geotech readings plus PDF/CSV/DXF/LAS file import

**Engineering**
- Structural analysis (OpenSeesPy) with an analytic fallback, ACI 318 concrete design
- Generative design (NSGA-II via DEAP) → top alternatives by cost, carbon, flexibility, safety
- BOQ + BBS with cutting optimisation; PDF & Excel exports

**Sustainability**
- Embodied-carbon calculator, green alternatives (GGBS, recycled steel), LCA report, LEED/Mostadam/Estidama alignment

**Visualisation**
- Live 3D building (Three.js): floor selector, structural/finished toggle, glTF export

**Review, Validation & Compliance**
- Engineering validation benchmark suite (hand-calc comparison, accuracy score)
- SBC 304 compliance engine, digital seal/signature, municipality submission packages
- Immutable hash-chained audit trail

**BIM, Collaboration & Workflow**
- IFC import/export, BCF issue tracking, comments, approvals, kanban tasks, notifications, plugin webhooks

**Ecosystem & Marketplace**
- Anonymised design database + analytics, regional cost database, supplier directory, licensed-consultant marketplace, certification quiz

**Platform & Enterprise**
- JWT auth, role-based access, rate limiting, background job queue, API keys, white-label
- Subscription plans (Free / Pay-Per-Project / Office / Enterprise), Stripe sandbox placeholders
- AI agents: sales, marketing, support chatbot; tutorials & support chat

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · SQLite (Postgres-ready) |
| Structural | OpenSeesPy (analytic fallback) |
| AI | Ollama (AIProvider) · agents · support chatbot |
| Optimisation | DEAP (NSGA-II) |
| Reporting | ReportLab · XlsxWriter / OpenPyXL |
| BIM | ifcopenshell · custom IFC SPF writer |
| Frontend | React 18 · Vite · Three.js |
| Ops | Docker Compose · Redis · nginx |

## Local setup

**Backend**
```bash
cd backend
pip install -r backend/requirements.txt
cp ../.env.example ../.env      # set SECRET_KEY, DATABASE_URL
uvicorn app.main:app --reload   # → http://localhost:8000/docs
```

**Frontend**
```bash
cd frontend/app
npm install
npm run dev                     # → http://localhost:5173
```

**Docker** (full stack, including Redis + worker)
```bash
cp .env.example .env
docker compose up --build
```

**Tests**
```bash
cd backend
pytest
```

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | JWT signing secret | dev-insecure (change!) |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./imad.db` |
| `APP_ENV` | development / staging / production | development |
| `MAX_UPLOAD_SIZE_MB` | Upload gate | 128 |
| `AI_PROVIDER` | openai / anthropic / ollama | openai |
| `REDIS_URL` | Queue broker (Docker) | redis://redis:6379/0 |
| `VITE_APP_API_BASE` | Frontend API base | /api/v1 |

## Project structure

```text
imad/
├── backend/app/
│   ├── core/       config, security, database, jobs, ratelimit, docstore, audit, worker
│   ├── models/     SQLAlchemy + PlanData/survey contracts + business entities
│   ├── schemas/    Pydantic request/response models
│   ├── api/        versioned routers (auth → ecosystem)
│   └── services/   structural, generative, boq, carbon, compliance, bim, agents...
├── backend/tests/  pytest unit + smoke suites
├── frontend/app/   React + Vite SPA (16 workspaces)
├── database/schema.sql
├── docker/         Dockerfiles + nginx conf
├── docker-compose.yml
└── docs/           validation, security, scaling, monetization, api, plugins
```

## Sprints progress

| Sprint | Deliverable | Status |
|---|---|---|
| 0  | Repo scaffold, design system, Docker | ✅ |
| 1  | Auth/JWT, projects, upload, dashboard | ✅ |
| 2  | CAD / OpenCV plan extraction | ✅ |
| 3  | Non-CAD plans (questionnaire / template / NL) | ✅ |
| 4  | Survey & site data | ✅ |
| 5  | Structural analysis + ACI design + BOQ | ✅ |
| 6  | Generative design (NSGA-II) | ✅ |
| 7  | BOQ / BBS + PDF / Excel | ✅ |
| 8  | Carbon & sustainability | ✅ |
| 9  | 3D building, AI agents, subscriptions | ✅ |
| 10 | Compliance, e-signatures, audit | ✅ |
| 11 | Validation & certification | ✅ |
| 12 | BIM / IFC, collaboration, plugins | ✅ |
| 13 | Ecosystem & marketplace | ✅ |
| 14 | Enterprise security, queue, monetization | ✅ |

## License

MIT (placeholder — to be finalised).

## Contributors

Built by structural and software engineers. Contributions welcome — see CONTRIBUTING (TBD).