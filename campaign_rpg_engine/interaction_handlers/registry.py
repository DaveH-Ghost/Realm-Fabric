"""Process-wide interaction handler registry (V0.6.1)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from campaign_rpg_engine.action_outcome import ActionOutcome
from campaign_rpg_engine.interaction_handlers.base import InteractionHandler

if TYPE_CHECKING:
    from campaign_rpg_engine.agent import Agent
    from campaign_rpg_engine.area import Area
    from campaign_rpg_engine.object import Object
    from campaign_rpg_engine.object_action import ObjectAction
    from campaign_rpg_engine.session import Session

ValidateParams = Callable[[dict[str, str]], str | None]

# JSON-serializable host UI hints for object-action editors (1.4.2).
ParamField = dict[str, Any]


@dataclass(frozen=True)
class HandlerRegistration:
    handler: InteractionHandler
    description: str = ""
    validate_params: ValidateParams | None = None
    param_fields: tuple[ParamField, ...] = ()
    summary_template: str = ""


_REGISTRY: dict[str, HandlerRegistration] = {}


def register_interaction_handler(
    handler_id: str,
    handler: InteractionHandler,
    *,
    description: str = "",
    validate_params: ValidateParams | None = None,
    param_fields: list[ParamField] | tuple[ParamField, ...] | None = None,
    summary_template: str = "",
) -> None:
    """Register a handler for the current process.

    *param_fields* / *summary_template* are optional host UI hints (Studio action
    editor). They do not affect runtime validation or dispatch.
    """
    cleaned = handler_id.strip()
    if not cleaned:
        raise ValueError("handler_id must not be empty")
    fields = tuple(dict(item) for item in (param_fields or ()))
    _REGISTRY[cleaned] = HandlerRegistration(
        handler=handler,
        description=description,
        validate_params=validate_params,
        param_fields=fields,
        summary_template=str(summary_template or ""),
    )


def is_handler_registered(handler_id: str) -> bool:
    return handler_id in _REGISTRY


def list_registered_handlers() -> list[str]:
    return sorted(_REGISTRY)


def get_handler_registration(handler_id: str) -> HandlerRegistration | None:
    return _REGISTRY.get(handler_id)


def handler_catalog_entry(handler_id: str) -> dict[str, Any] | None:
    """JSON-friendly catalog dict for *handler_id*, or None if unknown."""
    reg = _REGISTRY.get(handler_id)
    if reg is None:
        return None
    return {
        "id": handler_id,
        "description": reg.description,
        "param_fields": [dict(f) for f in reg.param_fields],
        "summary_template": reg.summary_template,
    }


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


def collect_prefixed_params(
    params: dict[str, str],
    prefix: str,
    *,
    skip_keys: frozenset[str] | set[str] | None = None,
) -> dict[str, str]:
    """
    Collect nested handler params stored under a branch prefix.

    Keys starting with *prefix* are included with the prefix stripped once.
    *skip_keys* (e.g. ``pass_handler`` / ``fail_handler``) are never returned.
    """
    if not prefix:
        raise ValueError("prefix must not be empty")
    skip = frozenset(skip_keys or ())
    out: dict[str, str] = {}
    for key, value in params.items():
        if key in skip:
            continue
        if not key.startswith(prefix):
            continue
        stripped = key[len(prefix) :]
        if not stripped:
            continue
        out[stripped] = value
    return out


def run_named_handler(
    session: Session | None,
    area: Area,
    agent: Agent,
    obj: Object,
    handler_id: str,
    params: dict[str, str] | None = None,
    *,
    source_action: ObjectAction,
) -> ActionOutcome | str | None:
    """
    Invoke a registered handler by id with an explicit params dict.

    Builds a shallow copy of *source_action* with ``handler_id`` /
    ``handler_params`` replaced so existing handlers that read
    ``action.handler_params`` keep working. Used by plugins that branch into
    follow-up handlers (e.g. skills ``pass_handler`` / ``fail_handler``).
    """
    from dataclasses import replace

    cleaned = (handler_id or "").strip()
    if not cleaned:
        return "Handler id must not be empty."
    param_map = dict(params or {})
    err = validate_handler_params(cleaned, param_map)
    if err:
        return err
    reg = _REGISTRY.get(cleaned)
    if reg is None:
        known = ", ".join(list_registered_handlers()) or "(none)"
        return f"Unknown handler '{cleaned}'. Known handlers: {known}."
    synthetic = replace(
        source_action,
        handler_id=cleaned,
        handler_params=param_map,
    )
    return reg.handler(session, area, agent, obj, synthetic)


def run_interaction_handler(
    session: Session | None,
    area: Area,
    agent: Agent,
    obj: Object,
    action: ObjectAction,
) -> ActionOutcome | str | None:
    """
    Dispatch a registered handler.

    Returns ``None`` on success (use action templates), an error ``str`` to abort
    with actor-only text, or an ``ActionOutcome`` as the final interact result (1.4.1).
    """
    handler_id = action.handler_id
    if not handler_id:
        return None
    return run_named_handler(
        session,
        area,
        agent,
        obj,
        handler_id,
        action.handler_params,
        source_action=action,
    )


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
