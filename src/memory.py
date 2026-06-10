from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.memory_modules.base import (
    MemoryModule,
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    TurnGatedMemoryModule,
    WitnessedEvent,
)
from src.memory_modules.registry import create_module
from src.turn_record import StepKind, TurnRecord, TurnStep

if TYPE_CHECKING:
    from src.agent import Agent
    from src.world import World

# Re-export turn types for backward compatibility.
__all__ = [
    "Memory",
    "StepKind",
    "TurnRecord",
    "TurnStep",
]


@dataclass(init=False)
class Memory:
    """
    Per-agent memory facade: look knowledge + pluggable prompt memory module.

    Look knowledge (`looked_at` / `ever_looked`) controls passive vision.
    The assigned memory module owns turn history and witnessed observations
    for the Memory: prompt section.
    """

    def __init__(
        self,
        module_id: str | None = None,
        *,
        module: MemoryModule | None = None,
        **module_config: Any,
    ) -> None:
        if module is not None and module_id is not None:
            raise ValueError("Pass module_id or module, not both.")
        self._module = (
            module if module is not None else create_module(module_id, **module_config)
        )
        self._looked_at: set[str] = set()
        self._ever_looked: set[str] = set()

    @property
    def module(self) -> MemoryModule:
        return self._module

    @property
    def module_id(self) -> str:
        return self._module.module_id

    @property
    def turns(self) -> list[TurnRecord]:
        """Verbatim detail turns in the prompt memory module (module-specific window)."""
        return self._module.stored_turns

    @property
    def looked_at(self) -> set[str]:
        return set(self._looked_at)

    @property
    def ever_looked(self) -> set[str]:
        return set(self._ever_looked)

    @property
    def turn_count(self) -> int:
        """Total own turns taken (not capped by the prompt window)."""
        return self._module.total_turns

    def render_prompt_block(self, agent: Agent, world: World) -> str:
        """Text body for the Memory: section (empty module → default message)."""
        body = self._module.render(MemoryRenderContext(agent=agent, world=world))
        if not body.strip():
            return "No memories yet."
        return body.strip()

    def record_turn(self, record: TurnRecord, *, agent_id: str, agent_name: str = "") -> None:
        self._module.record_turn(
            record,
            MemoryRecordContext(
                agent_id=agent_id,
                turn_number=record.turn_number,
                agent_name=agent_name,
            ),
        )

    def record_observation(self, event: WitnessedEvent, *, observer_id: str) -> None:
        self._module.record_observation(
            event,
            MemoryObserveContext(observer_id=observer_id),
        )

    def add_turn(self, record: TurnRecord, *, agent_id: str = "") -> None:
        """Record a committed turn. Prefer passing agent_id when available."""
        self.record_turn(record, agent_id=agent_id)

    def get_detail_turns(self, count: int = 10) -> list[TurnRecord]:
        """
        Return up to the last ``count`` turns from the module's verbatim detail buffer.

        This is what appears (in full or compressed form) in the Memory: prompt section.
        For ``rolling_summary``, older turns may exist only in the consolidated summary
        block—not in this list.
        """
        turns = self._module.stored_turns
        return list(turns[-count:])

    def get_recent_turns(self, count: int = 10) -> list[TurnRecord]:
        """Alias for :meth:`get_detail_turns` (kept for backward compatibility)."""
        return self.get_detail_turns(count)

    def mark_looked_at(self, object_id: str) -> None:
        self._looked_at.add(object_id)
        self._ever_looked.add(object_id)

    def has_looked_at(self, object_id: str) -> bool:
        return object_id in self._looked_at

    def has_ever_looked_at(self, object_id: str) -> bool:
        return object_id in self._ever_looked

    def invalidate_look(self, object_id: str) -> None:
        self._looked_at.discard(object_id)

    def clear_examination(self, object_id: str) -> None:
        self._looked_at.discard(object_id)
        self._ever_looked.discard(object_id)

    def ensure_ready_for_turn(self) -> None:
        """Wait for memory consolidation when the module requires it."""
        if isinstance(self._module, TurnGatedMemoryModule):
            self._module.ensure_ready_for_turn()

    def reset_looked_at(self) -> None:
        self._looked_at.clear()
        self._ever_looked.clear()
