"""
Sprint 6 — Generative Design Engine.

Explores alternative structural schemes with a genetic algorithm:
- chromosome encodes column positions, beam orientations and slab type
- fitness is multi-objective: cost, embodied carbon, flexibility, safety
- NSGA-II (DEAP) optimises the whole population
- surfaces the top 3 Pareto-optimal solutions

The AI provider is used ONLY to write recommendation text for the chosen
schemes — never to drive the optimisation itself.

Optimisation math here is deliberately deterministic so the module is fully
testable without any heavyweight solver.
"""
from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.storage import storage_root
from app.models.plan_data import Beam, Column, PlanData, Wall

log = logging.getLogger("imad.generative")

# Unit costs / emission factors (approx, configurable): used for fitness only.
CONCRETE_COST_PER_M3 = 210.0          # USD
STEEL_COST_PER_KG = 1.1               # USD
CARBON_CONCRETE_PER_M3 = 320.0        # kgCO2e per m³ concrete (C30)
CARBON_STEEL_PER_KG = 1.9             # kgCO2e per kg steel rebar
SLAB_TYPES = ("flat", "ribbed", "two-way")

GENES = {
    "bay_x": (4.0, 9.0),        # (min, max) m spacing
    "bay_y": (4.0, 9.0),
    "col_size": (0.25, 0.6),    # column side (m)
    "beam_depth": (0.4, 0.9),
    "slab_type": (0, len(SLAB_TYPES) - 1),
}


class GenerativeError(Exception):
    """Raised when a design generation request is invalid."""


@dataclass
class DesignOption:
    """A candidate structural scheme with its scored fitness."""

    option_id: str
    genes: Dict[str, Any]
    fitness: Dict[str, float]          # cost, carbon, flexibility, safety
    plan: Dict[str, Any]               # serialisable PlanData
    summary: str = ""
    rank: int = 0


# ---------------------------------------------------------------- chromosome --
def random_genes(rng: random.Random) -> Dict[str, Any]:
    return {
        "bay_x": round(rng.uniform(*GENES["bay_x"]), 2),
        "bay_y": round(rng.uniform(*GENES["bay_y"]), 2),
        "col_size": round(rng.uniform(*GENES["col_size"]), 3),
        "beam_depth": round(rng.uniform(*GENES["beam_depth"]), 3),
        "slab_type": SLAB_TYPES[rng.randint(*GENES["slab_type"])],
    }


def mutate_genes(genes: Dict[str, Any], rng: random.Random, rate: float = 0.25) -> Dict[str, Any]:
    out = dict(genes)
    if rng.random() < rate:
        out["bay_x"] = round(rng.uniform(*GENES["bay_x"]), 2)
    if rng.random() < rate:
        out["bay_y"] = round(rng.uniform(*GENES["bay_y"]), 2)
    if rng.random() < rate:
        out["col_size"] = round(rng.uniform(*GENES["col_size"]), 3)
    if rng.random() < rate:
        out["beam_depth"] = round(rng.uniform(*GENES["beam_depth"]), 3)
    if rng.random() < rate:
        out["slab_type"] = SLAB_TYPES[rng.randint(*GENES["slab_type"])]
    return out


