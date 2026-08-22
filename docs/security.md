# Security Model — Imad (عِماد)

> Audience: engineering leads, security reviewers, IT administrators.
> Scope: Sprint 14 enterprise-hardening layer and the governance controls
> introduced in Sprint 10.

## 1. Authentication

* **JWT bearer tokens** issued by `POST /api/v1/auth/login` (HS256, `JWT_SECRET`
  from environment). Access tokens are short-lived; `POST /api/v1/auth/refresh`
  mints new ones. Passwords are hashed with passlib (bcrypt) — never stored or
  logged in plaintext.
* Tokens are validated on every request by the `get_current_user` dependency.
* **Production checklist:** rotate `JWT_SECRET`, serve over TLS only, set
  `secure`/`HttpOnly` cookie flags when moving tokens out of localStorage.

## 2. Role-Based Access Control (RBAC)

Roles are declared in `app/models/business.py` (`RoleName`) and enforced in
`app/core/security.py`:

| Role | Capabilities |
|------|--------------|
| `owner` | everything, including billing and white-label settings |
| `admin` | user/role management, analytics, agent tools, API keys |
| `engineer` | create/edit designs, run analysis, **request signatures** |
| `reviewer` | compliance checks, approvals, **approve & sign** (licensed) |
| `viewer` | read-only dashboards and exports |

**Signing is restricted to `reviewer`/`admin` roles with a license number on
file** — enforced server-side in `POST /api/signature/request`; the frontend
merely hides the control (never trust the client).

## 3. Rate Limiting

`app/core/ratelimit.py` implements a sliding-window limiter keyed on
`(client_ip, route-group)`:

* auth endpoints: 10 req/min
* analysis / generative jobs: 6 req/min (they enqueue background work)
* default API: 120 req/min

Headers `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `Retry-After` (on
429) are returned. In multi-worker deployments back the limiter with Redis
(see `docs/scaling.md`).

## 4. Audit Trail (immutable, append-only)

`app/core/audit.py` writes hash-chained records to `storage/db/audit_log.json`:

```
entry_n.hash = sha256(entry_n.payload + entry_{n-1}.hash)
```

* `log_action(action, project_id, user, details)` is the **only** write path;
  there is no update or delete API by design.
* `GET /api/v1/audit-log/{project_id}` exposes a read-only view.
* `verify_chain()` recomputes the chain to detect tampering — wire it to a
  scheduled job and alert on failure.

Logged events include: login, register, upload, CAD processing, plan
creation, analysis runs, generative runs, BOQ/carbon exports, signature
requests, submissions, subscription changes, and admin operations.

## 5. API Keys (machine access)

`POST /api/v1/api-keys/generate` returns the **full key exactly once**;
storage keeps only a SHA-256 hash plus a display prefix (`imad_live_ab12…`).
Keys carry scopes (`read`, `analyze`, `export`, `admin`) and can be revoked
but never rotated in place — generate a new key instead. Clients send
`Authorization: Bearer <api-key>`; the platform distinguishes user JWTs from
machine keys by prefix.

## 6. Data Protection

* Uploads live under `storage/uploads/` with sanitized, randomised names —
  original filenames are metadata only.
* Export downloads are constrained to the `storage/exports/` directory
  (path-traversal guarded in `/api/v1/exports/download`).
* Design snapshots stored for the data-moat (Sprint 13) are anonymised at
  ingestion: no client names, addresses, coordinates or project identifiers
  ever leave the project record (see `docs/scaling.md` §retention).
* Secrets (DB URL, JWT, Stripe, Sentry DSN) come exclusively from environment
  variables — `.env` is git-ignored; `.env.example` documents every key.

## 7. Placeholder Integrations (explicitly not production yet)

| Integration | Status | Notes |
|---|---|---|
| DocuSign / Adobe Sign | stub | `signature_requests.provider` field ready; webhook handler pending |
| Stripe billing | sandbox stub | `/api/v1/payments/webhook` verifies nothing yet — add signature verification before go-live |
| Sentry | optional | set `SENTRY_DSN` to enable; SDK init point in `app/main.py` |

## 8. Reporting Issues

Email security@imad.engineering (placeholder) or open a private advisory.
Please do not open public issues for suspected vulnerabilities.
