"""Move result messaging (V0.6.0a follow-up)."""

from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.move_target import (
    ResolvedMoveTarget,
    format_move_towards_message,
    format_unreachable_message,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.occupancy import resolve_standable_goal


def test_partial_move_to_entity_reports_steps_away_without_coordinates():
    area = Area(bounds=GridBounds.square(5))
    mover = Agent(
        id="agent_test_01",
        name="Tester",
        personality="",
        position=(0, 0),
        memory=Memory(),
        move_speed=1,
    )
    area.add_agent(mover)
    ball = Object(
        id="obj_ball_01",
        name="Ceramic Ball",
        description="",
        position=(3, 1),
        blocks_movement=True,
    )
    area.add_object(ball)

    outcome = do_move(mover, area, "obj_ball_01")

    assert mover.position in {(1, 0), (1, 1)}
    assert outcome.result.startswith("You moved towards Ceramic Ball; you are still ")
    assert "steps away" in outcome.result or "step away" in outcome.result
    assert "(" not in outcome.result


def test_format_move_towards_entity_includes_blocker_when_given():
    resolved = ResolvedMoveTarget((2, 0), entity_id="obj_ball_01", entity_name="Ceramic Ball")
    message = format_move_towards_message(
        resolved,
        (0, 0),
        blocker_name="Wall",
    )
    assert message == (
        "You moved towards Ceramic Ball; you are still 2 steps away. Wall is blocking the way."
    )


def test_unreachable_entity_behind_wall_partition_reports_blocker():
    area = Area(bounds=GridBounds.square(5))
    mover = Agent(
        id="agent_test_01",
        name="Tester",
        personality="",
        position=(0, 0),
        memory=Memory(),
        move_speed=2,
    )
    area.add_agent(mover)
    for y in range(5):
        area.add_object(
            Object(
                id=f"obj_wall_{y:02d}",
                name="Wall",
                description="",
                position=(2, y),
                blocks_movement=True,
            )
        )
    ball = Object(
        id="obj_ball_01",
        name="Ceramic Ball",
        description="",
        position=(4, 2),
        blocks_movement=True,
    )
    area.add_object(ball)

    standable = resolve_standable_goal(area, ball.position, mover.id)
    assert standable is not None
    assert standable[0] > 2

    from campaign_rpg_engine.pathfinding import find_path

    assert not find_path(mover.position, standable, area, mover.id)

    outcome = do_move(mover, area, "obj_ball_01")

    assert mover.position == (0, 0)
    assert outcome.result == ("You cannot reach Ceramic Ball; Wall is blocking the way.")


def test_unreachable_message_without_blocker_name():
    resolved = ResolvedMoveTarget((2, 2), entity_id="obj_ball_01", entity_name="Ceramic Ball")
    assert format_unreachable_message(resolved, "(2, 2)", None) == (
        "You cannot reach Ceramic Ball; movement is fully blocked."
    )


def test_already_at_coordinate_as_close_as_possible_to_blocked_tile():
    area = Area(bounds=GridBounds.square(5))
    mover = Agent(
        id="agent_test_01",
        name="Tester",
        personality="",
        position=(1, 1),
        memory=Memory(),
        move_speed=1,
    )
    area.add_agent(mover)
    wall = Object(
        id="obj_wall_01",
        name="Wall",
        description="",
        position=(2, 2),
        blocks_movement=True,
    )
    area.add_object(wall)

    outcome = do_move(mover, area, "2,2")

    assert mover.position == (1, 1)
    assert outcome.result == ("You are already at (1, 1), as close as you can get to (2, 2).")
