"""Tests for rolling_summary memory module."""

import threading

import pytest
from campaign_rpg_engine.area import create_initial_area
from campaign_rpg_engine.area_edit import create_agent_from_args
from campaign_rpg_engine.memory import Memory
from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
)
from campaign_rpg_engine.memory_modules.recent_turns import DEFAULT_WINDOW
from campaign_rpg_engine.memory_modules.registry import create_module, format_memory_module_label
from campaign_rpg_engine.memory_modules.rolling_summary import (
    DEFAULT_MAX_SUMMARY_CHARS,
    DEFAULT_SUMMARY_INTERVAL,
    DEFAULT_SUMMARY_TAIL,
    MemoryConsolidationError,
    RollingSummaryModule,
    validate_max_summary_chars,
    validate_summary_interval,
    validate_summary_tail,
)
from campaign_rpg_engine.turn_record import TurnRecord, TurnStep


def _record_ctx(
    agent_id: str = "agent_01",
    turn_number: int = 1,
    agent_name: str = "Explorer",
) -> MemoryRecordContext:
    return MemoryRecordContext(
        agent_id=agent_id,
        turn_number=turn_number,
        agent_name=agent_name,
    )


def _observe_ctx(observer_id: str = "agent_01") -> MemoryObserveContext:
    return MemoryObserveContext(observer_id=observer_id)


def _render_ctx():
    area = create_initial_area()
    return MemoryRenderContext(agent=area.get_agent(), area=area)


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


def _fake_summary_generator(**kwargs):
    prior = kwargs["previous_summary"]
    batch = kwargs["batch_text"]
    if prior:
        return f"Merged summary. Batch had {batch.count('Turn ')} turns."
    return f"First summary. Batch had {batch.count('Turn ')} turns."


def test_default_summary_interval_matches_recent_turns_window():
    assert DEFAULT_SUMMARY_INTERVAL == DEFAULT_WINDOW


def _module(**kwargs) -> RollingSummaryModule:
    kwargs.setdefault("summary_tail", 0)
    return RollingSummaryModule(background_consolidation=False, **kwargs)


def _async_module(**kwargs) -> RollingSummaryModule:
    kwargs.setdefault("summary_tail", 0)
    return RollingSummaryModule(background_consolidation=True, **kwargs)


def _blocking_summary_generator(start: threading.Event, release: threading.Event, result: str):
    def _generator(**kwargs):
        start.set()
        assert release.wait(timeout=2.0)
        return result

    return _generator


def _fill_turns(module: RollingSummaryModule, count: int) -> None:
    for i in range(1, count + 1):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i))


def test_no_summary_before_interval_complete():
    module = _module(_summary_generator=_fake_summary_generator)
    for i in range(1, DEFAULT_SUMMARY_INTERVAL):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i))

    assert module.summary == ""
    assert len(module.stored_turns) == DEFAULT_SUMMARY_INTERVAL - 1
    text = module.render(_render_ctx())
    assert "Summary:" not in text
    assert "Turn 9:" in text


def test_summary_runs_on_interval_and_clears_detail_buffer():
    module = _module(_summary_generator=_fake_summary_generator)
    for i in range(1, DEFAULT_SUMMARY_INTERVAL + 1):
        module.record_turn(_speak_turn(i, content=f"t{i}"), _record_ctx(turn_number=i))

    assert module.summary == f"First summary. Batch had {DEFAULT_SUMMARY_INTERVAL} turns."
    assert module.stored_turns == []
    text = module.render(_render_ctx())
    assert "Summary:" in text
    assert "First summary" in text
    assert "Turn 1:" not in text


def test_second_summary_merges_previous():
    module = _module(
        summary_interval=5,
        _summary_generator=_fake_summary_generator,
    )
    for i in range(1, 11):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i))

    assert module.summary == "Merged summary. Batch had 5 turns."
    assert len(module.stored_turns) == 0

    module.record_turn(_speak_turn(11), _record_ctx(turn_number=11))
    text = module.render(_render_ctx())
    assert "Merged summary" in text
    assert "Turn 11:" in text


def test_render_keeps_recent_detail_after_summary():
    module = _module(
        summary_interval=3,
        _summary_generator=_fake_summary_generator,
    )
    for i in range(1, 5):
        module.record_turn(_speak_turn(i, content=f"t{i}"), _record_ctx(turn_number=i))

    text = module.render(_render_ctx())
    assert "Summary:" in text
    assert "Turn 3:" not in text
    assert "Turn 4:" in text


