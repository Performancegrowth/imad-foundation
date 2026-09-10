# Imad — Current State (Audit Date: 2026-09-10)

## 1. What Imad Is (2-3 sentences, factual only)

Imad (عِماد) is a FastAPI + React/Vite structural-engineering platform: plan intake (DXF/image/IFC, questionnaire, templates, Ollama NL) → analytic/OpenSees structural analysis with ACI 318-19 concrete design → BOQ/BBS, embodied-carbon LCA, SBC 304 compliance + submission packages, Three.js 3D viewer, plus collaboration, marketplace, billing, and background jobs. Persistence is SQLite (`database/schema.sql`) + JSON file stores (`backend/storage/`: plans, survey, results, jobs, audit, exports, db); Docker Compose adds Redis, a Python worker, Ollama, and nginx.

## 2. Verified Working (from Table A)

Table A — end-to-end (backend route → service → view → test). Auth column: only `plans/*` (data routes) and `projects/*` require a bearer token; everything else is public.

| # | Feature | Backend endpoint(s) | Service(s) | Frontend view → client → call | Test status |
|---|---------|---------------------|------------|-------------------------------|-------------|
| 1 | Register / login / refresh, project CRUD | `POST /register`, `POST /token`, `POST /refresh`; `GET/POST /projects`, `GET /projects/{id}` (auth required) | `core/security.py` (PBKDF2 + HS256 JWT), SQL over `schema.sql` | `AuthWorkspace.jsx` → `platformApi.js` `login/register`; `CreatePlanWorkspace.jsx` → `api.js` `listProjects/createProject` | Covered by `e2e_audit.py` script (not pytest); no pytest auth file |
| 2 | Plan intake: questionnaire / template / NL description | `GET /plans/templates` (public); `POST /plans/questionnaire`, `POST /plans/template`, `POST /plans/description` (auth); `POST /plans/save`, `GET /plans/{project_id}`, `GET /plans/{project_id}/{name}` (auth + owner check) | `services/noncad_processor.py` (`PlanGenerator`), `services/ai_provider.py` (`OllamaLocalProvider`, 120 s timeout, 503 when Ollama down) | `CreatePlanWorkspace.jsx` → `api.js` `generateQuestionnaire/generateTemplate/generateDescription/savePlan/listPlans` | `test_plans.py` passes (template lib ≥5, questionnaire, save/load) |
| 3 | CAD / image / IFC upload + extract | `POST /files/upload`; `POST /process-cad`; `POST /ifc/import`, `POST /ifc/export` | `core/storage.py` (`save_upload`), `services/cad_processor.py` (`EzdxfCADProcessor` S-WALLS/S-COLUMNS/S-BEAMS, `ImageCADProcessor` OpenCV, `IfcCADProcessor` ifcopenshell-or-regex), `services/geometry_utils.py` (`enrich_plan`), `services/bim_service.py` | `CadWorkspace.jsx` → `api.js` `uploadFile/processCad`; IFC import via `api.js` `importIfc` (`/ifc/import`) | `test_cad_processor.py`, `test_ifc_processor.py` pass (incl. name-fallback parse) |
| 4 | Survey: manual + file import + summary | `POST /survey/manual`, `POST /survey/upload` (pdf/csv/dxf/las/laz), `GET /survey/{project_id}` (all public) | `services/survey_processor.py` (`ManualSurveyProcessor`, `FileSurveyProcessor`), lateral fields (`ss/s1/site_class/R`, wind speed/exposure) flow into analysis | `SurveyWorkspace.jsx` → `api.js` `saveSurveyManual/uploadSurvey/getSurvey` | `test_survey.py` passes |
| 5 | Structural analysis + concrete/steel design | `POST /analyze` (public; `options.async` → job) | `services/structural_engine.py` (`OpenSeesEngine`, analytic fallback), `services/concrete_design.py` (flexure/shear/dev-length/stairs, real bar cages), `services/lateral_loads.py` (SBC 301 §12.8 ELF + ch.27 wind, no hardcoded Cs), `services/load_combinations.py` (LC1–LC6), `services/foundation_design.py` (#13 isolated footings) | `AnalysisWorkspace.jsx` → `api.js` `analyze` + auto `getComplianceReport`; demo-frame button works with no saved plan | `test_structural.py`, `test_load_combinations.py`, `test_lateral_loads.py`, `test_concrete_bars.py`, `test_shear_9d.py`, `test_stair_design.py` pass |

| 6 | Generative design (NSGA-II top-3) | `POST /generate-designs`, `GET /generate-designs/status/{id}`, `GET /generate-designs/{id}/recommendation`, `POST /generate-designs/select` (public, bg thread + cache) | `services/generative_design.py` (`_real_fitness` via analyze-BOQ-LCA-compliance), `services/ai_provider.py` fallback | `GenerativeDesignWorkspace.jsx` → `api.js` + cost/carbon/flexibility slider | `test_generative_design.py` passes |
| 7 | BOQ + BBS + PDF/XLSX exports | `POST /generate-boq`, `GET /generate-boq/{result_id}`, `POST /generate-boq/{result_id}/export/pdf\|xlsx`, `GET /exports/download` (public, traversal-guarded) | `services/boq_generator.py` (BBS, ≤2% cutting-stock), `services/exporters.py` | `BoqWorkspace.jsx` → `api.js` `generateBoq/exportBoqPdf/exportBoqXlsx/downloadUrl` | `test_wiring_9c.py` + smoke xlsx pass |
| 8 | Carbon LCA + green alternatives | `POST /carbon-report`, `POST /carbon-report/lca-pdf` (public) | `services/carbon_calculator.py` (ICE v3.0/worldsteel, GGBS/PFA/EAF, LEED/Mostadam/Estidama) | `CarbonWorkspace.jsx` → `api.js` `carbonReport` + `downloadUrl(report.lca_pdf)` | No carbon test file; via generative + smoke |
| 9 | 3D building viewer (engineer/customer) | `POST /viz/building/scene`, `POST /viz/building/gltf` (public; resolves latest plan + analysis) | Inline `_build_three_js_scene` in `api/visualization.py`; `building_scene.py`/`visualization_service.py` NOT imported | `Building3DWorkspace.jsx` → `platformApi.js` `getVisualizationData` (`/viz/building/scene`); `StructureViewer.jsx` in Analysis | No pytest file; e2e script only |
| 10 | SBC 304 compliance (13 checks) | `POST /compliance/check`, `POST /compliance/sbc304-package`, `GET /compliance/sbc304-readiness/{project_id}` (public) | `services/compliance_engine.py` (slab §7.6.1.1, beam §9.6.1.2, deflection, column 1–8%, ELF real Cs, wind, §22.4, §22.6 punching, §22.5 shear, §25.4.2 ld, #9f cross-check, foundations, stairs), `cross_check.py` (EC2 ±20%), `sbc304_report.py` (builder only) | `GovernanceWorkspace.jsx`; `AnalysisWorkspace.jsx` auto-run + badge; `ReviewWorkspace.jsx` checklist | `test_compliance_engine.py` (13 checks), `test_cross_check.py` pass |
| 11 | Submission packages + DOCX note | `POST /submission/generate`, `GET /submission/{ref}` (dual numeric/id), `POST /submission/{id}/status`, `POST /submission/{id}/export/docx` (public) | `services/sbc304_report.py`, `services/exporters.py` (`submission_docx`), docstore | `GovernanceWorkspace.jsx` → `getSubmissionPackage/transitionSubmission/exportSubmissionDocx/downloadExport` | Smoke submission + docx pass |
| 12 | E-sign + audit trail | `POST /signature/request` (role string engineer/admin/owner), `GET /signature/{id}`, `POST /signature/{id}/complete`; `GET /audit-log/{project_id}` | `core/audit.py` (SHA-256 hash-chained log), `exporters.build_pdf_report` seal PDF | `ReviewWorkspace.jsx` + `GovernanceWorkspace.jsx` audit tables | Smoke-covered; no dedicated test |
| 13 | Validation benchmark suite | `POST /validation/run`, `GET /validation/report`, `GET /validation/report/pdf` (public) | `services/validation_engine.py` (beam UDL / column / 2-storey ELF vs hand calc, 5% pass / 5–10% warn) | `ValidationWorkspace.jsx` is a RETIRED redirect to Governance (see Table B); API live | No pytest file; smoke hits run+report |
| 14 | IFC/BIM + comments/approvals/tasks/notifications/webhooks | `POST /ifc/export`, `POST /ifc/import`, `GET/POST/PATCH /bcf/issues`, `GET/POST/PATCH /comments`, `GET/POST /approvals` + `/approvals/{id}/transition`, `GET/POST/PATCH /tasks` (+DELETE), `GET /notifications` + `POST /notifications/{id}/read`, `GET/POST/DELETE /webhooks` (public) | `services/bim_service.py` (built-in IFC4 SPF writer; ifcopenshell import optional) | `CollaborationWorkspace.jsx` uses comments + tasks only (authors hardcoded `Demo User`); IFC/BCF/approvals/webhooks have no view | `test_ifc_processor.py` passes; smoke skips collab |
| 15 | Ecosystem: snapshots, costs, suppliers, consultants, certification | `POST /design-data/snapshot`, `GET /analytics/design`, `/costs`, `/costs/import`, `/suppliers`, `/consultants`, `/consultants/request-review`, `/consultants/requests/{pid}`, `/certification/quiz`, `/certification/complete` (public) | docstore collections; region hashed, PII stripped | `EcosystemWorkspace.jsx` (supplier filter, consultant cards + `alert()` on review, cost table) | No pytest file; smoke hits `/suppliers` only |
| 16 | Billing catalog, sandbox checkout, API keys, white-label, analytics | `GET /plans`, `GET /subscriptions/{email}`, `POST /subscriptions/upgrade`, `POST /payments/checkout`, `POST /payments/webhook` (unverified), `POST/GET/DELETE /api-keys/*`, `GET/PUT /whitelabel/{email}`, `GET /analytics` (public) | `services/subscriptions.py` (`PLANS`, `ROLE_MATRIX`, `create_checkout_placeholder`) | `PricingWorkspace.jsx` (`pApi.currentSubscription/upgradeSubscription`, sandbox notice); `AdminWorkspace.jsx` (analytics + plans) | No pytest file; smoke skips billing |
| 17 | Jobs queue + tutorials + support chat | `GET /jobs` + `GET /jobs/{job_id}` (platform) AND `GET /jobs/{job_id}` + `GET /jobs/{job_id}/result` (jobs router — duplicate, platform wins); `GET /tutorials`; `POST /support/chat` (also in agents router — platform wins) | `core/jobs.py` (disk JSON + optional Redis `imad:jobs`), `core/worker.py` (BLPOP for analysis/boq/carbon), `services/agents.py` (Ollama + template fallback) | No jobs view; `platformApi.js` status helpers, agents via `endpoints.js`/`platformApiOps.js` | No pytest file |
| 18 | Section designer | `POST /sections/analyze` (public) | `services/section_designer.py` (sectionproperties when present, else closed-form rect/circle/I/tee/channel) | No view calls it (dead from UI) | `test_section_designer.py` passes (incl. API test) |
| 19 | SEO/public pages | n/a (static) | `seoData.js` (JSON-LD org/software/FAQ) | `Landing/Blog/Faq/CaseStudies/Pricing` render; Blog (4 posts) + Case Studies (3) hardcoded arrays | n/a |

## 3. Incomplete / Placeholder (from Table B)

- RED `POST /payments/*` is a Stripe **sandbox placeholder** — `services/subscriptions.py:150` `"Stripe *sandbox* placeholder — swap for stripe.checkout.Session.create."`, `api/billing.py:80` `# TODO(S9C): stripe.Webhook.construct_event(...)`; webhook returns `{"received": True, "mode": "sandbox"}` with no signature check. Pricing UI admits: `"Stripe sandbox placeholder — no payment taken"`. No real money can move.
- RED AuthZ gap: only `projects/*` and `plans/*` (data routes) enforce `Depends(_current_uid)` / owner checks. `POST /analyze`, `/generate-boq`, `/carbon-report`, `/generate-designs`, `/compliance/*`, `/submission/*`, `/survey/*`, `/files/upload`, and ALL Sprint 11–14 routers take no token. Any client can run engines and read/write other projects' docstore data.
- ORANGE Duplicate route shadowing: `GET /jobs/{job_id}` in BOTH `platform.py:66` and `jobs.py:23` (platform included first in `api/__init__.py:27,39`, so `jobs.py`'s version is unreachable); `POST /support/chat` in BOTH `platform.py:79` and `agents.py:59` (platform wins, agents alias dead). Quoted: `agents.py:59 @router.post("/support/chat", include_in_schema=False) # Sprint 14 alias`.

- ORANGE Stale/dead frontend clients: `frontend/app/src/endpoints.js` (postTry/getTry layer) is imported by no view; `api.js` `buildingScene/buildScene/exportGltf` point at `/building/scene` + `/building/gltf`, but backend only serves `/viz/building/*` (works because `Building3DWorkspace` uses `platformApiOps.getVisualizationData` → `/viz/building/scene`); `platformApi.js` wrappers `analyzeStructure(designId)`, `generateBoq(designId)`, `getBoq(designId)`, `generateCarbonReport(designId)` send `{design_id}` which backend schemas (`AnalyzeRequest`, `GenerateBOQRequest`, `CarbonReportRequest`) do not accept → 422 if ever called. No view calls them.
- ORANGE Unwired services: `services/visualization_service.py` (`VisualizationService`) and `services/building_scene.py` (`build_3d_scene/export_gltf`) are never imported by `api/visualization.py` (router has its own `_build_three_js_scene`); `services/foundation_design.py::design_foundations` IS imported by `structural_engine.py`, but the isolated-footing #13 path surfaces only via analysis payload/compliance, with no dedicated route or view.
- ORANGE `ValidationWorkspace.jsx` is a retired redirect, not a feature: lines 1–4 `"Code-compliance checking has moved to the Governance tab... This page now only redirects."` It still occupies the `/project/:id/validation` nav slot. Backend validation API is live but has no UI.
- YELLOW E-sign providers are stubs: `governance.py:631-635` labels are `"DocuSign (sandbox)"` / `"Adobe Sign (sandbox)"`; `docs/security.md:90` table: `DocuSign / Adobe Sign | stub | ... webhook handler pending`. `ReviewWorkspace.jsx:34` hardcodes `engineer_name: 'Demo Engineer', license_number: 'SCE-1001'`; `CollaborationWorkspace.jsx:34,38` hardcodes `author/assignee: 'Demo User'`.
- YELLOW `AdminWorkspace.jsx` is half-wired: user table always hits `EmptyState ... "Role-based access management requires an admin users endpoint."` (no such endpoint exists); System Health badges are hardcoded (`API Operational v0.5.0`, `Database Operational SQLite`, `Monitoring Placeholder Sentry / Cloudflare`); analytics keys are guessed via `metric([...])` fallbacks.
- YELLOW Content pages are static: `BlogWorkspace.jsx` `POSTS` (4 articles) and `CaseStudiesWorkspace.jsx` `CASES` (3 stories) are in-file constants; `ROADMAP_TO_CODE_MAP.md #1/#2` (blog/case-study APIs) was never built — no `/blogs` or `/case-studies` routes exist. Pricing math (`PricingCard.jsx` annual `*12*0.85`) disagrees with `subscriptions.py` yearly prices (e.g. Office 2870 vs 299*12*0.85=3054).
- YELLOW Unit-safety theater: `pint>=0.24` is installed and `core/units.py` + `test_units.py` pass, but NO service imports `app.core.units` (verified via service import scan); all engine math uses raw floats. `ROADMAP #3` status is accurate: present, not wired.
- GREEN Docs drift (low, but quoted): `docs/security.md:11` claims `passlib (bcrypt)` — code uses stdlib PBKDF2 (`core/security.py`); `docs/security.md:9,13` claims `POST /api/v1/auth/login` + `get_current_user` per-request — real paths are `/register|/token|/refresh` and most routers have no auth; `docs/scaling.md:14` claims `db (PostgreSQL profile)` and `alembic.ini` is copied in Docker, but `backend/migrations/versions/` is EMPTY and `start.sh:9` `alembic upgrade head` is a no-op; `database/schema.sql` `survey_data` columns do not match `SurveyReading` (no `soil_bearing_capacity_kpa`, seismic, or wind columns — survey persists via JSON files, not SQL); old `README.md` sprint table marks all 15 sprints done and `frontend/app/README.md` documents only 4 views.
- GREEN Frontend build warnings (non-blocking, exit 0): 4x `[plugin:vite:esbuild] ... Building3DWorkspace.jsx: The character ">" is not valid inside a JSX element` on line 176 (`green -> lime -> yellow -> orange -> red` inside a `<p>` — renders as text but should be escaped); bundle `dist/assets/index-CgejlxTk.js 800.21 kB` (>500 kB warning, three.js, no code-splitting).

## 4. Tech Stack (as actually installed, not as planned)

Backend (`backend/requirements.txt`, top 10 by importance):
1. `fastapi>=0.110` + `uvicorn[standard]` — API + server (`app/main.py` v0.5.0, `/api/v1`, `/health`, `/docs`)
2. `SQLAlchemy>=2.0` + `aiosqlite` — auth/projects SQL over `database/schema.sql` (SQLite default `sqlite:///./imad.db`); everything else is JSON docstore/files
3. `pydantic[email]>=2.6` + `pydantic-settings` — models/schemas/config (note: `orm_mode`/`class Config` deprecation warnings, ignored per instructions)
4. `PyJWT` + `python-jose` + `passlib` — JWT auth (code actually uses PBKDF2 via stdlib + `jwt` encode/decode)
5. `openseespy>=3.5` + `scipy` — structural engine (analytic fallback is what tests exercise)
6. `structuralcodes>=0.7,<0.8` — #9f EC2 cross-check (needs Python ≤3.12; see §5)
7. `ezdxf`, `opencv-python`, `numpy`, `pandas`, `Pillow`, `img2pdf`, `shapely>=2.0` — CAD/image/geometry
8. `pdfplumber`, `geopandas`, `laspy`, `rasterio` — survey file import
9. `deap` (NSGA-II), `reportlab`, `openpyxl`, `xlsxwriter`, `python-docx` — generative + PDF/XLSX/DOCX exports
10. `redis`, `celery`, `alembic`, `pytest`, `httpx`, `pint`, `requests`, `python-multipart`, `email-validator` — queue (optional), migrations (empty), tests, units (unused in engine)

Frontend (`frontend/app/package.json`): `react ^18.3.1`, `react-dom ^18.3.1`, `react-router-dom ^7.18.3`, `react-helmet-async ^3.0.0` (SEO), `three ^0.165.0` (3D), dev `vite ^5.3.4` + `@vitejs/plugin-react ^4.3.1`. No chart, form, or state library (custom SVG charts in `components/ui.jsx`).

External services: Redis 7 (`imad:jobs` list; optional — `queue_available()` false without `REDIS_URL`, API defaults to sync + threads); Ollama (`http://localhost:11434`, `qwen2.5:0.5b`; graceful 503/rule-based fallback everywhere); SQLite file DB (`./imad.db` + `backend/imad.db`); no Postgres, no Sentry, no Stripe, no DocuSign (all documented placeholders).
## 5. Test & Build Status

- Pytest: **142 passed / 0 failed** in **37.35s** via `backend\.venv\Scripts\python.exe -m pytest -q` (Python **3.12.14**; 12 warnings — 10x Pydantic `class Config`/`orm_mode`, 1x `starlette.testclient`/httpx, 1x anyio portal; `orm_mode → from_attributes` ignored per instructions). 19 test files: cad, compliance (13 checks), concrete bars, cross-check, generative, geometry, IFC, lateral loads, load combos, plans, section designer (+API test), shear #9d, smoke routers, stair, structural, survey, units, wiring #9c. Gaps: no pytest files for auth/projects, billing, ecosystem, collaboration, validation suite, jobs/platform, carbon standalone.
- Frontend build: **PASS, exit 0, ~7.4 s** via `cd frontend/app; npm run build` → `dist/index.html 0.90 kB`, `index-BW6favmr.css 13.51 kB`, `index-CgejlxTk.js 800.21 kB (gzip 221 kB)`; warnings only (4x JSX `>` on `Building3DWorkspace.jsx:176`, 1x >500 kB chunk).
- Git: clean tree (`git status --short` empty). Last commit `4d7d036ea9d0f023a414d6ccb05fbe5b01feb8e5` — `feat: real ACI 318-19 isolated footing design (compliance check #13)` — date 2026-09-10. Recent log (`git log --oneline -20`, head): `4d7d036` footing #13, `8269a7f` stair module, `b59cd91` analysis→3D + generative→plans wiring, `49c24fc` #31 building viewer, `726d462` #20 slider re-rank, `e5e6541` #10 real-engine validation, `7c60ec5` seismic/wind survey fields, `da8653f` column steel/occupancy/Ec fix, `8d5dbb4` real-Cs base shear + wind, `2e499ac` #9e lateral-load infra, `7e81819` real deflection/slab, `266c307` auto compliance + retire validation, `8d5a9f4` #9f cross-check + py3.12 venv, `f7e14dd` #9d shear + ld, `e6e0470` #9c SBC/BBS wiring, `38dad66` #9c bar selection, `486565f` #9b punching + §22.4.
- Scratch tests: **none**. No `backend/_test_*.py`, no `_test_*` under `backend/app` or `backend/tests`. Root `e2e_audit.py` is a tracked stdlib end-to-end probe script (register→plans→survey→analyze→boq→carbon→viz→validation), not a pytest file and not run in this audit (backend not served live here).

## 6. Architecture Diagram (ASCII)

```
Browser (React/Vite, :5173 → nginx :80 → backend:8000)
  views/*.jsx ── api.js / platformApi.js (+apiClient.js) ── /api/v1/*
       │  CreatePlan/CAD/Survey/Analysis/BOQ/Carbon/3D/Governance/...
       ▼
FastAPI app/main.py ── api/__init__.py (prefix /api/v1, NO global auth)
  auth/projects/plans ── Depends(_current_uid) ── SQLite (schema.sql)
  analyze/boq/carbon/generative ── services/ ── storage/*.json (results/jobs)
       structural_engine → concrete_design → compliance_engine
              │                  │                    │
              ▼                  ▼                    ▼
        lateral_loads/    foundation_design      sbc304_report
        load_combinations cross_check            exporters (pdf/xlsx/docx)
  survey/cad/upload ── processors ── storage/uploads + plans/
  governance ── docstore (signatures/submissions/checks) + audit chain
  collab/ecosystem/billing/platform/jobs ── docstore collections
       │
       ▼ (optional) REDIS_URL=redis://redis:6379/0, queue imad:jobs
  worker (python -m app.core.worker, BLPOP) ── run_analysis/run_boq/run_carbon
       │
  Ollama :11434 (qwen2.5:0.5b) ── NL plans, recommendations, agents
       (every LLM call has deterministic fallback; engines never trust LLM numbers)
```

## 7. Known Gaps (top 10, ranked by impact)

1. Payments are fake (Stripe sandbox, unverified webhook) — cannot monetize; blocks all revenue.
2. Authorization missing on ~17/20 routers — engines, BOQ/carbon, compliance, submissions, survey, uploads, and all collaboration/marketplace/admin data are world-readable/writable.
3. No live backend verification in this audit (pytest + build only); `e2e_audit.py` expects a served backend and was not executed — runtime 500s/503s (Ollama) unproven here.
## 8. How to Run Locally

Exact PowerShell (Windows) commands from repo root `C:\Users\Asus\Desktop\imad`:

```powershell
# Backend (canonical venv per this repo: backend/.venv, Python 3.12.14)
backend\.venv\Scripts\python.exe -m pytest -q
$env:PYTHONPATH = "backend"
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# NOTE: run uvicorn from backend/ so `app.main` resolves; open http://localhost:8000/docs

# Frontend (separate shell; backend must be up first — Vite proxies /api → :8000)
cd frontend/app
npm install
npm run dev      # → http://localhost:5173
npm run build    # production check (exit 0; expect JSX ">" warnings + >500 kB chunk note)

# Full stack (needs Docker Desktop + .env)
Copy-Item .env.example .env
docker compose up --build
# services: backend :8000, frontend :5173→80, redis :6379, ollama :11434, worker

# Optional live E2E probe (backend must be serving first)
backend\.venv\Scripts\python.exe e2e_audit.py
```

Env notes: `.env.example` defaults work for SQLite + local Ollama; `SECRET_KEY`/`JWT_SECRET_KEY` must be rotated before any shared deployment; `REDIS_URL` unset = sync execution (no worker needed); Ollama absent = NL/recommendation/agents fall back deterministically (analysis/BOQ/carbon still run).

## 9. Next Sprint Candidates (from the gaps)

1. **Enforce authZ on all project-scoped routers (impact × ease: highest).** Add the existing `plans._current_uid`/`_require_owner` pattern (or a shared dependency) to analyze/boq/carbon/generative/compliance/submission/survey/upload/collaboration/ecosystem/billing reads, and scope docstore records by `owner_id`. Small diff, kills the biggest security hole; verify with new `test_authz.py` (unauthenticated → 401, cross-owner → 404).
2. **Make one job route true and delete the shadows (high × trivial).** Keep a single `GET /jobs/{job_id}` (+ `/result`), a single `POST /support/chat`, remove `endpoints.js`, fix `api.js` viz paths to `/viz/*`, and delete or repair the `{design_id}` wrappers. Prevents the next bug being built against a dead endpoint.
3. **Stripe minimum-viable-real checkout behind the existing sandbox seam (high × medium).** `create_checkout_placeholder()` already returns the future shape; swap in `stripe.checkout.Session.create`, verify `payments/webhook` signatures, flip `Subscription` on `checkout.session.completed`, and keep the sandbox path for dev. Unlocks revenue without API churn.

