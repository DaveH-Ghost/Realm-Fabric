"""Hidden objects (V0.6.0e)."""

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_object_from_args, edit_object_from_args
from campaign_rpg_engine.perception import (
    build_passive_vision,
    get_visible_object_ids,
    perform_look,
)


def test_hidden_object_excluded_from_passive_vision():
    area = create_initial_area()
    agent = area.get_agent()
    obj, _ = create_object_from_args(
        area,
        'name "Trap" pdesc "A trap." at 2,2 hidden true blocks-movement false',
    )
    assert obj.hidden is True

    vision = build_passive_vision(agent, area)
    assert "Trap" not in vision
    assert obj.id not in get_visible_object_ids(agent, area)


def test_hidden_object_visible_after_reveal():
    area = create_initial_area()
    agent = area.get_agent()
    obj, _ = create_object_from_args(
        area,
        'name "Trap" pdesc "A trap." at 2,2 hidden true blocks-movement false',
    )

    edit_object_from_args(area, f"{obj.id} hidden false")

    assert obj.hidden is False
    vision = build_passive_vision(agent, area)
    assert "Trap" in vision


def test_cannot_look_at_hidden_object():
    area = create_initial_area()
    agent = area.get_agent()
    obj, _ = create_object_from_args(
        area,
        'name "Trap" pdesc "A trap." desc "Spikes." at 2,2 hidden true blocks-movement false',
    )

    outcome = perform_look(agent, area, obj.id)
    assert "don't see" in outcome.result.lower()
