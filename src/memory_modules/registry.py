"""Factory registry for memory modules."""

from __future__ import annotations

from typing import Any, Callable

from src.memory_modules.base import MemoryModule
from src.memory_modules.recent_turns import DEFAULT_WINDOW, RecentTurnsModule, validate_window
from src.memory_modules.rolling_summary import (
    DEFAULT_MAX_SUMMARY_CHARS,
    DEFAULT_SUMMARY_INTERVAL,
    DEFAULT_SUMMARY_TAIL,
    RollingSummaryModule,
    validate_max_summary_chars,
    validate_summary_interval,
    validate_summary_tail,
)
from src.memory_modules.salient_turns import (
    DEFAULT_CHAR_BUDGET,
    SalientTurnsModule,
    validate_char_budget,
)

ModuleFactory = Callable[..., MemoryModule]

DEFAULT_MODULE_ID = "recent_turns"

_REGISTRY: dict[str, ModuleFactory] = {
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
}


def default_module_id() -> str:
    return DEFAULT_MODULE_ID


def _validate_module_config(module_id: str, config: dict[str, Any]) -> None:
    if module_id != "recent_turns" and "window" in config:
        raise ValueError(
            "memory-window is only valid with memory recent_turns "
            f"(got memory {module_id!r})."
        )
    if module_id == "recent_turns" and "window" in config:
        validate_window(int(config["window"]))

    if module_id != "salient_turns" and "char_budget" in config:
        raise ValueError(
            "memory-budget is only valid with memory salient_turns "
            f"(got memory {module_id!r})."
        )
    if module_id == "salient_turns" and "char_budget" in config:
        validate_char_budget(int(config["char_budget"]))

    if module_id != "rolling_summary" and (
        "summary_interval" in config
        or "max_summary_chars" in config
        or "summary_tail" in config
    ):
        raise ValueError(
            "memory-summary-interval, memory-summary-max, and memory-summary-tail "
            f"are only valid with memory rolling_summary (got memory {module_id!r})."
        )
    if module_id == "rolling_summary":
        if "summary_interval" in config:
            validate_summary_interval(int(config["summary_interval"]))
        if "max_summary_chars" in config:
            validate_max_summary_chars(int(config["max_summary_chars"]))
        if "summary_tail" in config:
            validate_summary_tail(int(config["summary_tail"]))


def create_module(module_id: str | None = None, **config: Any) -> MemoryModule:
    """Construct a memory module by id. Defaults to recent_turns."""
    resolved = module_id or DEFAULT_MODULE_ID
    factory = _REGISTRY.get(resolved)
    if factory is None:
        known = ", ".join(known_module_ids())
        raise ValueError(f"Unknown memory module {resolved!r}. Known modules: {known}")
    _validate_module_config(resolved, config)
    return factory(**config)


def known_module_ids() -> list[str]:
    """Return registered memory module ids (for create-agent and listing)."""
    return sorted(_REGISTRY)


def format_memory_module_label(module: MemoryModule) -> str:
    """Short label for agent listings (module id + module-specific config)."""
    if isinstance(module, SalientTurnsModule):
        return f"memory={module.module_id} budget={module.char_budget}"
    if isinstance(module, RollingSummaryModule):
        return (
            f"memory={module.module_id} interval={module.summary_interval} "
            f"max={module.max_summary_chars} tail={module.summary_tail}"
        )
    return f"memory={module.module_id}"


def format_memory_modules_list() -> str:
    """Read-only listing of registered memory modules."""
    lines = ["Registered memory modules:"]
    for module_id in known_module_ids():
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
            flags = (
                "memory-summary-interval N, memory-summary-max N, memory-summary-tail N"
            )
        else:
            desc = "(no description)"
            flags = "(unknown)"
        lines.append(f"  - {module_id}: {desc}")
        lines.append(f"      create-agent flags: {flags}")
    return "\n".join(lines)
