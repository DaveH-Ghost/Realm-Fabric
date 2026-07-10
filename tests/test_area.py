"""
test_area.py — initial demo area state and grid helpers.

Run: uv run pytest tests/test_area.py -v
"""

import pytest

from campaign_rpg_engine.perception import build_passive_vision, perform_look
from campaign_rpg_engine.area import create_initial_area, create_area


def test_initial_area_has_correct_agent():
    """The initial area should contain the expected starting agent."""
    area = create_initial_area()
    agent = area.get_agent()

    assert agent is not None
    assert agent.id == "agent_01"
    assert agent.name == "Explorer"
    assert agent.position == (1, 1)
    assert len(agent.memory.turns) == 0
    assert agent.last_action is None
    assert "curious explorer" in agent.personality.lower()
    assert "curious explorer" in agent.passive_description.lower()


def test_initial_area_has_correct_objects():
    """The initial area should contain exactly the ball and the sign."""
    area = create_initial_area()
    objects = area.get_objects()

    assert len(objects) == 2

    ids = {obj.id for obj in objects}
    assert ids == {"obj_ball_01", "obj_sign_01"}

    names = {obj.name for obj in objects}
    assert names == {"Ceramic Ball", "Wooden Sign"}


def test_object_positions_match_spec():
    """Ball and sign should be at the exact positions defined in the V0 spec."""
    area = create_initial_area()

    ball = area.get_object_at((2, 2))
    assert ball is not None
    assert ball.id == "obj_ball_01"
    assert ball.name == "Ceramic Ball"

    sign = area.get_object_at((2, 4))
    assert sign is not None
    assert sign.id == "obj_sign_01"
    assert sign.name == "Wooden Sign"


def test_empty_tile_has_no_object():
    """Tiles without objects should return None from get_object_at."""
    area = create_initial_area()

    assert area.get_object_at((0, 0)) is None
    assert area.get_object_at((1, 1)) is None  # Agent's starting tile


def test_is_valid_position_respects_grid_boundaries():
    """is_valid_position should correctly identify in-bounds and out-of-bounds positions."""
    area = create_initial_area()

    # Valid positions (0-4 inclusive)
    assert area.is_valid_position((0, 0)) is True
    assert area.is_valid_position((1, 1)) is True
    assert area.is_valid_position((4, 4)) is True
    assert area.is_valid_position((2, 3)) is True

    # Invalid positions
    assert area.is_valid_position((5, 3)) is False
    assert area.is_valid_position((-1, 2)) is False
    assert area.is_valid_position((3, 5)) is False
    assert area.is_valid_position((5, 5)) is False


def test_get_agent_returns_same_agent():
    """get_agent should consistently return the same agent instance."""
    area = create_initial_area()

    agent1 = area.get_agent()
    agent2 = area.get_agent()

    assert agent1 is agent2
    assert agent1.id == "agent_01"


def test_area_grid_constants_are_correct():
    """The area should declare the expected 5x5 grid dimensions."""
    area = create_initial_area()

    assert area.WIDTH == 5
    assert area.HEIGHT == 5
    assert area.MIN_COORD == 0
    assert area.MAX_COORD == 4


def test_area_description_is_configurable():
    """Area description is set at area creation."""
    area = create_initial_area()
    desc = area.get_area_description()

    assert isinstance(desc, str)
    assert len(desc) > 0
    assert "hardwood floor" in desc.lower() or "wooden walls" in desc.lower()

    custom = create_area(area_description="A windy mountaintop.")
    assert custom.get_area_description() == "A windy mountaintop."


def test_passive_vision_matches_initial_state():
    """build_passive_vision should produce the expected text for the starting area."""
    area = create_initial_area()
    agent = area.get_agent()

    vision = build_passive_vision(agent, area)

    assert "You are at (1, 1)." in vision
    # Ball starts unknown
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in vision
    # Sign shows passive glance + [?] until examined
    assert (
        "Wooden Sign (obj_sign_01), (2, 4) - [?] A simple wooden sign on the wall."
        in vision
    )


def test_perform_look_updates_memory_and_returns_description():
    """Looking at an object should mark it looked-at and return the description."""
    area = create_initial_area()
    agent = area.get_agent()

    # Ball starts unknown
    assert not agent.memory.has_looked_at("obj_ball_01")

    outcome = perform_look(agent, area, "obj_ball_01")

    assert "You looked at the ceramic ball" in outcome.result
    assert "scuffs and feels light" in outcome.result
    assert agent.memory.has_looked_at("obj_ball_01")
    assert agent.memory.has_ever_looked_at("obj_ball_01")
