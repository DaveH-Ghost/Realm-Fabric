"""Recent-turns memory module — last N own turns plus witnessed agent actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from campaign_rpg_engine.memory_modules.base import (
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.formatting import format_stored_turns_block, join_lines
from campaign_rpg_engine.memory_modules.serialization import (
    deserialize_turn_list,
    deserialize_witness_list,
    deserialize_witnessed_before,
    serialize_turn_list,
    serialize_witness_list,
    serialize_witnessed_before,
)
from campaign_rpg_engine.turn_record import TurnRecord

DEFAULT_WINDOW = 10
MIN_WINDOW = 1
MAX_WINDOW = 100


def validate_window(value: int) -> None:
    if value < MIN_WINDOW or value > MAX_WINDOW:
        raise ValueError(
            f"memory-window must be between {MIN_WINDOW} and {MAX_WINDOW} (got {value})."
        )


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

    def __post_init__(self) -> None:
        validate_window(self.window)

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

    def export_state(self) -> dict:
        return {
            "window": self.window,
            "total_turns": self._total_turns,
            "turns": serialize_turn_list(self._turns),
            "witnessed_before": serialize_witnessed_before(self._witnessed_before),
            "pending": serialize_witness_list(self._pending),
        }

    def restore_state(self, data: dict) -> None:
        self.window = int(data["window"])
        validate_window(self.window)
        self._total_turns = int(data["total_turns"])
        self._turns = deserialize_turn_list(data.get("turns", []))
        self._witnessed_before = deserialize_witnessed_before(data.get("witnessed_before", []))
        self._pending = deserialize_witness_list(data.get("pending", []))
