"""Protocol and shared types for memory modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from campaign_rpg_engine.turn_record import TurnRecord

if TYPE_CHECKING:
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.area import Area


@dataclass(frozen=True)
class WitnessedEvent:
    """Something the observer saw another agent do (from passive_result at commit time)."""

    session_turn: int
    actor_id: str
    actor_name: str
    text: str
    actor_position: tuple[int, int]


@dataclass(frozen=True)
class MemoryRecordContext:
    agent_id: str
    turn_number: int
    agent_name: str = ""


@dataclass(frozen=True)
class MemoryObserveContext:
    observer_id: str


@dataclass(frozen=True)
class MemoryRenderContext:
    agent: Agent
    area: Area


class MemoryModule(Protocol):
    """Prompt memory for one agent. Look knowledge stays on Memory facade."""

    module_id: str

    def record_turn(self, record: TurnRecord, ctx: MemoryRecordContext) -> None:
        """Ingest the observer's own committed turn."""

    def record_observation(self, event: WitnessedEvent, ctx: MemoryObserveContext) -> None:
        """Ingest another agent's observable action this observer witnessed."""

    def render(self, ctx: MemoryRenderContext) -> str:
        """Body text for the Memory: prompt section (no header)."""

    @property
    def total_turns(self) -> int:
        """Monotonic count of this agent's own turns (for TurnRecord numbering)."""

    @property
    def stored_turns(self) -> list[TurnRecord]:
        """
        Own turns kept verbatim in the prompt detail buffer.

        Meaning is module-specific: full retained window (``recent_turns``),
        salience-selected storage (``salient_turns``), or post-consolidation
        detail only (``rolling_summary`` — see that module's ``summary`` property
        for consolidated history).
        """

    def export_state(self) -> dict[str, Any]:
        """Serialize config and runtime buffers for session save/load."""

    def restore_state(self, data: dict[str, Any]) -> None:
        """Restore config and runtime buffers from :meth:`export_state`."""


@runtime_checkable
class TurnGatedMemoryModule(Protocol):
    """Memory module that may block turn start until async work completes."""

    def ensure_ready_for_turn(self) -> None:
        """Block until the module is ready to record another own turn."""
