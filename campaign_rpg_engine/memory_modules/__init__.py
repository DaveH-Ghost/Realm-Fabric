"""Pluggable agent memory modules for prompt assembly."""
from __future__ import annotations

from campaign_rpg_engine.memory_modules.base import (
    MemoryModule,
    MemoryObserveContext,
    MemoryRecordContext,
    MemoryRenderContext,
    WitnessedEvent,
)
from campaign_rpg_engine.memory_modules.registry import (
    create_module,
    default_module_id,
    format_memory_modules_list,
    known_module_ids,
)

__all__ = [
    "MemoryModule",
    "MemoryObserveContext",
    "MemoryRecordContext",
    "MemoryRenderContext",
    "WitnessedEvent",
    "create_module",
    "default_module_id",
    "format_memory_modules_list",
    "known_module_ids",
]