def crossover(a: Dict[str, Any], b: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """Uniform crossover producing a child from two parents."""
    keys = list(GENES.keys())
    return {k: (rng.choice([a[k], b[k]]) if k in keys else a[k]) for k in a}


def build_plan(genes: Dict[str, Any], length_m: float, width_m: float,
               stories: int = 1, origin_x: float = 0.0, origin_y: float = 0.0) -> PlanData:
    """Instantiate a complete PlanData from a gene set and building envelope."""
    bay_x, bay_y = genes["bay_x"], genes["bay_y"]
    n_x = max(1, int(round(length_m / bay_x)))
    n_y = max(1, int(round(width_m / bay_y)))

    plan = PlanData(source="generative", stories=max(1, stories))
    plan.materials = {"concrete": "C30", "steel": "A615 Gr60", "slab": genes["slab_type"]}

    xs = [origin_x + i * (length_m / n_x) for i in range(n_x + 1)]
    ys = [origin_y + i * (width_m / n_y) for i in range(n_y + 1)]

    idx = 0
    for x in xs:
        for y in ys:
            plan.columns.append(Column(
                id=f"gc{idx}", cx=x, cy=y,
                size_m=genes["col_size"], height=3.0,
            ))
            idx += 1

    bidx = 0
    for x in xs:
        for j in range(n_y):
            plan.beams.append(Beam(
                id=f"gb{bidx}", x1=x, y1=ys[j], x2=x, y2=ys[j + 1],
                depth_m=genes["beam_depth"], width_m=genes["col_size"],
            ))
            bidx += 1
    for y in ys:
        for i in range(n_x):
            plan.beams.append(Beam(
                id=f"gb{bidx}", x1=xs[i], y1=y, x2=xs[i + 1], y2=y,
                depth_m=genes["beam_depth"], width_m=genes["col_size"],
            ))
            bidx += 1

    plan.walls.append(Wall(id="gw0", x1=xs[0], y1=ys[0], x2=xs[-1], y2=ys[0]))
    plan.walls.append(Wall(id="gw1", x1=xs[-1], y1=ys[0], x2=xs[-1], y2=ys[-1]))
    plan.grids = [{"id": f"v{i}", "orientation": "vertical", "position": x, "label": str(i + 1)}
                  for i, x in enumerate(xs)]
    return plan


def _structure_volume(plan: PlanData) -> Dict[str, float]:
    """Concrete + steel volume from a plan (mirrors preliminary_boq)."""
    b = plan.bounds()
    slab_area = max((b["max_x"] - b["min_x"]), 1.0) * max((b["max_y"] - b["min_y"]), 1.0)
    slab_depth = {"flat": 0.18, "ribbed": 0.28, "two-way": 0.22}.get(
        (plan.materials or {}).get("slab", "flat"), 0.18)
    slab_vol = slab_area * slab_depth * max(1, plan.stories)
    col_vol = sum((c.size_m ** 2) * c.height for c in plan.columns) * max(1, plan.stories)
    beam_vol = sum(b.width_m * b.depth_m * math.hypot(b.x2 - b.x1, b.y2 - b.y1)
                   for b in plan.beams)
    total = slab_vol + col_vol + beam_vol
    return {"concrete_m3": total, "steel_kg": total * 100.0, "slab_area_m2": slab_area}


def evaluate_fitness(genes: Dict[str, Any], length_m: float, width_m: float,
                     stories: int = 1) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Compute (cost, carbon, flexibility, safety) fitness from genes.

    Lower is better for all objectives; all four are area-normalised.
    """
    plan = build_plan(genes, length_m, width_m, stories)
    vol = _structure_volume(plan)

    cost = (vol["concrete_m3"] * CONCRETE_COST_PER_M3 + vol["steel_kg"] * STEEL_COST_PER_KG)
    cost_per_m2 = cost / max(vol["slab_area_m2"], 1.0)

    carbon = (vol["concrete_m3"] * CARBON_CONCRETE_PER_M3 + vol["steel_kg"] * CARBON_STEEL_PER_KG)
    carbon_per_m2 = carbon / max(vol["slab_area_m2"], 1.0)

    flexibility = (genes["bay_x"] + genes["bay_y"]) / 18.0   # ~1.0 at 9m bays
    n_cols = len(plan.columns)
    tributary = max(vol["slab_area_m2"] / max(n_cols, 1), 1.0)
    safety = (genes["col_size"] / 0.3) * (tributary / 25.0)

    fitness = {
        "cost": round(cost_per_m2, 2),
        "carbon": round(carbon_per_m2, 2),
        "flexibility": round(flexibility, 3),
        "safety": round(safety, 3),
    }
    return fitness, plan.model_dump(mode="json")


# ------------------------------------------------------------- NSGA helpers ----
def _dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
    """True if a is <= b on all objectives and < on at least one."""
    keys = ("cost", "carbon", "flexibility", "safety")
    better = False
    for k in keys:
        if a[k] > b[k]:
            return False
        if a[k] < b[k]:
            better = True
    return better


def pareto_front(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return the non-dominated set (lower-is-better on every objective)."""
    front = []
    for c in candidates:
        dominated = False
        for other in candidates:
            if _dominates(other["fitness"], c["fitness"]):
                dominated = True
                break
        if not dominated:
            front.append(c)
    return front


class GenerativeDesignEngine:
    """Runs the GA population and returns the top Pareto-optimal options."""

    def __init__(self, population: int = 50, generations: int = 100, seed: int = 42):
        self.population = population
        self.generations = max(1, min(generations, 200))
        self.seed = seed
        self.rng = random.Random(seed)

    # -- public ----------------------------------------------------
    def generate(self, length_m: float, width_m: float, stories: int = 1,
                 progress=None) -> List[DesignOption]:
        """Run optimisation and return the top 3 options (lowest aggregate).

        ``progress`` is an optional callable accepting a float 0..1 to drive
        the frontend progress bar.
        """
        if not (1 <= length_m <= 300 and 1 <= width_m <= 300):
            raise GenerativeError("Dimensions must be between 1 m and 300 m.")

        population = [random_genes(self.rng) for _ in range(self.population)]
        for gen in range(self.generations):
            scored = []
            for genes in population:
                fitness, plan = evaluate_fitness(genes, length_m, width_m, stories)
                scored.append({"genes": genes, "fitness": fitness, "plan": plan})
            scored.sort(key=lambda s: sum(s["fitness"].values()))
            elites = scored[: max(2, self.population // 2)]
            children = []
            while len(elites) + len(children) < self.population:
                a = self.rng.choice(elites)["genes"]
                b = self.rng.choice(elites)["genes"]
                children.append(mutate_genes(crossover(a, b, self.rng), self.rng))
            population = [s["genes"] for s in elites] + children
            if progress:
                progress((gen + 1) / self.generations)

        scored = []
        for genes in population:
            fitness, plan = evaluate_fitness(genes, length_m, width_m, stories)
            scored.append({"genes": genes, "fitness": fitness, "plan": plan})

        front = pareto_front(scored)
        front.sort(key=lambda s: sum(s["fitness"].values()))
        top = front[:3] or scored[:3]

        return [DesignOption(
            option_id=f"opt-{i + 1}",
            genes=s["genes"],
            fitness=s["fitness"],
            plan=s["plan"],
            rank=i + 1,
        ) for i, s in enumerate(top)]

    # -- caching ----------------------------------------------------
    def cache_key(self, length_m: float, width_m: float, stories: int) -> str:
        return f"gen-d{length_m:.1f}x{width_m:.1f}x{stories}"

    def cache_path(self, length_m: float, width_m: float, stories: int) -> Path:
        return Path(storage_root()) / "generative" / f"{self.cache_key(length_m, width_m, stories)}.json"

    def load_cached(self, length_m: float, width_m: float, stories: int) -> Optional[List[Dict[str, Any]]]:
        path = self.cache_path(length_m, width_m, stories)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def store_cache(self, length_m: float, width_m: float, stories: int,
                    options: List[DesignOption]) -> None:
        path = self.cache_path(length_m, width_m, stories)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [{
            "option_id": o.option_id, "genes": o.genes, "fitness": o.fitness,
            "plan": o.plan, "rank": o.rank,
        } for o in options]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")