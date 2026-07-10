"""Movement blocking and BFS pathfinding (V0.6.0a)."""

from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.area import Area, GridBounds, create_initial_area
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.occupancy import is_tile_enterable, resolve_standable_goal
from campaign_rpg_engine.pathfinding import find_path, walk_with_pathfinding
from campaign_rpg_engine.session import Session


def test_objects_block_by_default_agents_do_not():
    area = create_initial_area()
    agent = area.get_agent()
    ball = area.get_object_by_id("obj_ball_01")
    assert ball is not None
    assert ball.blocks_movement is True
    assert agent.blocks_movement is False


def test_teleport_targets_standable_tile_not_blocking_object_center():
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (0, 0)

    outcome = do_move(agent, area, "obj_ball_01")

    assert agent.position != (2, 2)
    assert agent.position in {(1, 1), (1, 2), (2, 1), (3, 2), (2, 3), (3, 1), (3, 3), (1, 3)}
    assert "Ceramic Ball" in outcome.result


def test_pathfinds_around_blocking_wall_object():
    area = Area(bounds=GridBounds.square(5))
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.memory import Memory

    mover = Agent(
        id="agent_test_01",
        name="Tester",
        personality="",
        position=(0, 0),
        memory=Memory(),
        move_speed=4,
    )
    area.add_agent(mover)
    wall = Object(
        id="obj_wall_01",
        name="Wall",
        description="",
        position=(2, 0),
        blocks_movement=True,
    )
    area.add_object(wall)

    path = find_path((0, 0), (4, 0), area, mover.id)
    assert path
    assert (2, 0) not in path
    assert path[-1] == (4, 0)

    final, reached, segment = walk_with_pathfinding((0, 0), (4, 0), 4, area, mover.id)
    assert reached is True
    assert final == (4, 0)
    assert len(segment) == 5


def test_move_to_entity_stops_adjacent_to_blocking_object():
    area = create_initial_area()
    agent = area.get_agent()
    agent.move_speed = 1
    agent.position = (0, 0)

    outcome = do_move(agent, area, "obj_ball_01")

    assert agent.position == (1, 1)
    assert outcome.result == "You have successfully moved next to Ceramic Ball."


def test_agents_can_share_tile_by_default():
    area = create_initial_area()
    agent = area.get_agent()
    from campaign_rpg_engine.area_edit import create_agent_from_args

    other, _ = create_agent_from_args(
        area,
        'name "Buddy" personality "x" at 1,1',
    )
    assert other is not None
    assert is_tile_enterable(area, (1, 1), other.id)


def test_selective_blocking_exception_allows_passage():
    area = create_initial_area()
    agent = area.get_agent()
    ball = area.get_object_by_id("obj_ball_01")
    assert ball is not None
    ball.movement_exceptions = [agent.id]

    assert is_tile_enterable(area, ball.position, agent.id)
    standable = resolve_standable_goal(area, ball.position, agent.id)
    assert standable == ball.position


def test_create_object_blocks_movement_flag():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area,
        'name "Crate" at 0,3 blocks-movement false',
    )
    assert obj is not None
    assert obj.blocks_movement is False
    assert "Crate" in msg


def test_snapshot_includes_blocking_fields():
    session = Session.from_default()
    session.edit_object(
        "obj_ball_01",
        movement_exceptions=["agent_01"],
    )
    obj = session.snapshot(include_private=True)["areas"]["room"]["objects"]
    ball = next(item for item in obj if item["id"] == "obj_ball_01")
    assert ball["blocks_movement"] is True
    assert ball["movement_exceptions"] == ["agent_01"]
