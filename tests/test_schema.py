"""
test_schema.py

Purpose:
This module contains pytest tests for the AgentTurn Pydantic schema.

It is useful during early development to:
- Verify that the schema imports correctly
- Test that valid outputs are accepted
- Ensure the validators correctly reject various kinds of invalid outputs
- Experiment with edge cases without running the full simulation

Run with:
    uv run pytest tests/test_schema.py -q
    # or for more detail:
    uv run pytest tests/test_schema.py -v

# You can also just run:
#   uv run pytest
# to discover and run all tests in the tests/ folder.
"""

import pytest
from pydantic import ValidationError

from src.llm.schemas import AgentTurn


# =============================================================================
# VALID CASES
# =============================================================================

def test_valid_move_action():
    """A well-formed move action should parse successfully."""
    data = {
        "reasoning": "The sign is still showing [?]. I should move north to get closer to it.",
        "action": "move",
        "target": "north",
        "confidence": "decided",
        "emotion": "focused",
    }
    turn = AgentTurn(**data)
    assert turn.action == "move"
    assert turn.target == "north"
    assert turn.reasoning.startswith("The sign is still showing")


def test_valid_look_action():
    """A well-formed look action should parse successfully."""
    data = {
        "reasoning": "The ceramic ball has a question mark. I need to use the look action to learn more about it.",
        "action": "look",
        "target": "obj_ball_01",
        "confidence": "curious",
        "emotion": "intrigued",
    }
    turn = AgentTurn(**data)
    assert turn.action == "look"
    assert turn.target == "obj_ball_01"


def test_valid_speak_action():
    """A well-formed speak action within limits should parse successfully."""
    data = {
        "reasoning": "I don't have new information yet. I should comment on what I see.",
        "action": "speak",
        "target": None,
        "content": "That ball looks interesting. I wonder what it is made of.",
        "confidence": "uncertain",
        "emotion": "curious",
    }
    turn = AgentTurn(**data)
    assert turn.action == "speak"
    assert "ball looks interesting" in turn.content


# =============================================================================
# INVALID CASES
# =============================================================================

def test_invalid_move_direction_not_cardinal():
    """Move target must be one of north, east, south, west."""
    data = {
        "reasoning": "I want to explore.",
        "action": "move",
        "target": "northwest",  # Invalid
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "INVALID_TARGET" in str(exc_info.value)


def test_invalid_reasoning_exceeds_400_chars():
    """Reasoning must be 400 characters or fewer."""
    data = {
        "reasoning": "This is a very long reasoning string. " * 25,  # Way over 400 chars
        "action": "move",
        "target": "south",
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "REASONING_TOO_LONG" in str(exc_info.value)


def test_invalid_speak_contains_emotes_asterisks():
    """Speak content must not contain emotes using * or _."""
    data = {
        "reasoning": "I feel happy.",
        "action": "speak",
        "content": "This ball is really cool! *smiles happily*",
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "INVALID_CONTENT" in str(exc_info.value)


def test_invalid_speak_contains_parentheses():
    """Speak content must not contain parentheses (lightweight heuristic)."""
    data = {
        "reasoning": "Just thinking out loud.",
        "action": "speak",
        "content": "I wonder what (the sign) is trying to tell me.",
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "INVALID_CONTENT" in str(exc_info.value)


def test_invalid_speak_exceeds_3_sentences():
    """Speak content is limited to a maximum of 3 sentences."""
    data = {
        "reasoning": "I have a lot to say.",
        "action": "speak",
        "content": "First sentence. Second sentence. Third sentence. Fourth sentence here.",
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "CONTENT_TOO_LONG" in str(exc_info.value)
    assert "3 sentences" in str(exc_info.value)


def test_invalid_speak_exceeds_280_characters():
    """Speak content is limited to 280 characters."""
    data = {
        "reasoning": "Testing length limits.",
        "action": "speak",
        "content": (
            "This is a deliberately long piece of dialogue designed to exceed the "
            "two hundred and eighty character limit that exists for the speak action "
            "in Version 0. The schema should reject this input during validation."
            "This is extra text that is needed to reach the maximum 280 character limit."
        ),
    }
    with pytest.raises(ValidationError) as exc_info:
        AgentTurn(**data)
    assert "CONTENT_TOO_LONG" in str(exc_info.value)
    assert "280 characters" in str(exc_info.value)
