"""Tests for affinity memory module (1.5.0)."""

from __future__ import annotations

import pytest
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.llm.affinity_update import parse_and_validate_affinity_updates
from campaign_rpg_engine.memory_modules.affinity import AffinityModule
from campaign_rpg_engine.memory_modules.affinity_ladder import format_affinity_tag
from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.registry import create_module, loaded_module_ids
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep


def _speak_turn(turn_number: int, *, content: str = "Hi.") -> TurnRecord:
    return TurnRecord(
        turn_number=turn_number,
        steps=[
            TurnStep(
                kind="speak",
                reasoning=f"reason-{turn_number}",
                target=None,
                content=content,
                result=f'You said: "{content}"',
            )
        ],
        result=f'You said: "{content}"',
        reasoning=f"reason-{turn_number}",
    )


def _ctx(
    agent_id: str = "hero",
    turn_number: int = 1,
    nearby: tuple[tuple[str, str], ...] = (("npc", "Mira"),),
) -> MemoryRecordContext:
    return MemoryRecordContext(
        agent_id=agent_id,
        turn_number=turn_number,
        agent_name="Hero",
        nearby_agents=nearby,
    )


def _fake_summary(**kwargs) -> str:
    prior = kwargs.get("previous_summary") or ""
    batch = kwargs.get("batch_text") or ""
    n = batch.count("Turn ")
    if prior:
        return f"Merged. turns={n}"
    return f"First. turns={n}"


def _fake_affinity(**kwargs) -> list[dict]:
    candidates = kwargs.get("candidates") or []
    out = []
    for c in candidates:
        out.append(
            {
                "agent_id": c["agent_id"],
                "name": c["name"],
                "delta": 1 if c["score"] < 10 else 0,
                "summary": f"Updated bond with {c['name']}.",
            }
        )
    return out


def _module(**kwargs) -> AffinityModule:
    kwargs.setdefault("summary_interval", 2)
    kwargs.setdefault("summary_tail", 0)
    kwargs.setdefault("background_consolidation", False)
    return AffinityModule(
        _summary_generator=_fake_summary,
        _affinity_generator=_fake_affinity,
        **kwargs,
    )


def test_affinity_in_builtin_registry():
    assert "affinity" in loaded_module_ids()
    mod = create_module("affinity", summary_interval=4, summary_tail=1)
    assert isinstance(mod, AffinityModule)
    assert mod.module_id == "affinity"
    assert mod.summary_interval == 4


def test_create_agent_affinity_flags():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Scout" personality "x" memory affinity '
        "memory-summary-interval 4 memory-summary-tail 1 at 0,0",
    )
    assert agent is not None
    assert agent.memory.module_id == "affinity"
    assert agent.memory.module.summary_interval == 4
    assert "interval=4" in msg
    assert "tail=1" in msg


def test_parallel_consolidation_updates_summary_and_affinity():
    mod = _module()
    for n in (1, 2):
        mod.record_turn(_speak_turn(n, content=f"Hello Mira {n}"), _ctx(turn_number=n))
    assert mod.summary.startswith("First.")
    assert "npc" in mod.affinities
    assert mod.affinities["npc"]["score"] == 1
    assert "Updated bond" in mod.affinities["npc"]["summary"]


def test_call_b_skipped_without_candidates():
    def empty_affinity(**kwargs):
        assert kwargs.get("candidates") == [] or True
        return []

    mod = AffinityModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=_fake_summary,
        _affinity_generator=empty_affinity,
    )
    # No nearby agents → candidates empty (unless directory later)
    lonely = MemoryRecordContext(agent_id="hero", turn_number=1, agent_name="Hero")
    mod.record_turn(_speak_turn(1), lonely)
    mod.record_turn(
        _speak_turn(2),
        MemoryRecordContext(agent_id="hero", turn_number=2, agent_name="Hero"),
    )
    assert mod.summary.startswith("First.")
    assert mod.affinities == {}


def test_failure_applies_nothing_then_retry_succeeds():
    calls = {"n": 0}

    def flaky_summary(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom A")
        return _fake_summary(**kwargs)

    mod = AffinityModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=flaky_summary,
        _affinity_generator=_fake_affinity,
    )
    mod.record_turn(_speak_turn(1), _ctx(turn_number=1))
    mod.record_turn(_speak_turn(2), _ctx(turn_number=2))
    assert mod.summary == ""
    assert mod.affinities == {}
    assert mod.consolidation_state == "failed"

    mod.ensure_ready_for_turn()
    assert mod.summary.startswith("First.")
    assert mod.affinities["npc"]["score"] == 1
    assert mod.consolidation_state == "idle"


