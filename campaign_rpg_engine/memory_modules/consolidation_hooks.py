"""Process-wide hooks for memory consolidation failures (apps / Studio)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ConsolidationFailureListener = Callable[..., None]

_LISTENERS: list[ConsolidationFailureListener] = []


def register_consolidation_failure_listener(listener: ConsolidationFailureListener) -> None:
    """Register a process-wide listener invoked when consolidation fails."""
    _LISTENERS.append(listener)


def clear_consolidation_failure_listeners_for_tests() -> None:
    _LISTENERS.clear()


def notify_consolidation_failure(
    *,
    agent_name: str = "",
    turn_number: int | None = None,
    concurrency_limit_exceeded: bool = False,
    message: str = "",
    **extra: Any,
) -> None:
    """Notify listeners (best-effort; listener errors are ignored)."""
    payload = {
        "agent_name": agent_name,
        "turn_number": turn_number,
        "concurrency_limit_exceeded": concurrency_limit_exceeded,
        "message": message,
        **extra,
    }
    for listener in list(_LISTENERS):
        try:
            listener(**payload)
        except Exception:
            continue
