"""
test_object_actions.py

V0.2 Section 3: declarative object interactions.
"""

from src.actions.interact import interact
from src.llm.prompt import build_action_prompt
from src.llm.schemas import AgentActionTurn, AgentNavigationTurn
from src.object_effects import format_effects_list
from src.perception import build_passive_vision, perform_look
from src.simulation import next_turn_number_for_agent, run_compound_turn
from src.world import create_initial_world
from src.world_edit import (
    create_agent_from_args,
    create_object_from_args,
    delete_object_by_id,
    edit_object_from_args,
    format_objects_list,
)


COOKIE_ARGS = (
    'name "Cookie" pdesc "A cookie." desc "A tasty cookie." at 2,2 '
    'action eat range 1 effect delete_self '
    'result "You ate the cookie, it was delicious." '
    'passive "{actor} ate the cookie."'
)


def _create_cookie(world):
    obj, _ = create_object_from_args(world, COOKIE_ARGS)
    assert obj is not None
    return obj


def _create_goblin(world, at="0,3"):
    agent, _ = create_agent_from_args(
        world, f'name "Goblin" personality "Hungry." at {at}'
    )
    assert agent is not None
    return agent


def test_effects_command_lists_registered_effects():
    text = format_effects_list()
    assert "delete_self" in text
    assert "random_move_self" in text
    assert "Remove the interacted object" in text
    assert "different random in-bounds grid position" in text


def test_effect_registry_descriptions_match_handlers():
    from src.object_effects import EFFECT_DESCRIPTIONS, _EFFECT_HANDLERS

    assert set(EFFECT_DESCRIPTIONS) == set(_EFFECT_HANDLERS)


def test_create_cookie_shows_action_in_objects_list():
    world = create_initial_world()
    cookie = _create_cookie(world)
    text = format_objects_list(world)
    assert cookie.id in text
    assert "actions: eat" in text


def test_initial_ball_shows_kick_action_in_objects_list():
    world = create_initial_world()
    text = format_objects_list(world)
    assert "obj_ball_01" in text
    assert "actions: kick" in text


def test_kick_appears_in_action_prompt_when_adjacent():
    world = create_initial_world()
    explorer = world.get_agent()
    explorer.position = (2, 3)

    prompt = build_action_prompt(explorer, world)
    assert "Object interactions available this turn:" in prompt
    assert "kick obj_ball_01 (Ceramic Ball) — range 1" in prompt


def test_unknown_interact_wrong_action_name():
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="2,3")

    outcome = interact(goblin, world, cookie.id, "drink")
    assert "ERR:UNKNOWN_INTERACT" in outcome.result
    assert world.get_object_by_id(cookie.id) is not None


def test_range_zero_same_tile_interact():
    world = create_initial_world()
    obj, _ = create_object_from_args(
        world,
        'name "Gem" desc "A gem." at 2,3 action pick range 0 '
        'result "You pick up the {object}." passive "{actor} picks up the {object}."',
    )
    goblin = _create_goblin(world, at="2,3")

    prompt = build_action_prompt(goblin, world)
    assert "pick obj_gem_01 (Gem) — same tile" in prompt

    outcome = interact(goblin, world, obj.id, "pick")
    assert "You pick up the Gem." in outcome.result


def test_multiple_actions_on_one_object():
    world = create_initial_world()
    obj, _ = create_object_from_args(
        world, 'name "Cookie" desc "Tasty." at 2,2'
    )
    assert edit_object_from_args(
        world,
        f'{obj.id} add-action eat range 1 effect delete_self '
        'result "Yum." passive "{actor} ate it."',
    ).startswith("Added action")
    assert edit_object_from_args(
        world,
        f'{obj.id} add-action smell range 1 result "Nice." '
        'passive "{actor} smells it."',
    ).startswith("Added action")

    text = format_objects_list(world)
    assert "actions: eat, smell" in text


def test_create_object_accepts_random_move_self_effect():
    world = create_initial_world()
    obj, msg = create_object_from_args(
        world,
        'name "Marble" desc "Round." at 1,1 action roll range 0 '
        'effect random_move_self result "It rolls." passive "{actor} rolls it."',
    )
    assert obj is not None
    assert obj.actions["roll"].effects == ["random_move_self"]
    assert "Created object" in msg


