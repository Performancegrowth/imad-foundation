"""
Imad (عِماد) — Autonomous Engineering Engine.

FastAPI entrypoint. Wires configuration, middleware (CORS / request logging),
the versioned API router, and a /health liveness marker.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import get_settings
from app.core.database import init_db

log = logging.getLogger("imad")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialise the database engine + schema on startup."""
    try:
        init_db()
        log.info("Database initialised.")
    except Exception as exc:  # pragma: no cover — surface startup issues loudly
        log.error("Database init failed: %s", exc)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.5.0",
    description="Imad — Autonomous Engineering Engine API (Sprints 2–5: CAD→Plan→Survey→Analysis).",
    lifespan=lifespan,
    root_path="",
)

# ------------------------------------------------------------------ middleware --
# ------------------------------------------------------------- middleware --
# CORS uses an explicit allow-list (see Settings.cors_origin_list); it is
# applied unconditionally so the backend is reachable from deployed origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------- routes --
@app.get("/", tags=["meta"], summary="Service banner")
async def root() -> dict:
    return {
        "service": settings.APP_NAME,
        "tagline": "The Autonomous Engineering Engine",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["meta"], summary="Liveness + engine status")
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.APP_ENV}


app.include_router(api_router)