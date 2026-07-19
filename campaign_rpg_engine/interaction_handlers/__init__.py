"""Pluggable object interaction handlers (V0.6.1)."""

from __future__ import annotations

from campaign_rpg_engine.interaction_handlers.base import InteractionHandler
from campaign_rpg_engine.interaction_handlers.registry import (
    collect_prefixed_params,
    format_handlers_list,
    get_handler_registration,
    handler_catalog_entry,
    is_handler_registered,
    list_registered_handlers,
    register_interaction_handler,
    run_interaction_handler,
    run_named_handler,
    validate_handler_params,
)

__all__ = [
    "InteractionHandler",
    "collect_prefixed_params",
    "format_handlers_list",
    "get_handler_registration",
    "handler_catalog_entry",
    "is_handler_registered",
    "list_registered_handlers",
    "register_interaction_handler",
    "run_interaction_handler",
    "run_named_handler",
    "validate_handler_params",
]
