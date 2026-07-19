"""
Token parsing for legacy stepper-style argument strings.

Used by ``area_edit`` helpers and application-level command dispatch (e.g.
CampAIgn-RPG-Studio). Not part of the typed ``Session`` public API.
"""

from __future__ import annotations

import shlex


def tokenize_args(arg: str) -> tuple[list[str] | None, str | None]:
    """Split arguments with shlex. Returns (tokens, error_message)."""
    try:
        return shlex.split(arg), None
    except ValueError as exc:
        return None, f"Invalid quoting in arguments: {exc}"


def parse_field_tokens(
    tokens: list[str],
    allowed: set[str],
    *,
    allow_extra: bool = False,
) -> tuple[dict[str, str], str | None]:
    """Parse keyword/value pairs (case-insensitive keys).

    When ``allow_extra`` is True, unknown keys that look like field names
    (``[a-z][a-z0-9_-]*``) are accepted so plugin handler params can be passed
    without extending the reserved allowlist for every handler.
    """
    fields: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        key = tokens[i].lower()
        if key not in allowed and (not allow_extra or not _is_extra_field_key(key)):
            return {}, f"Unknown or unexpected token: '{tokens[i]}'"
        if i + 1 >= len(tokens):
            return {}, f"Missing value for '{key}'"
        if key in fields:
            return {}, f"Duplicate field '{key}' in arguments."
        fields[key] = tokens[i + 1]
        i += 2
    return fields, None


def _is_extra_field_key(key: str) -> bool:
    """Accept plugin/handler param keys, including numbered prefixes like ``1_pdesc``."""
    if not key:
        return False
    # Reject pure numbers so values are not mistaken for field names.
    if key.isdigit():
        return False
    if not key[0].isalnum():
        return False
    return all(c.isalnum() or c in "_-" for c in key)
