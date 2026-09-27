"""Equilibrium verification tests (post-analysis helper + /analyze wiring)."""
from __future__ import annotations

from app.services.equilibrium_check import check_equilibrium


def _result(applied_v=100.0, react_v=100.0, applied_h=20.0, react_h=20.0):
    return {
        "loads": {"total_weight_kN": applied_v, "lateral_base_kN": applied_h},
        "reactions": {"total_gravity_kN": react_v, "base_shear_kN": react_h,
                      "overturning_moment_kNm": 10.0},
    }


def test_equilibrium_passes_for_correct_result():
    out = check_equilibrium(_result())
    assert out["overall"] == "PASS"
    assert out["vertical"]["status"] == "PASS"
    assert out["horizontal"]["status"] == "PASS"
    assert out["moment"]["status"] == "NOT_APPLICABLE"


def test_equilibrium_warns_for_small_imbalance():
    out = check_equilibrium(_result(react_v=101.0))  # 1% imbalance
    assert out["vertical"]["status"] == "WARN"
    assert out["overall"] == "WARN"


def test_equilibrium_fails_for_large_imbalance():
    out = check_equilibrium(_result(react_v=105.0))  # 5% imbalance
    assert out["vertical"]["status"] == "FAIL"
    assert out["overall"] == "FAIL"


def test_equilibrium_not_applicable_when_no_loads():
    out = check_equilibrium(_result(0.0, 0.0, 0.0, 0.0))
    assert out["vertical"]["status"] == "NOT_APPLICABLE"
    assert out["horizontal"]["status"] == "NOT_APPLICABLE"
    assert out["overall"] == "NOT_APPLICABLE"


def test_equilibrium_integration():
    from fastapi.testclient import TestClient
    from app.core.security import create_access_token
    from app.main import app

    email = "equilibrium@imad.ai"
    with TestClient(app) as client:
        reg = client.post("/api/v1/register", json={
            "email": email, "password": "EquilPass1234!", "full_name": "Equil",
            "role": "engineer"})
        uid = int(reg.json()["user"]["id"]) if reg.status_code in (200, 201) else 1
        headers = {"Authorization": f"Bearer {create_access_token(uid, email)}"}
        proj = client.post("/api/v1/projects", headers=headers,
                           json={"name": "equil-proj", "description": "e"})
        pid = int(proj.json()["id"])
        res = client.post("/api/v1/analyze", headers=headers, json={
            "project_id": pid,
            "plan": {"source": "x", "stories": 1,
                     "columns": [{"id": "c1", "cx": 0, "cy": 0,
                                  "size_m": 0.3, "height": 3}],
                     "beams": [], "walls": [], "grids": []}})
        assert res.status_code == 200, res.text
        body = res.json()
        assert "equilibrium" in body
        assert body["equilibrium"]["overall"] in {"PASS", "WARN", "NOT_APPLICABLE"}
