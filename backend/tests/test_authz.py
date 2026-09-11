"""AuthZ smoke tests: protected routes require a bearer token, and
project-scoped routes reject foreign project ids with 404."""
from __future__ import annotations

import pytest

from app.core.security import create_access_token
from app.main import app
from fastapi.testclient import TestClient

pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    token = create_access_token(subject_id=1, email="authz@imad.ai")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def owned_project(client, auth_headers):
    """Register a real user + create a project they own."""
    email = "authz-owner@imad.ai"
    client.post("/api/v1/register", json={
        "email": email, "password": "AuthzPass1234!", "full_name": "Authz Owner",
        "role": "engineer",
    })
    token = create_access_token(subject_id=1, email=email)
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/v1/projects", headers=headers,
                      json={"name": "authz-owned", "description": "owned"})
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


PROTECTED_ROUTES = [
    ("POST", "/api/v1/analyze", {"project_id": 1, "plan": {"source": "x", "stories": 1,
        "columns": [{"id": "c1", "cx": 0, "cy": 0, "size_m": 0.3, "height": 3}],
        "beams": [], "walls": [], "grids": []}}),
    ("POST", "/api/v1/generate-boq", {"project_id": 1, "plan": {"source": "x", "stories": 1,
        "columns": [{"id": "c1", "cx": 0, "cy": 0, "size_m": 0.3, "height": 3}],
        "beams": [], "walls": [], "grids": []}}),
    ("POST", "/api/v1/carbon-report", {"project_id": 1, "plan": {"source": "x", "stories": 1,
        "columns": [{"id": "c1", "cx": 0, "cy": 0, "size_m": 0.3, "height": 3}],
        "beams": [], "walls": [], "grids": []}}),
    ("POST", "/api/v1/generate-designs", {"length_m": 10, "width_m": 8, "stories": 1}),
    ("POST", "/api/v1/compliance/check", {"project_id": 1}),
    ("POST", "/api/v1/submission/generate", {"project_id": 1}),
    ("POST", "/api/v1/survey/manual", {"project_id": 1,
        "reading": {"soil_bearing_capacity_kpa": 150}}),
    ("POST", "/api/v1/sections/analyze", {"section": {"shape": "rect", "b": 300, "d": 500}}),
    ("GET", "/api/v1/audit-log/1", None),
    ("GET", "/api/v1/comments?project_id=1", None),
    ("GET", "/api/v1/tasks?project_id=1", None),
    ("GET", "/api/v1/jobs", None),
    ("GET", "/api/v1/compliance/sbc304-readiness/1", None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_rejects_anonymous(client, method, path, body):
    """No token → 401."""
    if method == "POST":
        res = client.post(path, json=body)
    else:
        res = client.get(path)
    assert res.status_code == 401, f"{method} {path} expected 401, got {res.status_code}"


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_protected_route_accepts_authed(client, auth_headers, method, path, body):
    """Valid token → not 401 (ownership may still 404, that's fine)."""
    if method == "POST":
        res = client.post(path, headers=auth_headers, json=body)
    else:
        res = client.get(path, headers=auth_headers)
    assert res.status_code != 401, f"{method} {path} got 401 with valid token"


def test_ownership_scoping_rejects_foreign_project(client, auth_headers):
    """A project the caller does NOT own → 404, never 200/500."""
    res = client.post("/api/v1/analyze", headers=auth_headers,
                      json={"project_id": 999999, "plan": {"source": "x", "stories": 1,
                          "columns": [{"id": "c1", "cx": 0, "cy": 0, "size_m": 0.3, "height": 3}],
                          "beams": [], "walls": [], "grids": []}})
    assert res.status_code == 404


def test_ownership_scoping_accepts_owned_project(client, owned_project, auth_headers):
    """A project the caller owns → passes ownership check (may 422 on plan, never 404)."""
    res = client.post("/api/v1/analyze", headers=auth_headers,
                      json={"project_id": owned_project, "plan": {"source": "x", "stories": 1,
                          "columns": [{"id": "c1", "cx": 0, "cy": 0, "size_m": 0.3, "height": 3}],
                          "beams": [], "walls": [], "grids": []}})
    assert res.status_code != 404
