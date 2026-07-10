"""
test_object_actions.py

V0.2 Section 3: declarative object interactions.
"""

from campaign_rpg_engine.actions.interact import interact
from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.interaction_handlers.registry import format_handlers_list
from campaign_rpg_engine.perception import build_passive_vision, PASSIVE_VISION_LOOK_RULE, perform_look
from campaign_rpg_engine.simulation import next_turn_number_for_agent, run_compound_turn
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import (
    create_agent_from_args,
    create_object_from_args,
    delete_object_by_id,
    edit_object_from_args,
    format_objects_list,
)


COOKIE_ARGS = (
    'name "Cookie" pdesc "A cookie." desc "A tasty cookie." at 2,2 '
    'action eat range 1 handler delete_self '
    'result "You ate the cookie, it was delicious." '
    'passive "{actor} ate the cookie."'
)


COOKIE_FAR_ARGS = (
    'name "Cookie" pdesc "A cookie." desc "A tasty cookie." at 4,4 '
    'action eat range 1 handler delete_self '
    'result "You ate the cookie, it was delicious." '
    'passive "{actor} ate the cookie."'
)


def _create_cookie(area):
    obj, _ = create_object_from_args(area, COOKIE_ARGS)
    assert obj is not None
    return obj


def _create_goblin(area, at="0,3"):
    agent, _ = create_agent_from_args(
        area, f'name "Goblin" personality "Hungry." at {at}'
    )
    assert agent is not None
    return agent


def test_handlers_command_lists_registered_handlers():
    text = format_handlers_list()
    assert "delete_self" in text
    assert "random_move_self" in text
    assert "move_area" in text
    assert "Remove the interacted object" in text
    assert "different random in-bounds grid position" in text


def test_handler_registry_descriptions_match_registration():
    from campaign_rpg_engine.interaction_handlers.registry import get_handler_registration, list_registered_handlers

    for handler_id in list_registered_handlers():
        reg = get_handler_registration(handler_id)
        assert reg is not None
        assert reg.description


def test_create_cookie_shows_action_in_objects_list():
    area = create_initial_area()
    cookie = _create_cookie(area)
    text = format_objects_list(area)
    assert cookie.id in text
    assert "actions: eat" in text


def test_initial_ball_shows_kick_action_in_objects_list():
    area = create_initial_area()
    text = format_objects_list(area)
    assert "obj_ball_01" in text
    assert "actions: kick" in text


def test_kick_appears_in_action_prompt_when_adjacent():
    area = create_initial_area()
    explorer = area.get_agent()
    explorer.position = (2, 3)

    prompt = build_compound_prompt(explorer, area)
    assert PASSIVE_VISION_LOOK_RULE in prompt
    assert "  - kick (range 1)" in prompt
    assert "Object interactions available this turn:" not in prompt


def test_unknown_interact_wrong_action_name():
    area = create_initial_area()
    cookie = _create_cookie(area)
    goblin = _create_goblin(area, at="2,3")

    outcome = interact(goblin, area, cookie.id, "drink")
    assert "'drink' is not an action you can perform on Cookie." in outcome.result
    assert area.get_object_by_id(cookie.id) is not None


def test_range_zero_same_tile_interact():
    area = create_initial_area()
    obj, _ = create_object_from_args(
        area,
        'name "Gem" desc "A gem." at 2,3 action pick range 0 '
        'result "You pick up the {object}." passive "{actor} picks up the {object}."',
    )
    goblin = _create_goblin(area, at="2,3")

    prompt = build_compound_prompt(goblin, area)
    assert "  - pick (same tile)" in prompt

    outcome = interact(goblin, area, obj.id, "pick")
    assert "You pick up the Gem." in outcome.result


def test_multiple_actions_on_one_object():
    area = create_initial_area()
    obj, _ = create_object_from_args(
        area, 'name "Cookie" desc "Tasty." at 2,2'
    )
    assert edit_object_from_args(
        area,
        f'{obj.id} add-action eat range 1 handler delete_self '
        'result "Yum." passive "{actor} ate it."',
    ).startswith("Added action")
    assert edit_object_from_args(
        area,
        f'{obj.id} add-action smell range 1 result "Nice." '
        'passive "{actor} smells it."',
    ).startswith("Added action")

    text = format_objects_list(area)
    assert "actions: eat, smell" in text


def test_create_object_accepts_random_move_self_effect():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area,
        'name "Marble" desc "Round." at 1,1 action roll range 0 '
        'handler random_move_self result "It rolls." passive "{actor} rolls it."',
    )
    assert obj is not None
    assert obj.actions["roll"].handler_id == "random_move_self"
    assert "Created object" in msg


