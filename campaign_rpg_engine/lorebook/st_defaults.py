"""SillyTavern lorebook entry defaults (V0.5.0).

Derived from a typical ST export (e.g. tri-system-universe.lorebook.json).
Realm Fabric's matcher ignores most of these; they are kept so session edits and
downloads round-trip cleanly in SillyTavern and other ST-compatible tools.
"""

from __future__ import annotations

import copy
from typing import Any

# Fields present on a typical ST lorebook entry when not using advanced features.
ST_ENTRY_DEFAULTS: dict[str, Any] = {
    "vectorized": False,
    "selective": False,
    "selectiveLogic": 0,
    "addMemo": True,
    "position": 0,
    "disable": False,
    "constant": False,
    "ignoreBudget": False,
    "excludeRecursion": False,
    "preventRecursion": False,
    "matchPersonaDescription": False,
    "matchCharacterDescription": False,
    "matchCharacterPersonality": False,
    "matchCharacterDepthPrompt": False,
    "matchScenario": False,
    "matchCreatorNotes": False,
    "delayUntilRecursion": False,
    "probability": 100,
    "useProbability": True,
    "depth": 4,
    "outletName": "",
    "group": "",
    "groupOverride": False,
    "groupWeight": 100,
    "scanDepth": None,
    "caseSensitive": None,
    "matchWholeWords": None,
    "useGroupScoring": None,
    "automationId": "",
    "role": None,
    "sticky": 0,
    "cooldown": 0,
    "delay": 0,
    "triggers": [],
    "key": [],
    "keysecondary": [],
    "content": "",
    "comment": "",
    "order": 0,
}


def with_st_entry_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with missing ST keys filled from ``ST_ENTRY_DEFAULTS``."""
    merged = dict(data)
    for key, value in ST_ENTRY_DEFAULTS.items():
        if key not in merged:
            merged[key] = copy.deepcopy(value) if isinstance(value, list) else value
    if "displayIndex" not in merged and "uid" in merged:
        merged["displayIndex"] = merged["uid"]
    return merged


def new_st_entry_dict(
    uid: int,
    *,
    order: int = 0,
    display_index: int | None = None,
    comment: str = "New entry",
    content: str = "",
    keys: list[str] | None = None,
    keys_secondary: list[str] | None = None,
    disable: bool = False,
    constant: bool = False,
    selective: bool = False,
    selective_logic: int = 0,
    ignore_budget: bool = False,
) -> dict[str, Any]:
    """Build a full ST-shaped entry dict for a newly created session entry."""
    return with_st_entry_defaults(
        {
            "uid": uid,
            "order": order,
            "displayIndex": display_index if display_index is not None else uid,
            "comment": comment,
            "content": content,
            "key": list(keys or []),
            "keysecondary": list(keys_secondary or []),
            "disable": disable,
            "constant": constant,
            "selective": selective,
            "selectiveLogic": selective_logic,
            "ignoreBudget": ignore_budget,
        }
    )
