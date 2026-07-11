"""Session coordinate presentation modes for LLM prompts."""

from __future__ import annotations

from typing import Literal

CoordinateMode = Literal["full", "relative"]

COORDINATE_MODE_FULL: CoordinateMode = "full"
COORDINATE_MODE_RELATIVE: CoordinateMode = "relative"

SUPPORTED_COORDINATE_MODES = frozenset({COORDINATE_MODE_FULL, COORDINATE_MODE_RELATIVE})


def normalize_coordinate_mode(value: str | None) -> CoordinateMode:
    """Return a supported coordinate mode (default ``full``)."""
    if value == COORDINATE_MODE_RELATIVE:
        return COORDINATE_MODE_RELATIVE
    return COORDINATE_MODE_FULL


def coordinate_mode_label(mode: str) -> str:
    normalized = normalize_coordinate_mode(mode)
    if normalized == COORDINATE_MODE_RELATIVE:
        return "Relative (entity ids and bearings)"
    return "Full (grid coordinates)"


def apply_passive_vision_mode(
    options: dict[str, object] | None,
    coordinate_mode: str,
    *,
    normalize,
) -> dict[str, bool]:
    """Merge slot options with coordinate-mode overrides."""
    opts = normalize(options)
    if normalize_coordinate_mode(coordinate_mode) == COORDINATE_MODE_RELATIVE:
        opts["include_you_are_at"] = False
        opts["include_entity_coordinates"] = False
        opts["include_relative_bearing"] = True
    return opts


def apply_move_instructions_mode(
    options: dict[str, object] | None,
    coordinate_mode: str,
    *,
    normalize,
) -> dict[str, bool]:
    opts = normalize(options)
    if normalize_coordinate_mode(coordinate_mode) == COORDINATE_MODE_RELATIVE:
        opts["include_coordinate_moves"] = False
    return opts
