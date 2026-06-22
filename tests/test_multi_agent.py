"""
test_multi_agent.py

Tests for V0.1 Section 3 multi-agent support (updated for V0.2 compound turns).
"""

from src.llm.schemas import AgentCompoundTurn
from src.perception import build_passive_vision, perform_look
from src.simulation import next_turn_number_for_agent, run_compound_turn
from src.area import create_initial_area
from src.area_edit import create_agent_from_args, edit_object_from_args


def _compound(**kwargs) -> AgentCompoundTurn:
    defaults = {"reasoning": "test", "action": "none"}
    defaults.update(kwargs)
    return AgentCompoundTurn(**defaults)


def _speak(content: str, **kwargs) -> AgentCompoundTurn:
    return _compound(action="none", say=content, **kwargs)


def test_get_agents_returns_copy():
    area = create_initial_area()
    agents = area.get_agents()
    assert len(agents) == 1
    agents.clear()
    assert len(area.agents) == 1


def test_get_agent_by_name_case_insensitive():
    area = create_initial_area()
    assert area.get_agent_by_name("explorer") is area.get_agent()
    assert area.get_agent_by_name("EXPLORER") is area.get_agent()
    assert area.get_agent_by_name("Missing") is None


def test_memory_isolation_between_agents():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(area, 'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3')
    goblin = area.get_agent_by_name("Goblin")

    perform_look(explorer, area, "obj_ball_01")

    assert explorer.memory.has_looked_at("obj_ball_01")
    assert not goblin.memory.has_looked_at("obj_ball_01")
    goblin_vision = build_passive_vision(goblin, area)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in goblin_vision
    assert (
        "Explorer (agent_01), (1, 1) - [?] A curious explorer in the room."
        in goblin_vision
    )
    explorer_vision = build_passive_vision(explorer, area)
    assert "Explorer (agent_01)" not in explorer_vision
    assert "Goblin (agent_goblin_01), (0, 3) - [?] A goblin." in explorer_vision


def test_personality_not_in_passive_vision_or_look():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "Visible detail." '
        'personality "SECRET_PERSONALITY_TEXT" at 0,3',
    )
    vision = build_passive_vision(explorer, area)
    assert "SECRET_PERSONALITY_TEXT" not in vision
    outcome = perform_look(explorer, area, "agent_goblin_01")
    assert "SECRET_PERSONALITY_TEXT" not in outcome.result
    assert "Visible detail." in outcome.result


def test_per_agent_turn_numbers_when_alternating():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(area, 'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3')
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        explorer,
        area,
        _speak("Explorer speaks."),
        next_turn_number_for_agent(explorer),
    )
    run_compound_turn(
        goblin,
        area,
        _speak("Goblin speaks."),
        next_turn_number_for_agent(goblin),
    )
    run_compound_turn(
        explorer,
        area,
        _speak("Explorer again."),
        next_turn_number_for_agent(explorer),
    )

    assert [t.turn_number for t in explorer.memory.turns] == [1, 2]
    assert [t.turn_number for t in goblin.memory.turns] == [1]


def test_speak_visible_in_observer_memory_not_passive_vision():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "A green goblin." '
        'personality "x" at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        goblin,
        area,
        _speak("Hello, Explorer!"),
        next_turn_number_for_agent(goblin),
    )

    vision = build_passive_vision(explorer, area)
    assert 'Goblin says: "Hello, Explorer!"' not in vision
    assert "Goblin (agent_goblin_01), (0, 3) - [?] A goblin." in vision
    memory = explorer.memory.render_prompt_block(explorer, area)
    assert 'Goblin says: "Hello, Explorer!"' in memory


def test_failed_move_does_not_update_passive_result():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 0,0',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        goblin,
        area,
        _speak("Hi."),
        next_turn_number_for_agent(goblin),
    )
    run_compound_turn(
        goblin,
        area,
        _compound(move="-1,0"),
        next_turn_number_for_agent(goblin),
    )

    assert goblin.passive_result == 'Goblin says: "Hi."'
    vision = build_passive_vision(explorer, area)
    assert 'Goblin says: "Hi."' not in vision
    assert "moves to" not in vision


def test_edit_agent_personality_does_not_invalidate():
    from src.area_edit import edit_agent_from_args

    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "Original detail." personality "Old" at 0,3',
    )
    perform_look(explorer, area, "agent_goblin_01")
    edit_agent_from_args(area, 'agent_goblin_01 personality "New personality"')

    vision = build_passive_vision(explorer, area)
    assert "Goblin (agent_goblin_01), (0, 3) - Original detail." in vision
    assert "[changed]" not in vision


def test_cross_agent_invalidation_per_agent():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(area, 'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3')
    goblin = area.get_agent_by_name("Goblin")

    perform_look(explorer, area, "obj_ball_01")
    perform_look(goblin, area, "obj_ball_01")
    edit_object_from_args(area, 'obj_ball_01 desc "A shiny ball."')

    assert "[?] [changed]" in build_passive_vision(explorer, area)
    assert "[?] [changed]" in build_passive_vision(goblin, area)


def test_stepper_switch_changes_active_agent_vision():
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('create-agent name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3')
    goblin = stepper.area.get_agent_by_name("Goblin")

    stepper.onecmd("switch Goblin")
    assert stepper.agent is goblin
    vision = build_passive_vision(stepper.agent, stepper.area)
    assert "You are at (0, 3)." in vision


