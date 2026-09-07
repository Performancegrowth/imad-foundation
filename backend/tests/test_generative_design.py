"""Roadmap #10 — generative design: real-engine validation of Pareto options."""
import pytest

from app.services.generative_design import (
    GenerativeDesignEngine, _real_fitness, _real_score,
    build_plan, evaluate_fitness, pareto_front,
)

GENES = {"bay_x": 6.0, "bay_y": 6.0, "col_size": 0.4, "beam_depth": 0.6,
         "slab_type": "flat"}


def test_real_fitness_returns_honest_metrics():
    """The final fitness must come from the real engine, with provenance."""
    fitness, plan = _real_fitness(GENES, 24.0, 14.0, stories=2)
    assert fitness["cost"] > 0                 # real BOQ USD/m²
    assert fitness["carbon"] > 0               # real LCA kgCO₂e/m²
    assert 0 < fitness["flexibility"] <= 1
    assert fitness["safety"] >= 0              # compliance penalty (0 = clean)
    assert fitness["validated"] is True
    assert "BOQ" in fitness["provenance"]["cost"]
    assert "LCA" in fitness["provenance"]["carbon"]
    assert "compliance" in fitness["provenance"]["safety"].lower()
    # plan is a serialisable dict with real geometry
    assert plan["columns"] and plan["beams"]


def test_real_fitness_penalises_failed_compliance():
    """A candidate that fails checks must score worse on safety."""
    # Very slender columns on a long span → likely punching/axial failures.
    bad = {"bay_x": 9.0, "bay_y": 9.0, "col_size": 0.25, "beam_depth": 0.4,
           "slab_type": "flat"}
    f_bad, _ = _real_fitness(bad, 30.0, 18.0, stories=3)
    f_good, _ = _real_fitness(GENES, 24.0, 14.0, stories=2)
    assert f_bad["safety"] >= f_good["safety"]


def test_real_score_ranks_lower_better():
    low = {"cost": 100.0, "carbon": 100.0, "flexibility": 0.5, "safety": 0.0}
    high = {"cost": 200.0, "carbon": 200.0, "flexibility": 0.5, "safety": 2.0}
    assert _real_score(low) < _real_score(high)


def test_generate_returns_validated_options():
    """A small run must return options whose fitness is real-engine validated."""
    opts = GenerativeDesignEngine(population=6, generations=3).generate(
        18.0, 12.0, stories=1)
    assert len(opts) == 3
    for o in opts:
        assert o.fitness.get("validated") is True
        assert o.fitness["cost"] > 0
        assert o.fitness["carbon"] > 0
        assert o.plan["columns"] and o.plan["beams"]


def test_generate_is_deterministic_with_seed():
    a = GenerativeDesignEngine(population=6, generations=3, seed=7).generate(
        18.0, 12.0)
    b = GenerativeDesignEngine(population=6, generations=3, seed=7).generate(
        18.0, 12.0)
    key = lambda o: (o.option_id, o.fitness["cost"], o.fitness["carbon"],
                     o.fitness["safety"])
    assert [key(o) for o in a] == [key(o) for o in b]


def test_fast_search_still_works():
    """The GA search heuristic (volumetric) must remain functional."""
    fitness, plan = evaluate_fitness(GENES, 24.0, 14.0, stories=2)
    assert fitness["cost"] > 0
    assert fitness["carbon"] > 0
    assert plan["columns"]


def test_pareto_front_returns_non_dominated():
    candidates = [
        {"fitness": {"cost": 100, "carbon": 100, "flexibility": 0.5, "safety": 0}},
        {"fitness": {"cost": 90, "carbon": 110, "flexibility": 0.5, "safety": 0}},
        {"fitness": {"cost": 120, "carbon": 90, "flexibility": 0.5, "safety": 0}},
        {"fitness": {"cost": 200, "carbon": 200, "flexibility": 0.5, "safety": 2}},
    ]
    front = pareto_front(candidates)
    # The dominated candidate (200/200/2) must not be on the front.
    assert all(c["fitness"]["cost"] < 200 for c in front)