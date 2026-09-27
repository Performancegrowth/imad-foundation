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

# ── Cross-owner regression: user B must not touch user A's project ──────────
@pytest.fixture(scope="module")
def two_owners(client):
    """Create two users (via /register uids), each owning one project."""
    from app.core.security import create_access_token as _tok

    def _register(email: str):
        import time as _t
        tag = f"{int(_t.time()*1000)%100000000}"
        email = email.replace("@", f"+{tag}@")
        res = client.post("/api/v1/register", json={
            "email": email, "password": "CrossOwner1234!", "full_name": "Cross Owner",
            "role": "engineer",
        })
        assert res.status_code in (200, 201), res.text
        return int(res.json()["user"]["id"]), email

    uid_a, em_a = _register("cross-a@imad.ai")
    uid_b, em_b = _register("cross-b@imad.ai")
    h_a = {"Authorization": f"Bearer {_tok(subject_id=uid_a, email=em_a)}"}
    h_b = {"Authorization": f"Bearer {_tok(subject_id=uid_b, email=em_b)}"}
    ra = client.post("/api/v1/projects", headers=h_a,
                     json={"name": "cross-a-proj", "description": "A"})
    assert ra.status_code == 201, ra.text
    rb = client.post("/api/v1/projects", headers=h_b,
                     json={"name": "cross-b-proj", "description": "B"})
    assert rb.status_code == 201, rb.text
    return {"headers_a": h_a, "headers_b": h_b,
            "project_a": int(ra.json()["id"]), "project_b": int(rb.json()["id"])}


def _seed_doc(coll_name: str, project_id: int, extra: dict | None = None):
    from app.core.docstore import collection as _coll
    base = {"project_id": project_id}
    base.update(extra or {})
    prefix = {"comments": "cmt", "tasks": "tsk", "approvals": "apr",
              "consultant_requests": "rev", "notifications": "ntf"}.get(coll_name, "doc")
    return _coll(coll_name).put(base, prefix=prefix)


def test_cross_owner_governance_audit_log(client, two_owners):
    res = client.get(f"/api/v1/audit-log/{two_owners['project_a']}",
                     headers=two_owners["headers_b"])
    assert res.status_code == 404


def test_cross_owner_governance_readiness(client, two_owners):
    res = client.get(f"/api/v1/compliance/sbc304-readiness/{two_owners['project_a']}",
                     headers=two_owners["headers_b"])
    assert res.status_code == 404


def test_cross_owner_governance_submission_list(client, two_owners):
    res = client.get(f"/api/v1/submission/{two_owners['project_a']}",
                     headers=two_owners["headers_b"])
    assert res.status_code == 404

def test_cross_owner_submission_doc_lifecycle(client, two_owners):
    from app.core.docstore import collection as _coll
    doc = _coll("submission_packages").put(
        {"project_id": two_owners["project_b"], "status": "generated",
         "tracking": [], "contents": []}, prefix="sub")
    sid = doc["id"]
    ha = two_owners["headers_a"]
    r1 = client.post(f"/api/v1/submission/{sid}/export/docx", headers=ha, json={})
    assert r1.status_code == 404, r1.text
    r2 = client.post(f"/api/v1/submission/{sid}/status", headers=ha,
                     json={"status": "submitted"})
    assert r2.status_code == 404, r2.text
    r3 = client.get(f"/api/v1/submission/{sid}", headers=ha)
    assert r3.status_code == 404, r3.text


def test_cross_owner_signature_lifecycle(client, two_owners):
    from app.core.docstore import collection as _coll
    doc = _coll("signature_requests").put(
        {"project_id": two_owners["project_b"], "status": "requested",
         "engineer_name": "E", "license_number": "L1",
         "provider": "internal_seal"}, prefix="sig")
    sid = doc["id"]
    ha = two_owners["headers_a"]
    assert client.get(f"/api/v1/signature/{sid}", headers=ha).status_code == 404
    assert client.post(f"/api/v1/signature/{sid}/complete", headers=ha,
                       json={"outcome": "signed"}).status_code == 404


def test_cross_owner_collaboration_mutations(client, two_owners):
    ha, pb = two_owners["headers_a"], two_owners["project_b"]
    from app.services import bim_service as _bim
    issue = _bim.create_issue(pb, "x-owner issue", "body", "a", "", None)
    assert client.patch(f"/api/v1/bcf/issues/{issue['id']}", headers=ha,
                        json={"status": "closed"}).status_code == 404
    cmt = _seed_doc("comments", pb, {"target_kind": "result", "target_id": "t",
                                     "author": "a", "body": "b"})
    assert client.patch(f"/api/v1/comments/{cmt['id']}/resolve",
                        headers=ha).status_code == 404
    tsk = _seed_doc("tasks", pb, {"title": "t", "state": "backlog"})
    assert client.patch(f"/api/v1/tasks/{tsk['id']}/move", headers=ha,
                        json={"state": "done", "order": 0}).status_code == 404
    assert client.delete(f"/api/v1/tasks/{tsk['id']}",
                         headers=ha).status_code == 404
    ntf = _seed_doc("notifications", pb, {"kind": "task", "message": "m"})
    assert client.post(f"/api/v1/notifications/{ntf['id']}/read",
                       headers=ha).status_code == 404
    apr = _seed_doc("approvals", pb, {"subject_kind": "design_result",
                                      "subject_id": "s1", "state": "draft",
                                      "history": []})
    assert client.post(f"/api/v1/approvals/{apr['id']}/transition", headers=ha,
                       json={"state": "under_review"}).status_code == 404


def test_cross_owner_collaboration_lists_reject(client, two_owners):
    pa = two_owners["project_a"]
    hb = two_owners["headers_b"]
    for path in (f"/api/v1/comments?project_id={pa}",
                 f"/api/v1/tasks?project_id={pa}",
                 f"/api/v1/bcf/issues?project_id={pa}",
                 f"/api/v1/approvals?project_id={pa}"):
        assert client.get(path, headers=hb).status_code == 404, path


def test_cross_owner_ecosystem_review(client, two_owners):
    pa = two_owners["project_a"]
    hb = two_owners["headers_b"]
    from app.core.docstore import collection as _coll
    cns = _coll("consultants").put({"name": "X", "license_number": "L",
                                    "specialties": [], "regions": [],
                                    "review_rate_usd": 0, "available": True},
                                   prefix="cns")
    res2 = client.post("/api/v1/consultants/request-review", headers=hb,
                       json={"consultant_id": cns["id"],
                             "project_id": pa, "scope": "review"})
    assert res2.status_code == 404, res2.text
    assert client.get(f"/api/v1/consultants/requests/{pa}",
                      headers=hb).status_code == 404


def test_cross_owner_visualization(client, two_owners):
    hb, pa = two_owners["headers_b"], two_owners["project_a"]
    body = {"project_id": pa}
    assert client.post("/api/v1/viz/building/scene", headers=hb,
                       json=body).status_code == 404
    assert client.post("/api/v1/viz/building/inspect?element_id=B1", headers=hb,
                       json=body).status_code == 404
    assert client.post("/api/v1/viz/building/gltf", headers=hb,
                       json={"project_id": pa,
                             "scene_data": {"nodes": []}}).status_code == 404
