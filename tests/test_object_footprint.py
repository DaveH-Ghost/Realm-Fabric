"""Multi-tile object footprints (V0.6.0d)."""

from campaign_rpg_engine.actions.interact import interact
from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, GridBounds
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.move_target import ResolvedMoveTarget, format_move_towards_message
from campaign_rpg_engine.object import (
    Object,
    chebyshev_distance_to_object,
    nearest_footprint_tile_to,
    object_footprint_tiles,
    object_occupies_tile,
)
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.occupancy import is_tile_enterable, objects_at
from campaign_rpg_engine.pathfinding import find_path
from campaign_rpg_engine.perception import build_passive_vision
from campaign_rpg_engine.snapshot import serialize_object


def _agent_at(pos: tuple[int, int], *, move_speed: int | None = None) -> Agent:
    return Agent(
        id="agent_test_01",
        name="Tester",
        personality="",
        position=pos,
        memory=Memory(),
        move_speed=move_speed,
    )


def test_footprint_helpers():
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
    )
    assert object_footprint_tiles(table) == [(1, 1), (1, 2), (2, 1), (2, 2)]
    assert object_occupies_tile(table, 2, 2)
    assert not object_occupies_tile(table, 3, 2)
    assert chebyshev_distance_to_object((0, 1), table) == 1
    assert chebyshev_distance_to_object((4, 4), table) == 2


def test_objects_at_returns_multi_tile_object_on_extension_tile():
    area = Area(bounds=GridBounds.square(5))
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
        blocks_movement=True,
    )
    area.add_object(table)

    assert objects_at(area, (2, 2)) == [table]
    assert not is_tile_enterable(area, (2, 2), "agent_test_01")


def test_move_paths_around_two_by_two_blocker():
    area = Area(bounds=GridBounds.square(5))
    mover = _agent_at((0, 2), move_speed=4)
    area.add_agent(mover)
    area.add_object(
        Object(
            id="obj_table_01",
            name="Table",
            description="",
            position=(2, 1),
            width=2,
            height=2,
            blocks_movement=True,
        )
    )

    outcome = do_move(mover, area, "4,2")
    assert outcome.result == "You moved to (4, 2)."
    assert mover.position == (4, 2)
    assert find_path((0, 2), (4, 2), area, mover.id)


def test_interact_range_uses_nearest_footprint_tile():
    area = Area(bounds=GridBounds.square(5))
    mover = _agent_at((0, 2))
    area.add_agent(mover)
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
        actions={
            "kick": ObjectAction(
                name="kick",
                range=1,
                result="Thump.",
                passive_result="Thump.",
            )
        },
    )
    area.add_object(table)

    outcome = interact(mover, area, "obj_table_01", "kick")
    assert outcome.result == "Thump."


def test_format_move_towards_entity_uses_nearest_footprint_tile():
    area = Area(bounds=GridBounds.square(5))
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
    )
    area.add_object(table)
    resolved = ResolvedMoveTarget((1, 1), entity_id="obj_table_01", entity_name="Table")
    message = format_move_towards_message(resolved, (0, 2), area=area)
    assert message == "You moved towards Table; you are still 1 step away."


def test_create_object_with_footprint_via_cli():
    area = Area(bounds=GridBounds.square(5))
    obj, err = create_object_from_args(
        area,
        'name "Long Wall" at 0,1 width 1 height 3 blocks-movement true',
    )
    assert obj is not None
    assert "footprint 1x3" in err
    assert obj.width == 1
    assert obj.height == 3
    assert not is_tile_enterable(area, (0, 3), "agent_test_01")


def test_create_object_rejects_footprint_outside_bounds():
    area = Area(bounds=GridBounds.square(5))
    obj, err = create_object_from_args(
        area,
        'name "Too Big" at 3,3 width 3 height 3',
    )
    assert obj is None
    assert "extends outside" in err


def test_serialize_object_includes_footprint():
    obj = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=3,
    )
    data = serialize_object(obj)
    assert data["width"] == 2
    assert data["height"] == 3


def test_nearest_footprint_tile_to_breaks_ties_by_coordinate():
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
    )
    assert nearest_footprint_tile_to((0, 2), table) == (1, 2)
    assert nearest_footprint_tile_to((0, 1), table) == (1, 1)


def test_passive_vision_uses_nearest_footprint_tile_and_shows_size():
    area = Area(bounds=GridBounds.square(6))
    agent = _agent_at((3, 1))
    area.add_agent(agent)
    area.add_object(
        Object(
            id="obj_table_01",
            name="Large Table",
            description="",
            position=(0, 0),
            width=3,
            height=2,
            passive_description="A wide table.",
        )
    )

    vision = build_passive_vision(agent, area)

    assert "Large Table (obj_table_01), (2, 1), 3×2 tiles - A wide table." in vision
    assert "(0, 0)" not in vision


def test_passive_vision_relative_bearing_uses_nearest_footprint_tile():
    area = Area(bounds=GridBounds.square(6))
    agent = _agent_at((0, 0))
    area.add_agent(agent)
    area.add_object(
        Object(
            id="obj_wall_01",
            name="Long Wall",
            description="",
            position=(3, 0),
            width=1,
            height=3,
            passive_description="A wall segment.",
        )
    )

    vision = build_passive_vision(
        agent,
        area,
        include_relative_bearing=True,
        vision_units="ft",
        units_per_tile=5,
    )

    assert "Long Wall (obj_wall_01), (3, 0), 1×3 tiles" in vision
    assert "East of you, 15 ft away" in vision


def test_get_object_at_on_extension_tile():
    area = Area(bounds=GridBounds.square(5))
    table = Object(
        id="obj_table_01",
        name="Table",
        description="",
        position=(1, 1),
        width=2,
        height=2,
    )
    area.add_object(table)
    assert area.get_object_at((2, 2)) is table
