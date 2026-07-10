"""Tests for salient_turns memory module."""

import pytest

from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.base import MemoryObserveContext, MemoryRecordContext, MemoryRenderContext
from campaign_rpg_engine.memory_modules.registry import create_module, format_memory_module_label
from campaign_rpg_engine.memory_modules.salient_turns import (
    DEFAULT_CHAR_BUDGET,
    OMISSION_LINE,
    SalientTurnsModule,
    storage_salience,
    validate_char_budget,
)
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args


def _record_ctx(agent_id: str = "agent_01", turn_number: int = 1) -> MemoryRecordContext:
    return MemoryRecordContext(agent_id=agent_id, turn_number=turn_number)


def _observe_ctx(observer_id: str = "agent_01") -> MemoryObserveContext:
    return MemoryObserveContext(observer_id=observer_id)


def _render_ctx():
    area = create_initial_area()
    return MemoryRenderContext(agent=area.get_agent(), area=area)


def _move_turn(turn_number: int) -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="move",
                reasoning="move",
                target="2,2",
                content=None,
                result="You moved to (2, 2).",
            )
        ],
        result="You moved to (2, 2).",
        reasoning="move",
    )


def _speak_turn(turn_number: int, *, content: str = "Hi.", reasoning: str = "speak") -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="speak",
                reasoning=reasoning,
                target=None,
                content=content,
                result=f'You said: "{content}"',
            )
        ],
        result=f'You said: "{content}"',
        reasoning=reasoning,
    )


def _look_turn(turn_number: int, target: str = "obj_ball_01") -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="look",
                reasoning="look",
                target=target,
                content=None,
                result="You looked at the ball.",
            )
        ],
        result="You looked at the ball.",
        reasoning="look",
    )


def _compound_turn(turn_number: int) -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="move",
                reasoning="move",
                target="1,2",
                content=None,
                result="You moved to (1, 2).",
            ),
            TurnStep(
                kind="look",
                reasoning="look",
                target="agent_01",
                content=None,
                result="You looked at the explorer.",
            ),
            TurnStep(
                kind="speak",
                reasoning="speak",
                target=None,
                content="Hello!",
                result='You said: "Hello!"',
            ),
        ],
        result=(
            "You moved to (1, 2).\n"
            "You looked at the explorer.\n"
            'You said: "Hello!"'
        ),
        reasoning="Chat with the explorer.",
    )


def test_storage_salience_uses_peak_step():
    assert storage_salience(_move_turn(1)) == 1
    assert storage_salience(_look_turn(1)) == 3
    assert storage_salience(_speak_turn(1)) == 10
    assert storage_salience(_compound_turn(1)) == 10


def test_validate_char_budget_rejects_out_of_range():
    with pytest.raises(ValueError, match="memory-budget"):
        validate_char_budget(50)
    with pytest.raises(ValueError, match="memory-budget"):
        validate_char_budget(99999)


def test_salient_turns_empty_render():
    module = SalientTurnsModule(char_budget=1000)
    assert module.render(_render_ctx()) == ""


def test_storage_evicts_move_only_before_speak():
    module = SalientTurnsModule(char_budget=5000, storage_window=4, recency_floor=1)
    for i in range(1, 5):
        module.record_turn(_move_turn(i), _record_ctx(turn_number=i))
    module.record_turn(_speak_turn(5, content="Important."), _record_ctx(turn_number=5))

    stored_numbers = [t.turn_number for t in module.stored_turns]
    assert 5 in stored_numbers
    assert 1 not in stored_numbers
    assert len(stored_numbers) == 4


def test_recency_floor_protects_recent_move_only_in_storage():
    module = SalientTurnsModule(char_budget=5000, storage_window=3, recency_floor=2)
    module.record_turn(_move_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))
    module.record_turn(_move_turn(3), _record_ctx(turn_number=3))
    module.record_turn(_move_turn(4), _record_ctx(turn_number=4))

    stored_numbers = [t.turn_number for t in module.stored_turns]
    assert stored_numbers[-2:] == [3, 4]
    assert 2 in stored_numbers
    assert 1 not in stored_numbers


def test_render_respects_char_budget():
    module = SalientTurnsModule(char_budget=220, recency_floor=1, storage_window=20)
    module.record_turn(
        _speak_turn(1, content="A" * 80, reasoning="old"),
        _record_ctx(turn_number=1),
    )
    module.record_turn(
        _speak_turn(2, content="B" * 80, reasoning="newer"),
        _record_ctx(turn_number=2),
    )
    module.record_turn(
        _speak_turn(3, content="C" * 80, reasoning="newest"),
        _record_ctx(turn_number=3),
    )

    text = module.render(_render_ctx())
    assert len(text) <= 220 + len(OMISSION_LINE) + 4
    assert "Turn 3:" in text
    assert "Turn 1:" not in text
    assert OMISSION_LINE in text


