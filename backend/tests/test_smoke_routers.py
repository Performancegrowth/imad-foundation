"""Smoke tests for the Sprint 9–14 routers.

Boots the real FastAPI app and hits one representative endpoint per router,
asserting the response is not a 5xx server error. Authentication is supplied
only where a router requires it (project listing).
"""
from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.main import app

from fastapi.testclient import TestClient

pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    """A TestClient with the app lifespan run (DB bootstrapped)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    """A valid signed JWT for the protected project-listing endpoint."""
    token = create_access_token(subject_id=1, email="smoke@imad.ai")
    return {"Authorization": f"Bearer {token}"}


def test_projects_router_not_500(client, auth_headers):
    """Protected CRUD router must answer with a valid token (200 → empty list)."""
    res = client.get("/api/v1/projects", headers=auth_headers)
    assert res.status_code < 500


def test_plans_templates_router_not_500(client):
    """Public template catalogue should never 500."""
    res = client.get("/api/v1/plans/templates")
    assert res.status_code < 500


def test_validation_router_not_500(client):
    """Benchmark suite runs and the stored report is retrievable."""
    run = client.post("/api/v1/validation/run", json={})
    assert run.status_code < 500
    report = client.get("/api/v1/validation/report")
    assert report.status_code < 500


def test_ecosystem_suppliers_not_500(client):
    """Marketplace supplier directory should answer without auth."""
    res = client.get("/api/v1/suppliers")
    assert res.status_code < 500


_SMOKE_PLAN = {
    "source": "smoke",
    "label": "smoke",
    "stories": 1,
    "columns": [
        {"id": "c1", "cx": 0.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c2", "cx": 5.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
        {"id": "c3", "cx": 10.0, "cy": 0.0, "size_m": 0.3, "height": 3.0},
    ],
    "beams": [{"id": "b1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 0.0,
               "width_m": 0.3, "depth_m": 0.5}],
    "walls": [],
    "grids": [],
}


def test_governance_compliance_not_500(client):
    """Compliance engine accepts a minimal plan and returns a report."""
    res = client.post("/api/v1/compliance/check", json={"plan": _SMOKE_PLAN})
    assert res.status_code < 500


def test_governance_sbc304_package_not_500(client):
    """Sprint 10 package endpoint assembles the preliminary PDF package."""
    analysis = {
        "method": "equivalent-frame",
        "design": {
            "max_utilization": 0.62,
            "members": [
                {"id": "c1", "utilization": 0.62,
                 "governing_check": "axial+moment"},
            ],
            "design_factors": {
                "phi_flexure": {"value": 0.9,
                                "clause": "ACI 318-19 Table 21.2.1"},
            },
            "references": [
                {"name": "SBC 304", "purpose": "Concrete design",
                 "source": "Saudi Building Code"},
            ],
        },
    }
    res = client.post("/api/v1/compliance/sbc304-package", json={
        "project_id": 1,
        "project_name": "Smoke Package",
        "plan": _SMOKE_PLAN,
        "analysis": analysis,
    })
    assert res.status_code < 500
    if res.status_code == 200:
        body = res.json()
        assert body.get("file_path")
        assert body.get("package_type") == "sbc304_preliminary_calculation_package"


def test_platform_analytics_not_500(client):
    """Business analytics endpoint must not error (lives in the billing router)."""
    res = client.get("/api/v1/analytics")
    assert res.status_code < 500
    # The platform router itself: tutorials catalogue.
    res2 = client.get("/api/v1/tutorials")
    assert res2.status_code < 500


def test_governance_sbc304_package_auto_analysis(client):
    """Homebuilder flow: no analysis supplied — the endpoint runs the
    authoritative engine itself and still produces the package PDF."""
    res = client.post("/api/v1/compliance/sbc304-package", json={
        "project_id": 1,
        "project_name": "Auto Analysis Package",
        "plan": _SMOKE_PLAN,
    })
    assert res.status_code < 500
    if res.status_code == 200:
        body = res.json()
        assert body.get("file_path")
        assert "sbc304_calculation_package" in body.get("contents", [])


def test_governance_readiness_checklist(client):
    """Readiness endpoint reports a data-driven checklist, never 500."""
    res = client.get("/api/v1/compliance/sbc304-readiness/1")
    assert res.status_code < 500
    if res.status_code == 200:
        body = res.json()
        assert isinstance(body.get("checks"), list) and body["checks"]
        assert isinstance(body.get("ready"), bool)
        assert body.get("status")


def test_governance_submission_tracking_flow(client):
    """Roadmap #16: dual-mode GET /submission/{ref} plus auditable status
    transitions. Numeric ref lists a project's packages (sorted), a
    submission id returns one record, and transitions append tracking
    events. Nothing 500s and invalid statuses are 422, never guessed."""
    res = client.post("/api/v1/compliance/sbc304-package", json={
        "project_id": 1,
        "project_name": "Tracking Flow",
        "plan": _SMOKE_PLAN,
    })
    assert res.status_code < 500

    # Numeric ref → project listing.
    listing = client.get("/api/v1/submission/1")
    assert listing.status_code == 200
    packages = listing.json().get("packages", [])
    assert isinstance(packages, list)

    if packages:
        sub_id = packages[0]["id"]

        # Submission-id ref → single record detail.
        detail = client.get(f"/api/v1/submission/{sub_id}")
        assert detail.status_code == 200
        assert detail.json().get("id") == sub_id

        # A real-world transition appends an auditable tracking event.
        tr = client.post(f"/api/v1/submission/{sub_id}/status", json={
            "status": "submitted",
            "authority": "Baladiyah",
            "reference_number": "PRM-123",
        })
        assert tr.status_code == 200
        body = tr.json()
        assert body.get("status") == "submitted"
        tracking = body.get("tracking") or []
        assert tracking and tracking[-1]["reference_number"] == "PRM-123"

        # Invalid statuses are rejected by validation, never stored.
        bad = client.post(f"/api/v1/submission/{sub_id}/status",
                          json={"status": "bogus"})
        assert bad.status_code == 422

    # Unknown submission id → 404, not 500.
    assert client.get("/api/v1/submission/sub-doesnotexist").status_code == 404


def test_boq_xlsx_export_with_context(client):
    """Roadmap #18: the Excel export widens to Submission Summary, Material
    Certifications and Rates Comparison sheets using stored context. The
    endpoint must produce a real .xlsx file and never 500."""
    from pathlib import Path as _P

    gen = client.post("/api/v1/generate-boq", json={
        "project_id": 1, "project_name": "Xlsx Flow", "plan": _SMOKE_PLAN,
    })
    assert gen.status_code < 500
    rid = gen.json().get("result_id")
    assert rid

    res = client.post(f"/api/v1/generate-boq/{rid}/export/xlsx")
    assert res.status_code < 500
    if res.status_code == 200:
        data = res.json()
        assert data.get("file", "").endswith(".xlsx")
        assert _P(data["file"]).exists()

    # Unknown result id → 404, not 500.
    assert client.post("/api/v1/generate-boq/boq-nope/export/xlsx").status_code == 404


def test_submission_docx_export(client):
    """Roadmap #17: a generated SBC 304 package exports as an editable Word
    calculation note. The endpoint resolves the same stored inputs as the
    package flow, writes a real .docx and never 500s."""
    from pathlib import Path as _P

    pkg = client.post("/api/v1/compliance/sbc304-package", json={
        "project_id": 1, "project_name": "Docx Flow", "plan": _SMOKE_PLAN,
    })
    assert pkg.status_code < 500

    listing = client.get("/api/v1/submission/1")
    assert listing.status_code == 200
    packages = listing.json().get("packages", [])
    assert packages, "package generation should record a submission"

    res = client.post(f"/api/v1/submission/{packages[0]['id']}/export/docx",
                      json={})
    assert res.status_code < 500
    if res.status_code == 200:
        data = res.json()
        assert data.get("file", "").endswith(".docx")
        assert _P(data["file"]).exists()

    # Unknown submission id → 404, not 500.
    assert client.post("/api/v1/submission/sub-nope/export/docx",
                       json={}).status_code == 404