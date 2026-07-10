"""
test_schema.py

Pydantic validation for V0.2.5 compound turn schema.
"""

import pytest
from pydantic import ValidationError

from campaign_rpg_engine.llm.schemas import (
    AgentCompoundTurn,
    count_speak_sentences,
    normalize_compound_turn_payload,
)


def test_valid_compound_stay_and_speak():
    turn = AgentCompoundTurn(
        reasoning="Staying put.",
        move=None,
        action="none",
        say="Hello.",
    )
    assert turn.move is None
    assert turn.say == "Hello."


def test_valid_compound_speak_and_interact():
    turn = AgentCompoundTurn(
        reasoning="Talk and act.",
        say="Hello.",
        action="interact",
        target="obj_cookie_01",
        verb="eat",
    )
    assert turn.say == "Hello."
    assert turn.action == "interact"


def test_valid_compound_move():
    turn = AgentCompoundTurn(
        reasoning="Going.",
        move="2,4",
        action="none",
    )
    assert turn.move == "2,4"


def test_valid_compound_move_to_entity_id():
    turn = AgentCompoundTurn(
        reasoning="To the ball.",
        move="obj_ball_01",
        action="none",
    )
    assert turn.move == "obj_ball_01"


def test_invalid_compound_cardinal_move():
    with pytest.raises(ValidationError) as exc_info:
        AgentCompoundTurn(
            reasoning="Old.",
            move="north",
            action="none",
        )
    assert "ERR:INVALID_TARGET" in str(exc_info.value)


def test_valid_compound_speak():
    turn = AgentCompoundTurn(
        reasoning="Speaking.",
        action="none",
        say="Hello there.",
    )
    assert turn.say == "Hello there."


def test_compound_rejects_legacy_speak_turn_action():
    with pytest.raises(ValidationError):
        AgentCompoundTurn(reasoning="x", action="speak", say="Hi")


def test_valid_compound_look_only():
    turn = AgentCompoundTurn(
        reasoning="Looking.",
        look="obj_ball_01",
        action="none",
    )
    assert turn.look == "obj_ball_01"


def test_compound_interact_requires_fields():
    with pytest.raises(ValidationError):
        AgentCompoundTurn(reasoning="x", action="interact", target="obj_x")


def test_legacy_json_keys_normalized():
    payload = normalize_compound_turn_payload(
        {
            "reasoning": "legacy",
            "move_target": "2,3",
            "look_target": "obj_ball_01",
            "content": "Hi",
            "turn_action": "none",
            "target": None,
            "action_name": None,
        }
    )
    turn = AgentCompoundTurn.model_validate(payload)
    assert turn.move == "2,3"
    assert turn.look == "obj_ball_01"
    assert turn.say == "Hi"


def test_count_speak_sentences_ellipsis():
    assert count_speak_sentences("Hi! Wait... really?") == 2


def test_speak_truncated_when_later_sentence_starts_after_budget():
    first = "A" * 498 + ". "
    second = "B" * 50
    turn = AgentCompoundTurn(
        reasoning="x",
        action="none",
        say=first + second,
    )
    assert turn.say == "A" * 498 + "."
    assert "B" not in turn.say


def test_speak_single_long_sentence_not_cut_mid_sentence():
    text = "A" * 501
    turn = AgentCompoundTurn(reasoning="x", action="none", say=text)
    assert len(turn.say) == 501


def test_reasoning_truncated_drops_late_sentences():
    first = "a" * 398 + ". "
    second = "b" * 100
    turn = AgentCompoundTurn(reasoning=first + second, action="none")
    assert turn.reasoning == "a" * 398 + "."
