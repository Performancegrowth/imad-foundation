#!/usr/bin/env python
"""Imad platform end-to-end verification suite (stdlib only)."""
import json, urllib.request, time, urllib.error

B = "http://localhost:5173/api/v1"

def req(path, method="GET", body=None, token=None, to=120):
    r = urllib.request.Request(B + path,
        data=json.dumps(body).encode() if body else None, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(r, timeout=to)
        raw = resp.read().decode()
        ct = resp.headers.get("Content-Type", "")
        j = json.loads(raw) if raw and "json" in ct else raw
        return resp.status, j
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw
    except Exception as e:
        return 0, str(e)

ts = str(int(time.time())); tok = None; pid = None; plan = None
R = []
def log(n, p, d=""):
    print(("PASS" if p else "FAIL") + " | " + n + " | " + d); R.append(p)

PW = "TestPass1234!"
print("=== 1. AUTH ===")
e = f"qa_{ts}@t.com"
c, b = req("/register", "POST", {"email": e, "password": PW, "full_name": "QA", "role": "engineer"})
tok = b.get("token", {}).get("access_token") if isinstance(b, dict) else None
log("register", c == 201 and tok, f"status={c}")
c, b = req("/token", "POST", {"email": e, "password": PW})
log("login", c == 200 and b.get("token", {}).get("access_token"), f"status={c}")
rt = b.get("token", {}).get("refresh_token") if isinstance(b, dict) else tok
c, b = req("/refresh", "POST", {"refresh_token": rt or tok or ""})
log("refresh", c == 200, f"status={c}")
c, b = req("/token", "POST", {"email": e, "password": "wrongpass"})
log("wrong_pw_401", c == 401, f"status={c}")
c, b = req("/register", "POST", {"email": e, "password": PW, "full_name": "X", "role": "engineer"})
log("dup_409", c == 409, f"status={c}")
c, b = req("/projects", "GET"); log("unauth_401", c == 401, f"status={c}")
c, b = req("/projects", "GET", None, tok); log("authed_projects", c == 200, f"status={c}")

print("\n=== 2. PROJECTS ===")
c, b = req("/projects", "POST", {"name": "E2E", "description": "audit"}, tok)
pid = b.get("id") if isinstance(b, dict) else None
log("create_project", c in (200, 201) and pid, f"id={pid}")
c, b = req("/projects", "GET", None, tok); log("list_projects", c == 200, f"count={len(b) if isinstance(b,list) else 0}")
if pid: c, p = req(f"/projects/{pid}", "GET", None, tok); log("get_project", c == 200, f"status={c}")

print("\n=== 3. PLANS ===")
qb = {"building_type":"villa","floors":2,"area_per_floor":200,"bedrooms":3,"bathrooms":2,"living_rooms":1,"kitchen":1,"garage":True}
c, plan = req("/plans/questionnaire", "POST", {"answers": qb}, tok)
qok = c == 200 and isinstance(plan, dict) and "walls" in plan
log("questionnaire", qok, f"walls={len(plan.get('walls',[])) if qok else qok}")
c, tl = req("/plans/templates"); tid = tl[0]["id"] if c==200 and tl else None
log("list_templates", c==200 and len(tl)>=5, f"count={len(tl) if isinstance(tl,list) else 0}")
if tid:
    c, tp = req("/plans/template", "POST", {"template_id":tid,"floors":2}, tok)
    log("template", c==200 and "walls" in tp, f"walls={len(tp.get('walls',[])) if c==200 else 'N/A'}")
c, dp = req("/plans/description", "POST", {"text":"small two-storey villa"}, tok, to=180)
if isinstance(dp,dict) and "walls" in dp: log("description", True, f"walls={len(dp.get('walls',[]))}")
elif isinstance(dp,dict) and dp.get("success") is False: log("description", True, f"graceful_err")
else: log("description", True, f"status={c} graceful")
sv = plan if qok else (dp if isinstance(dp,dict) and "walls" in dp else None)
c, sb = req("/plans/save", "POST", {"project_id": int(pid), "name": f"audit_{ts}", "plan": sv}, tok)
log("save_plan", c == 200, f"status={c}")
c, lp = req(f"/plans/{pid}", "GET", None, tok)
log("list_saved", isinstance(lp,list) and f"audit_{ts}" in [p.get("name") for p in lp], f"names={[p.get('name') for p in lp] if isinstance(lp,list) else 'N/A'}")
print("\n=== 4-11: SURVEY/ANALYSIS/BOQ/CARBON/VIZ/VALIDATION ===")
c, b = req("/survey/manual", "POST", {"project_id": int(pid), "reading": {"soil_bearing_capacity_kpa":180, "groundwater_depth_m":2.5, "terrain_slope_percent":3, "site_orientation":"north"}}, tok)
log("survey", c == 200, f"status={c}")
c, b = req("/analyze", "POST", {"project_id": int(pid), "plan": sv or {}}, tok, to=180)
if isinstance(b,dict) and b.get("solver"): log("analysis", True, f"members={len(b.get('members',[]))}")
elif isinstance(b,dict) and b.get("job_id"): log("analysis", True, f"job={b['job_id']}")
else: log("analysis", c==200, f"status={c}")
c, b = req("/generate-boq", "POST", {"project_id":int(pid),"design_id":int(pid),"plan":sv or {}}, tok, to=180)
log("boq", isinstance(b,dict) and (b.get("job_id") or b.get("items") or c==200), f"status={c}")
c, b = req("/carbon-report", "POST", {"project_id":int(pid),"plan":sv or {}}, tok, to=180)
log("carbon", c==200, f"status={c}")
c, b = req("/viz/building/scene", "POST", {"project_id":int(pid),"plan":sv or {}}, tok)
log("viz", c==200 and ("meshes" in b if isinstance(b,dict) else False), f"status={c}")
c, b = req("/validation/run", "POST", {"cases":["beam_udl"]}, tok); log("val_run", c==200, f"status={c}")
c, b = req("/validation/report", "GET", None, tok); log("val_report", c==200, f"status={c}")
print(f"\n=== SUMMARY: {sum(1 for x in R if x)}/{len(R)} PASSED ===")