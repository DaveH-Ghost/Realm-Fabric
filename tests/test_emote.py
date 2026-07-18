"""Tests for emote turn action (V0.4.2)."""

from campaign_rpg_engine.actions.emote import emote
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.emote_phrasing import (
    emote_target_phrase_for_actor,
    emote_target_phrase_for_witness,
    emote_target_phrase_neutral,
)
from campaign_rpg_engine.llm.prompt import build_compound_prompt
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.simulation import run_compound_turn
from campaign_rpg_engine.compound_arg_parse import parse_compound_step_arg


def test_emote_at_object():
    area = create_initial_area()
    agent = area.get_agent()
    sign = area.get_object_by_id("obj_sign_01")
    assert sign is not None

    outcome = emote(agent, area, sign.id, "pointed")
    assert outcome.result == "[emote] Explorer pointed at the Wooden Sign."
    assert outcome.passive_result == "[emote] Explorer pointed at the Wooden Sign."


def test_emote_at_agent():
    area = create_initial_area()
    explorer = area.get_agent()
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="Grumpy.",
        description="A goblin.",
        position=(2, 2),
    )
    area.add_agent(goblin)

    outcome = emote(explorer, area, goblin.id, "smiled")
    assert outcome.result == "[emote] Explorer smiled at Goblin."
    assert outcome.passive_result == "[emote] Explorer smiled at Goblin."


def test_emote_at_self():
    area = create_initial_area()
    agent = area.get_agent()
    outcome = emote(agent, area, agent.id, "smiled")
    assert outcome.result == "[emote] Explorer smiled at Explorer."


def test_emote_without_target():
    area = create_initial_area()
    agent = area.get_agent()
    outcome = emote(agent, area, "", "nodded")
    assert outcome.result == "[emote] Explorer nodded."
    assert outcome.passive_result == "[emote] Explorer nodded."


def test_emote_schema_allows_null_target():
    turn = AgentCompoundTurn(
        reasoning="Agree quietly.",
        action="emote",
        target=None,
        verb="nodded",
    )
    assert turn.action == "emote"
    assert turn.target is None
    assert turn.verb == "nodded"


def test_phrasing_helpers():
    area = create_initial_area()
    agent = area.get_agent()
    assert emote_target_phrase_neutral(area, "obj_sign_01") == "the Wooden Sign"
    assert emote_target_phrase_for_actor(area, agent, agent.id) == "Explorer"
    goblin = Agent(
        id="agent_goblin_01",
        name="Goblin",
        personality="x",
        description="x",
        position=(0, 0),
    )
    area.add_agent(goblin)
    assert emote_target_phrase_for_witness(area, goblin.id, goblin) == "you"


def test_emote_witness_at_you_in_memory():
    area = create_initial_area()
    explorer = area.get_agent()
    create_agent_from_args(
        area,
        'name "Goblin" pdesc "A goblin." desc "x" personality "x" at 1,1',
    )
    goblin = area.get_agent_by_name("Goblin")

    run_compound_turn(
        explorer,
        area,
        AgentCompoundTurn(
            reasoning="Friendly.",
            action="emote",
            target=goblin.id,
            verb="smiled",
        ),
        turn_number=1,
        session_turn=1,
    )

    memory_text = goblin.memory.render_prompt_block(goblin, area)
    assert "[emote] Explorer smiled at you." in memory_text


def test_emote_compound_turn_step():
    area = create_initial_area()
    agent = area.get_agent()
    sign = area.get_object_by_id("obj_sign_01")
    record = run_compound_turn(
        agent,
        area,
        AgentCompoundTurn(
            reasoning="Point.",
            action="emote",
            target=sign.id,
            verb="pointed",
        ),
        turn_number=1,
    )
    assert record.steps[-1].kind == "emote"
    assert record.result == "[emote] Explorer pointed at the Wooden Sign."


def test_emote_schema_validation():
    turn = AgentCompoundTurn(
        reasoning="x",
        action="emote",
        target="obj_sign_01",
        verb="waved",
    )
    assert turn.action == "emote"


def test_prompt_mentions_emote():
    area = create_initial_area()
    agent = area.get_agent()
    prompt = build_compound_prompt(agent, area)
    assert '"emote"' in prompt
    assert "nonverbal" in prompt.lower()
    assert "past-tense" in prompt.lower()
    assert "[emote]" in prompt
    assert "remember" in prompt.lower() or "socially" in prompt.lower()


def test_step_compound_emote():
    parsed = parse_compound_step_arg("emote obj_sign_01 pointed")
    assert parsed.turn.action == "emote"
    assert parsed.turn.target == "obj_sign_01"
    assert parsed.turn.verb == "pointed"


def test_step_compound_emote_without_target():
    parsed = parse_compound_step_arg("emote nodded")
    assert parsed.turn.action == "emote"
    assert parsed.turn.target is None
    assert parsed.turn.verb == "nodded"
