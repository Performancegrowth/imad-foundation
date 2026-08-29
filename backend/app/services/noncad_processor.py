"""
Sprint 3 — Plan generation from non-CAD inputs.

Clients without CAD files get the same ``PlanData`` contract through four
paths: a guided questionnaire, a template library, hand-drawn photo parsing
(reuses :mod:`ImageCADProcessor`), and natural-language descriptions parsed by
a local AI provider. All share :class:`PlanGenerator`.
"""
from __future__ import annotations

import json
import logging
from abc import ABC
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.models.plan_data import (
    Beam, Column, GridLine, PlanData, Wall, GeoPoint, Room,
)
from app.services.ai_provider import AIProvider, BaseMessage, OllamaLocalProvider, Role

log = logging.getLogger("imad.plans")

DEFAULT_BAY = 6.0    # typical structural bay (m)
DEFAULT_FLOOR = 3.0  # storey height (m)


class PlanGenerationError(Exception):
    """Raised when plan generation fails validation."""


# ──────────────────────────────────────────────────────────── templates ─────
def _layout_grid(width: float, depth: float, bays_x: int, bays_y: int,
                 bay_x: float = DEFAULT_BAY, bay_y: float = DEFAULT_BAY,
                 label: str = "") -> PlanData:
    """Build a rectangular column-grid frame."""
    plan = PlanData(source="template", label=label)
    xs = [0.0]
    for i in range(1, bays_x + 1):
        xs.append(i * bay_x)
    ys = [0.0]
    for i in range(1, bays_y + 1):
        ys.append(i * bay_y)

    # columns
    n = 0
    for x in xs:
        for y in ys:
            plan.columns.append(Column(id=f"c{n}", cx=x, cy=y, size_m=0.3))
            n += 1
    # perimeter walls + interior partition (center line)
    plan.walls.append(Wall(id="w0", x1=xs[0], y1=ys[0], x2=xs[-1], y2=ys[0]))
    plan.walls.append(Wall(id="w1", x1=xs[-1], y1=ys[0], x2=xs[-1], y2=ys[-1]))
    plan.walls.append(Wall(id="w2", x1=xs[-1], y1=ys[-1], x2=xs[0], y2=ys[-1]))
    plan.walls.append(Wall(id="w3", x1=xs[0], y1=ys[-1], x2=xs[0], y2=ys[0]))
    # beams along grid lines
    m = 0
    for x in xs:
        for j in range(bays_y):
            plan.beams.append(Beam(id=f"b{m}", x1=x, y1=ys[j], x2=x, y2=ys[j + 1]))
            m += 1
    for y in ys:
        for i in range(bays_x):
            plan.beams.append(Beam(id=f"b{m}", x1=xs[i], y1=y, x2=xs[i + 1], y2=y))
            m += 1
    # grids
    plan.grids = ([GridLine(id=f"v{i}", orientation="vertical", position=x, label=f"{i+1}")
                   for i, x in enumerate(xs)] +
                  [GridLine(id=f"h{i}", orientation="horizontal", position=y, label=f"{i+1}")
                   for i, y in enumerate(ys)])
    plan.stories = 1
    return plan


# Template library: id -> human name + SVG hint + builder callable.
TemplateDef = Dict[str, Any]


def _t(name: str, kind: str, build: Callable[[], PlanData]) -> TemplateDef:
    return {"name": name, "kind": kind, "build": build}


TEMPLATE_LIBRARY: Dict[str, TemplateDef] = {
    "small_office": _t(
        "Small Office / Clinic",
        "low-rise",
        lambda: _layout_grid(12.0, 8.0, 2, 1, label="Small Office"),
    ),
    "residential_villa": _t(
        "Residential Villa (2-storey)",
        "residential",
        lambda: _residential(),
    ),
    "warehouse": _t(
        "Warehouse / Workshop",
        "industrial",
        lambda: _layout_grid(30.0, 18.0, 4, 2, bay_x=7.5, bay_y=9.0, label="Warehouse"),
    ),
    "school_block": _t(
        "School Block",
        "institutional",
        lambda: _layout_grid(24.0, 12.0, 3, 1, label="School Block"),
    ),
    "hospital_wing": _t(
        "Hospital Wing (elevated)",
        "institutional",
        lambda: _layout_grid(30.0, 15.0, 4, 2, bay_x=7.5, bay_y=7.5, label="Hospital Wing"),
    ),
}


