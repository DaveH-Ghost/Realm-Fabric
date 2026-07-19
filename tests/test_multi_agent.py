"""
test_multi_agent.py

Tests for V0.1 Section 3 multi-agent support (updated for V0.2 compound turns).
"""

import contextlib

from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args, edit_object_from_args
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.perception import build_passive_vision, perform_look
from campaign_rpg_engine.simulation import next_turn_number_for_agent, run_compound_turn


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
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    perform_look(explorer, area, "obj_ball_01")

    assert explorer.memory.has_looked_at("obj_ball_01")
    assert not goblin.memory.has_looked_at("obj_ball_01")
    goblin_vision = build_passive_vision(goblin, area)
    assert "Ceramic Ball (obj_ball_01), (2, 2) - [?]" in goblin_vision
    assert "Explorer (agent_01), (1, 1) - [?] A curious explorer in the room." in goblin_vision
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
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3',
    )
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
        'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "x" at 0,3',
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
    from campaign_rpg_engine.area_edit import edit_agent_from_args

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
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "A green goblin." personality "Secret goblin mind." at 0,3',
    )
    goblin = area.get_agent_by_name("Goblin")

    perform_look(explorer, area, "obj_ball_01")
    perform_look(goblin, area, "obj_ball_01")
    edit_object_from_args(area, 'obj_ball_01 desc "A shiny ball."')

    assert "[?] [changed]" in build_passive_vision(explorer, area)
    assert "[?] [changed]" in build_passive_vision(goblin, area)


def test_set_active_agent_changes_vision():
    from campaign_rpg_engine import Session, load_profile

    session = Session.from_profile(load_profile("default_compound"))
    session.create_agent(
        name="Goblin",
        position=(0, 3),
        passive_description="A goblin.",
        description="A green goblin.",
        personality="Secret goblin mind.",
    )
    session.set_active_agent("Goblin")
    vision = build_passive_vision(session.get_active_agent(), session.area)
    assert "You are at (0, 3)." in vision


def test_set_active_agent_unknown_fails():
    from campaign_rpg_engine import Session, load_profile

    session = Session.from_profile(load_profile("default_compound"))
    result = session.set_active_agent("Nobody")
    assert not result.ok
    assert "not found" in result.message.lower()


def test_set_active_agent_does_not_increment_session_turn():
    from campaign_rpg_engine import Session, load_profile

    session = Session.from_profile(load_profile("default_compound"))
    session.create_agent(name="Goblin", position=(0, 0), personality="x")
    before = session.session_turn
    session.set_active_agent("Goblin")
    assert session.session_turn == before
    assert session.get_active_agent().name == "Goblin"


def test_manual_compound_uses_per_agent_turn_number():
    from campaign_rpg_engine import Session, load_profile
    from campaign_rpg_engine.compound_arg_parse import parse_compound_step_arg

    session = Session.from_profile(load_profile("default_compound"))
    explorer = session.get_active_agent()
    session.create_agent(name="Goblin", position=(0, 0), personality="x")
    session.set_active_agent("Explorer")
    session.run_compound_turn(parse_compound_step_arg("speak Hi from Explorer.").turn)
    session.set_active_agent("Goblin")
    session.run_compound_turn(parse_compound_step_arg("speak Hi from Goblin.").turn)
    session.set_active_agent("Explorer")
    session.run_compound_turn(parse_compound_step_arg("speak Explorer turn two.").turn)

    assert [t.turn_number for t in explorer.memory.turns] == [1, 2]
    assert [t.turn_number for t in session.area.get_agent_by_name("Goblin").memory.turns] == [1]


def test_create_agent_reserved_command_name_rejected():
    area = create_initial_area()
    agent, msg = create_agent_from_args(area, 'name "vision" personality "x" at 0,0')
    assert agent is None
    assert "conflicts with a reserved command" in msg


def test_create_agent_reserved_hyphen_command_rejected():
    area = create_initial_area()
    agent, msg = create_agent_from_args(area, 'name "create-object" personality "x" at 0,0')
    assert agent is None
    assert "conflicts" in msg


def test_edit_agent_rename_to_reserved_name_rejected():
    from campaign_rpg_engine.area_edit import edit_agent_from_args

    area = create_initial_area()
    result = edit_agent_from_args(area, 'agent_01 name "switch"')
    assert not result.ok
    assert "conflicts" in result.message


def test_llm_turn_flow_uses_active_agent(monkeypatch):
    from campaign_rpg_engine import Session, get_compound_turn, load_profile
    from campaign_rpg_engine.llm.types import LLMResponse

    session = Session.from_profile(load_profile("default_compound"))
    active = session.get_active_agent()

    def fake_compound(_prompt):
        return LLMResponse(
            parsed=AgentCompoundTurn(reasoning="x", action="none", say="hi"),
            raw_response="{}",
        )

    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_compound_turn", fake_compound)
    response = get_compound_turn(session.build_prompt())
    result = session.run_compound_turn(response.parsed)
    assert result.ok
    assert session.get_active_agent() is active


def test_llm_turn_after_switch_uses_switched_agent(monkeypatch):
    from campaign_rpg_engine import Session, get_compound_turn, load_profile
    from campaign_rpg_engine.llm.types import LLMResponse

    session = Session.from_profile(load_profile("default_compound"))
    session.create_agent(name="Goblin", position=(0, 0), personality="x")
    goblin = session.get_agent("Goblin")
    session.set_active_agent("Goblin")

    def fake_compound(_prompt):
        return LLMResponse(
            parsed=AgentCompoundTurn(reasoning="x", action="none", say="hi"),
            raw_response="{}",
        )

    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_compound_turn", fake_compound)
    response = get_compound_turn(session.build_prompt())
    result = session.run_compound_turn(response.parsed)
    assert result.ok
    assert result.agent is goblin


def test_reserved_command_names_include_run_and_hyphenated():
    from campaign_rpg_engine.reserved_names import get_reserved_command_names

    cached = get_reserved_command_names()
    assert "run" in cached
    assert "create-agent" in cached
    assert "step-compound" in cached
    assert "handlers" in cached
    assert "?" in cached


def test_llm_failure_does_not_increment_session_turn(monkeypatch):
    from campaign_rpg_engine import Session, get_compound_turn, load_profile

    session = Session.from_profile(load_profile("default_compound"))
    agent = session.get_active_agent()
    before_session = session.session_turn
    before_turns = agent.memory.turn_count

    def fail_llm(_prompt):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_compound_turn", fail_llm)
    with contextlib.suppress(RuntimeError):
        get_compound_turn(session.build_prompt())

    assert session.session_turn == before_session
    assert agent.memory.turn_count == before_turns


def test_compound_turn_increments_session_turn_once():
    from campaign_rpg_engine import Session, load_profile
    from campaign_rpg_engine.compound_arg_parse import parse_compound_step_arg

    session = Session.from_profile(load_profile("default_compound"))
    before = session.session_turn
    session.run_compound_turn(parse_compound_step_arg("2,3").turn)
    assert session.session_turn == before + 1


def test_set_active_agent_by_name():
    from campaign_rpg_engine import Session, load_profile

    session = Session.from_profile(load_profile("default_compound"))
    session.create_agent(name="Goblin", position=(0, 0), personality="x")
    goblin = session.get_agent("Goblin")
    assert session.get_active_agent().name == "Explorer"

    session.set_active_agent("Goblin")
    assert session.get_active_agent() is goblin


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
    from campaign_rpg_engine.area_edit import edit_agent_from_args

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
