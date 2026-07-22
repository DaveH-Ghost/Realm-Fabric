"""Opt-in pathing for registered turn verbs."""

from campaign_rpg_engine import (
    AgentCompoundTurn,
    Session,
    clear_turn_verbs_for_tests,
    load_profile,
    register_turn_verb,
    run_compound_turn,
)
from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.area_edit import create_agent_from_args


def _register_near_verb():
    def near(session, agent, area, turn):
        del session
        target_id = (turn.target or "").strip()
        other = area.get_agent_by_id(target_id)
        name = other.name if other is not None else "them"
        return ActionOutcome(
            result=f"You are near {name}.",
            passive_result=f"{agent.name} approaches {name}.",
        )

    register_turn_verb(
        "near",
        near,
        description="Approach another agent",
        path_range=1,
        path_target_from_turn=lambda turn: (turn.target or "").strip() or None,
    )


def test_verb_paths_toward_agent_before_execute():
    clear_turn_verbs_for_tests()
    _register_near_verb()

    session = Session.from_profile(load_profile("default_compound"))
    actor = session.get_active_agent()
    actor.position = (0, 0)
    actor.move_speed = 2
    area = session.get_area_for_agent(actor)
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 2,2',
    )
    goblin = area.get_agent_by_name("Goblin")

    record = run_compound_turn(
        actor,
        area,
        AgentCompoundTurn(
            reasoning="Get close.",
            action="verb",
            verb="near",
            target=goblin.id,
        ),
        1,
        session=session,
        session_turn=1,
    )

    move_steps = [step for step in record.steps if step.kind == "move"]
    verb_steps = [step for step in record.steps if step.kind == "verb"]
    assert len(move_steps) == 1
    assert len(verb_steps) == 1
    assert "Goblin" in move_steps[0].result
    assert "near Goblin" in record.result
    clear_turn_verbs_for_tests()


def test_verb_pathing_ignores_explicit_move_when_out_of_range():
    clear_turn_verbs_for_tests()
    _register_near_verb()

    session = Session.from_profile(load_profile("default_compound"))
    actor = session.get_active_agent()
    actor.position = (0, 0)
    actor.move_speed = 2
    area = session.get_area_for_agent(actor)
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 2,2',
    )
    goblin = area.get_agent_by_name("Goblin")

    record = run_compound_turn(
        actor,
        area,
        AgentCompoundTurn(
            reasoning="Try to move away but verb pathing wins.",
            move="4,4",
            action="verb",
            verb="near",
            target=goblin.id,
        ),
        1,
        session=session,
        session_turn=1,
    )

    assert actor.position != (4, 4)
    assert any(step.kind == "move" for step in record.steps)
    assert "Goblin" in record.result
    clear_turn_verbs_for_tests()


def test_verb_honors_explicit_move_when_already_in_range():
    clear_turn_verbs_for_tests()
    _register_near_verb()

    session = Session.from_profile(load_profile("default_compound"))
    actor = session.get_active_agent()
    actor.position = (0, 0)
    actor.move_speed = 4
    area = session.get_area_for_agent(actor)
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 2,0',
    )
    goblin = area.get_agent_by_name("Goblin")

    record = run_compound_turn(
        actor,
        area,
        AgentCompoundTurn(
            reasoning="Step next to them first.",
            move="1,0",
            action="verb",
            verb="near",
            target=goblin.id,
        ),
        1,
        session=session,
        session_turn=1,
    )

    assert actor.position == (1, 0)
    move_steps = [step for step in record.steps if step.kind == "move"]
    assert len(move_steps) == 1
    assert "near Goblin" in record.result
    clear_turn_verbs_for_tests()


def test_verb_dynamic_path_range_from_turn():
    clear_turn_verbs_for_tests()

    def far(session, agent, area, turn):
        del session, area, turn
        return ActionOutcome(
            result=f"You gesture at range from {agent.position}.",
            passive_result="",
        )

    register_turn_verb(
        "far",
        far,
        description="Approach with dynamic range",
        path_range=1,
        path_range_from_turn=lambda session, agent, area, turn: 3,
        path_target_from_turn=lambda turn: (turn.target or "").strip() or None,
    )

    session = Session.from_profile(load_profile("default_compound"))
    actor = session.get_active_agent()
    actor.position = (0, 0)
    actor.move_speed = 1
    area = session.get_area_for_agent(actor)
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 3,0',
    )
    goblin = area.get_agent_by_name("Goblin")

    record = run_compound_turn(
        actor,
        area,
        AgentCompoundTurn(
            reasoning="Dynamic range should let me act without pathing fully.",
            action="verb",
            verb="far",
            target=goblin.id,
        ),
        1,
        session=session,
        session_turn=1,
    )

    # range 3 from (0,0) to (3,0) — already in range, no move needed
    assert actor.position == (0, 0)
    assert not any(step.kind == "move" for step in record.steps)
    assert "gesture" in record.result.lower()
    clear_turn_verbs_for_tests()


def test_verb_pathing_fails_when_budget_too_short():
    clear_turn_verbs_for_tests()
    _register_near_verb()

    session = Session.from_profile(load_profile("default_compound"))
    actor = session.get_active_agent()
    actor.position = (0, 0)
    actor.move_speed = 1
    area = session.get_area_for_agent(actor)
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 3,0',
    )
    goblin = area.get_agent_by_name("Goblin")

    record = run_compound_turn(
        actor,
        area,
        AgentCompoundTurn(
            reasoning="Too far for one step.",
            action="verb",
            verb="near",
            target=goblin.id,
        ),
        1,
        session=session,
        session_turn=1,
    )

    assert any(step.kind == "move" for step in record.steps)
    verb_steps = [step for step in record.steps if step.kind == "verb"]
    assert len(verb_steps) == 1
    assert "too far" in verb_steps[0].result.lower()
    clear_turn_verbs_for_tests()
