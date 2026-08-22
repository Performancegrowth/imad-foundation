"""Versioned API routers for Imad.

FastAPI dependencies are declared here and aggregated in :mod:`app.main`.
"""
from fastapi import APIRouter

from . import (
    auth, projects, upload, survey, plans,
    visualization, cad, analysis, generative, boq, sustainability,
    platform, agents, billing, governance, validation, collaboration,
    ecosystem,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(upload.router, prefix="/files", tags=["files"])
api_router.include_router(survey.router, prefix="/survey", tags=["survey"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(visualization.router, prefix="/viz", tags=["visualization"])
api_router.include_router(cad.router, tags=["cad"])
api_router.include_router(analysis.router, tags=["analysis"])
api_router.include_router(generative.router, tags=["generative"])
api_router.include_router(boq.router, tags=["boq"])
api_router.include_router(sustainability.router, tags=["sustainability"])
# Sprint 9B/9C — agents & business layer (platform first: owns /support/chat)
api_router.include_router(platform.router, tags=["platform"])
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(billing.router, tags=["billing"])
# Sprint 10 — regulatory trust & compliance
api_router.include_router(governance.router, tags=["governance"])
# Sprint 11 — engineering validation
api_router.include_router(validation.router, tags=["validation"])
# Sprint 12 — BIM & collaboration
api_router.include_router(collaboration.router, tags=["collaboration"])
# Sprint 13 — data moat & marketplace
api_router.include_router(ecosystem.router, tags=["ecosystem"])

__all__ = ["api_router"]