def test_failed_interact_after_move_shows_move_in_passive_result():
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="0,0")

    record = run_compound_turn(
        goblin,
        world,
        AgentNavigationTurn(reasoning="approach", move_target="4,3"),
        AgentActionTurn(
            reasoning="eat from too far",
            turn_action="interact",
            target=cookie.id,
            action_name="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert goblin.position == (4, 3)
    assert "ERR:INTERACT_OUT_OF_RANGE" in record.result
    assert goblin.passive_result == "Goblin moves to (4, 3)."
    explorer = world.get_agent()
    vision = build_passive_vision(explorer, world)
    assert "Goblin moves to (4, 3)." in vision
    assert "ate the cookie" not in vision
    assert world.get_object_by_id(cookie.id) is not None


def test_in_range_goblin_sees_eat_in_action_prompt():
    world = create_initial_world()
    _create_cookie(world)
    goblin = _create_goblin(world, at="2,3")

    prompt = build_action_prompt(goblin, world)
    assert "Object interactions available this turn:" in prompt
    assert "eat obj_cookie_01 (Cookie) — range 1" in prompt


def test_goblin_interact_eat_deletes_cookie():
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="2,3")

    record = run_compound_turn(
        goblin,
        world,
        AgentNavigationTurn(reasoning="stay", move_target=None),
        AgentActionTurn(
            reasoning="eat",
            turn_action="interact",
            target=cookie.id,
            action_name="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert world.get_object_by_id(cookie.id) is None
    assert "You ate the cookie, it was delicious." in record.result
    assert goblin.passive_result == "Goblin ate the cookie."


def test_step_compound_move_adjacent_and_eat():
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd(f"create-object {COOKIE_ARGS}")
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    stepper.onecmd("switch Goblin")
    cookie_id = stepper.world.get_objects()[-1].id
    stepper.onecmd(f"step-compound 2,3 interact {cookie_id} eat")

    assert stepper.world.get_object_by_id(cookie_id) is None
    goblin = stepper.world.get_agent_by_name("Goblin")
    assert goblin.position == (2, 3)
    assert "You ate the cookie" in goblin.memory.turns[-1].result


def test_out_of_range_not_in_prompt_and_runtime_fails():
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="0,0")

    prompt = build_action_prompt(goblin, world)
    assert "Object interactions available this turn:" not in prompt

    outcome = interact(goblin, world, cookie.id, "eat")
    assert "ERR:INTERACT_OUT_OF_RANGE" in outcome.result
    assert world.get_object_by_id(cookie.id) is not None


def test_not_visible_interact_fails(monkeypatch):
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="2,3")

    monkeypatch.setattr(
        "src.actions.interact.is_object_in_passive_vision",
        lambda _agent, _world, object_id: object_id != cookie.id,
    )

    outcome = interact(goblin, world, cookie.id, "eat")
    assert "ERR:INTERACT_NOT_VISIBLE" in outcome.result


def test_objects_list_after_eat_cookie_gone():
    world = create_initial_world()
    cookie = _create_cookie(world)
    goblin = _create_goblin(world, at="2,3")
    interact(goblin, world, cookie.id, "eat")

    text = format_objects_list(world)
    assert cookie.id not in text


def test_explorer_vision_shows_goblin_eat_passive_result():
    world = create_initial_world()
    cookie = _create_cookie(world)
    explorer = world.get_agent()
    goblin = _create_goblin(world, at="2,3")

    run_compound_turn(
        goblin,
        world,
        AgentNavigationTurn(reasoning="stay", move_target=None),
        AgentActionTurn(
            reasoning="eat",
            turn_action="interact",
            target=cookie.id,
            action_name="eat",
        ),
        next_turn_number_for_agent(goblin),
    )

    vision = build_passive_vision(explorer, world)
    assert "Goblin ate the cookie." in vision


def test_eat_clears_explorer_look_memory_for_cookie():
    world = create_initial_world()
    cookie = _create_cookie(world)
    explorer = world.get_agent()
    goblin = _create_goblin(world, at="2,3")

    perform_look(explorer, world, cookie.id)
    assert explorer.memory.has_looked_at(cookie.id)

    interact(goblin, world, cookie.id, "eat")

    assert world.get_object_by_id(cookie.id) is None
    assert not explorer.memory.has_looked_at(cookie.id)
    assert not explorer.memory.has_ever_looked_at(cookie.id)


def test_create_object_unknown_effect_rejected():
    world = create_initial_world()
    obj, msg = create_object_from_args(
        world,
        'name "Cookie" desc "x" at 2,2 action eat range 1 effect vanish '
        'result "x" passive "x"',
    )
    assert obj is None
    assert "Unknown effect" in msg


def test_result_only_interact_leaves_object():
    world = create_initial_world()
    obj, _ = create_object_from_args(
        world,
        'name "Flower" desc "Pretty." at 2,2 action smell range 1 '
        'result "It smells nice." passive "{actor} smells the flower."',
    )
    goblin = _create_goblin(world, at="2,3")

    record = run_compound_turn(
        goblin,
        world,
        AgentNavigationTurn(reasoning="stay", move_target=None),
        AgentActionTurn(
            reasoning="smell",
            turn_action="interact",
            target=obj.id,
            action_name="smell",
        ),
        next_turn_number_for_agent(goblin),
    )

    assert "It smells nice." in record.result
    assert goblin.passive_result == "Goblin smells the flower."
    assert world.get_object_by_id(obj.id) is not None


def test_edit_object_add_and_remove_action():
    world = create_initial_world()
    obj, _ = create_object_from_args(
        world, 'name "Cookie" desc "Tasty." at 2,2'
    )
    msg = edit_object_from_args(
        world,
        f'{obj.id} add-action eat range 1 effect delete_self '
        'result "Yum." passive "{actor} ate it."',
    )
    assert "Added action" in msg
    assert "eat" in obj.actions

    msg = edit_object_from_args(world, f"{obj.id} remove-action eat")
    assert "Removed action" in msg
    assert not obj.actions


def test_delete_object_clears_look_memory():
    world = create_initial_world()
    agent = world.get_agent()
    perform_look(agent, world, "obj_ball_01")
    assert agent.memory.has_looked_at("obj_ball_01")

    delete_object_by_id(world, "obj_ball_01")

    assert not agent.memory.has_looked_at("obj_ball_01")
    assert not agent.memory.has_ever_looked_at("obj_ball_01")


def test_stepper_effects_command(capsys):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd("effects")
    out = capsys.readouterr().out
    assert "delete_self" in out
    assert "random_move_self" in out


def test_random_move_self_moves_ball(monkeypatch):
    world = create_initial_world()
    ball = world.get_object_by_id("obj_ball_01")
    explorer = world.get_agent()
    explorer.position = (2, 3)
    original = ball.position

    monkeypatch.setattr(
        "src.object_effects.random.choice",
        lambda positions: (0, 4),
    )

    record = run_compound_turn(
        explorer,
        world,
        AgentNavigationTurn(reasoning="stay", move_target=None),
        AgentActionTurn(
            reasoning="kick",
            turn_action="interact",
            target="obj_ball_01",
            action_name="kick",
        ),
        next_turn_number_for_agent(explorer),
    )

    assert ball.position == (0, 4)
    assert ball.position != original
    assert "You kick the Ceramic Ball." in record.result
    assert explorer.passive_result == "Explorer kicks the Ceramic Ball."
    assert world.get_object_by_id("obj_ball_01") is ball


def test_random_move_self_excludes_current_tile(monkeypatch):
    world = create_initial_world()
    ball = world.get_object_by_id("obj_ball_01")
    explorer = world.get_agent()
    explorer.position = (2, 3)
    original = ball.position
    seen_positions: list[set[tuple[int, int]]] = []

    def capture_choice(positions):
        seen_positions.append(set(positions))
        return (0, 0)

    monkeypatch.setattr("src.object_effects.random.choice", capture_choice)

    interact(explorer, world, "obj_ball_01", "kick")

    assert len(seen_positions) == 1
    assert original not in seen_positions[0]
    assert ball.position == (0, 0)


def test_step_compound_kick_ball_moves(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.agent.position = (2, 3)
    monkeypatch.setattr(
        "src.object_effects.random.choice",
        lambda _positions: (4, 0),
    )
    stepper.onecmd("step-compound - interact obj_ball_01 kick")

    ball = stepper.world.get_object_by_id("obj_ball_01")
    assert ball.position == (4, 0)
    assert "You kick the Ceramic Ball." in stepper.agent.memory.turns[-1].result
