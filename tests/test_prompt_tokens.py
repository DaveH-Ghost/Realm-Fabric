"""Default prompt token budget regression tests (V0.4.4)."""

from src.llm.prompt_context import build_prompt_context
from src.llm.token_estimate import DEFAULT_PROMPT_TOKEN_BUDGET, estimate_prompt_tokens
from src.session import Session


def test_default_prompt_token_budget():
    session = Session.from_default()
    tokens = estimate_prompt_tokens(session.build_prompt())
    assert tokens <= DEFAULT_PROMPT_TOKEN_BUDGET, (
        f"Default prompt est. {tokens} tokens exceeds budget {DEFAULT_PROMPT_TOKEN_BUDGET}"
    )


def test_compound_rules_section_budget():
    session = Session.from_default()
    agent = session.get_active_agent()
    ctx = build_prompt_context(agent, session.get_area_for_agent(agent))
    rules_tokens = estimate_prompt_tokens(ctx.compound_rules)
    assert rules_tokens <= 200, f"compound_rules est. {rules_tokens} tokens (max 200)"
