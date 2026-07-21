"""Affinity Call B JSON repair (Featherless missing leading '[')."""

from __future__ import annotations

import pytest

from campaign_rpg_engine.llm.affinity_update import (
    _extract_json_array,
    parse_and_validate_affinity_updates,
)


def test_extract_json_array_repairs_missing_leading_bracket():
    raw = """{"agent_id": "__area__", "name": "Environment", "delta": 0, "summary": "Polite greeting."},
{"agent_id": "agent_mara_01", "name": "Mara", "delta": 0, "summary": "Boss; no interaction this turn."},
{"agent_id": "agent_pip_01", "name": "Pip", "delta": 1, "summary": "Warm rapport opening."}
]"""
    rows = _extract_json_array(raw)
    assert len(rows) == 3
    assert rows[0]["agent_id"] == "__area__"
    assert rows[2]["delta"] == 1


def test_parse_validates_repaired_missing_bracket():
    candidates = [
        {"agent_id": "__area__", "name": "Environment", "score": 0, "summary": ""},
        {"agent_id": "agent_mara_01", "name": "Mara", "score": 0, "summary": ""},
        {"agent_id": "agent_pip_01", "name": "Pip", "score": 0, "summary": ""},
    ]
    raw = (
        '{"agent_id": "__area__", "name": "Environment", "delta": 0, "summary": "Polite."},'
        '{"agent_id": "agent_mara_01", "name": "Mara", "delta": 0, "summary": "No chat."},'
        '{"agent_id": "agent_pip_01", "name": "Pip", "delta": 1, "summary": "Friendly."}'
        "]"
    )
    updates = parse_and_validate_affinity_updates(raw, candidates=candidates)
    assert [u["agent_id"] for u in updates] == [
        "__area__",
        "agent_mara_01",
        "agent_pip_01",
    ]
    assert updates[2]["delta"] == 1


def test_extract_still_rejects_garbage():
    with pytest.raises(Exception):
        _extract_json_array("not json at all")


def test_extract_repairs_missing_brackets_when_ending_with_brace():
    raw = (
        '{"agent_id": "a", "name": "A", "delta": 0, "summary": "x"},'
        '{"agent_id": "b", "name": "B", "delta": 1, "summary": "y"}'
    )
    rows = _extract_json_array(raw)
    assert len(rows) == 2
    assert rows[1]["delta"] == 1


def test_extract_repairs_trailing_brace_instead_of_bracket():
    raw = (
        '[{"agent_id": "a", "name": "A", "delta": 0, "summary": "x"},'
        '{"agent_id": "b", "name": "B", "delta": 1, "summary": "y"}'
        "}"
    )
    rows = _extract_json_array(raw)
    assert len(rows) == 2


def test_extract_repairs_curly_wrapper_around_objects():
    raw = (
        '{{"agent_id": "a", "name": "A", "delta": 0, "summary": "x"},'
        '{"agent_id": "b", "name": "B", "delta": 1, "summary": "y"}}'
    )
    rows = _extract_json_array(raw)
    assert len(rows) == 2
    assert rows[0]["agent_id"] == "a"
    assert rows[1]["delta"] == 1
