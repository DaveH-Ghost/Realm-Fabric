"""Rolling-summary memory — recent turns plus periodic LLM consolidation."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Callable, Literal

from src.llm.memory_summary import generate_rolling_summary, log_consolidation_error
from src.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from src.memory_modules.formatting import (
    format_stored_turns_block,
    format_turns_batch_for_summary,
    join_lines,
)
from src.memory_modules.recent_turns import DEFAULT_WINDOW
from src.turn_record import TurnRecord

DEFAULT_SUMMARY_INTERVAL = DEFAULT_WINDOW
DEFAULT_MAX_SUMMARY_CHARS = 8000
DEFAULT_SUMMARY_TAIL = 3
MIN_SUMMARY_INTERVAL = 2
MIN_MAX_SUMMARY_CHARS = 500
MAX_MAX_SUMMARY_CHARS = DEFAULT_MAX_SUMMARY_CHARS
MIN_SUMMARY_TAIL = 0

ConsolidationState = Literal["idle", "running", "failed"]


class MemoryConsolidationError(RuntimeError):
    """Raised when an agent cannot act until rolling summary consolidation succeeds."""

    def __init__(
        self,
        *,
        agent_name: str = "",
        turn_number: int | None = None,
    ) -> None:
        subject = f"Agent {agent_name!r}" if agent_name else "Agent"
        if turn_number is not None:
            subject = f"{subject} (turn {turn_number})"
        super().__init__(
            f"{subject} cannot act until memory summary consolidation succeeds. "
            "Check the log for consolidation errors (API, network, or LLM response). "
            "Fix the issue and try again."
        )
        self.agent_name = agent_name
        self.turn_number = turn_number


def validate_summary_interval(value: int) -> None:
    if value < MIN_SUMMARY_INTERVAL:
        raise ValueError(
            f"memory-summary-interval must be at least {MIN_SUMMARY_INTERVAL} "
            f"(got {value})."
        )


def validate_max_summary_chars(value: int) -> None:
    if value < MIN_MAX_SUMMARY_CHARS or value > MAX_MAX_SUMMARY_CHARS:
        raise ValueError(
            f"memory-summary-max must be between {MIN_MAX_SUMMARY_CHARS} and "
            f"{MAX_MAX_SUMMARY_CHARS} (got {value})."
        )


def validate_summary_tail(value: int) -> None:
    if value < MIN_SUMMARY_TAIL:
        raise ValueError(
            f"memory-summary-tail must be at least {MIN_SUMMARY_TAIL} (got {value})."
        )


SummaryGenerator = Callable[..., str]


@dataclass
class _ConsolidationSnapshot:
    turns: list[TurnRecord]
    witnessed_before: list[list[WitnessedEvent]]
    agent_name: str
    turn_number: int
    previous_summary: str


@dataclass
class RollingSummaryModule:
    """
    Like ``recent_turns`` for detail, but every ``summary_interval`` own turns
    consolidate into a rolling summary.

    After a successful interval turn, consolidation runs in the background.
    The agent cannot take another turn until consolidation succeeds; failed
    runs retry synchronously at the start of the next turn attempt using a
    snapshot of the interval batch (``_pending`` witnesses are excluded).

    After consolidation, the last ``summary_tail`` turns from the summarized
    batch stay in the detail buffer until the next summary. They are shown in
    the prompt but excluded from the next merge batch.
    """

    module_id: str = "rolling_summary"
    summary_interval: int = DEFAULT_SUMMARY_INTERVAL
    max_summary_chars: int = DEFAULT_MAX_SUMMARY_CHARS
    summary_tail: int = DEFAULT_SUMMARY_TAIL
    background_consolidation: bool = True
    _summary_generator: SummaryGenerator = field(
        default=generate_rolling_summary, repr=False
    )

    _summary: str = field(default="", repr=False)
    _turns: list[TurnRecord] = field(default_factory=list, repr=False)
    _witnessed_before: list[list[WitnessedEvent]] = field(default_factory=list, repr=False)
    _pending: list[WitnessedEvent] = field(default_factory=list, repr=False)
    _total_turns: int = field(default=0, repr=False)
    _last_summarized_turn_number: int = field(default=0, repr=False)

    _consolidation_state: ConsolidationState = field(default="idle", repr=False)
    _snapshot: _ConsolidationSnapshot | None = field(default=None, repr=False)
    _consolidation_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _consolidation_thread: threading.Thread | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        validate_summary_interval(self.summary_interval)
        validate_max_summary_chars(self.max_summary_chars)
        validate_summary_tail(self.summary_tail)

    @property
    def consolidation_state(self) -> ConsolidationState:
        return self._consolidation_state

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        self._witnessed_before.append(list(self._pending))
        self._pending.clear()
        self._turns.append(record)
        self._total_turns += 1

        if self._should_summarize():
            self._schedule_consolidation(ctx.agent_name or ctx.agent_id, record.turn_number)

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        del ctx
        self._pending.append(event)

    def ensure_ready_for_turn(self) -> None:
        """Block until consolidation is idle; sync-retry if the last run failed."""
        while True:
            with self._consolidation_lock:
                state = self._consolidation_state

            if state == "idle":
                return

            if state == "running":
                self._wait_for_background_consolidation()
                continue

            if state == "failed":
                self._retry_consolidation_sync()
                with self._consolidation_lock:
                    if self._consolidation_state == "idle":
                        return
                    snapshot = self._snapshot
                raise MemoryConsolidationError(
                    agent_name=snapshot.agent_name if snapshot else "",
                    turn_number=snapshot.turn_number if snapshot else None,
                )

    def render(self, ctx: MemoryRenderContext) -> str:
        del ctx
        detail = format_stored_turns_block(
            self._turns, self._witnessed_before, self._pending
        )
        if not self._summary and not detail:
            return ""

        lines: list[str] = []
        if self._summary:
            lines.append("Summary:")
            lines.append(self._summary)
            if detail:
                lines.append("")
        lines.extend(detail)
        return join_lines(lines)

    def _should_summarize(self) -> bool:
        return (
            self._total_turns >= self.summary_interval
            and self._total_turns % self.summary_interval == 0
        )

    def _schedule_consolidation(self, agent_name: str, turn_number: int) -> None:
        batch_turns, batch_witnessed = self._turns_for_summary_batch()
        snapshot = _ConsolidationSnapshot(
            turns=copy.deepcopy(batch_turns),
            witnessed_before=copy.deepcopy(batch_witnessed),
            agent_name=agent_name,
            turn_number=turn_number,
            previous_summary=self._summary,
        )
        with self._consolidation_lock:
            self._snapshot = snapshot
            self._consolidation_state = "running"

        if self.background_consolidation:
            thread = threading.Thread(
                target=self._consolidation_worker,
                args=(snapshot,),
                daemon=True,
                name=f"rolling-summary-{agent_name}-turn-{turn_number}",
            )
            self._consolidation_thread = thread
            thread.start()
            return

        self._consolidation_worker(snapshot)

    def _consolidation_worker(self, snapshot: _ConsolidationSnapshot) -> None:
        try:
            new_summary = self._run_summary_for_snapshot(snapshot)
        except Exception as exc:
            log_consolidation_error("Rolling summary consolidation failed", exc)
            with self._consolidation_lock:
                self._consolidation_state = "failed"
                self._consolidation_thread = None
            return

        with self._consolidation_lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                self._apply_successful_consolidation(new_summary, snapshot)
            self._consolidation_thread = None

    def _snapshot_matches(self, snapshot: _ConsolidationSnapshot) -> bool:
        if self._snapshot is None:
            return False
        return self._snapshot.turn_number == snapshot.turn_number

    def _wait_for_background_consolidation(self) -> None:
        thread = None
        with self._consolidation_lock:
            thread = self._consolidation_thread
        if thread is not None and thread.is_alive():
            thread.join()

    def _retry_consolidation_sync(self) -> None:
        with self._consolidation_lock:
            snapshot = self._snapshot
            if snapshot is None:
                self._consolidation_state = "idle"
                return

        try:
            new_summary = self._run_summary_for_snapshot(snapshot)
        except Exception as exc:
            log_consolidation_error("Rolling summary consolidation retry failed", exc)
            with self._consolidation_lock:
                self._consolidation_state = "failed"
            return

        with self._consolidation_lock:
            if self._snapshot is snapshot or self._snapshot_matches(snapshot):
                self._apply_successful_consolidation(new_summary, snapshot)

    def _turns_for_summary_batch(
        self,
    ) -> tuple[list[TurnRecord], list[list[WitnessedEvent]]]:
        """Own turns not yet covered by the rolling summary (excludes prior tail)."""
        turns: list[TurnRecord] = []
        witnessed: list[list[WitnessedEvent]] = []
        for turn, events in zip(self._turns, self._witnessed_before):
            if turn.turn_number > self._last_summarized_turn_number:
                turns.append(turn)
                witnessed.append(events)
        return turns, witnessed

    def _tail_turn_numbers_from_batch(self, batch_turns: list[TurnRecord]) -> set[int]:
        if self.summary_tail <= 0 or not batch_turns:
            return set()
        keep = min(self.summary_tail, len(batch_turns))
        return {turn.turn_number for turn in batch_turns[-keep:]}

    def _apply_successful_consolidation(
        self,
        new_summary: str,
        snapshot: _ConsolidationSnapshot,
    ) -> None:
        self._summary = new_summary
        self._last_summarized_turn_number = snapshot.turn_number

        tail_numbers = self._tail_turn_numbers_from_batch(snapshot.turns)
        if not tail_numbers:
            self._turns.clear()
            self._witnessed_before.clear()
        else:
            kept_turns: list[TurnRecord] = []
            kept_witnessed: list[list[WitnessedEvent]] = []
            for turn, events in zip(self._turns, self._witnessed_before):
                if turn.turn_number in tail_numbers:
                    kept_turns.append(turn)
                    kept_witnessed.append(events)
            self._turns = kept_turns
            self._witnessed_before = kept_witnessed

        self._snapshot = None
        self._consolidation_state = "idle"
        self._consolidation_thread = None

    def _run_summary_for_snapshot(self, snapshot: _ConsolidationSnapshot) -> str:
        batch_text = format_turns_batch_for_summary(
            snapshot.turns, snapshot.witnessed_before
        )
        return self._summary_generator(
            agent_name=snapshot.agent_name,
            previous_summary=snapshot.previous_summary,
            batch_text=batch_text,
            max_chars=self.max_summary_chars,
            turn_number=snapshot.turn_number,
        )

    @property
    def total_turns(self) -> int:
        return self._total_turns

    @property
    def last_summarized_turn_number(self) -> int:
        """Own turn number through which the rolling summary is current (0 if never)."""
        return self._last_summarized_turn_number

    @property
    def stored_turns(self) -> list[TurnRecord]:
        """
        Verbatim detail buffer: post-summary tail plus turns since last consolidation.

        Older own turns live in :attr:`summary` only, not here.
        """
        return list(self._turns)

    @property
    def summary(self) -> str:
        return self._summary
