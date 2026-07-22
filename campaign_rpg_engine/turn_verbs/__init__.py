"""Registered compound-turn verbs (1.2.0)."""

from __future__ import annotations

from campaign_rpg_engine.turn_verbs.phases import (
    explicit_move_reaches_agent_range,
    run_turn_verb_phases,
    verb_turn_has_pathing,
)
from campaign_rpg_engine.turn_verbs.registry import (
    clear_turn_verbs_for_tests,
    format_turn_verbs_list,
    get_turn_verb_registration,
    list_registered_turn_verbs,
    register_turn_verb,
    resolve_verb_path_range,
    run_turn_verb,
)

__all__ = [
    "clear_turn_verbs_for_tests",
    "explicit_move_reaches_agent_range",
    "format_turn_verbs_list",
    "get_turn_verb_registration",
    "list_registered_turn_verbs",
    "register_turn_verb",
    "resolve_verb_path_range",
    "run_turn_verb",
    "run_turn_verb_phases",
    "verb_turn_has_pathing",
]
