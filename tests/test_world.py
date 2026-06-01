"""
test_world.py

Purpose:
Pytest tests for the initial world state in Version 0.

These tests verify that:
- The core data models (World, Agent, Object) work together correctly
- The initial world state matches the design in the readiness checklist
- Helper methods on World behave as expected

Run with:
    uv run pytest tests/test_world.py -q
    # or for more detail:
    uv run pytest tests/test_world.py -v

# You can also just run:
#   uv run pytest
# to discover and run all tests in the tests/ folder.
"""

import pytest

from src.world import create_initial_world


def test_initial_world_has_correct_agent():
    """The initial world should contain the expected starting agent."""
    world = create_initial_world()
    agent = world.get_agent()

    assert agent is not None
    assert agent.id == "agent_01"
    assert agent.name == "Explorer"
    assert agent.position == (1, 1)
    assert len(agent.memory) == 0
    assert agent.last_action is None
    assert "curious explorer" in agent.description.lower()


def test_initial_world_has_correct_objects():
    """The initial world should contain exactly the ball and the sign."""
    world = create_initial_world()
    objects = world.get_objects()

    assert len(objects) == 2

    ids = {obj.id for obj in objects}
    assert ids == {"obj_ball_01", "obj_sign_01"}

    names = {obj.name for obj in objects}
    assert names == {"Ceramic Ball", "Wooden Sign"}


def test_object_positions_match_spec():
    """Ball and sign should be at the exact positions defined in the V0 spec."""
    world = create_initial_world()

    ball = world.get_object_at((2, 2))
    assert ball is not None
    assert ball.id == "obj_ball_01"
    assert ball.name == "Ceramic Ball"

    sign = world.get_object_at((2, 4))
    assert sign is not None
    assert sign.id == "obj_sign_01"
    assert sign.name == "Wooden Sign"


def test_empty_tile_has_no_object():
    """Tiles without objects should return None from get_object_at."""
    world = create_initial_world()

    assert world.get_object_at((0, 0)) is None
    assert world.get_object_at((1, 1)) is None  # Agent's starting tile


def test_is_valid_position_respects_grid_boundaries():
    """is_valid_position should correctly identify in-bounds and out-of-bounds positions."""
    world = create_initial_world()

    # Valid positions (0-4 inclusive)
    assert world.is_valid_position((0, 0)) is True
    assert world.is_valid_position((1, 1)) is True
    assert world.is_valid_position((4, 4)) is True
    assert world.is_valid_position((2, 3)) is True

    # Invalid positions
    assert world.is_valid_position((5, 3)) is False
    assert world.is_valid_position((-1, 2)) is False
    assert world.is_valid_position((3, 5)) is False
    assert world.is_valid_position((5, 5)) is False


def test_get_agent_returns_same_agent():
    """get_agent should consistently return the same agent instance."""
    world = create_initial_world()

    agent1 = world.get_agent()
    agent2 = world.get_agent()

    assert agent1 is agent2
    assert agent1.id == "agent_01"


def test_world_grid_constants_are_correct():
    """The world should declare the expected 5x5 grid dimensions."""
    world = create_initial_world()

    assert world.WIDTH == 5
    assert world.HEIGHT == 5
    assert world.MIN_COORD == 0
    assert world.MAX_COORD == 4


def test_room_description_is_present():
    """The world should provide a static room description."""
    world = create_initial_world()
    desc = world.get_room_description()

    assert isinstance(desc, str)
    assert len(desc) > 0
    assert "hardwood floor" in desc.lower() or "wooden walls" in desc.lower()