def test_validate_summary_interval_and_max():
    with pytest.raises(ValueError, match="memory-summary-interval"):
        validate_summary_interval(1)
    with pytest.raises(ValueError, match="memory-summary-max"):
        validate_max_summary_chars(100)
    with pytest.raises(ValueError, match="memory-summary-max"):
        validate_max_summary_chars(9000)
    with pytest.raises(ValueError, match="memory-summary-tail"):
        validate_summary_tail(-1)


def test_create_module_rolling_summary():
    module = create_module(
        "rolling_summary",
        summary_interval=12,
        max_summary_chars=6000,
    )
    assert isinstance(module, RollingSummaryModule)
    assert module.summary_interval == 12
    assert module.max_summary_chars == 6000


def test_create_module_rejects_summary_config_for_recent_turns():
    with pytest.raises(ValueError, match="memory-summary-interval"):
        create_module("recent_turns", summary_interval=10)


def test_create_agent_rolling_summary():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Archivist" personality "x" memory rolling_summary at 2,2',
    )
    assert agent is not None
    assert agent.memory.module_id == "rolling_summary"
    assert agent.memory.module.summary_interval == DEFAULT_SUMMARY_INTERVAL
    assert agent.memory.module.max_summary_chars == DEFAULT_MAX_SUMMARY_CHARS
    assert "interval=10" in msg


def test_create_agent_custom_summary_interval():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Archivist" personality "x" memory rolling_summary '
        "memory-summary-interval 15 memory-summary-max 5000 at 2,2",
    )
    assert agent is not None
    assert agent.memory.module.summary_interval == 15
    assert agent.memory.module.max_summary_chars == 5000


def test_memory_facade_label():
    memory = Memory(module_id="rolling_summary")
    label = format_memory_module_label(memory.module)
    assert label == (
        f"memory=rolling_summary interval={DEFAULT_SUMMARY_INTERVAL} "
        f"max={DEFAULT_MAX_SUMMARY_CHARS} tail={DEFAULT_SUMMARY_TAIL}"
    )


def test_default_max_summary_chars_and_tail():
    module = RollingSummaryModule()
    assert module.max_summary_chars == 8000
    assert module.summary_tail == DEFAULT_SUMMARY_TAIL


def test_witnesses_included_in_summary_batch(monkeypatch):
    calls: list[str] = []

    def capture(**kwargs):
        calls.append(kwargs["batch_text"])
        return "Summary with witnesses."

    module = _module(summary_interval=2, _summary_generator=capture)
    module.record_turn(_speak_turn(1), _record_ctx(turn_number=1))
    module.record_observation(
        _witness("Goblin waves."),
        _observe_ctx(),
    )
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))

    assert "Goblin waves." in calls[0]
    assert module.summary == "Summary with witnesses."


def test_generate_rolling_summary_uses_plain_text_completion(monkeypatch):
    from campaign_rpg_engine.llm.memory_summary import generate_rolling_summary
    from campaign_rpg_engine.llm.types import LLMResponse

    captured: dict[str, str] = {}
    log_calls: list[dict] = []

    def fake_completion(prompt, **kwargs):
        captured["prompt"] = prompt
        return LLMResponse(parsed="You explored the room and spoke with Goblin.")

    def fake_log_turn(turn_number, **kwargs):
        log_calls.append({"turn_number": turn_number, **kwargs})

    monkeypatch.setattr(
        "campaign_rpg_engine.llm.memory_summary.get_text_completion", fake_completion
    )
    monkeypatch.setattr("campaign_rpg_engine.llm.memory_summary.log_turn", fake_log_turn)

    summary = generate_rolling_summary(
        agent_name="Explorer",
        previous_summary="",
        batch_text='Turn 1:\nResult: You said: "Hi."',
        max_chars=8000,
        turn_number=10,
    )
    assert summary == "You explored the room and spoke with Goblin."
    assert "no json" in captured["prompt"].lower()
    assert len(log_calls) == 1
    assert log_calls[0]["turn_number"] == 10
    assert log_calls[0]["phase"] == "memory_summary"


def test_create_module_defaults_to_background_consolidation():
    module = create_module("rolling_summary")
    assert module.background_consolidation is True


def test_background_consolidation_stays_running_until_complete():
    started = threading.Event()
    release = threading.Event()
    module = _async_module(
        summary_interval=2,
        _summary_generator=_blocking_summary_generator(started, release, "Async summary"),
    )

    module.record_turn(_speak_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))

    assert started.wait(timeout=2.0)
    assert module.consolidation_state == "running"
    assert module.summary == ""
    assert len(module.stored_turns) == 2

    release.set()
    module.ensure_ready_for_turn()

    assert module.consolidation_state == "idle"
    assert module.summary == "Async summary"
    assert module.stored_turns == []


