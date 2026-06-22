"""Tests for emote turn action (V0.4.2)."""

from src.actions.emote import emote
from src.area import create_initial_area
from src.area_edit import create_agent_from_args
from src.agent import Agent
from src.emote_phrasing import (
    emote_target_phrase_for_actor,
    emote_target_phrase_for_witness,
    emote_target_phrase_neutral,
)
from src.llm.prompt import build_compound_prompt
from src.llm.schemas import AgentCompoundTurn
from src.simulation import run_compound_turn
from src.compound_stepper import parse_compound_step_arg


def test_emote_at_object():
    area = create_initial_area()
    agent = area.get_agent()
    sign = area.get_object_by_id("obj_sign_01")
    assert sign is not None

    outcome = emote(agent, area, sign.id, "pointed")
    assert outcome.result == "You pointed at the Wooden Sign."
    assert outcome.passive_result == "Explorer pointed at the Wooden Sign."


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
    assert outcome.result == "You smiled at Goblin."
    assert outcome.passive_result == "Explorer smiled at Goblin."


def test_emote_at_self():
    area = create_initial_area()
    agent = area.get_agent()
    outcome = emote(agent, area, agent.id, "smiled")
    assert outcome.result == "You smiled at yourself."


def test_phrasing_helpers():
    area = create_initial_area()
    agent = area.get_agent()
    assert emote_target_phrase_neutral(area, "obj_sign_01") == "the Wooden Sign"
    assert emote_target_phrase_for_actor(area, agent, agent.id) == "yourself"
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
    assert "Explorer smiled at you." in memory_text


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
    assert record.result == "You pointed at the Wooden Sign."


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
    assert "past tense" in prompt.lower()


def test_step_compound_emote():
    parsed = parse_compound_step_arg("emote obj_sign_01 pointed")
    assert parsed.turn.action == "emote"
    assert parsed.turn.target == "obj_sign_01"
    assert parsed.turn.verb == "pointed"
