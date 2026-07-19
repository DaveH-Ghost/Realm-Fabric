"""LLM client provider resolution and input budget gate (1.5.2)."""

import pytest

from campaign_rpg_engine.llm.client import (
    LLMParseError,
    PromptTooLargeError,
    get_llm_client,
    get_llm_provider,
    get_structured_turn,
    resolve_llm_model,
)
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.llm.token_estimate import (
    DEFAULT_INPUT_WARNING_PERCENT,
    DEFAULT_MAX_INPUT_TOKENS,
    estimate_prompt_tokens,
    get_input_warning_percent,
    get_max_input_tokens,
    prompt_token_budget_status,
)


def test_llm_client_raises_invalid_json_on_bad_output(monkeypatch):
    class FakeMessage:
        content = "not json at all"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = None

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return FakeResponse()

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "1000000")
    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_llm_client", lambda: FakeClient())

    with pytest.raises(LLMParseError) as exc_info:
        get_structured_turn("prompt", AgentCompoundTurn)

    assert "ERR:INVALID_JSON" in str(exc_info.value)
    assert exc_info.value.raw_response == "not json at all"


def test_llm_client_repairs_missing_leading_brace(monkeypatch):
    """Featherless DeepSeek Flash often omits the opening brace."""
    body = (
        '"reasoning": "Stay put.",\n'
        '  "move": null,\n'
        '  "look": null,\n'
        '  "say": null,\n'
        '  "action": "none",\n'
        '  "target": null,\n'
        '  "verb": null\n'
        "}"
    )

    class FakeMessage:
        content = body

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]
        usage = None

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return FakeResponse()

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "1000000")
    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_llm_client", lambda: FakeClient())

    result = get_structured_turn("prompt", AgentCompoundTurn)
    assert result.parsed.action == "none"
    assert result.parsed.reasoning == "Stay put."
    assert result.raw_response.startswith("{")


def test_provider_defaults_to_openrouter(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert get_llm_provider() == "openrouter"


def test_provider_featherless(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "featherless")
    assert get_llm_provider() == "featherless"
    monkeypatch.setenv("FEATHERLESS_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    assert resolve_llm_model() == "meta-llama/Meta-Llama-3.1-8B-Instruct"


def test_featherless_client_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "featherless")
    monkeypatch.delenv("FEATHERLESS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FEATHERLESS_API_KEY"):
        get_llm_client()


def test_openrouter_client_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        get_llm_client()


def test_max_input_tokens_defaults_and_env(monkeypatch):
    monkeypatch.delenv("LLM_MAX_INPUT_TOKENS", raising=False)
    assert get_max_input_tokens() == DEFAULT_MAX_INPUT_TOKENS
    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "16000")
    assert get_max_input_tokens() == 16000


def test_warning_percent_defaults_and_clamp(monkeypatch):
    monkeypatch.delenv("LLM_INPUT_WARNING_PERCENT", raising=False)
    assert get_input_warning_percent() == DEFAULT_INPUT_WARNING_PERCENT
    monkeypatch.setenv("LLM_INPUT_WARNING_PERCENT", "90")
    status = prompt_token_budget_status("x" * 4 * 30000)
    assert status["warning_threshold"] == (32768 * 90) // 100
    monkeypatch.setenv("LLM_INPUT_WARNING_PERCENT", "0")
    assert get_input_warning_percent() == 1
    monkeypatch.setenv("LLM_INPUT_WARNING_PERCENT", "150")
    assert get_input_warning_percent() == 100


def test_prompt_too_large_refuses_before_api(monkeypatch):
    called = {"create": False}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            called["create"] = True
            raise AssertionError("API should not be called")

    class FakeClient:
        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setenv("LLM_MAX_INPUT_TOKENS", "10")
    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_llm_client", lambda: FakeClient())

    big = "word " * 100
    assert estimate_prompt_tokens(big) > 10
    with pytest.raises(PromptTooLargeError) as exc_info:
        get_structured_turn(big, AgentCompoundTurn)
    assert exc_info.value.limit == 10
    assert called["create"] is False