def test_ensure_ready_waits_for_background_job():
    started = threading.Event()
    release = threading.Event()
    module = _async_module(
        summary_interval=2,
        _summary_generator=_blocking_summary_generator(started, release, "Waited summary"),
    )
    _fill_turns(module, 2)
    assert started.wait(timeout=2.0)

    waiter = threading.Thread(target=module.ensure_ready_for_turn, daemon=True)
    waiter.start()
    assert waiter.is_alive()

    release.set()
    waiter.join(timeout=2.0)
    assert not waiter.is_alive()
    assert module.consolidation_state == "idle"


def test_failed_background_retries_sync_on_next_turn():
    attempts = {"count": 0}

    def flaky(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("background fail")
        return "Recovered summary"

    module = _async_module(summary_interval=2, _summary_generator=flaky)
    _fill_turns(module, 2)

    module._wait_for_background_consolidation()
    assert module.consolidation_state == "failed"
    assert module.summary == ""
    assert len(module.stored_turns) == 2

    module.ensure_ready_for_turn()

    assert module.consolidation_state == "idle"
    assert module.summary == "Recovered summary"
    assert module.stored_turns == []
    assert attempts["count"] == 2


def test_failed_retry_raises_when_still_failing():
    def always_fail(**kwargs):
        raise RuntimeError("still failing")

    module = _module(summary_interval=2, _summary_generator=always_fail)
    _fill_turns(module, 2)

    assert module.consolidation_state == "failed"
    assert module.summary == ""
    assert len(module.stored_turns) == 2

    with pytest.raises(MemoryConsolidationError, match="Check the log") as raised:
        module.ensure_ready_for_turn()
    assert module.consolidation_state == "failed"
    assert raised.value.concurrency_limit_exceeded is False
    assert raised.value.error_code is None


def test_failed_retry_marks_concurrency_limit():
    def always_fail(**kwargs):
        raise RuntimeError(
            "Error code: 429 - Concurrency limit exceeded. Your plan limit: 4 units"
        )

    module = _module(summary_interval=2, _summary_generator=always_fail)
    _fill_turns(module, 2)
    assert module.consolidation_state == "failed"

    with pytest.raises(MemoryConsolidationError) as raised:
        module.ensure_ready_for_turn()
    assert raised.value.concurrency_limit_exceeded is True
    assert raised.value.error_code == "concurrency_limit_exceeded"
    assert "concurrency" in str(raised.value).lower()


def test_flush_for_save_does_not_raise_on_failed_consolidation():
    def always_fail(**kwargs):
        raise RuntimeError("still failing")

    module = _module(summary_interval=2, _summary_generator=always_fail)
    _fill_turns(module, 2)
    assert module.consolidation_state == "failed"
    module.flush_for_save()
    assert module.consolidation_state == "failed"


def test_memory_consolidation_error_includes_agent_context():
    err = MemoryConsolidationError(agent_name="Explorer", turn_number=10)
    assert "Explorer" in str(err)
    assert "turn 10" in str(err)
    assert "Check the log" in str(err)


def test_pending_witnesses_excluded_from_snapshot_but_shown_in_render():
    started = threading.Event()
    release = threading.Event()
    batch_texts: list[str] = []

    def capture_and_block(**kwargs):
        batch_texts.append(kwargs["batch_text"])
        started.set()
        assert release.wait(timeout=2.0)
        return "Summary done"

    module = _async_module(summary_interval=2, _summary_generator=capture_and_block)
    module.record_turn(_speak_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))

    assert started.wait(timeout=2.0)
    module.record_observation(_witness("Goblin waves after turn 2."), _observe_ctx())

    assert len(batch_texts) == 1
    assert "Goblin waves after turn 2." not in batch_texts[0]

    release.set()
    module.ensure_ready_for_turn()

    text = module.render(_render_ctx())
    assert "Summary done" in text
    assert "You observed:" in text
    assert "Goblin waves after turn 2." in text
    assert "Turn 1:" not in text


def test_pending_witnesses_preserved_after_successful_consolidation():
    module = _module(summary_interval=2, _summary_generator=_fake_summary_generator)
    module.record_turn(_speak_turn(1), _record_ctx(turn_number=1))
    module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))
    module.record_observation(_witness("Goblin speaks between turns."), _observe_ctx())

    text = module.render(_render_ctx())
    assert "First summary" in text
    assert "Goblin speaks between turns." in text
    assert "Turn 1:" not in text
    assert "Turn 2:" not in text