def test_condensed_turn_format_without_step_list():
    module = SalientTurnsModule(char_budget=5000)
    module.record_turn(_compound_turn(1), _record_ctx(turn_number=1))

    text = module.render(_render_ctx())
    assert "  - move" not in text
    assert "Result:" in text
    assert 'You said: "Hello!"' in text


def test_reasoning_only_in_newest_three_turns():
    module = SalientTurnsModule(char_budget=5000, storage_window=10)
    for i in range(1, 6):
        module.record_turn(
            _speak_turn(i, content=f"t{i}", reasoning=f"reason-{i}"),
            _record_ctx(turn_number=i),
        )

    text = module.render(_render_ctx())
    assert "Reasoning: reason-3" in text
    assert "Reasoning: reason-4" in text
    assert "Reasoning: reason-5" in text
    assert "Reasoning: reason-1" not in text
    assert "Reasoning: reason-2" not in text


def test_old_compound_turn_drops_move_and_look_fragments():
    module = SalientTurnsModule(char_budget=5000, storage_window=10, recency_floor=1)
    module.record_turn(_compound_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_move_turn(2), _record_ctx(turn_number=2))

    text = module.render(_render_ctx())
    turn_one = text.split("Turn 2:")[0]
    assert "You moved to (1, 2)." not in turn_one
    assert "You looked at the explorer." not in turn_one
    assert 'You said: "Hello!"' in turn_one


def test_recency_floor_turn_keeps_all_compound_fragments():
    module = SalientTurnsModule(char_budget=5000, storage_window=10, recency_floor=2)
    module.record_turn(_compound_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_move_turn(2), _record_ctx(turn_number=2))

    text = module.render(_render_ctx())
    turn_two_section = text.split("Turn 2:")[1]
    assert "You moved to (2, 2)." in turn_two_section


def test_render_includes_witnessed_events():
    module = SalientTurnsModule(char_budget=2000)
    module.record_turn(_move_turn(1), _record_ctx(turn_number=1))
    module.record_observation(_witness("Goblin speaks."), _observe_ctx())
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))

    text = module.render(_render_ctx())
    assert "Before turn 2, you observed:" in text
    assert "Goblin speaks." in text


def test_create_module_salient_turns_with_budget():
    module = create_module("salient_turns", char_budget=1500)
    assert isinstance(module, SalientTurnsModule)
    assert module.char_budget == 1500


def test_create_module_rejects_budget_for_recent_turns():
    with pytest.raises(ValueError, match="memory-budget is only valid"):
        create_module("recent_turns", char_budget=2000)


def test_create_agent_salient_turns_with_memory_budget():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scribe" personality "x" memory salient_turns memory-budget 1800 at 2,2',
    )
    assert agent is not None
    assert agent.memory.module_id == "salient_turns"
    assert agent.memory.module.char_budget == 1800
    assert "budget=1800" in msg


def test_create_agent_memory_budget_without_module_implies_salient():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scribe" personality "x" memory-budget 2200 at 2,2',
    )
    assert agent is not None
    assert agent.memory.module_id == "salient_turns"
    assert agent.memory.module.char_budget == 2200


def test_create_agent_rejects_budget_with_recent_turns():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scribe" personality "x" memory recent_turns memory-budget 2200 at 2,2',
    )
    assert agent is None
    assert "memory-budget is only valid" in msg


def test_create_agent_rejects_invalid_memory_budget():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scribe" personality "x" memory salient_turns memory-budget huge at 2,2',
    )
    assert agent is None
    assert "integer" in msg


def test_memory_facade_salient_turns():
    memory = Memory(module_id="salient_turns", char_budget=2500)
    assert memory.module_id == "salient_turns"
    assert format_memory_module_label(memory.module) == "memory=salient_turns budget=2500"


def test_default_char_budget_constant():
    module = SalientTurnsModule()
    assert module.char_budget == DEFAULT_CHAR_BUDGET


def test_total_turns_monotonic_despite_storage_eviction():
    module = SalientTurnsModule(char_budget=5000, storage_window=3, recency_floor=1)
    for i in range(1, 8):
        module.record_turn(_move_turn(i), _record_ctx(turn_number=i))
    assert module.total_turns == 7
    assert len(module.stored_turns) == 3


def _witness(text: str):
    from campaign_rpg_engine.memory_modules.base import WitnessedEvent

    return WitnessedEvent(
        session_turn=1,
        actor_id="agent_goblin_01",
        actor_name="Goblin",
        text=text,
        actor_position=(0, 3),
    )
