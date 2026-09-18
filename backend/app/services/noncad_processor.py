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
import re
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

# ─────────────────────── natural-language parsing helpers ──────────────────
# Word numbers so "two-story" / "three storeys" resolve to digits.
_WORD_NUMBERS: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

_NUM_WORDS = (r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
              r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
              r"nineteen|twenty")

# "3-story" / "three storeys" / "2 floors"
_FLOOR_COUNT_RX = re.compile(
    r"(?P<num>" + _NUM_WORDS + r")\s*[- ]?\s*"
    r"(?:story|stories|storey|storeys|floor|floors)\b",
    re.IGNORECASE,
)

# "210 per floor" / "210 square meters per floor" (unit optional)
_PER_FLOOR_AREA_RX = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?:square\s*meters?|sqm|m2|sq\.?\s*m\.?)?\s*"
    r"(?:per\s*floor|each\s*floor|a\s*floor|/\s*floor)\b",
    re.IGNORECASE,
)

# "total (built-up) area (of) 420" / "420 square meters total"
_TOTAL_AREA_RX = re.compile(
    r"total\s+(?:built[-\s]*up\s+)?area\s+(?:of\s+)?(?P<num>\d+(?:\.\d+)?)"
    r"|(?P<num2>\d+(?:\.\d+)?)\s*(?:square\s*meters?|sqm|m2)\s*total\b",
    re.IGNORECASE,
)

# Bare "800 square meters" with no qualifier.
_BARE_AREA_RX = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?:square\s*meters?|sqm|m2)\b",
    re.IGNORECASE,
)

# "20 by 30 meters" / "20m x 30m" — an explicit footprint wins over area.
_DIMS_RX = re.compile(
    r"(?P<a>\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)?\s*(?:x|by)\s*"
    r"(?P<b>\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)?",
    re.IGNORECASE,
)

# Ordered keyword → occupancy class. Checked in order, first hit wins.
_OCCUPANCY_KEYWORDS = (
    ("industrial", ("warehouse", "industrial", "factory", "workshop", "storage")),
    ("institutional", ("mosque", "school", "hospital", "clinic", "university")),
    ("office", ("office", "commercial", "retail", "tower")),
    ("residential", ("villa", "house", "residential", "home", "apartment", "flat")),
)


def _word_to_number(token: str) -> Optional[int]:
    """Resolve a digit string or an English word-number to an int."""
    token = (token or "").strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def _parse_floor_count(text: str) -> Optional[int]:
    """Floor count from free text ("3-story", "three storeys", "2 floors")."""
    match = _FLOOR_COUNT_RX.search(text or "")
    if not match:
        return None
    return _word_to_number(match.group("num"))


def _parse_occupancy(text: str) -> str:
    """Keyword → occupancy class. Residential is the safe default."""
    lowered = (text or "").lower()
    for label, keywords in _OCCUPANCY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return label
    return "residential"


def _parse_area_per_floor(text: str, floors: int) -> Optional[float]:
    """Per-floor area (m²) from per-floor / total / bare area mentions."""
    lowered = text or ""
    per_floor = _PER_FLOOR_AREA_RX.search(lowered)
    if per_floor:
        return float(per_floor.group("num"))
    n_floors = max(1, int(floors or 1))
    total = _TOTAL_AREA_RX.search(lowered)
    if total:
        raw = total.group("num") or total.group("num2")
        if raw:
            return float(raw) / n_floors
    bare = _BARE_AREA_RX.search(lowered)
    if bare:
        return float(bare.group("num")) / n_floors
    return None


def _footprint_from_area(area_sqm: float) -> tuple:
    """Rectangular footprint ``(width, depth)`` for an area, aspect ~1.2:1."""
    area = max(25.0, min(float(area_sqm), 2000.0))
    depth = round((area * 1.2) ** 0.5 * 2.0) / 2.0
    width = round((area / 1.2) ** 0.5 * 2.0) / 2.0
    return max(5.0, min(width, 60.0)), max(5.0, min(depth, 60.0))


