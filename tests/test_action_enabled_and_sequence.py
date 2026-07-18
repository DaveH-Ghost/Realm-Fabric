"""Object action enabled flag + sequence / set_object_text / set_action_enabled."""

from campaign_rpg_engine.actions.interact import interact
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args, create_object_from_args
from campaign_rpg_engine.perception import (
    build_passive_vision,
    get_object_interactions_reachable_after_move,
)
from campaign_rpg_engine.session_persistence import deserialize_object_action
from campaign_rpg_engine.snapshot import serialize_object_action


def _make_table_with_lower_chairs(area):
    obj, msg = create_object_from_args(
        area,
        'name "Table" '
        'pdesc "A table with chairs stacked on top." '
        'desc "Four chairs are perched on the tabletops." '
        "at 2,2 "
        'action "lower chairs" range 1 handler sequence '
        "handler_1 set_object_text "
        '1_set_pdesc "A sturdy wooden table." '
        '1_set_desc "A wooden table with chairs tucked underneath." '
        "handler_2 set_action_enabled "
        "2_target _self "
        "2_enabled false "
        'result "You lower the chairs from the tabletop." '
        'passive "{actor} lowers the chairs from the table."',
    )
    assert obj is not None, msg
    return obj


def test_object_action_enabled_round_trip():
    from campaign_rpg_engine.object_action import ObjectAction

    action = ObjectAction(
        name="peek",
        range=1,
        result="ok",
        passive_result="{actor} peeks.",
        enabled=False,
    )
    data = serialize_object_action(action)
    assert data["enabled"] is False
    restored = deserialize_object_action("peek", data)
    assert restored.enabled is False


def test_disabled_action_hidden_from_vision_and_interact():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area,
        'name "Box" pdesc "A box." desc "A closed box." at 1,1 '
        'action open range 1 enabled false '
        'result "You open it." passive "{actor} opens it."',
    )
    assert obj is not None, msg
    agent, msg = create_agent_from_args(area, 'name "Goblin" personality "Curious." at 1,0')
    assert agent is not None, msg

    assert obj.actions["open"].enabled is False
    assert get_object_interactions_reachable_after_move(agent, area, obj) == []
    vision = build_passive_vision(agent, area)
    assert "open" not in vision

    outcome = interact(agent, area, obj.id, "open")
    assert "not available" in outcome.result


def test_lower_chairs_sequence_updates_text_and_hides_action():
    area = create_initial_area()
    table = _make_table_with_lower_chairs(area)
    agent, msg = create_agent_from_args(
        area, 'name "Praxis" personality "Helpful." at 2,1'
    )
    assert agent is not None, msg

    action = table.actions["lower chairs"]
    assert action.enabled is True
    assert action.handler_id == "sequence"

    before = build_passive_vision(agent, area)
    assert "lower chairs" in before

    outcome = interact(agent, area, table.id, "lower chairs")
    assert "lower the chairs" in outcome.result.lower()
    assert table.passive_description == "A sturdy wooden table."
    assert table.description == "A wooden table with chairs tucked underneath."
    assert table.actions["lower chairs"].enabled is False

    after = build_passive_vision(agent, area)
    assert "lower chairs" not in after

    again = interact(agent, area, table.id, "lower chairs")
    assert "not available" in again.result


def test_set_object_text_clear_desc_keeps_pdesc():
    from reference_handlers.handlers.set_object_text import set_object_text
    from campaign_rpg_engine.object_action import ObjectAction

    area = create_initial_area()
    obj, msg = create_object_from_args(
        area,
        'name "Curio" pdesc "A curious trinket." desc "It hums faintly when touched." at 1,1',
    )
    assert obj is not None, msg
    agent, msg = create_agent_from_args(area, 'name "Goblin" personality "Curious." at 0,0')
    assert agent is not None, msg

    action = ObjectAction(
        name="examine",
        range=1,
        result="You study it.",
        passive_result="{actor} studies it.",
        handler_id="set_object_text",
        handler_params={"set_desc": "[EMPTY]"},
    )
    err = set_object_text(None, area, agent, obj, action)
    assert err is None
    assert obj.passive_description == "A curious trinket."
    assert obj.description == ""
