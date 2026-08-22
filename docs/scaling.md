# Scaling & Infrastructure — Imad (عِماد)

> Audience: DevOps / platform engineers. Covers the Sprint 14 queue, cache,
> CDN and monitoring posture.

## 1. Topology

```
[Cloudflare CDN] ──> [frontend container :3000 (nginx)]
                 └─> [backend container :8000] ──> [Redis :6379] <── [worker container]
                          └──────────────────────> [SQLite volume -> PostgreSQL]
```

`docker-compose.yml` ships five services: `backend`, `frontend`, `db`
(PostgreSQL profile), `redis`, `worker`. For local development only
`backend` + `frontend` are required — Redis/worker are optional profiles.

```bash
docker compose up -d backend frontend          # minimal dev
docker compose --profile production up -d      # full stack with queue
```

## 2. Background Jobs

Two interchangeable runners behind one interface (`app/core/jobs.py`):

* **Dev default:** in-process `ThreadPoolExecutor` (`run_in_background`).
  Zero-dependency, survives for the demo profile, state visible via
  `GET /api/v1/jobs/{job_id}`.
* **Production:** Redis-backed queue consumed by the `worker` container
  (`QUEUES_BACKEND=redis`). Job payloads are small JSON envelopes; heavy
  artifacts (BOQ PDFs, IFC files) are written to the shared volume and only
  their paths are enqueued.

Long-running work that must use the queue: generative NSGA-II runs,
OpenSeesPy analysis, BOQ/LCA PDF rendering, IFC import.

## 3. Caching

* Generative design results are cached per envelope
  (`GenerativeDesignEngine.store_cache/load_cache`) — repeat requests for the
  same length×width×stories return instantly.
* Scene JSON (`/api/v1/viz/building/scene`) is deterministic per plan; put a
  `Cache-Control: private, max-age=300` header at the reverse proxy when
  plans are immutable.
* In multi-worker deployments move both caches to Redis with a 24 h TTL.

## 4. CDN (Cloudflare free tier)

1. Point a subdomain (e.g. `app.imad.engineering`) at the frontend container;
   proxy through Cloudflare (orange cloud).
2. Cache rules: `CacheEverything` for `/assets/*` (Vite hashed filenames are
   immutable — safe to cache 1 year); **bypass** for `/api/*` and `/download`.
3. Enable Brotli, HTTP/3, and the free TLS edge certificate.
4. Optional R2 binding: set `STORAGE_BACKEND=r2` and the three `R2_*` vars in
   `.env` to move uploads/exports off local disk (Sprint 1 hook already
   abstracts this behind `app/core/storage.py`).

## 5. Monitoring

* **Sentry (free tier):** set `SENTRY_DSN`; `app/main.py` initialises the SDK
  when present. FastAPI + worker both report.
* **Health endpoints:** `GET /health` (backend liveness), worker exposes the
  same via `python -m app.worker healthcheck`.
* **Metrics placeholder:** `/api/v1/platform/metrics` returns job counters
  (queued/running/failed) — scrape with a cron → Prometheus Pushgateway until
  a first-class `/metrics` lands.
* Log shape: structured single-line JSON on stdout (`logger` names
  `imad.*`), ready for any aggregator.

## 6. Database Growth Path

SQLite (dev) → PostgreSQL (compose `db` service). All models are declarative
SQLAlchemy; switching is a `DATABASE_URL` change plus `schema.sql` replay.
The JSON document store (`app/core/docstore.py`) mirrors a tiny document DB —
collections map 1:1 to future PostgreSQL tables when volume demands it.

## 7. Data Retention Policy

| Data class | Retention | Basis |
|---|---|---|
| Project files & results | until project deletion + 30 days | user contract |
| Audit log | 7 years, append-only | regulatory defence |
| Anonymised design snapshots | indefinite (no PII by construction) | product analytics |
| Job status records | 30 days rolling | operational |
| Support chat transcripts | 90 days | quality assurance |

Deletion requests remove the project record, its files and its snapshots;
audit entries are retained in redacted form (hash-chain preserved).

## 8. Capacity Notes

* NSGA-II (pop 50 × 100 gen) on a 2-vCPU worker: ~25–45 s for simple
  buildings — one worker slot per run; scale workers horizontally.
* OpenSeesPy analysis: <5 s per typical frame; memory <300 MB.
* BOQ/PDF rendering: <2 s; CPU-bound, safe to run inline if queue is down
  (feature-flagged fallback).
