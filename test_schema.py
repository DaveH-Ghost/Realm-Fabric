"""
test_schema.py

Purpose:
This script exists to test the AgentTurn Pydantic schema in isolation.

It is useful during early development to:
- Verify that the schema imports correctly
- See what valid outputs look like
- Understand what kinds of invalid outputs the validators catch
- Experiment with edge cases without running the full simulation

Run it with:
    uv run python test_schema.py
"""

from src.llm.schemas import AgentTurn
from pydantic import ValidationError


def print_separator(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_valid_case(name: str, data: dict):
    """Test a case that should succeed."""
    print(f"\n>>> Testing: {name}")
    try:
        turn = AgentTurn(**data)
        print("SUCCESS")
        print(f"  action   : {turn.action}")
        print(f"  target   : {turn.target}")
        print(f"  content  : {turn.content}")
        print(f"  reasoning: {turn.reasoning[:80]}{'...' if len(turn.reasoning) > 80 else ''}")
    except ValidationError as e:
        print("UNEXPECTED FAILURE")
        print(e)


def test_invalid_case(name: str, data: dict):
    """Test a case that should fail validation."""
    print(f"\n>>> Testing: {name}")
    try:
        turn = AgentTurn(**data)
        print("UNEXPECTED SUCCESS (this should have failed!)")
        print(turn)
    except ValidationError as e:
        print("EXPECTED FAILURE")
        # Print only the first error for readability
        error = e.errors()[0]
        print(f"  Error type : {error['type']}")
        print(f"  Location   : {error['loc']}")
        print(f"  Message    : {error['msg']}")


if __name__ == "__main__":
    print("AgentTurn Schema Test Script")
    print("Testing structured output validation for V0\n")

    # ==========================================
    # VALID CASES
    # ==========================================

    print_separator("VALID CASES")

    # Valid move
    test_valid_case(
        "Valid move action",
        {
            "reasoning": "The sign is still showing [?]. I should move north to get closer to it.",
            "action": "move",
            "target": "north",
            "confidence": "decided",
            "emotion": "focused",
        },
    )

    # Valid look
    test_valid_case(
        "Valid look action",
        {
            "reasoning": "The ceramic ball has a question mark. I need to use the look action to learn more about it.",
            "action": "look",
            "target": "obj_ball_01",
            "confidence": "curious",
            "emotion": "intrigued",
        },
    )

    # Valid speak (within limits)
    test_valid_case(
        "Valid speak action",
        {
            "reasoning": "I don't have new information yet. I should comment on what I see.",
            "action": "speak",
            "target": None,
            "content": "That ball looks interesting. I wonder what it is made of.",
            "confidence": "uncertain",
            "emotion": "curious",
        },
    )

    # ==========================================
    # INVALID CASES (should trigger validators)
    # ==========================================

    print_separator("INVALID CASES")

    # Invalid move direction
    test_invalid_case(
        "Invalid move direction (not cardinal)",
        {
            "reasoning": "I want to explore.",
            "action": "move",
            "target": "northwest",  # Invalid
        },
    )

    # Reasoning too long
    test_invalid_case(
        "Reasoning exceeds 400 character limit",
        {
            "reasoning": "This is a very long reasoning string. " * 25,  # Way over 400 chars
            "action": "move",
            "target": "south",
        },
    )

    # Speak with emotes (asterisks)
    test_invalid_case(
        "Speak contains emotes using asterisks",
        {
            "reasoning": "I feel happy.",
            "action": "speak",
            "content": "This ball is really cool! *smiles happily*",
        },
    )

    # Speak with parentheses (heuristic)
    test_invalid_case(
        "Speak contains parentheses (heuristic trigger)",
        {
            "reasoning": "Just thinking out loud.",
            "action": "speak",
            "content": "I wonder what (the sign) is trying to tell me.",
        },
    )

    # Speak with too many sentences
    test_invalid_case(
        "Speak exceeds 3 sentence limit",
        {
            "reasoning": "I have a lot to say.",
            "action": "speak",
            "content": "First sentence. Second sentence. Third sentence. Fourth sentence here.",
        },
    )

    # Speak too long (character limit)
    # This string is 317 characters long.
    test_invalid_case(
        "Speak content exceeds 280 characters",
        {
            "reasoning": "Testing length limits.",
            "action": "speak",
            "content": (
                "This is a deliberately long piece of dialogue designed to exceed the "
                "two hundred and eighty character limit that exists for the speak action "
                "in Version 0. The schema should reject this input during validation."
                "This is extra text that is needed to reach the maximum 280 character limit."
            ),
        },
    )

    print("\n" + "=" * 60)
    print("  All tests completed.")
    print("=" * 60)
