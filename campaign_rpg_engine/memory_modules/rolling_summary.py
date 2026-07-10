"""Rolling-summary memory — recent turns plus periodic LLM consolidation."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from campaign_rpg_engine.llm.memory_summary import generate_rolling_summary
from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.consolidation_runner import (
    ConsolidationRunner,
    ConsolidationSnapshot,
    ConsolidationState,
    MemoryConsolidationError,
)
from campaign_rpg_engine.memory_modules.formatting import (
    format_stored_turns_block,
    format_turns_batch_for_summary,
    join_lines,
)
from campaign_rpg_engine.memory_modules.serialization import (
    deserialize_turn_list,
    deserialize_witness_list,
    deserialize_witnessed_before,
    serialize_turn_list,
    serialize_witness_list,
    serialize_witnessed_before,
)
from campaign_rpg_engine.memory_modules.recent_turns import DEFAULT_WINDOW
from campaign_rpg_engine.turn_record import TurnRecord

DEFAULT_SUMMARY_INTERVAL = DEFAULT_WINDOW
DEFAULT_MAX_SUMMARY_CHARS = 8000
DEFAULT_SUMMARY_TAIL = 3
MIN_SUMMARY_INTERVAL = 2
MIN_MAX_SUMMARY_CHARS = 500
MAX_MAX_SUMMARY_CHARS = DEFAULT_MAX_SUMMARY_CHARS
MIN_SUMMARY_TAIL = 0

__all__ = [
    "ConsolidationState",
    "DEFAULT_MAX_SUMMARY_CHARS",
    "DEFAULT_SUMMARY_INTERVAL",
    "DEFAULT_SUMMARY_TAIL",
    "MemoryConsolidationError",
    "RollingSummaryModule",
    "SummaryGenerator",
    "validate_max_summary_chars",
    "validate_summary_interval",
    "validate_summary_tail",
]

SummaryGenerator = Callable[..., str]


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
    _consolidation_runner: ConsolidationRunner = field(
        default_factory=ConsolidationRunner, repr=False
    )

    def __post_init__(self) -> None:
        validate_summary_interval(self.summary_interval)
        validate_max_summary_chars(self.max_summary_chars)
        validate_summary_tail(self.summary_tail)

    @property
    def consolidation_state(self) -> ConsolidationState:
        return self._consolidation_runner.state

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
        self._consolidation_runner.ensure_ready(
            run=self._run_summary_for_snapshot,
            on_success=self._apply_successful_consolidation,
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
        snapshot = ConsolidationSnapshot(
            turns=copy.deepcopy(batch_turns),
            witnessed_before=copy.deepcopy(batch_witnessed),
            agent_name=agent_name,
            turn_number=turn_number,
            previous_summary=self._summary,
        )
        self._consolidation_runner.start(
            snapshot,
            background=self.background_consolidation,
            run=self._run_summary_for_snapshot,
            on_success=self._apply_successful_consolidation,
            thread_name=f"rolling-summary-{agent_name}-turn-{turn_number}",
        )

    def _wait_for_background_consolidation(self) -> None:
        """Wait for an in-flight background job (tests / internal)."""
        self._consolidation_runner.wait_for_background()

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
        snapshot: ConsolidationSnapshot,
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

    def _run_summary_for_snapshot(self, snapshot: ConsolidationSnapshot) -> str:
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

    def export_state(self) -> dict:
        return {
            "summary_interval": self.summary_interval,
            "max_summary_chars": self.max_summary_chars,
            "summary_tail": self.summary_tail,
            "total_turns": self._total_turns,
            "summary": self._summary,
            "last_summarized_turn_number": self._last_summarized_turn_number,
            "turns": serialize_turn_list(self._turns),
            "witnessed_before": serialize_witnessed_before(self._witnessed_before),
            "pending": serialize_witness_list(self._pending),
        }

    def restore_state(self, data: dict) -> None:
        self.summary_interval = int(data["summary_interval"])
        self.max_summary_chars = int(data["max_summary_chars"])
        self.summary_tail = int(data["summary_tail"])
        validate_summary_interval(self.summary_interval)
        validate_max_summary_chars(self.max_summary_chars)
        validate_summary_tail(self.summary_tail)
        self._total_turns = int(data["total_turns"])
        self._summary = str(data.get("summary", ""))
        self._last_summarized_turn_number = int(
            data.get("last_summarized_turn_number", 0)
        )
        self._turns = deserialize_turn_list(data.get("turns", []))
        self._witnessed_before = deserialize_witnessed_before(
            data.get("witnessed_before", [])
        )
        self._pending = deserialize_witness_list(data.get("pending", []))
        self._consolidation_runner = ConsolidationRunner()
