"""
test_simulation.py

Purpose:
Pytest tests for the core step functionality (step_turn + execute_action).

These tests verify:
- TurnRecord creation with correct reasoning + result
- Memory updates (turns added, looked_at changes via look)
- last_action tracking on the agent
- Correct result strings for move / look / speak per the V0 spec
- Position changes only on successful actions
- Graceful handling of unexpected actions

This lets us exercise the full "AgentTurn → action → memory/world update" loop
in isolation, before wiring up the LLM client.

Run with:
    uv run pytest tests/test_simulation.py -q
    # or for more detail:
    uv run pytest tests/test_simulation.py -v

# You can also just run:
#   uv run pytest
# to discover and run all tests in the tests/ folder.
"""

import pytest

from src.llm.prompt import build_prompt
from src.llm.schemas import AgentTurn
from src.simulation import execute_action, step_turn
from src.world import create_initial_world


# =============================================================================
# Helper to create AgentTurn for tests (simulates LLM output)
# =============================================================================

def make_turn(
    reasoning: str = "Test reasoning.",
    action: str = "move",
    target: str | None = None,
    content: str | None = None,
) -> AgentTurn:
    """Convenience for creating valid AgentTurn objects in tests."""
    return AgentTurn(
        reasoning=reasoning,
        action=action,
        target=target,
        content=content,
    )


# =============================================================================
# Basic step_turn behavior
# =============================================================================

def test_step_turn_creates_and_records_turn_record():
    """step_turn should return a TurnRecord and add it to the agent's memory."""
    world = create_initial_world()
    agent = world.get_agent()

    turn = make_turn(action="look", target="obj_ball_01")
    record = step_turn(agent, world, turn, turn_number=1)

    assert record.turn_number == 1
    assert record.action == "look"
    assert record.target == "obj_ball_01"
    assert record.reasoning == "Test reasoning."
    assert "You looked at the ceramic ball" in record.result

    assert len(agent.memory.turns) == 1
    assert agent.memory.turns[0] is record  # same object
    assert agent.last_action == "look"


def test_step_turn_preserves_reasoning_from_agent_turn():
    """The agent's private reasoning must be stored exactly as provided."""
    world = create_initial_world()
    agent = world.get_agent()

    custom_reasoning = "I really want to examine that interesting ball because reasons."
    turn = make_turn(reasoning=custom_reasoning, action="look", target="obj_ball_01")
    record = step_turn(agent, world, turn, turn_number=42)

    assert record.reasoning == custom_reasoning
    assert agent.memory.turns[0].reasoning == custom_reasoning


# =============================================================================
# Move action via step
# =============================================================================

def test_step_move_success_updates_position():
    """Successful move should change the agent's position and produce correct result."""
    world = create_initial_world()
    agent = world.get_agent()
    start_pos = agent.position  # (1, 1)

    turn = make_turn(action="move", target="north")
    record = step_turn(agent, world, turn, turn_number=1)

    assert agent.position == (1, 2)
    assert "You moved north to (1, 2)" in record.result
    assert len(agent.memory.turns) == 1


def test_step_move_failure_does_not_change_position():
    """Failed move (out of bounds) must leave position unchanged."""
    world = create_initial_world()
    agent = world.get_agent()
    # Force to north edge
    agent.position = (1, 4)

    turn = make_turn(action="move", target="north")
    record = step_turn(agent, world, turn, turn_number=1)

    assert agent.position == (1, 4)  # unchanged
    assert "outside the room" in record.result.lower()
    assert len(agent.memory.turns) == 1
    assert agent.last_action == "move"


# =============================================================================
# Look action via step
# =============================================================================

def test_step_look_marks_object_as_looked_at():
    """Successful look must update the agent's memory so future vision shows full desc."""
    world = create_initial_world()
    agent = world.get_agent()

    # Ball starts unknown (except for pre-marked sign)
    assert not agent.memory.has_looked_at("obj_ball_01")

    turn = make_turn(action="look", target="obj_ball_01")
    record = step_turn(agent, world, turn, turn_number=1)

    assert agent.memory.has_looked_at("obj_ball_01")
    assert "You looked at the ceramic ball" in record.result
    assert "scuffs and feels light" in record.result


def test_step_look_on_already_known_object_still_works():
    """Looking at something already known should still succeed and record the turn."""
    world = create_initial_world()
    agent = world.get_agent()
    agent.memory.mark_looked_at("obj_sign_01")

    turn = make_turn(action="look", target="obj_sign_01")
    record = step_turn(agent, world, turn, turn_number=1)

    assert agent.memory.has_looked_at("obj_sign_01")
    assert "You looked at the wooden sign" in record.result


