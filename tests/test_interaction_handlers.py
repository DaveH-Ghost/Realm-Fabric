"""Tests for pluggable interaction handlers (V0.6.1)."""

from __future__ import annotations

import pytest
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.area_edit import create_object_from_args
from campaign_rpg_engine.interaction_handlers.registry import (
    clear_handlers_for_tests,
    collect_prefixed_params,
    format_handlers_list,
    is_handler_registered,
    list_registered_handlers,
    register_interaction_handler,
    run_interaction_handler,
    run_named_handler,
    validate_handler_params,
)
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction, migrate_legacy_effects_to_handler
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.session_persistence import (
    SNAPSHOT_VERSION,
    build_save_snapshot,
    load_session_from_snapshot,
    validate_snapshot_handlers,
)


@pytest.fixture
def isolated_registry():
    clear_handlers_for_tests()
    yield
    clear_handlers_for_tests()
    from reference_handlers import register_reference_handlers

    register_reference_handlers()


def test_register_and_list_handlers(isolated_registry):
    def noop(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return None

    register_interaction_handler(
        "noop",
        noop,
        description="Does nothing",
        param_fields=[{"name": "x", "type": "text", "label": "X"}],
        summary_template="noop {x}",
    )
    assert is_handler_registered("noop")
    assert "noop" in list_registered_handlers()
    text = format_handlers_list()
    assert "noop" in text
    assert "Does nothing" in text
    from campaign_rpg_engine.interaction_handlers.registry import handler_catalog_entry

    entry = handler_catalog_entry("noop")
    assert entry is not None
    assert entry["param_fields"][0]["name"] == "x"
    assert entry["summary_template"] == "noop {x}"


def test_validate_unknown_handler(isolated_registry):
    err = validate_handler_params("missing", {})
    assert err is not None
    assert "Unknown handler" in err


def test_validate_rejects_params_for_paramless_handler(isolated_registry):
    def noop(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return None

    register_interaction_handler("noop", noop)
    err = validate_handler_params("noop", {"x": "1"})
    assert "does not accept parameters" in err


def test_collect_prefixed_params_strips_and_skips_controls():
    params = {
        "pass_handler": "move_area",
        "pass_dest-area": "hall",
        "pass_dest-at": "1,2",
        "fail_handler": "delete_self",
        "fail_result": "nope",
        "stat": "DEX",
    }
    assert collect_prefixed_params(params, "pass_", skip_keys={"pass_handler"}) == {
        "dest-area": "hall",
        "dest-at": "1,2",
    }
    assert (
        collect_prefixed_params(
            params,
            "fail_",
            skip_keys={"fail_handler", "fail_result", "fail_passive"},
        )
        == {}
    )


def test_run_named_handler_invokes_with_explicit_params(isolated_registry):
    seen: dict[str, str] = {}

    def tagged(session, area, agent, obj, action):
        del session, area, agent, obj
        seen["handler_id"] = str(action.handler_id)
        seen["tag"] = action.handler_params.get("tag", "")
        return None

    def validate(params: dict[str, str]) -> str | None:
        if set(params) - {"tag"}:
            return "only tag allowed"
        return None

    register_interaction_handler("tagged", tagged, validate_params=validate)
    area = Area(area_description="Room.")
    agent = Agent(id="agent_01", name="A", position=(0, 0), personality="")
    obj = Object(id="obj_01", name="O", description="", position=(0, 0))
    source = ObjectAction(
        name="lift",
        range=1,
        result="ok",
        passive_result="ok",
        handler_id="skillish",
        handler_params={"stat": "STR"},
    )
    err = run_named_handler(
        None,
        area,
        agent,
        obj,
        "tagged",
        {"tag": "x"},
        source_action=source,
    )
    assert err is None
    assert seen == {"handler_id": "tagged", "tag": "x"}


def test_run_named_handler_returns_validation_error(isolated_registry):
    def noop(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return None

    register_interaction_handler("noop", noop)
    area = Area(area_description="Room.")
    agent = Agent(id="agent_01", name="A", position=(0, 0), personality="")
    obj = Object(id="obj_01", name="O", description="", position=(0, 0))
    source = ObjectAction(name="x", range=0, result="", passive_result="")
    err = run_named_handler(None, area, agent, obj, "noop", {"bad": "1"}, source_action=source)
    assert err is not None
    assert "does not accept parameters" in err


def test_create_object_forwards_generic_handler_params(isolated_registry):
    def check(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return None

    def validate(params: dict[str, str]) -> str | None:
        if params.get("stat") != "STR":
            return "expected STR"
        if params.get("dc") != "12":
            return "expected 12"
        return None

    register_interaction_handler(
        "skillish",
        check,
        validate_params=validate,
    )
    area = Area(area_description="Room.")
    obj, msg = create_object_from_args(
        area,
        'name "Ball" pdesc "Ball." desc "Ceramic." at 0,0 '
        "action lift range 1 handler skillish stat STR dc 12 "
        'result "You lift it." passive "{actor} lifts it."',
    )
    assert obj is not None
    assert "Created object" in msg
    action = obj.actions["lift"]
    assert action.handler_id == "skillish"
    assert action.handler_params == {"stat": "STR", "dc": "12"}


def test_run_handler_success_and_error(isolated_registry):
    def fail_handler(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return "Nope."

    register_interaction_handler("fail", fail_handler)
    area = Area(area_description="Room.")
    agent = Agent(id="agent_01", name="A", position=(0, 0), personality="")
    obj = Object(id="obj_01", name="O", description="", position=(0, 0))
    action = ObjectAction(
        name="x",
        range=0,
        result="",
        passive_result="",
        handler_id="fail",
    )
    err = run_interaction_handler(None, area, agent, obj, action)
    assert err == "Nope."


def test_handler_may_return_action_outcome(isolated_registry):
    from campaign_rpg_engine.action_outcome import ActionOutcome
    from campaign_rpg_engine.actions.interact import interact
    from campaign_rpg_engine.area import create_initial_area

    def custom_fail(session, area, agent, obj, action):
        del session, area, agent, obj, action
        return ActionOutcome(
            result="Custom fail result.",
            passive_result="Custom fail passive.",
        )

    register_interaction_handler("custom_fail", custom_fail)
    area = create_initial_area()
    agent = area.get_agent()
    agent.position = (2, 2)
    obj = area.get_object_by_id("obj_ball_01")
    assert obj is not None
    obj.actions["kick"] = ObjectAction(
        name="kick",
        range=1,
        result="Success result.",
        passive_result="Success passive.",
        handler_id="custom_fail",
    )
    outcome = interact(agent, area, "obj_ball_01", "kick")
    assert outcome.result == "Custom fail result."
    assert outcome.passive_result == "Custom fail passive."


def test_migrate_legacy_effects_to_handler():
    assert migrate_legacy_effects_to_handler([]) == (None, {})
    handler_id, params = migrate_legacy_effects_to_handler(
        [{"name": "move_area", "params": {"dest-area": "hall", "dest-at": "1,2"}}]
    )
    assert handler_id == "move_area"
    assert params == {"dest-area": "hall", "dest-at": "1,2"}


def test_snapshot_v4_round_trip_handler_fields():
    session = Session.from_default()
    room = session.area
    obj, _ = create_object_from_args(
        room,
        'name "Cookie" desc "x" at 2,2 action eat range 1 handler delete_self '
        'result "Yum." passive "{actor} ate it."',
    )
    assert obj is not None
    assert obj.actions["eat"].handler_id == "delete_self"

    save = build_save_snapshot(session)
    assert save["snapshot_version"] == SNAPSHOT_VERSION == 5
    kick = next(o for o in save["areas"]["room"]["objects"] if o["id"] == "obj_ball_01")
    assert kick["actions_detail"]["kick"]["handler_id"] == "random_move_self"

    restored = load_session_from_snapshot(save)
    cookie = restored.area.get_object_by_id(obj.id)
    assert cookie.actions["eat"].handler_id == "delete_self"


def test_v3_effects_import_migrates_to_handler(isolated_registry):
    from reference_handlers import register_reference_handlers

    register_reference_handlers()
    session = Session.from_default()
    save = build_save_snapshot(session)
    save["snapshot_version"] = 3
    ball = next(o for o in save["areas"]["room"]["objects"] if o["id"] == "obj_ball_01")
    detail = ball["actions_detail"]["kick"]
    detail.pop("handler_id", None)
    detail.pop("handler_params", None)
    detail["effects"] = [{"name": "random_move_self", "params": {}}]

    restored = load_session_from_snapshot(save)
    kick_action = restored.area.get_object_by_id("obj_ball_01").actions["kick"]
    assert kick_action.handler_id == "random_move_self"


def test_import_fails_when_handler_missing(isolated_registry):
    from reference_handlers import register_reference_handlers

    register_reference_handlers()
    session = Session.from_default()
    save = build_save_snapshot(session)
    cookie_detail = {
        "range": 1,
        "result": "Yum.",
        "passive_result": "ate",
        "handler_id": "not_registered",
        "handler_params": {},
        "kind": "interact",
    }
    save["areas"]["room"]["objects"].append(
        {
            "id": "obj_cookie_01",
            "name": "Cookie",
            "position": [2, 2],
            "actions": ["eat"],
            "actions_detail": {"eat": cookie_detail},
            "appearance": "",
            "blocks_movement": True,
            "movement_exceptions": [],
            "width": 1,
            "height": 1,
            "hidden": False,
            "private_data": "",
            "passive_description": "",
            "description": "",
        }
    )
    with pytest.raises(ValueError, match="Interaction handler 'not_registered'"):
        validate_snapshot_handlers(save)
        load_session_from_snapshot(save)
