"""Process-wide session event listener registry (1.2.0)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from campaign_rpg_engine.session import Session

EventListener = Callable[["Session"], None]


@dataclass(frozen=True)
class EventListenerRegistration:
    listener: EventListener
    plugin_id: str = ""


_REGISTRY: dict[str, list[EventListenerRegistration]] = {}


def register_event_listener(
    event: str,
    listener: EventListener,
    *,
    plugin_id: str = "",
) -> None:
    """Register a listener for *event* (process-wide)."""
    cleaned = event.strip()
    if not cleaned:
        raise ValueError("event must not be empty")
    reg = EventListenerRegistration(listener=listener, plugin_id=plugin_id.strip())
    _REGISTRY.setdefault(cleaned, []).append(reg)


def unregister_event_listeners(plugin_id: str) -> None:
    """Remove all listeners registered for *plugin_id*."""
    cleaned = plugin_id.strip()
    if not cleaned:
        return
    for event in list(_REGISTRY):
        _REGISTRY[event] = [reg for reg in _REGISTRY[event] if reg.plugin_id != cleaned]
        if not _REGISTRY[event]:
            del _REGISTRY[event]


def list_registered_events() -> list[str]:
    return sorted(_REGISTRY)


def emit_session_event(session: Session, event: str, **payload: Any) -> None:
    """Invoke all listeners for *event* with *session* and keyword payload."""
    cleaned = event.strip()
    if not cleaned:
        return
    for reg in list(_REGISTRY.get(cleaned, [])):
        reg.listener(session, **payload)


def clear_event_listeners_for_tests() -> None:
    _REGISTRY.clear()
