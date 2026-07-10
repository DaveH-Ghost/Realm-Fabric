"""Process-wide interaction handler registry (V0.6.1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from campaign_rpg_engine.interaction_handlers.base import InteractionHandler

if TYPE_CHECKING:
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.object import Object
    from campaign_rpg_engine.object_action import ObjectAction
    from campaign_rpg_engine.session import Session

ValidateParams = Callable[[dict[str, str]], str | None]


@dataclass(frozen=True)
class HandlerRegistration:
    handler: InteractionHandler
    description: str = ""
    validate_params: ValidateParams | None = None


_REGISTRY: dict[str, HandlerRegistration] = {}


def register_interaction_handler(
    handler_id: str,
    handler: InteractionHandler,
    *,
    description: str = "",
    validate_params: ValidateParams | None = None,
) -> None:
    """Register a handler for the current process."""
    cleaned = handler_id.strip()
    if not cleaned:
        raise ValueError("handler_id must not be empty")
    _REGISTRY[cleaned] = HandlerRegistration(
        handler=handler,
        description=description,
        validate_params=validate_params,
    )


def is_handler_registered(handler_id: str) -> bool:
    return handler_id in _REGISTRY


def list_registered_handlers() -> list[str]:
    return sorted(_REGISTRY)


def get_handler_registration(handler_id: str) -> HandlerRegistration | None:
    return _REGISTRY.get(handler_id)


def validate_handler_params(handler_id: str, params: dict[str, str]) -> str | None:
    """Return an error message if params are invalid for *handler_id*."""
    if not handler_id:
        return None
    reg = _REGISTRY.get(handler_id)
    if reg is None:
        known = ", ".join(list_registered_handlers()) or "(none)"
        return f"Unknown handler '{handler_id}'. Known handlers: {known}."
    if reg.validate_params is not None:
        return reg.validate_params(dict(params))
    if params:
        return f"Handler '{handler_id}' does not accept parameters."
    return None


def run_interaction_handler(
    session: Session | None,
    area: Area,
    agent: Agent,
    obj: Object,
    action: ObjectAction,
) -> str | None:
    """Dispatch a registered handler. Returns an error message or ``None``."""
    handler_id = action.handler_id
    if not handler_id:
        return None
    err = validate_handler_params(handler_id, action.handler_params)
    if err:
        return err
    reg = _REGISTRY.get(handler_id)
    if reg is None:
        known = ", ".join(list_registered_handlers()) or "(none)"
        return f"Unknown handler '{handler_id}'. Known handlers: {known}."
    return reg.handler(session, area, agent, obj, action)


def format_handlers_list() -> str:
    """Format the read-only handlers listing for the stepper."""
    lines = ["Registered interaction handlers:"]
    if not _REGISTRY:
        lines.append("  (none)")
    else:
        for handler_id in sorted(_REGISTRY):
            reg = _REGISTRY[handler_id]
            suffix = f": {reg.description}" if reg.description else ""
            lines.append(f"  - {handler_id}{suffix}")
    return "\n".join(lines)


def clear_handlers_for_tests() -> None:
    """Remove all registered handlers (tests only)."""
    _REGISTRY.clear()
