"""Recent-turns memory module — last N own turns plus witnessed agent actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from src.memory_modules.formatting import format_stored_turns_block, join_lines
from src.turn_record import TurnRecord

DEFAULT_WINDOW = 10


@dataclass
class RecentTurnsModule:
    """
    Keep the last ``window`` own turns and witnessed other-agent actions
    between those turns.
    """

    module_id: str = "recent_turns"
    window: int = DEFAULT_WINDOW

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
        return join_lines(
            format_stored_turns_block(self._turns, self._witnessed_before, self._pending)
        )

    @property
    def total_turns(self) -> int:
        return self._total_turns

    @property
    def stored_turns(self) -> list[TurnRecord]:
        """Last ``window`` own turns kept verbatim in the prompt detail buffer."""
        return list(self._turns)