def _parse_description_metrics(text: str, floors: int) -> tuple:
    """Deterministic fallback: ``(width, depth, floors, occupancy)``.

    Understands word-numbers, per-floor / total areas, explicit WxD and
    occupancy keywords. Defaults to a ~150 m² footprint (11 m x 13.5 m) when
    the text carries no usable numbers, so this never raises.
    """
    parsed_floors = _parse_floor_count(text)
    floors = parsed_floors if parsed_floors else (floors or 1)
    floors = max(1, min(int(floors), 30))
    occupancy = _parse_occupancy(text)

    dims = _DIMS_RX.search(text or "")
    if dims:
        width = max(5.0, min(float(dims.group("a")), 60.0))
        depth = max(5.0, min(float(dims.group("b")), 60.0))
        # Keep the per-floor footprint under the 2000 m² sanity ceiling.
        if width * depth > 2000.0:
            scale = (2000.0 / (width * depth)) ** 0.5
            width = round(width * scale * 2.0) / 2.0
            depth = round(depth * scale * 2.0) / 2.0
        return width, depth, floors, occupancy

    area = _parse_area_per_floor(text or "", floors)
    width, depth = _footprint_from_area(area if area else 150.0)
    return width, depth, floors, occupancy


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
        plan.occupancy_type = use          # SBC 301 Table 4.1 live load
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
        """Convert a plain-language description to a reliable rectangular plan.

        Robust by construction: it first asks the local AI (Ollama) for strict
        JSON; on any failure — unreachable, malformed, or missing dimensions —
        it falls back to the deterministic natural-language parser
        (:func:`_parse_description_metrics`), which understands word-numbers,
        per-floor/total areas and occupancy keywords. ``plan.source`` is
        ``"ai"`` only when the model actually supplied the footprint, so
        callers can tell the two paths apart. Never returns an invalid plan.
        """
        width_m, length_m, n_floors, occupancy, source = await self._extract_metrics(
            text, floors)
        plan = self._build_description_grid(width_m, length_m, n_floors, source=source)
        plan.occupancy_type = occupancy
        plan.original = {"description": text[:200], "source": source}
        return plan

    async def _extract_metrics(self, text: str, floors: int):
        """Return ``(width_m, length_m, floors, occupancy, source)``.

        Ollama's strict-JSON reply is preferred; if it is unreachable,
        malformed, or short of dimensions, the deterministic NL parser takes
        over. Every value is clamped to a safe envelope before grid building,
        and ``source`` reports which path actually produced the footprint.
        """
        width = length = None
        reply: Dict[str, Any] = {}
        try:
            reply = await self.ai.chat_json([
                BaseMessage(Role.SYSTEM,
                    "You are a structural plan extractor. Respond with ONLY "
                    "JSON, no prose and no markdown: "
                    "{\"width_m\":number (5-60), \"length_m\":number (5-60), "
                    "\"floors\":integer (1-20), \"occupancy\":string "
                    "(residential|office|industrial|institutional)}."),
                BaseMessage(Role.USER, text),
            ])
            if isinstance(reply, dict):
                width = reply.get("width_m")
                length = reply.get("length_m")
            else:  # provider returned something unexpected
                reply = {}
        except Exception as exc:  # AI unreachable — never block the user
            log.warning("AI unavailable for description; NL fallback (%s)", exc)
            reply = {}

        if width is None or length is None:
            # Deterministic fallback: the text itself beats the floors param.
            f_width, f_depth, f_floors, f_occ = _parse_description_metrics(text, floors)
            return f_width, f_depth, f_floors, f_occ, "fallback"

        if reply.get("floors") is not None:
            try:
                floors = int(reply["floors"])
            except (TypeError, ValueError):
                pass

        width = round(min(60.0, max(5.0, float(width))), 2)
        length = round(min(60.0, max(5.0, float(length))), 2)
        n_floors = min(30, max(1, int(floors)))
        raw_occ = str(reply.get("occupancy") or "").strip().lower()
        occupancy = raw_occ if raw_occ in {
            "residential", "office", "industrial", "institutional",
        } else _parse_occupancy(text)
        return width, length, n_floors, occupancy, "ai"

    @staticmethod
    def _build_description_grid(width: float, length: float, floors: int,
                                source: str = "fallback") -> PlanData:
        """Deterministic rectangular frame: 4 perimeter walls + ~5 m grid.

        Columns sit at the grid intersections; beams run between adjacent
        columns in both directions; ``plan.stories`` is set to the requested
        floor count so the same PlanData flow feeds analysis / BOQ / 3D.
        """
        # ~5 m bays, never fewer than 2 per side. The cap keeps grids sane:
        # villa-scale input yields 12-24 columns instead of hundreds.
        bays_x = max(2, int(round(width / 5.0)))
        bays_y = max(2, int(round(length / 5.0)))
        while (bays_x + 1) * (bays_y + 1) > 48 and (bays_x > 2 or bays_y > 2):
            if bays_x >= bays_y and bays_x > 2:
                bays_x -= 1
            elif bays_y > 2:
                bays_y -= 1
            else:
                break
        plan = _layout_grid(
            width, length, bays_x, bays_y,
            bay_x=width / bays_x, bay_y=length / bays_y,
            label="IMAD description layout",
        )
        plan.source = source
        plan.stories = floors
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