def test_stepper_switch_unknown_agent(capsys):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd("switch Nobody")
    out = capsys.readouterr().out
    assert "not found" in out
    assert "agents" in out or "list" in out


def test_stepper_switch_does_not_increment_session_turn():
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    before = stepper.session_turn
    stepper.onecmd("switch Goblin")
    assert stepper.session_turn == before
    assert stepper.agent.name == "Goblin"


def test_stepper_manual_compound_uses_per_agent_turn_number():
    from src.main import ManualStepper

    stepper = ManualStepper()
    explorer = stepper.agent
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    stepper.onecmd("switch Explorer")
    stepper.onecmd("step-compound speak Hi from Explorer.")
    stepper.onecmd("switch Goblin")
    stepper.onecmd("step-compound speak Hi from Goblin.")
    stepper.onecmd("switch Explorer")
    stepper.onecmd("step-compound speak Explorer turn two.")

    assert [t.turn_number for t in explorer.memory.turns] == [1, 2]
    assert [t.turn_number for t in stepper.area.get_agent_by_name("Goblin").memory.turns] == [1]


def test_create_agent_reserved_command_name_rejected():
    area = create_initial_area()
    agent, msg = create_agent_from_args(area, 'name "vision" personality "x" at 0,0')
    assert agent is None
    assert "conflicts with a stepper command" in msg


def test_create_agent_reserved_hyphen_command_rejected():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area, 'name "create-object" personality "x" at 0,0'
    )
    assert agent is None
    assert "conflicts" in msg


def test_edit_agent_rename_to_reserved_name_rejected():
    from src.area_edit import edit_agent_from_args

    area = create_initial_area()
    result = edit_agent_from_args(area, 'agent_01 name "switch"')
    assert not result.ok
    assert "conflicts" in result.message


def test_run_command_uses_active_agent(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    called = []

    def fake_run(agent):
        called.append(agent)

    monkeypatch.setattr(stepper, "_run_llm_turn_for_agent", fake_run)
    stepper.onecmd("run")
    assert len(called) == 1
    assert called[0] is stepper.agent


def test_run_after_switch_uses_switched_agent(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    goblin = stepper.area.get_agent_by_name("Goblin")
    stepper.onecmd("switch Goblin")
    called = []

    def fake_run(agent):
        called.append(agent)

    monkeypatch.setattr(stepper, "_run_llm_turn_for_agent", fake_run)
    stepper.onecmd("run")
    assert called == [goblin]


def test_stepper_commands_case_insensitive(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    called = []

    def fake_run(agent):
        called.append(agent)

    monkeypatch.setattr(stepper, "_run_llm_turn_for_agent", fake_run)
    stepper.onecmd("Run")
    assert len(called) == 1


def test_reserved_commands_include_run_and_hyphenated():
    from src.main import ManualStepper
    from src.stepper_commands import collect_reserved_command_names, get_reserved_stepper_commands

    derived = collect_reserved_command_names(ManualStepper)
    cached = get_reserved_stepper_commands()
    assert derived == cached
    assert "run" in cached
    assert "create-agent" in cached
    assert "step-compound" in cached
    assert "effects" in cached
    assert "?" in cached


def test_llm_failure_does_not_increment_session_turn(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    agent = stepper.agent
    before_session = stepper.session_turn
    before_turns = agent.memory.turn_count

    def fail_llm(_prompt):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("src.llm.client.get_compound_turn", fail_llm)
    stepper._run_llm_turn_for_agent(agent)

    assert stepper.session_turn == before_session
    assert agent.memory.turn_count == before_turns


def test_step_compound_increments_session_turn_once():
    from src.main import ManualStepper

    stepper = ManualStepper()
    before = stepper.session_turn
    stepper.onecmd("step-compound 2,3")
    assert stepper.session_turn == before + 1


def test_llm_failure_still_sets_active_agent(monkeypatch):
    from src.main import ManualStepper

    stepper = ManualStepper()
    stepper.onecmd('create-agent name "Goblin" personality "x" at 0,0')
    goblin = stepper.area.get_agent_by_name("Goblin")
    assert stepper.agent.name == "Explorer"

    def fail_llm(_prompt):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("src.llm.client.get_compound_turn", fail_llm)
    stepper.default("Goblin")
    assert stepper.agent is goblin


def test_look_at_agent_reveals_description_not_personality():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A short figure." desc "A grumpy-looking goblin." '
        'personality "You are a grumpy goblin." at 0,3',
    )

    outcome = perform_look(explorer, area, "agent_goblin_01")
    assert "You looked at the goblin." in outcome.result
    assert "grumpy-looking goblin" in outcome.result
    assert "You are a grumpy goblin" not in outcome.result
    vision = build_passive_vision(explorer, area)
    assert "Goblin (agent_goblin_01), (0, 3) - A grumpy-looking goblin." in vision


def test_edit_agent_desc_invalidates_other_agents():
    from src.area_edit import edit_agent_from_args

    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "Original detail." personality "x" at 0,3',
    )
    perform_look(explorer, area, "agent_goblin_01")
    edit_agent_from_args(area, 'agent_goblin_01 desc "Updated detail."')

    vision = build_passive_vision(explorer, area)
    assert "Goblin (agent_goblin_01), (0, 3) - [?] [changed] A goblin." in vision