def test_interact_templates_substitute_object_start_and_end(monkeypatch):
    area = create_initial_area()
    explorer = area.get_agent()
    explorer.position = (2, 3)
    ball = area.get_object_by_id("obj_ball_01")
    assert ball.position == (2, 2)

    monkeypatch.setattr(
        "reference_handlers.handlers.random_move_self.random.choice",
        lambda _positions: (4, 0),
    )

    outcome = interact(explorer, area, "obj_ball_01", "kick")
    assert outcome.result == (
        "You kick the Ceramic Ball. It rolls from (2, 2) to (4, 0)."
    )
    assert outcome.passive_result == (
        "Explorer kicks the Ceramic Ball. It rolls from (2, 2) to (4, 0)."
    )


def test_interact_pathing_fails_when_move_budget_too_short():
    area = create_initial_area()
    obj, _ = create_object_from_args(area, COOKIE_FAR_ARGS)
    assert obj is not None
    cookie = obj
    goblin = _create_goblin(area, at="0,0")
    goblin.move_speed = 1

    record = run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="try to eat from far away",
            move="4,3",
            action="interact",
            target=cookie.id,
            verb="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert goblin.position != (4, 4)
    assert "Unfortunately you are too far from Cookie to eat." in record.result
    assert area.get_object_by_id(cookie.id) is not None


def test_in_range_goblin_sees_eat_in_action_prompt():
    area = create_initial_area()
    _create_cookie(area)
    goblin = _create_goblin(area, at="2,3")

    prompt = build_compound_prompt(goblin, area)
    assert "  - eat (range 1)" in prompt


def test_goblin_interact_eat_deletes_cookie():
    area = create_initial_area()
    cookie = _create_cookie(area)
    goblin = _create_goblin(area, at="2,3")

    record = run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="eat",
            action="interact",
            target=cookie.id,
            verb="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert area.get_object_by_id(cookie.id) is None
    assert "You ate the cookie, it was delicious." in record.result
    assert goblin.passive_result == "Goblin ate the cookie."


def test_step_compound_move_adjacent_and_eat():
    from campaign_rpg_engine import ObjectAction, Session, load_profile
    from campaign_rpg_engine.compound_arg_parse import parse_compound_step_arg

    session = Session.from_profile(load_profile("default_compound"))
    session.create_object(
        name="Cookie",
        position=(2, 2),
        passive_description="A cookie.",
        description="A tasty cookie.",
        actions={
            "eat": ObjectAction(
                name="eat",
                range=1,
                result="You ate the cookie, it was delicious.",
                passive_result="{actor} ate the cookie.",
                handler_id="delete_self",
            ),
        },
    )
    session.create_agent(name="Goblin", position=(0, 0), personality="x")
    session.set_active_agent("Goblin")
    cookie_id = session.area.get_objects()[-1].id
    turn = parse_compound_step_arg(f"2,3 interact {cookie_id} eat").turn
    session.run_compound_turn(turn)

    assert session.area.get_object_by_id(cookie_id) is None
    goblin = session.area.get_agent_by_name("Goblin")
    assert goblin.position in {(1, 1), (1, 2), (2, 1), (2, 3), (3, 2)}
    assert "You ate the cookie" in goblin.memory.turns[-1].result


def test_out_of_range_not_in_prompt_and_runtime_fails():
    area = create_initial_area()
    obj, _ = create_object_from_args(area, COOKIE_FAR_ARGS)
    assert obj is not None
    cookie = obj
    goblin = _create_goblin(area, at="0,0")
    goblin.move_speed = 1

    prompt = build_compound_prompt(goblin, area)
    assert "  - eat" not in prompt

    outcome = interact(goblin, area, cookie.id, "eat")
    assert "Unfortunately you are too far from Cookie to eat." in outcome.result
    assert area.get_object_by_id(cookie.id) is not None


def test_not_visible_interact_fails(monkeypatch):
    area = create_initial_area()
    cookie = _create_cookie(area)
    goblin = _create_goblin(area, at="2,3")

    monkeypatch.setattr(
        "campaign_rpg_engine.actions.interact.is_object_in_passive_vision",
        lambda _agent, _world, object_id: object_id != cookie.id,
    )

    outcome = interact(goblin, area, cookie.id, "eat")
    assert "You can't reach Cookie from here." in outcome.result


def test_objects_list_after_eat_cookie_gone():
    area = create_initial_area()
    cookie = _create_cookie(area)
    goblin = _create_goblin(area, at="2,3")
    interact(goblin, area, cookie.id, "eat")

    text = format_objects_list(area)
    assert cookie.id not in text


def test_explorer_memory_records_goblin_eat_not_passive_vision():
    area = create_initial_area()
    cookie = _create_cookie(area)
    explorer = area.get_agent()
    goblin = _create_goblin(area, at="2,3")

    run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="eat",
            action="interact",
            target=cookie.id,
            verb="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    vision = build_passive_vision(explorer, area)
    assert "Goblin ate the cookie." not in vision
    memory = explorer.memory.render_prompt_block(explorer, area)
    assert "Goblin ate the cookie." in memory


