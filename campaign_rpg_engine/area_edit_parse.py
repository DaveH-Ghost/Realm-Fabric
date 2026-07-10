"""
Token parsing for legacy stepper-style argument strings.

Used by ``area_edit`` helpers and application-level command dispatch (e.g.
CampAIgn-RPG-Studio). Not part of the typed ``Session`` public API.
"""

from __future__ import annotations

import shlex
from typing import Optional


def tokenize_args(arg: str) -> tuple[Optional[list[str]], Optional[str]]:
    """Split arguments with shlex. Returns (tokens, error_message)."""
    try:
        return shlex.split(arg), None
    except ValueError as exc:
        return None, f"Invalid quoting in arguments: {exc}"


def parse_field_tokens(
    tokens: list[str], allowed: set[str]
) -> tuple[dict[str, str], Optional[str]]:
    """Parse keyword/value pairs (case-insensitive keys)."""
    fields: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        key = tokens[i].lower()
        if key not in allowed:
            return {}, f"Unknown or unexpected token: '{tokens[i]}'"
        if i + 1 >= len(tokens):
            return {}, f"Missing value for '{key}'"
        if key in fields:
            return {}, f"Duplicate field '{key}' in arguments."
        fields[key] = tokens[i + 1]
        i += 2
    return fields, None
