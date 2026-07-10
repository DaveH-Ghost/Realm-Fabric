"""Tests for prompt token estimates (V0.4.2)."""

from campaign_rpg_engine.llm.token_estimate import estimate_prompt_tokens


def test_estimate_prompt_tokens_empty():
    assert estimate_prompt_tokens("") == 0


def test_estimate_prompt_tokens_rounds_up():
    assert estimate_prompt_tokens("abcd") == 1
    assert estimate_prompt_tokens("a" * 8) == 2
