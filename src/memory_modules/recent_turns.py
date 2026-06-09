"""Recent-turns memory module — last N own turns plus witnessed agent actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from src.memory_modules.formatting import (
    format_own_turn,
    format_witnessed_events,
    join_lines,
    should_include_reasoning,
)
from src.turn_record import TurnRecord


@dataclass
class RecentTurnsModule:
    """
    Keep the last ``window`` own turns and witnessed other-agent actions
    between those turns.
    """

    module_id: str = "recent_turns"
    window: int = 10

    _turns: list[TurnRecord] = field(default_factory=list, repr=False)
    _witnessed_before: list[list[WitnessedEvent]] = field(default_factory=list, repr=False)
    _pending: list[WitnessedEvent] = field(default_factory=list, repr=False)
    _total_turns: int = field(default=0, repr=False)

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        del ctx  # reserved for future module config
        self._witnessed_before.append(list(self._pending))
        self._pending.clear()
        self._turns.append(record)
        self._total_turns += 1
        while len(self._turns) > self.window:
            self._turns.pop(0)
            self._witnessed_before.pop(0)

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        del ctx
        self._pending.append(event)

    def render(self, ctx: MemoryRenderContext) -> str:
        del ctx
        if not self._turns and not self._pending:
            return ""

        lines: list[str] = []
        total = len(self._turns)
        for index, turn in enumerate(self._turns):
            witnessed = self._witnessed_before[index] if index < len(self._witnessed_before) else []
            if witnessed:
                lines.extend(
                    format_witnessed_events(
                        witnessed,
                        f"Before turn {turn.turn_number}, you observed:",
                    )
                )
                lines.append("")
            lines.extend(
                format_own_turn(
                    turn,
                    include_reasoning=should_include_reasoning(index, total),
                )
            )
            lines.append("")

        if self._pending:
            if self._turns:
                heading = f"Since turn {self._turns[-1].turn_number}, you observed:"
            else:
                heading = "You observed:"
            lines.extend(format_witnessed_events(self._pending, heading))

        return join_lines(lines)

    @property
    def total_turns(self) -> int:
        return self._total_turns

    @property
    def stored_turns(self) -> list[TurnRecord]:
        return list(self._turns)
