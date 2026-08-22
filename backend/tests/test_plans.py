"""Sprint 3 — Plan generation tests."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from app.services.ai_provider import AIProvider, BaseMessage
from app.services.noncad_processor import (
    PlanGenerationError,
    PlanGenerator,
    TEMPLATE_LIBRARY,
)


class FakeAI(AIProvider):
    """Deterministic provider that echoes a fixed layout for NL input."""

    provider_name = "fake"

    def __init__(self, reply: Dict[str, Any]):
        self.reply = reply

    async def chat_json(self, messages: List[BaseMessage], temperature: float = 0.2):
        return dict(self.reply)


def test_template_library_has_at_least_five():
    assert len(TEMPLATE_LIBRARY) >= 5
    for tid in ("small_office", "warehouse", "school_block"):
        assert tid in TEMPLATE_LIBRARY


def test_generate_from_template():
    gen = PlanGenerator()
    plan = gen.generate_from_template("warehouse", floors=2)
    assert plan.source == "template"
    assert plan.stories == 2
    assert len(plan.columns) >= 6
    assert plan.original["template_id"] == "warehouse"


def test_generate_from_questionnaire():
    gen = PlanGenerator()
    plan = gen.generate_from_questionnaire({"length_m": 18, "width_m": 9, "floors": 3})
    assert plan.source == "questionnaire"
    assert plan.stories == 3
    assert len(plan.columns) >= 4


def test_questionnaire_rejects_bad_dimensions():
    gen = PlanGenerator()
    with pytest.raises(PlanGenerationError):
        gen.generate_from_questionnaire({"length_m": 0, "width_m": 1, "floors": 1})


def test_generate_from_description():
    fake = FakeAI({"length_m": 24, "width_m": 12, "bays_x": 3, "bays_y": 2, "use": "office"})
    gen = PlanGenerator(ai=fake)

    plan = asyncio.run(
        gen.generate_from_description("A three-bay office block of 24 by 12 metres")
    )
    assert plan.source == "ai"
    assert plan.stories == 1
    assert len(plan.columns) >= 4


def test_save_and_load_plan(temp_storage):
    gen = PlanGenerator(storage_dir=temp_storage)
    plan = gen.generate_from_template("small_office")
    meta = gen.save_plan(7, "My Office", plan)
    assert meta["walls"] == len(plan.walls)

    loaded = PlanGenerator.load_plan(7, "My Office", storage_dir=temp_storage)
    assert loaded.label == plan.label

    listed = PlanGenerator.list_plans(7, storage_dir=temp_storage)
    assert any(item["name"] == "my-office" for item in listed)


def test_load_missing_plan_raises(temp_storage):
    with pytest.raises(PlanGenerationError):
        PlanGenerator.load_plan(99, "ghost", storage_dir=temp_storage)