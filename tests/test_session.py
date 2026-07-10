"""Session API (V0.3.0a) — engine entry point for turns and commands."""

from campaign_rpg_engine import ObjectAction
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.session import Session
from campaign_rpg_engine.area import create_initial_area


def test_from_default_matches_initial_world():
    session = Session.from_default()
    assert session.get_active_agent().name == "Explorer"
    assert session.area.get_object_by_id("obj_ball_01") is not None
    assert session.area.get_object_by_id("obj_sign_01") is not None


def test_create_object_adds_to_world():
    session = Session.from_default()
    result = session.create_object(
        name="Cookie",
        position=(2, 2),
        passive_description="A cookie.",
        description="Tasty.",
        actions={
            "eat": ObjectAction(
                name="eat",
                range=1,
                result="You ate the cookie.",
                passive_result="{actor} ate the cookie.",
                handler_id="delete_self",
            ),
        },
    )
    assert result.ok
    cookies = [
        o for o in session.area.get_objects() if o.name == "Cookie"
    ]
    assert len(cookies) == 1
    assert cookies[0].position == (2, 2)


def test_run_compound_turn_moves_agent():
    session = Session.from_default()
    agent = session.get_active_agent()
    assert agent.position == (1, 1)

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="move north",
            move="1,2",
            action="none",
        ),
    )
    assert result.ok
    assert result.record is not None
    assert agent.position == (1, 2)
    assert "You moved to (1, 2)." in result.message
    assert session.session_turn == 1


def test_run_compound_turn_by_agent_id():
    session = Session.from_default()
    session.create_agent(
        name="Goblin",
        position=(0, 0),
        personality="Grumpy.",
    )
    goblin = session.get_agent("Goblin")
    assert goblin is not None

    result = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="step",
            move="0,1",
            action="none",
        ),
        agent_id=goblin.id,
    )
    assert result.ok
    assert goblin.position == (0, 1)
    assert session.get_active_agent().id == goblin.id


def test_set_active_agent_does_not_consume_turn():
    session = Session.from_default()
    session.create_agent(
        name="Goblin",
        position=(0, 0),
        personality="Grumpy.",
    )
    before = session.session_turn

    switch = session.set_active_agent("Goblin")
    assert switch.ok
    assert session.get_active_agent().name == "Goblin"
    assert session.session_turn == before


def test_set_active_agent_unknown_fails():
    session = Session.from_default()
    result = session.set_active_agent("Nobody")
    assert not result.ok


def test_build_prompt_for_active_agent():
    session = Session.from_default()
    prompt = session.build_prompt()
    assert "Passive Vision:" in prompt
    assert "Explorer" in prompt
    assert "Memory:" in prompt


def test_build_prompt_for_named_agent():
    session = Session.from_default()
    session.create_agent(
        name="Goblin",
        position=(0, 0),
        personality="Grumpy goblin.",
    )
    prompt = session.build_prompt("Goblin")
    assert "Grumpy goblin." in prompt


def test_snapshot_is_read_only():
    session = Session.from_default()
    turn_before = session.session_turn
    snap = session.snapshot()
    assert snap["agents"][0]["name"] == "Explorer"
    assert session.session_turn == turn_before


def test_delete_active_agent_reassigns():
    session = Session.from_default()
    session.create_agent(
        name="Goblin",
        position=(0, 0),
        personality="Grumpy.",
    )
    goblin = session.get_agent("Goblin")
    assert goblin is not None
    session.set_active_agent("Goblin")

    result = session.delete_agent(goblin.id)
    assert result.ok
    assert session.get_active_agent().name == "Explorer"
    assert "Active agent:" in result.message


def test_format_debug_state_after_compound_turn():
    session = Session.from_default()
    session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="move",
            move="1,2",
            action="none",
        ),
    )
    report = session.format_debug_state()
    assert "Session turns (log label): 1" in report
    assert "Last turn" in report
    assert "passive_result:" in report


def test_gate_agent_turn_ready_by_default():
    session = Session.from_default()
    assert session.gate_agent_turn().ok


def test_web_handler_flow_create_then_turn():
    """Mirror what a FastAPI handler would do — no HTTP required."""
    session = Session.from_default()

    create = session.create_object(
        name="Cookie",
        position=(4, 4),
        passive_description="A cookie.",
        blocks_movement=False,
        actions={
            "eat": ObjectAction(
                name="eat",
                range=0,
                result="You ate it.",
                passive_result="{actor} ate it.",
                handler_id="delete_self",
            ),
        },
    )
    assert create.ok
    cookie_id = next(
        o.id for o in session.area.get_objects() if o.name == "Cookie"
    )

    session.set_active_agent("Explorer")
    session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="walk over",
            move="4,4",
            action="none",
        ),
    )
    eat = session.run_compound_turn(
        AgentCompoundTurn(
            reasoning="eat",
            action="interact",
            target=cookie_id,
            verb="eat",
        ),
    )
    assert eat.ok
    assert session.area.get_object_by_id(cookie_id) is None


def test_custom_world_constructor():
    area = create_initial_area()
    explorer = area.get_agent()
    session = Session(area, active_agent_id=explorer.id)
    assert session.get_active_agent().id == explorer.id