def test_memory_facade_ensure_ready_waits_for_background():
    started = threading.Event()
    release = threading.Event()
    memory = Memory(
        module=_async_module(
            summary_interval=2,
            _summary_generator=_blocking_summary_generator(started, release, "Facade summary"),
        )
    )
    memory.record_turn(_speak_turn(1), agent_id="agent_01", agent_name="Explorer")
    memory.record_turn(_speak_turn(2), agent_id="agent_01", agent_name="Explorer")

    assert started.wait(timeout=2.0)
    release.set()
    memory.ensure_ready_for_turn()

    assert memory.module.consolidation_state == "idle"
    assert memory.module.summary == "Facade summary"


def test_summary_keeps_detail_tail_after_consolidation():
    module = _module(
        summary_interval=10,
        summary_tail=3,
        _summary_generator=_fake_summary_generator,
    )
    for i in range(1, 11):
        module.record_turn(_speak_turn(i, content=f"t{i}"), _record_ctx(turn_number=i))

    assert module.summary == "First summary. Batch had 10 turns."
    assert [t.turn_number for t in module.stored_turns] == [8, 9, 10]
    text = module.render(_render_ctx())
    assert "First summary" in text
    assert "Turn 8:" in text
    assert "Turn 10:" in text
    assert "Turn 7:" not in text


def test_second_summary_excludes_tail_from_merge_batch():
    batch_sizes: list[int] = []

    def count_batch(**kwargs):
        batch_sizes.append(kwargs["batch_text"].count("Turn "))
        prior = kwargs["previous_summary"]
        if prior:
            return f"Merged summary. Batch had {batch_sizes[-1]} turns."
        return f"First summary. Batch had {batch_sizes[-1]} turns."

    module = _module(
        summary_interval=5,
        summary_tail=3,
        _summary_generator=count_batch,
    )
    for i in range(1, 11):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i))

    assert batch_sizes == [5, 5]
    assert module.summary == "Merged summary. Batch had 5 turns."
    assert [t.turn_number for t in module.stored_turns] == [8, 9, 10]


def test_detail_tail_accumulates_new_turns_until_next_summary():
    module = _module(
        summary_interval=5,
        summary_tail=2,
        _summary_generator=_fake_summary_generator,
    )
    for i in range(1, 6):
        module.record_turn(_speak_turn(i), _record_ctx(turn_number=i))

    assert [t.turn_number for t in module.stored_turns] == [4, 5]

    module.record_turn(_speak_turn(6), _record_ctx(turn_number=6))
    module.record_turn(_speak_turn(7), _record_ctx(turn_number=7))

    assert [t.turn_number for t in module.stored_turns] == [4, 5, 6, 7]


def test_create_agent_custom_summary_tail():
    area = create_initial_area()
    agent, msg = create_agent_from_args(
        area,
        'name "Archivist" personality "x" memory rolling_summary memory-summary-tail 1 at 2,2',
    )
    assert agent is not None
    assert agent.memory.module.summary_tail == 1


def _witness(text: str):
    from campaign_rpg_engine.memory_modules.base import WitnessedEvent

    return WitnessedEvent(
        session_turn=1,
        actor_id="agent_goblin_01",
        actor_name="Goblin",
        text=text,
        actor_position=(0, 3),
    )


def test_concurrent_disabled_forces_sync_consolidation_even_if_background_true():
    from campaign_rpg_engine.llm.client import set_concurrent_llm_calls

    started = threading.Event()
    release = threading.Event()
    set_concurrent_llm_calls(False)
    try:
        module = RollingSummaryModule(
            summary_interval=2,
            background_consolidation=True,
            _summary_generator=_blocking_summary_generator(
                started, release, "Forced sync summary"
            ),
        )
        module.record_turn(_speak_turn(1), _record_ctx(turn_number=1))
        # Without concurrent calls, consolidation must finish inside record_turn.
        # Release the blocker from another thread if the sync path waits on it.
        def _release_soon():
            assert started.wait(timeout=2.0)
            release.set()

        helper = threading.Thread(target=_release_soon, daemon=True)
        helper.start()
        module.record_turn(_speak_turn(2), _record_ctx(turn_number=2))
        helper.join(timeout=2.0)
        assert module.consolidation_state == "idle"
        assert module.summary == "Forced sync summary"
    finally:
        set_concurrent_llm_calls(True)