# =============================================================================
# Speak action via step
# =============================================================================

def test_step_speak_records_exact_text():
    """Speak should record the content exactly and have no side effects on position or looked_at."""
    world = create_initial_world()
    agent = world.get_agent()
    start_pos = agent.position
    initial_looked = set(agent.memory.looked_at)

    spoken = "This ball feels familiar. I wonder where it came from."
    turn = make_turn(action="speak", content=spoken)
    record = step_turn(agent, world, turn, turn_number=1)

    assert f'You said: "{spoken}"' in record.result
    assert agent.position == start_pos  # no movement
    assert agent.memory.looked_at == initial_looked  # no change to looked_at
    assert len(agent.memory.turns) == 1


# =============================================================================
# Memory and last_action side effects
# =============================================================================

def test_multiple_steps_accumulate_in_memory():
    """Repeated steps should add multiple TurnRecords (capped at 10 by Memory)."""
    world = create_initial_world()
    agent = world.get_agent()

    for i in range(5):
        turn = make_turn(action="move", target="east")
        step_turn(agent, world, turn, turn_number=i + 1)

    assert len(agent.memory.turns) == 5
    assert agent.last_action == "move"
    assert all(r.action == "move" for r in agent.memory.turns)


def test_last_action_is_always_updated():
    """last_action should reflect the most recent action taken."""
    world = create_initial_world()
    agent = world.get_agent()

    turn1 = make_turn(action="move", target="east")
    step_turn(agent, world, turn1, turn_number=1)
    assert agent.last_action == "move"

    turn2 = make_turn(action="look", target="obj_ball_01")
    step_turn(agent, world, turn2, turn_number=2)
    assert agent.last_action == "look"

    turn3 = make_turn(action="speak", content="Thinking out loud.")
    step_turn(agent, world, turn3, turn_number=3)
    assert agent.last_action == "speak"


# =============================================================================
# Edge / error cases for step
# =============================================================================

def test_execute_action_unknown_action_returns_error_result():
    """execute_action has a fallback for unknown actions (should never reach it via schema)."""
    world = create_initial_world()
    agent = world.get_agent()

    # Simulate a bad AgentTurn (e.g. if future schema changes or direct calls)
    class FakeTurn:
        action = "teleport"
        target = None
        content = None

    result = execute_action(agent, world, FakeTurn())

    assert "wasn't recognized" in result


def test_step_unknown_action_still_records_turn():
    """Even for unknown action, step_turn should still produce a TurnRecord."""
    world = create_initial_world()
    agent = world.get_agent()

    class FakeTurn:
        action = "teleport"
        target = None
        content = None
        reasoning = "Weird state"

    record = step_turn(agent, world, FakeTurn(), turn_number=1)

    assert "wasn't recognized" in record.result
    assert record.action == "teleport"
    assert len(agent.memory.turns) == 1


# =============================================================================
# Prompt builder integration (used by the real LLM path)
# =============================================================================

def test_build_prompt_produces_reasonable_output():
    """The prompt builder should produce a non-empty string containing key sections (with examples enabled)."""
    world = create_initial_world()
    agent = world.get_agent()

    prompt = build_prompt(agent, world, include_examples=True)

    assert isinstance(prompt, str)
    assert len(prompt) > 500  # at least the rules + examples + current state
    assert "You are Explorer" in prompt
    assert "You exist inside a small, controlled 5x5 grid room" in prompt
    assert "You are at (1, 1)" in prompt  # from passive vision
    assert "You can look at anything with the [?] tag" in prompt
    assert '"reasoning"' in prompt  # output format reminder
    assert "Example 1: Correct use of `speak`" in prompt  # few-shot present
    assert "Example 4: Responding to the sign being updated" in prompt


def test_build_prompt_without_fewshots_is_shorter_and_lacks_examples():
    """With include_examples=False, prompt should be much shorter and omit the examples."""
    world = create_initial_world()
    agent = world.get_agent()

    prompt_with = build_prompt(agent, world, include_examples=True)
    prompt_without = build_prompt(agent, world, include_examples=False)

    assert len(prompt_without) < len(prompt_with)
    assert "Example 1: Correct use of `speak`" not in prompt_without
    assert "You are Explorer" in prompt_without  # still has the core parts
    assert "You can look at anything with the [?] tag" in prompt_without
