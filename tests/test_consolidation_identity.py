"""Consolidation identity preamble (personality / appearance / other agents)."""

from __future__ import annotations

from campaign_rpg_engine.llm.affinity_update import build_affinity_update_prompt
from campaign_rpg_engine.llm.memory_summary import (
    build_rolling_summary_prompt,
    format_consolidation_identity_preamble,
)


def test_identity_preamble_format():
    text = format_consolidation_identity_preamble(
        personality="Dry-humored catfolk bartender.",
        appearance="A cat-eared woman with dyed hair.",
        other_agents=(
            ("Pip", "A nervous new arrival in earth clothes."),
            ("Mara", "Kitchen boss."),
        ),
    )
    assert "Your personality:\nDry-humored catfolk bartender." in text
    assert "Your appearance:\nA cat-eared woman with dyed hair." in text
    assert "Other Agents in this area:\nPip, A nervous new arrival in earth clothes.\nMara, Kitchen boss." in text


def test_rolling_summary_prompt_includes_identity():
    prompt = build_rolling_summary_prompt(
        agent_name="Praxis",
        previous_summary="",
        batch_text="Turn 1: hi",
        max_chars=1200,
        personality="You are Praxis, a woman with cat ears.",
        appearance="Cat-eared tavern worker.",
        other_agents=(("Pip", "Nervous spacer."),),
    )
    assert prompt.startswith("You maintain a rolling memory summary for Praxis")
    assert "Your personality:\nYou are Praxis, a woman with cat ears." in prompt
    assert "Your appearance:\nCat-eared tavern worker." in prompt
    assert "Pip, Nervous spacer." in prompt
    assert "Match pronouns" in prompt


def test_affinity_prompt_includes_identity():
    prompt = build_affinity_update_prompt(
        agent_name="Praxis",
        batch_text="Turn 1: hi",
        candidates=[
            {"agent_id": "agent_pip_01", "name": "Pip", "score": 0, "summary": ""},
        ],
        personality="You are Praxis; she/her.",
        appearance="Cat-eared woman.",
        other_agents=(("Pip", "Nervous spacer."),),
    )
    assert "Your personality:\nYou are Praxis; she/her." in prompt
    assert "Your appearance:\nCat-eared woman." in prompt
    assert "do not default to “he”" in prompt or "do not default to" in prompt
