"""
test_coordinate_move.py

V0.2 Section 1: coordinate-based move (via compound nav phase).
"""

import pytest
from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.coordinates import CoordinateParseError, parse_coordinate_target
from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.perception import build_passive_vision
from campaign_rpg_engine.simulation import execute_nav_phase, run_compound_turn
from pydantic import ValidationError


@pytest.mark.parametrize(
    "target,expected",
    [
        ("2,3", (2, 3)),
        ("2, 3", (2, 3)),
        ("(2,3)", (2, 3)),
        ("(2, 3)", (2, 3)),
    ],
)
def test_parse_coordinate_target_accepts_canonical_and_paren_forms(target, expected):
    assert parse_coordinate_target(target) == expected


@pytest.mark.parametrize("target", ["north", "2", "2,3,4", "obj_ball_01", ""])
def test_parse_coordinate_target_rejects_non_coordinates(target):
    with pytest.raises(CoordinateParseError):
        parse_coordinate_target(target)


def test_move_to_valid_coordinate_updates_position_and_results():
    area = create_initial_area()
    agent = area.get_agent()

    outcome = do_move(agent, area, "2,3")

    assert agent.position == (2, 3)
    assert outcome.result == "You moved to (2, 3)."
    assert outcome.passive_result == "Explorer moves to (2, 3)."


@pytest.mark.parametrize("target", ["5,5", "-1,0", "0,5"])
def test_move_off_grid_fails_without_position_change(target):
    area = create_initial_area()
    agent = area.get_agent()
    start = agent.position

    outcome = do_move(agent, area, target)

    assert agent.position == start
    assert "ERR:INVALID_COORDINATES" in outcome.result
    assert "outside the room" in outcome.result
    assert outcome.passive_result == ""


def test_move_same_tile_succeeds_without_passive_result():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (2, 3)

    outcome = do_move(agent, area, "2,3")

    assert agent.position == (2, 3)
    assert outcome.result == "You are already at (2, 3)."
    assert outcome.passive_result == ""


def test_move_malformed_target_returns_invalid_result():
    area = create_initial_area()
    agent = area.get_agent()
    start = agent.position

    outcome = do_move(agent, area, "north")

    assert agent.position == start
    assert "wasn't recognized" in outcome.result
    assert "ERR:INVALID_TARGET" in outcome.result
    assert outcome.passive_result == ""


def test_schema_rejects_cardinal_move_target():
    with pytest.raises(ValidationError) as exc_info:
        AgentCompoundTurn(
            reasoning="Old.",
            move="north",
            action="none",
        )
    assert "ERR:INVALID_TARGET" in str(exc_info.value)


def test_other_agent_vision_after_successful_move():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")
    goblin.position = (1, 1)

    run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="Repositioning.",
            move="2,3",
            action="none",
        ),
        turn_number=1,
    )

    vision = build_passive_vision(explorer, area)
    assert "Goblin (agent_goblin_01), (2, 3)" in vision
    assert "Goblin moves to (2, 3)." not in vision


def test_nav_phase_via_simulation():
    area = create_initial_area()
    agent = area.get_agent()
    steps = execute_nav_phase(
        agent,
        area,
        AgentCompoundTurn(
            reasoning="Test.",
            move="3,1",
            action="none",
        ),
    )
    assert agent.position == (3, 1)
    assert steps[0].result == "You moved to (3, 1)."


def test_prompt_uses_coordinate_move_not_cardinals():
    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area, include_examples=True)

    assert (
        "You may move to any coordinate (x, y) where x is an integer from 0 to 4 and "
        "y is an integer from 0 to 4." in prompt
    )
    assert '"move"' in prompt
    assert "cardinal direction" not in prompt.lower()
    assert "\n- north\n" not in prompt
