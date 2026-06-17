"""Prompt block model and rendering (V0.4.1b)."""

from src.game_profile import default_compound_profile
from src.llm.prompt_context import build_prompt_context
from src.prompt_blocks import (
    PromptBlock,
    default_prompt_blocks,
    prompt_blocks_from_dicts,
    render_prompt_blocks,
)
from src.prompt_template import PromptTemplate
from src.session import Session


def test_default_blocks_match_template_render():
    profile = default_compound_profile()
    session = Session.from_default()
    agent = session.get_active_agent()
    ctx = build_prompt_context(agent, session.get_area_for_agent(agent))

    from_template = profile.template.render_context(ctx)
    from_blocks = render_prompt_blocks(default_prompt_blocks(), ctx)
    assert from_blocks == from_template


def test_session_build_prompt_uses_blocks():
    session = Session.from_default()
    profile = session.profile
    agent = session.get_active_agent()
    ctx = build_prompt_context(agent, session.get_area_for_agent(agent))

    assert session.build_prompt() == render_prompt_blocks(default_prompt_blocks(), ctx)
    assert session.build_prompt() == profile.template.render_context(ctx)


def test_reorder_blocks_changes_prompt():
    session = Session.from_default()
    blocks = list(default_prompt_blocks())
    blocks.insert(0, PromptBlock(type="text", content="PROMPT START\n"))
    session.set_prompt_blocks(blocks)
    prompt = session.build_prompt()
    assert prompt.startswith("PROMPT START")
    assert "You are Explorer." in prompt


def test_section_override_changes_rules():
    session = Session.from_default()
    blocks = default_prompt_blocks()
    custom = []
    for block in blocks:
        if block.type == "section" and block.name == "compound_rules":
            custom.append(
                PromptBlock(
                    type="section",
                    name="compound_rules",
                    content="CUSTOM RULES ONLY.",
                )
            )
        else:
            custom.append(block)
    session.set_prompt_blocks(custom)
    prompt = session.build_prompt()
    assert "CUSTOM RULES ONLY." in prompt
    assert "Each turn you may plan" not in prompt


def test_set_prompt_blocks_validation():
    session = Session.from_default()
    err = session.set_prompt_blocks(
        [PromptBlock(type="slot", name="not_a_real_slot")]
    )
    assert err is not None
    assert session.prompt_blocks_use_default()


def test_prompt_blocks_from_dicts_round_trip():
    original = default_prompt_blocks()
    payload = [block.to_dict() for block in original]
    parsed, err = prompt_blocks_from_dicts(payload)
    assert err is None
    assert len(parsed) == len(original)


def test_reset_prompt_blocks():
    session = Session.from_default()
    blocks = default_prompt_blocks()
    blocks[0] = PromptBlock(type="text", content="TOP\n")
    session.set_prompt_blocks(blocks)
    assert not session.prompt_blocks_use_default()
    session.reset_prompt_blocks()
    assert session.prompt_blocks_use_default()


def test_put_invalid_blocks_rejected():
    session = Session.from_default()
    _, err = prompt_blocks_from_dicts([{"type": "slot"}])
    assert err is not None