def test_eat_clears_explorer_look_memory_for_cookie():
    area = create_initial_area()
    cookie = _create_cookie(area)
    explorer = area.get_agent()
    goblin = _create_goblin(area, at="2,3")

    perform_look(explorer, area, cookie.id)
    assert explorer.memory.has_looked_at(cookie.id)

    interact(goblin, area, cookie.id, "eat")

    assert area.get_object_by_id(cookie.id) is None
    assert not explorer.memory.has_looked_at(cookie.id)
    assert not explorer.memory.has_ever_looked_at(cookie.id)


def test_create_object_unknown_handler_rejected():
    area = create_initial_area()
    obj, msg = create_object_from_args(
        area,
        'name "Cookie" desc "x" at 2,2 action eat range 1 handler vanish '
        'result "x" passive "x"',
    )
    assert obj is None
    assert "Unknown handler" in msg


def test_result_only_interact_leaves_object():
    area = create_initial_area()
    obj, _ = create_object_from_args(
        area,
        'name "Flower" desc "Pretty." at 2,2 action smell range 1 '
        'result "It smells nice." passive "{actor} smells the flower."',
    )
    goblin = _create_goblin(area, at="2,3")

    record = run_compound_turn(
        goblin,
        area,
        AgentCompoundTurn(
            reasoning="smell",
            action="interact",
            target=obj.id,
            verb="smell",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert "It smells nice." in record.result
    assert goblin.passive_result == "Goblin smells the flower."
    assert area.get_object_by_id(obj.id) is not None


def test_edit_object_add_and_remove_action():
    area = create_initial_area()
    obj, _ = create_object_from_args(
        area, 'name "Cookie" desc "Tasty." at 2,2'
    )
    msg = edit_object_from_args(
        area,
        f'{obj.id} add-action eat range 1 handler delete_self '
        'result "Yum." passive "{actor} ate it."',
    )
    assert "Added action" in msg
    assert "eat" in obj.actions

    msg = edit_object_from_args(area, f"{obj.id} remove-action eat")
    assert "Removed action" in msg
    assert not obj.actions


def test_delete_object_clears_look_memory():
    area = create_initial_area()
    agent = area.get_agent()
    perform_look(agent, area, "obj_ball_01")
    assert agent.memory.has_looked_at("obj_ball_01")

    delete_object_by_id(area, "obj_ball_01")

    assert not agent.memory.has_looked_at("obj_ball_01")
    assert not agent.memory.has_ever_looked_at("obj_ball_01")


def test_handlers_list_includes_reference_set():
    out = format_handlers_list()
    assert "delete_self" in out
    assert "random_move_self" in out


def test_random_move_self_moves_ball(monkeypatch):
    area = create_initial_area()
    ball = area.get_object_by_id("obj_ball_01")
    explorer = area.get_agent()
    explorer.position = (2, 3)
    original = ball.position

    monkeypatch.setattr(
        "reference_handlers.handlers.random_move_self.random.choice",
        lambda positions: (0, 4),
    )

    record = run_compound_turn(
        explorer,
        area,
        AgentCompoundTurn(
            reasoning="kick",
            action="interact",
            target="obj_ball_01",
            verb="kick",
        ),
        next_turn_number_for_agent(explorer),
    )

    assert ball.position == (0, 4)
    assert ball.position != original
    assert (
        "You kick the Ceramic Ball. It rolls from (2, 2) to (0, 4)."
        in record.result
    )
    assert (
        explorer.passive_result
        == "Explorer kicks the Ceramic Ball. It rolls from (2, 2) to (0, 4)."
    )
    assert area.get_object_by_id("obj_ball_01") is ball


def test_random_move_self_excludes_current_tile(monkeypatch):
    area = create_initial_area()
    ball = area.get_object_by_id("obj_ball_01")
    explorer = area.get_agent()
    explorer.position = (2, 3)
    original = ball.position
    seen_positions: list[set[tuple[int, int]]] = []

    def capture_choice(positions):
        seen_positions.append(set(positions))
        return (0, 0)

    monkeypatch.setattr("reference_handlers.handlers.random_move_self.random.choice", capture_choice)

    interact(explorer, area, "obj_ball_01", "kick")

    assert len(seen_positions) == 1
    assert original not in seen_positions[0]
    assert ball.position == (0, 0)


def test_step_compound_kick_ball_moves(monkeypatch):
    from campaign_rpg_engine import Session, load_profile
    from campaign_rpg_engine.compound_arg_parse import parse_compound_step_arg

    session = Session.from_profile(load_profile("default_compound"))
    session.get_active_agent().position = (2, 3)
    monkeypatch.setattr(
        "reference_handlers.handlers.random_move_self.random.choice",
        lambda _positions: (4, 0),
    )
    turn = parse_compound_step_arg("- interact obj_ball_01 kick").turn
    session.run_compound_turn(turn)

    ball = session.area.get_object_by_id("obj_ball_01")
    assert ball.position == (4, 0)
    assert "You kick the Ceramic Ball. It rolls from (2, 2) to (4, 0)." in session.get_active_agent().memory.turns[-1].result
