"""Entity id and coordinate move targets (V0.4.0a)."""

import pytest
from pydantic import ValidationError

from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.coordinates import CoordinateParseError
from campaign_rpg_engine.move_target import (
    MoveTargetError,
    resolve_move_target,
    validate_move_target_syntax,
)
from campaign_rpg_engine.simulation import execute_nav_phase


def test_validate_move_target_syntax_accepts_entity_ids():
    assert validate_move_target_syntax("obj_ball_01") == "obj_ball_01"
    assert validate_move_target_syntax("agent_01") == "agent_01"


def test_validate_move_target_syntax_accepts_coordinates():
    assert validate_move_target_syntax("2,3") == "2,3"


def test_validate_move_target_syntax_rejects_garbage():
    with pytest.raises(CoordinateParseError):
        validate_move_target_syntax("north")


def test_resolve_move_target_object_position():
    area = create_initial_area()
    resolved = resolve_move_target(area, "obj_ball_01")
    assert resolved.position == (2, 2)
    assert resolved.entity_name == "Ceramic Ball"


def test_resolve_move_target_agent_position():
    area = create_initial_area()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "x" desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")
    resolved = resolve_move_target(area, goblin.id)
    assert resolved.position == (0, 3)
    assert resolved.entity_name == "Goblin"


def test_resolve_move_target_unknown_id():
    area = create_initial_area()
    with pytest.raises(MoveTargetError) as exc_info:
        resolve_move_target(area, "obj_missing_01")
    assert "ERR:INVALID_TARGET" in str(exc_info.value)


def test_move_to_object_id_teleports_to_adjacent_tile():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (0, 0)

    outcome = do_move(agent, area, "obj_ball_01")

    assert agent.position == (1, 1)
    assert outcome.result == "You have successfully moved next to Ceramic Ball."
    assert outcome.passive_result == "Explorer moves next to Ceramic Ball."


def test_move_to_agent_id_teleports_to_tile():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "x" desc "x" personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    outcome = do_move(explorer, area, goblin.id)

    assert explorer.position == (0, 3)
    assert outcome.result == "You moved to Goblin."
    assert explorer.position == goblin.position


def test_move_to_own_agent_id_already_there():
    area = create_initial_area()
    agent = area.get_agent()

    outcome = do_move(agent, area, agent.id)

    assert agent.position == (1, 1)
    assert outcome.result == "You are already at Explorer."
    assert outcome.passive_result == ""


def test_move_unknown_entity_id_fails_without_position_change():
    area = create_initial_area()
    agent = area.get_agent()
    start = agent.position

    outcome = do_move(agent, area, "obj_nope_01")

    assert agent.position == start
    assert "ERR:INVALID_TARGET" in outcome.result
    assert outcome.passive_result == ""


def test_schema_accepts_entity_id_move_target():
    turn = AgentCompoundTurn(
        reasoning="Go to the ball.",
        move="obj_ball_01",
        action="none",
    )
    assert turn.move == "obj_ball_01"


def test_compound_nav_phase_move_to_object_id():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (0, 0)

    steps = execute_nav_phase(
        agent,
        area,
        AgentCompoundTurn(
            reasoning="To the ball.",
            move="obj_ball_01",
            action="none",
        ),
    )

    assert agent.position == (1, 1)
    assert len(steps) == 1
    assert "Ceramic Ball" in steps[0].result


def test_prompt_move_instructions_entity_id_line():
    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area)

    assert "Entity move targets" not in prompt
    assert "obj_ball_01 Ceramic Ball at" not in prompt
    assert "You may move to any coordinate" in prompt
    assert (
        "move may be an entity id (obj_* or agent_*) for that tile."
    ) in prompt
