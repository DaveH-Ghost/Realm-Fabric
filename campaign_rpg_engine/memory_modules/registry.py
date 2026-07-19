"""Factory registry for memory modules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from campaign_rpg_engine.memory_modules.affinity import AffinityModule
from campaign_rpg_engine.memory_modules.base import MemoryModule
from campaign_rpg_engine.memory_modules.recent_turns import (
    DEFAULT_WINDOW,
    RecentTurnsModule,
    validate_window,
)
from campaign_rpg_engine.memory_modules.rolling_summary import (
    DEFAULT_MAX_SUMMARY_CHARS,
    DEFAULT_SUMMARY_INTERVAL,
    DEFAULT_SUMMARY_TAIL,
    RollingSummaryModule,
    validate_max_summary_chars,
    validate_summary_interval,
    validate_summary_tail,
)
from campaign_rpg_engine.memory_modules.salient_turns import (
    DEFAULT_CHAR_BUDGET,
    SalientTurnsModule,
    validate_char_budget,
)

DEFAULT_MODULE_ID = "recent_turns"

ModuleFactory = Callable[..., MemoryModule]

_BUILTIN_REGISTRY: dict[str, ModuleFactory] = {
    "recent_turns": lambda **cfg: RecentTurnsModule(window=cfg.get("window", DEFAULT_WINDOW)),
    "salient_turns": lambda **cfg: SalientTurnsModule(
        char_budget=int(cfg.get("char_budget", DEFAULT_CHAR_BUDGET)),
        storage_window=int(cfg.get("storage_window", 50)),
        recency_floor=int(cfg.get("recency_floor", 2)),
    ),
    "rolling_summary": lambda **cfg: RollingSummaryModule(
        summary_interval=int(cfg.get("summary_interval", DEFAULT_SUMMARY_INTERVAL)),
        max_summary_chars=int(cfg.get("max_summary_chars", DEFAULT_MAX_SUMMARY_CHARS)),
        summary_tail=int(cfg.get("summary_tail", DEFAULT_SUMMARY_TAIL)),
    ),
    "affinity": lambda **cfg: AffinityModule(
        summary_interval=int(cfg.get("summary_interval", DEFAULT_SUMMARY_INTERVAL)),
        max_summary_chars=int(cfg.get("max_summary_chars", DEFAULT_MAX_SUMMARY_CHARS)),
        summary_tail=int(cfg.get("summary_tail", DEFAULT_SUMMARY_TAIL)),
    ),
}


def default_module_id() -> str:
    return DEFAULT_MODULE_ID


def builtin_module_ids() -> list[str]:
    return sorted(_BUILTIN_REGISTRY)


def is_builtin_module_id(module_id: str) -> bool:
    return module_id in _BUILTIN_REGISTRY


def loaded_module_ids() -> list[str]:
    """Built-in memory module ids."""
    return builtin_module_ids()


def is_module_loaded(module_id: str) -> bool:
    return is_builtin_module_id(module_id)


def unknown_memory_module_message(module_id: str) -> str:
    known = ", ".join(builtin_module_ids())
    return f"Unknown or unsupported memory module {module_id!r}. Built-in modules: {known}."


def _validate_builtin_module_config(module_id: str, config: dict[str, Any]) -> None:
    if module_id != "recent_turns" and "window" in config:
        raise ValueError(
            f"memory-window is only valid with memory recent_turns (got memory {module_id!r})."
        )
    if module_id == "recent_turns" and "window" in config:
        validate_window(int(config["window"]))

    if module_id != "salient_turns" and "char_budget" in config:
        raise ValueError(
            f"memory-budget is only valid with memory salient_turns (got memory {module_id!r})."
        )
    if module_id == "salient_turns" and "char_budget" in config:
        validate_char_budget(int(config["char_budget"]))

    _SUMMARY_FLAG_MODULES = frozenset({"rolling_summary", "affinity"})
    if module_id not in _SUMMARY_FLAG_MODULES and (
        "summary_interval" in config or "max_summary_chars" in config or "summary_tail" in config
    ):
        raise ValueError(
            "memory-summary-interval, memory-summary-max, and memory-summary-tail "
            "are only valid with memory rolling_summary or affinity "
            f"(got memory {module_id!r})."
        )
    if module_id in _SUMMARY_FLAG_MODULES:
        if "summary_interval" in config:
            validate_summary_interval(int(config["summary_interval"]))
        if "max_summary_chars" in config:
            validate_max_summary_chars(int(config["max_summary_chars"]))
        if "summary_tail" in config:
            validate_summary_tail(int(config["summary_tail"]))


def create_module(module_id: str | None = None, **config: Any) -> MemoryModule:
    """Construct a memory module by id. Defaults to recent_turns."""
    resolved = module_id or DEFAULT_MODULE_ID
    if resolved not in _BUILTIN_REGISTRY:
        raise ValueError(unknown_memory_module_message(resolved))
    _validate_builtin_module_config(resolved, config)
    return _BUILTIN_REGISTRY[resolved](**config)


def export_module_state(module: MemoryModule) -> dict[str, Any]:
    """Serialize a memory module for session save."""
    export = getattr(module, "export_state", None)
    if export is None:
        raise TypeError(f"Memory module {module.module_id!r} does not support export_state")
    return export()


def restore_module_state(module: MemoryModule, data: dict[str, Any]) -> None:
    """Restore a memory module from :func:`export_module_state` output."""
    restore = getattr(module, "restore_state", None)
    if restore is None:
        raise TypeError(f"Memory module {module.module_id!r} does not support restore_state")
    restore(data)


def create_module_from_state(module_id: str, state: dict[str, Any]) -> MemoryModule:
    """Construct a module and restore saved state."""
    module = create_module(module_id)
    restore_module_state(module, state)
    return module


def known_module_ids() -> list[str]:
    """Return built-in memory module ids."""
    return loaded_module_ids()


def format_memory_module_label(module: MemoryModule) -> str:
    """Short label for agent listings (module id + module-specific config)."""
    if isinstance(module, SalientTurnsModule):
        return f"memory={module.module_id} budget={module.char_budget}"
    if isinstance(module, RollingSummaryModule):
        return (
            f"memory={module.module_id} interval={module.summary_interval} "
            f"max={module.max_summary_chars} tail={module.summary_tail}"
        )
    if hasattr(module, "summary_interval") and hasattr(module, "max_summary_chars"):
        return (
            f"memory={module.module_id} interval={module.summary_interval} "
            f"max={module.max_summary_chars} tail={module.summary_tail}"
        )
    return f"memory={module.module_id}"


def format_memory_modules_list() -> str:
    """Read-only listing of built-in memory modules."""
    lines = ["Registered memory modules:"]
    for module_id in loaded_module_ids():
        if module_id == "recent_turns":
            desc = "Last N own turns plus witnessed other-agent actions (default)"
            flags = "memory-window N"
        elif module_id == "salient_turns":
            desc = (
                f"Salience-weighted retention; render capped by memory-budget "
                f"({DEFAULT_CHAR_BUDGET} default)"
            )
            flags = "memory-budget N"
        elif module_id == "rolling_summary":
            desc = (
                f"Verbatim detail + rolling LLM summary every {DEFAULT_SUMMARY_INTERVAL} "
                f"turns ({DEFAULT_MAX_SUMMARY_CHARS} char cap); keeps last "
                f"{DEFAULT_SUMMARY_TAIL} turns in detail after each summary"
            )
            flags = "memory-summary-interval N, memory-summary-max N, memory-summary-tail N"
        elif module_id == "affinity":
            desc = (
                f"Relationships (-10…+10) + rolling LLM summary every "
                f"{DEFAULT_SUMMARY_INTERVAL} turns; consolidates affinity deltas from "
                f"the same turn window"
            )
            flags = "memory-summary-interval N, memory-summary-max N, memory-summary-tail N"
        else:
            desc = "(unknown)"
            flags = "(none)"
        lines.append(f"  - {module_id}: {desc}")
        lines.append(f"      create-agent flags: {flags}")
    return "\n".join(lines)
