-- ==================================================================
-- Imad (عِماد) — Sprint 0 Database Schema
-- Dialect: SQLite 3 (SQLAlchemy ORM will manage migrations in Sprint 2).
-- ==================================================================

PRAGMA foreign_keys = ON;

-- ── Users ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    full_name     TEXT    NOT NULL,
    hashed_password TEXT  NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    is_superuser  INTEGER NOT NULL DEFAULT 0,
    organization  TEXT,
    locale        TEXT    NOT NULL DEFAULT 'en',          -- 'en' | 'ar'
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Projects ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT    NOT NULL,
    description   TEXT,
    project_code  TEXT,
    city          TEXT,
    country       TEXT,
    latitude      REAL,
    longitude     REAL,
    status        TEXT    NOT NULL DEFAULT 'draft',       -- draft|active|archived
    design_standard TEXT  NOT NULL DEFAULT 'ACI 318-19',  -- structural code
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Design Files (CAD + non-CAD uploads) ─────────────────────────
CREATE TABLE IF NOT EXISTS design_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploader_id   INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
    original_name TEXT    NOT NULL,
    stored_name   TEXT    NOT NULL,
    kind          TEXT    NOT NULL,                        -- cad|noncad
    mime_type     TEXT,
    file_ext      TEXT,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'uploaded',     -- uploaded|processing|parsed|error
    meta          TEXT,                                   -- JSON blob
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Design Results ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS design_results (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_id       INTEGER REFERENCES design_files(id),
    status        TEXT    NOT NULL DEFAULT 'pending',      -- pending|processing|completed|failed
    engine        TEXT,                                    -- structural engine id
    payload       TEXT    NOT NULL DEFAULT '{}',           -- JSON result
    error_message TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Survey Data ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS survey_data (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cycle         TEXT    NOT NULL DEFAULT 'baseline',
    altitude_m    REAL,           -- survey measurement at altitude (m)
    latitude      REAL,
    longitude     REAL,
    temperature_c REAL,
    humidity_pct  REAL,
    wind_speed_ms REAL,
    notes         TEXT,
    raw_payload   TEXT,           -- JSON
    captured_at   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Plans (BOQ / sustainability / structural plans) ───────────────
CREATE TABLE IF NOT EXISTS plans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name          TEXT    NOT NULL,
    kind          TEXT    NOT NULL DEFAULT 'boq',        -- boq|structural|sustainability|cost
    status        TEXT    NOT NULL DEFAULT 'draft',      -- draft|active|generated|archived
    items_total   INTEGER NOT NULL DEFAULT 0,
    total_amount  REAL    NOT NULL DEFAULT 0,
    currency      TEXT    NOT NULL DEFAULT 'USD',
    metadata      TEXT,          -- JSON (stores PlanData geometry for plan rows)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Templates (Sprint 3 library) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id        TEXT    NOT NULL UNIQUE,               -- e.g. 'small_office'
    name          TEXT    NOT NULL,
    kind          TEXT    NOT NULL DEFAULT 'low-rise',
    preview_svg   TEXT,                                  -- inline SVG thumbnail
    schema_json   TEXT    NOT NULL DEFAULT '{}',         -- plan geometry caps
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Indexes ───────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_projects_owner      ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_design_files_project ON design_files(project_id);
CREATE INDEX IF NOT EXISTS idx_results_project     ON design_results(project_id);
CREATE INDEX IF NOT EXISTS idx_survey_project      ON survey_data(project_id);
CREATE INDEX IF NOT EXISTS idx_plans_project       ON plans(project_id);

-- ── Seed (development only) ───────────────────────────────────────
-- INSERT INTO users (email, full_name, hashed_password)
-- VALUES ('admin@imad.dev', 'Imad Administrator', '<bcrypt-hash>');