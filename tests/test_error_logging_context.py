"""Error logs should include prompt and raw model output when available."""

from __future__ import annotations

import pytest

from campaign_rpg_engine.llm.affinity_update import generate_affinity_updates
from campaign_rpg_engine.llm.types import LLMResponse
from campaign_rpg_engine.log_utils import exception_already_logged
from campaign_rpg_engine.log_utils import logger as logger_mod


def test_log_error_passes_prompt_and_raw(monkeypatch):
    calls = []

    def fake_log_turn(turn_number, **kwargs):
        calls.append({"turn_number": turn_number, **kwargs})

    monkeypatch.setattr(logger_mod, "log_turn", fake_log_turn)

    exc = RuntimeError("Extra data: line 1 column 129 (char 128)")
    logger_mod.log_error(
        "Affinity consolidation failed",
        exc,
        turn_number=3,
        phase="memory_affinity",
        prompt="PROMPT TEXT",
        raw_output='[{"agent_id":"a"}] trailing junk',
    )
    assert len(calls) == 1
    assert calls[0]["prompt"] == "PROMPT TEXT"
    assert "trailing junk" in calls[0]["raw_output"]
    assert "Extra data" in calls[0]["error"]
    assert exception_already_logged(exc) is True


def test_affinity_parse_failure_logs_prompt_and_raw(monkeypatch):
    logged = []

    def capture_log(message, exc, **kwargs):
        logged.append({"message": message, "exc": exc, **kwargs})
        from campaign_rpg_engine.log_utils import mark_exception_logged

        mark_exception_logged(exc)

    monkeypatch.setattr(
        "campaign_rpg_engine.llm.affinity_update.log_consolidation_error",
        capture_log,
    )
    monkeypatch.setattr(
        "campaign_rpg_engine.llm.affinity_update.get_text_completion",
        lambda *a, **k: LLMResponse(
            # Two arrays: first json.loads fails with Extra data; greedy [...] regex
            # still leaves Extra data on the second loads — matches real failure mode.
            parsed=(
                '[{"agent_id":"agent_02","name":"Pip","delta":0,"summary":"ok"}]'
                '[{"agent_id":"agent_02","name":"Pip","delta":1,"summary":"dup"}]'
            ),
            raw_response=(
                '[{"agent_id":"agent_02","name":"Pip","delta":0,"summary":"ok"}]'
                '[{"agent_id":"agent_02","name":"Pip","delta":1,"summary":"dup"}]'
            ),
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            model="test",
        ),
    )

    with pytest.raises(Exception) as raised:
        generate_affinity_updates(
            agent_name="Praxis",
            batch_text="Turn 1: hello",
            candidates=[{"agent_id": "agent_02", "name": "Pip", "score": 0, "summary": ""}],
            turn_number=4,
        )

    assert "Extra data" in str(raised.value)
    assert logged
    assert logged[0]["prompt"]
    assert "dup" in (logged[0]["raw_output"] or "")
    assert logged[0]["phase"] == "memory_affinity"