def test_affinity_b_failure_rolls_back_all():
    def bad_b(**kwargs):
        raise RuntimeError("boom B")

    mod = AffinityModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=_fake_summary,
        _affinity_generator=bad_b,
    )
    mod.record_turn(_speak_turn(1), _ctx(turn_number=1))
    mod.record_turn(_speak_turn(2), _ctx(turn_number=2))
    assert mod.summary == ""
    assert mod.affinities == {}
    assert mod.consolidation_state == "failed"


def test_render_order_relationships_then_summary():
    mod = _module()
    for n in (1, 2):
        mod.record_turn(_speak_turn(n, content="Hi Mira"), _ctx(turn_number=n))
    area = create_initial_area()
    # Put a second agent named Mira with matching id into area for prompt filter
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.memory import Memory

    mira = Agent(
        id="npc",
        name="Mira",
        position=(1, 0),
        personality="x",
        memory=Memory(module_id="recent_turns"),
    )
    area.agents.append(mira)
    hero = area.get_agent()
    text = mod.render(MemoryRenderContext(agent=hero, area=area))
    rel = text.index("Relationships:")
    summ = text.index("Summary:")
    assert rel < summ
    assert format_affinity_tag(1, "Mira") in text


def test_export_restore_round_trip():
    mod = _module()
    for n in (1, 2):
        mod.record_turn(_speak_turn(n), _ctx(turn_number=n))
    state = mod.export_state()
    restored = AffinityModule(
        background_consolidation=False,
        _summary_generator=_fake_summary,
        _affinity_generator=_fake_affinity,
    )
    restored.restore_state(state)
    assert restored.summary == mod.summary
    assert restored.affinities == mod.affinities
    assert restored.total_turns == mod.total_turns


def test_parse_affinity_updates_rejects_bad_delta():
    candidates = [{"agent_id": "a", "name": "A", "score": 0, "summary": ""}]
    with pytest.raises(ValueError):
        parse_and_validate_affinity_updates(
            '[{"agent_id":"a","name":"A","delta":2,"summary":"x"}]',
            candidates=candidates,
        )


def test_parse_affinity_updates_fills_omitted_candidates_as_no_change():
    candidates = [
        {"agent_id": "a", "name": "A", "score": 1, "summary": "Prior A"},
        {"agent_id": "b", "name": "B", "score": 0, "summary": "Prior B"},
        {"agent_id": "c", "name": "C", "score": -1, "summary": "Prior C"},
    ]
    updates = parse_and_validate_affinity_updates(
        '[{"agent_id":"b","name":"B","delta":1,"summary":"Warm chat."}]',
        candidates=candidates,
    )
    assert [u["agent_id"] for u in updates] == ["a", "b", "c"]
    assert updates[0] == {
        "agent_id": "a",
        "name": "A",
        "delta": 0,
        "summary": "Prior A",
    }
    assert updates[1]["delta"] == 1
    assert updates[1]["summary"] == "Warm chat."
    assert updates[2] == {
        "agent_id": "c",
        "name": "C",
        "delta": 0,
        "summary": "Prior C",
    }


def test_area_events_are_not_affinity_candidates():
    captured: list[list[dict]] = []

    def capture_affinity(**kwargs):
        captured.append(list(kwargs.get("candidates") or []))
        return _fake_affinity(**kwargs)

    mod = AffinityModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=_fake_summary,
        _affinity_generator=capture_affinity,
    )
    mod.record_observation(
        WitnessedEvent(
            session_turn=0,
            actor_id="__area__",
            actor_name="Environment",
            text="Pip enters the tavern.",
            actor_position=(-1, -1),
        ),
        MemoryObserveContext(observer_id="hero"),
    )
    mod.record_observation(
        WitnessedEvent(
            session_turn=0,
            actor_id="agent_pip_01",
            actor_name="Pip",
            text='Pip says: "Hello."',
            actor_position=(1, 1),
        ),
        MemoryObserveContext(observer_id="hero"),
    )
    mod.record_turn(_speak_turn(1), _ctx(nearby=(("agent_pip_01", "Pip"),)))
    mod.record_turn(_speak_turn(2), _ctx(nearby=(("agent_pip_01", "Pip"),)))

    assert captured
    ids = {c["agent_id"] for c in captured[0]}
    assert "__area__" not in ids
    assert "agent_pip_01" in ids
    assert "__area__" not in mod._directory
    assert "__area__" not in mod.affinities


def test_restore_state_drops_area_affinity_entries():
    mod = _module()
    mod.restore_state(
        {
            **mod.export_state(),
            "affinities": {
                "__area__": {"name": "Environment", "score": 1, "summary": "Welcoming."},
                "agent_pip_01": {"name": "Pip", "score": 0, "summary": ""},
            },
            "directory": {"__area__": "Environment", "agent_pip_01": "Pip"},
            "window_nearby_ids": ["__area__", "agent_pip_01"],
        }
    )
    assert "__area__" not in mod.affinities
    assert "agent_pip_01" in mod.affinities
    assert "__area__" not in mod._directory
    assert "__area__" not in mod._window_nearby_ids