def _residential() -> PlanData:
    """A detached 2-storey house with a perimeter frame and a ridge wall."""
    plan = _layout_grid(10.0, 8.0, 2, 1, label="Residential Villa")
    plan.stories = 2
    # interior partition
    plan.walls.append(Wall(id="wi", x1=5.0, y1=0.0, x2=5.0, y2=8.0,
                           thickness_m=0.12, kind="partition"))
    # living-room bay sweep
    plan.rooms.append(Room(id="r1", label="Living", boundary=[
        GeoPoint(x=0, y=0), GeoPoint(x=5, y=0), GeoPoint(x=5, y=4), GeoPoint(x=0, y=4)]))
    return plan


def get_template(template_id: str) -> TemplateDef:
    if template_id not in TEMPLATE_LIBRARY:
        raise PlanGenerationError(f"Unknown template '{template_id}'.")
    return TEMPLATE_LIBRARY[template_id]
# ──────────────────────────────────────────────────────────── generator ─────
class PlanGenerator(ABC):
    """Turn non-CAD inputs into :class:`PlanData` and persist them."""

    def __init__(self, ai: Optional[AIProvider] = None, storage_dir: Optional[str] = None):
        self.ai = ai or OllamaLocalProvider()
        self.storage_dir = storage_dir or _default_storage_dir()

    # -- shared builders -----------------------------------------------
    def generate_from_questionnaire(self, answers: Dict[str, Any]) -> PlanData:
        """Interpret a structured questionnaire into a simple grid layout."""
        try:
            length = float(answers.get("length_m", 12.0))
            width = float(answers.get("width_m", 8.0))
            floors = int(answers.get("floors", 1))
            bays_x = max(1, int(answers.get("bays_x", 2)))
            bays_y = max(1, int(answers.get("bays_y", 1)))
            use = str(answers.get("use", "generic"))
        except (TypeError, ValueError) as exc:
            raise PlanGenerationError(f"Invalid questionnaire answers: {exc}") from exc

        if not (1 <= length <= 300 and 1 <= width <= 300):
            raise PlanGenerationError("Dimensions must be between 1 m and 300 m.")
        if not (1 <= floors <= 30):
            raise PlanGenerationError("Floors must be between 1 and 30.")

        bay_x = length / max(bays_x, 1)
        bay_y = width / max(bays_y, 1)
        plan = _layout_grid(length, width, bays_x, bays_y, bay_x=bay_x, bay_y=bay_y,
                            label=f"{use.title()} building")
        plan.stories = floors
        plan.source = "questionnaire"
        plan.original = answers
        return plan

    def generate_from_template(self, template_id: str, floors: int = 1) -> PlanData:
        """Instantiate a named template from the library."""
        tpl = get_template(template_id)
        plan: PlanData = tpl["build"]()
        plan.source = "template"
        plan.stories = max(1, int(floors))
        plan.original = {"template_id": template_id, "template_name": tpl["name"]}
        return plan

    async def generate_from_description(self, text: str, floors: int = 1) -> PlanData:
        """Ask the local AI to convert a plain-language description to layout.

        Sanitises the model's JSON (clamping dimensions to the valid 1–300 m /
        1–30 floor envelope, coercing non-numeric junk back to sane defaults)
        and retries once with a simpler prompt before surfacing a clear,
        user-friendly error.
        """
        return await self._describe(text, floors, retry=True)

    async def _describe(self, text: str, floors: int, retry: bool) -> PlanData:
        instruction = (
            "You convert human building descriptions into structured JSON "
            "representing a rectangular floor plan in metres. Return ONLY a JSON "
            "object with keys: length_m (number between 5 and 50), width_m (number "
            "between 5 and 50), bays_x (int 1-5), bays_y (int 1-5), use (string). "
            "No prose, no markdown."
        )
        try:
            reply = await self.ai.chat_json([
                BaseMessage(Role.SYSTEM, instruction),
                BaseMessage(Role.USER, text),
            ])
        except Exception as exc:  # AI unreachable → deterministic fallback
            log.warning("AI unavailable for description (%s); using defaults", exc)
            if retry:
                return await self._describe("a modest two-storey building", floors,
                                            retry=False)
            raise PlanGenerationError(
                "AI could not generate a valid plan. Please try a simpler "
                "description or use Template/Questionnaire.") from exc

        length = self._safe_number(reply.get("length_m"), 12.0, 1.0, 300.0)
        width = self._safe_number(reply.get("width_m"), 8.0, 1.0, 300.0)
        bays_x = int(self._safe_number(reply.get("bays_x"), 2, 1, 10))
        bays_y = int(self._safe_number(reply.get("bays_y"), 1, 1, 10))
        use = str(reply.get("use") or "generic")[-40:]

        answers = {
            "length_m": length,
            "width_m": width,
            "bays_x": bays_x,
            "bays_y": bays_y,
            "floors": max(1, min(30, int(floors))),
            "use": use,
        }
        try:
            plan = self.generate_from_questionnaire(answers)
        except PlanGenerationError:
            # Clamped values can still be non-sensical (e.g. tiny/ludicrous
            # aspect) — retry once with a simpler, deterministic prompt.
            if retry:
                return await self._describe("a square building 12 by 10 metres",
                                            floors, retry=False)
            raise PlanGenerationError(
                "AI could not generate a valid plan. Please try a simpler "
                "description or use Template/Questionnaire.")
        plan.source = "ai"
        plan.original = {"description": text}
        return plan

    @staticmethod
    def _safe_number(value: Any, default: float, lo: float, hi: float) -> float:
        """Coerce arbitrary AI output to a float inside [lo, hi]."""
        try:
            num = float(value)
        except (TypeError, ValueError):
            num = default
        if not (lo <= num <= hi):
            num = default
        return round(num, 2)

    # -- persistence -----------------------------------------------------
    def save_plan(self, project_id: int, name: str, plan: PlanData) -> Dict[str, Any]:
        """Persist plan geometry keyed by project, returning its metadata."""
        dir_path = Path(self.storage_dir) / str(project_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        safe = _slugify(name) or "plan"
        file_path = dir_path / f"{safe}.json"
        payload = plan.model_dump(mode="json")
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {
            "project_id": project_id,
            "name": name,
            "path": str(file_path),
            "walls": len(plan.walls),
            "columns": len(plan.columns),
            "beams": len(plan.beams),
            "stories": plan.stories,
        }

    @staticmethod
    def load_plan(project_id: int, name: str, storage_dir: Optional[str] = None) -> PlanData:
        root = Path(storage_dir or _default_storage_dir())
        candidate = root / str(project_id) / f"{_slugify(name)}.json"
        if not candidate.exists():
            raise PlanGenerationError(f"No saved plan '{name}' for project {project_id}.")
        return PlanData(**json.loads(candidate.read_text(encoding="utf-8")))

    @staticmethod
    def list_plans(project_id: int, storage_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        root = Path(storage_dir or _default_storage_dir()) / str(project_id)
        if not root.exists():
            return []
        found: List[Dict[str, Any]] = []
        for file in sorted(root.glob("*.json")):
            try:
                data = PlanData(**json.loads(file.read_text(encoding="utf-8")))
            except Exception:  # corrupt/unrelated file — skip
                continue
            found.append({
                "name": file.stem,
                "walls": len(data.walls),
                "columns": len(data.columns),
                "beams": len(data.beams),
                "stories": data.stories,
                "source": data.source,
                "label": data.label or file.stem,
            })
        return found


def _default_storage_dir() -> str:
    return str(Path(__file__).resolve().parents[2] / "storage" / "plans")


def _slugify(name: str) -> str:
    import re
    cleaned = re.sub(r"[^A-Za-z0-9_\-]+", "-", name).strip("-_")
    return cleaned.lower()