"""LLM client parsing and error codes."""

import pytest

from campaign_rpg_engine.llm.client import LLMParseError, get_structured_turn
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn


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

    monkeypatch.setattr("campaign_rpg_engine.llm.client.get_llm_client", lambda: FakeClient())

    with pytest.raises(LLMParseError) as exc_info:
        get_structured_turn("prompt", AgentCompoundTurn)

    assert "ERR:INVALID_JSON" in str(exc_info.value)
