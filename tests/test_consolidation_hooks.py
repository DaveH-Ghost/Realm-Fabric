"""Consolidation failure hooks notify apps (e.g. Studio SSE)."""

from __future__ import annotations

from campaign_rpg_engine.memory_modules.base import MemoryRecordContext
from campaign_rpg_engine.memory_modules.consolidation_hooks import (
    clear_consolidation_failure_listeners_for_tests,
    notify_consolidation_failure,
    register_consolidation_failure_listener,
)
from campaign_rpg_engine.memory_modules.rolling_summary import RollingSummaryModule
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep


def setup_function():
    clear_consolidation_failure_listeners_for_tests()


def teardown_function():
    clear_consolidation_failure_listeners_for_tests()


def _record_ctx(turn_number: int = 1, agent_name: str = "Explorer") -> MemoryRecordContext:
    return MemoryRecordContext(
        agent_id="agent_01",
        turn_number=turn_number,
        agent_name=agent_name,
    )


def _speak_turn(turn_number: int) -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="speak",
                reasoning=f"reason-{turn_number}",
                target=None,
                content="Hi.",
                result='You said: "Hi."',
            )
        ],
        result='You said: "Hi."',
        reasoning=f"reason-{turn_number}",
    )


def test_notify_calls_registered_listeners():
    seen = []

    def listener(**payload):
        seen.append(payload)

    register_consolidation_failure_listener(listener)
    notify_consolidation_failure(
        agent_name="Praxis",
        turn_number=3,
        concurrency_limit_exceeded=True,
        message="Concurrency limit exceeded",
    )
    assert len(seen) == 1
    assert seen[0]["agent_name"] == "Praxis"
    assert seen[0]["concurrency_limit_exceeded"] is True


def test_rolling_summary_failure_notifies_concurrency():
    seen = []
    register_consolidation_failure_listener(lambda **p: seen.append(p))

    def always_fail(**kwargs):
        raise RuntimeError("Error code: 429 - Concurrency limit exceeded (4 units)")

    module = RollingSummaryModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=always_fail,
    )
    for i in range(1, 3):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i, agent_name="Praxis"))

    assert module.consolidation_state == "failed"
    assert seen
    assert seen[-1]["concurrency_limit_exceeded"] is True
    assert seen[-1]["agent_name"] == "Praxis"
