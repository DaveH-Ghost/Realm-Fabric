"""Scene decorations (V1.3.0)."""

from campaign_rpg_engine.decoration import (
    DECORATION_KIND_BACKGROUND,
    DECORATION_KIND_SPRITE,
)
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.session_persistence import (
    SNAPSHOT_VERSION,
    build_save_snapshot,
    load_session_from_snapshot,
)
from campaign_rpg_engine.snapshot import serialize_decoration


def test_create_sprite_decoration():
    session = Session.from_default()
    result = session.create_decoration(
        kind="sprite",
        image="assets/tree.png",
        x=10,
        y=20,
        width=64,
        height=128,
    )
    assert result.ok
    assert result.decoration is not None
    assert result.decoration.kind == DECORATION_KIND_SPRITE
    assert result.decoration.id == "decor_tree_01"
    assert result.decoration.z_index == 0


def test_decoration_id_increments_for_same_image():
    session = Session.from_default()
    first = session.create_decoration(
        kind="sprite",
        image="assets/oak.png",
        x=0,
        y=0,
        width=32,
        height=32,
    )
    second = session.create_decoration(
        kind="sprite",
        image="assets/oak.png",
        x=0,
        y=0,
        width=32,
        height=32,
    )
    assert first.decoration.id == "decor_oak_01"
    assert second.decoration.id == "decor_oak_02"


def test_background_tile_size_round_trip():
    session = Session.from_default()
    result = session.create_decoration(
        kind="background",
        image="assets/stone-tile.png",
        width=128,
        height=96,
        repeat="repeat",
    )
    assert result.ok
    assert result.decoration.width == 128
    assert result.decoration.height == 96
    restored = Session.from_snapshot(build_save_snapshot(session))
    bg = next(
        d
        for d in restored.areas[restored.active_area_id].decorations
        if d.kind == DECORATION_KIND_BACKGROUND
    )
    assert bg.width == 128
    assert bg.height == 96


def test_background_replaces_existing():
    session = Session.from_default()
    session.create_decoration(
        kind="background",
        image="assets/stone.png",
    )
    result = session.create_decoration(
        kind="background",
        image="assets/grass.png",
    )
    assert result.ok
    area = session.areas[session.active_area_id]
    backgrounds = [d for d in area.decorations if d.kind == DECORATION_KIND_BACKGROUND]
    assert len(backgrounds) == 1
    assert backgrounds[0].image == "assets/grass.png"


def test_reorder_sprite_z_index():
    session = Session.from_default()
    session.create_decoration(
        kind="sprite",
        image="a.png",
        x=0,
        y=0,
        width=32,
        height=32,
        decoration_id="decor_a",
    )
    session.create_decoration(
        kind="sprite",
        image="b.png",
        x=0,
        y=0,
        width=32,
        height=32,
        decoration_id="decor_b",
    )
    area = session.areas[session.active_area_id]
    assert area.get_decoration_by_id("decor_a").z_index == 0
    assert area.get_decoration_by_id("decor_b").z_index == 1

    up = session.reorder_decoration("decor_a", "up")
    assert up.ok
    assert area.get_decoration_by_id("decor_a").z_index > area.get_decoration_by_id("decor_b").z_index


def test_decorations_in_snapshot():
    session = Session.from_default()
    session.create_decoration(
        kind="sprite",
        image="assets/floor.png",
        x=0,
        y=0,
        width=320,
        height=320,
        decoration_id="decor_floor_01",
    )
    snap = session.snapshot()
    room = snap["areas"][session.active_area_id]
    assert len(room["decorations"]) == 1
    assert room["decorations"][0]["id"] == "decor_floor_01"


def test_decorations_save_round_trip():
    session = Session.from_default()
    session.create_decoration(
        kind="background",
        image="assets/stone-tile.png",
        repeat="repeat",
    )
    session.create_decoration(
        kind="sprite",
        image="assets/bush.png",
        x=64,
        y=128,
        width=48,
        height=48,
    )
    restored = Session.from_snapshot(build_save_snapshot(session))
    area = restored.areas[restored.active_area_id]
    assert len(area.decorations) == 2
    serialized = [serialize_decoration(d) for d in area.decorations]
    kinds = {item["kind"] for item in serialized}
    assert kinds == {DECORATION_KIND_BACKGROUND, DECORATION_KIND_SPRITE}


def test_v4_snapshot_loads_empty_decorations():
    session = Session.from_default()
    data = build_save_snapshot(session)
    data["snapshot_version"] = 4
    for area_data in data["areas"].values():
        area_data.pop("decorations", None)
    restored = load_session_from_snapshot(data)
    area = restored.areas[restored.active_area_id]
    assert area.decorations == []


def test_snapshot_version_is_five():
    assert SNAPSHOT_VERSION == 5


def test_sprite_negative_position():
    session = Session.from_default()
    result = session.create_decoration(
        kind="sprite",
        image="assets/overhang.png",
        x=-64,
        y=-32,
        width=128,
        height=128,
    )
    assert result.ok
    assert result.decoration.x == -64
    assert result.decoration.y == -32