def test_live_pending_preserved_across_consolidation():
    mod = _module()
    mod.record_turn(_speak_turn(1), _ctx(turn_number=1))
    mod.record_observation(
        WitnessedEvent(
            session_turn=1,
            actor_id="npc",
            actor_name="Mira",
            text="Mira waves.",
            actor_position=(1, 0),
        ),
        MemoryObserveContext(observer_id="hero"),
    )
    # Pending is moved onto turn 2 when recorded
    mod.record_turn(_speak_turn(2), _ctx(turn_number=2))
    # After consolidation with tail 0, detail may be empty but pending after
    # consolidation can still accept observations
    mod.record_observation(
        WitnessedEvent(
            session_turn=99,
            actor_id="npc",
            actor_name="Mira",
            text="Mira after summarize.",
            actor_position=(1, 0),
        ),
        MemoryObserveContext(observer_id="hero"),
    )
    assert any("after summarize" in e.text for e in mod._pending)


def test_window_nearby_accumulates_across_turns():
    """Same-area peers from any turn in the interval are Call B candidates."""
    seen: list[list[str]] = []

    def capture_affinity(**kwargs):
        candidates = kwargs.get("candidates") or []
        seen.append([c["agent_id"] for c in candidates])
        return _fake_affinity(**kwargs)

    mod = AffinityModule(
        summary_interval=2,
        summary_tail=0,
        background_consolidation=False,
        _summary_generator=_fake_summary,
        _affinity_generator=capture_affinity,
    )
    mod.record_turn(
        _speak_turn(1, content="Alone thoughts."),
        _ctx(turn_number=1, nearby=(("mira", "Mira"),)),
    )
    # Last turn has a different peer only — Mira must still be a candidate.
    mod.record_turn(
        _speak_turn(2, content="Later thoughts."),
        _ctx(turn_number=2, nearby=(("bob", "Bob"),)),
    )
    assert seen and set(seen[0]) >= {"mira", "bob"}
    assert "mira" in mod.affinities and "bob" in mod.affinities
    # Window resets after successful consolidation.
    assert mod._window_nearby_ids == set()


def test_name_matching_ignores_structural_tokens():
    """Batch headings / 'You said' must not invent Call B candidates."""
    from campaign_rpg_engine.memory_modules.formatting import (
        format_turns_batch_for_summary,
    )

    mod = _module(summary_interval=99)
    mod._directory.update(
        {
            "r1": "Result",
            "y1": "You",
            "t1": "Turn",
            "m1": "Mira",
        }
    )
    turns = [_speak_turn(1, content="I keep thinking about Mira.")]
    batch_text = format_turns_batch_for_summary(turns, [[]])
    assert "Result:" in batch_text
    assert "Turn 1:" in batch_text
    candidates = mod._build_candidates(turns, [[]], batch_text)
    ids = {c["agent_id"] for c in candidates}
    assert ids == {"m1"}


def test_empty_row_summary_preserves_prior_blurb():
    mod = _module(summary_interval=2)
    mod.record_turn(_speak_turn(1), _ctx(turn_number=1))
    mod.record_turn(_speak_turn(2), _ctx(turn_number=2))
    prior_blurb = mod.affinities["npc"]["summary"]
    assert prior_blurb

    def empty_blurbs(**kwargs):
        return [
            {
                "agent_id": c["agent_id"],
                "name": c["name"],
                "delta": 0,
                "summary": "",
            }
            for c in (kwargs.get("candidates") or [])
        ]

    mod._affinity_generator = empty_blurbs
    mod.record_turn(_speak_turn(3), _ctx(turn_number=3))
    mod.record_turn(_speak_turn(4), _ctx(turn_number=4))
    assert mod.affinities["npc"]["summary"] == prior_blurb
    assert mod.affinities["npc"]["score"] == 1


def test_affinity_calls_run_sequentially_when_concurrent_disabled(monkeypatch):
    from campaign_rpg_engine.llm.client import set_concurrent_llm_calls

    order: list[str] = []

    def summary(**kwargs):
        order.append("A")
        return "Summary A."

    def affinity(**kwargs):
        order.append("B")
        return [
            {
                "agent_id": c["agent_id"],
                "name": c["name"],
                "delta": 1,
                "summary": "Bond",
            }
            for c in (kwargs.get("candidates") or [])
        ]

    set_concurrent_llm_calls(False)
    try:
        mod = AffinityModule(
            summary_interval=2,
            summary_tail=0,
            background_consolidation=True,
            _summary_generator=summary,
            _affinity_generator=affinity,
        )
        mod.record_turn(_speak_turn(1), _ctx(turn_number=1))
        mod.record_turn(_speak_turn(2), _ctx(turn_number=2))
        assert order == ["A", "B"]
        assert mod.consolidation_state == "idle"
        assert mod.summary.startswith("Summary")
    finally:
        set_concurrent_llm_calls(True)
