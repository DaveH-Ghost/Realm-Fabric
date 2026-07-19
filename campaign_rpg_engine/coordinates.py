"""
coordinates.py

Shared coordinate parsing for V0.2 grid moves.

Canonical advertised form: "x,y". Parser also accepts "(x,y)" variants silently.

Grid bounds are defined on ``Area`` (``min_x`` / ``max_x`` / ``min_y`` / ``max_y``);
this module only parses.
"""

from __future__ import annotations


class CoordinateParseError(ValueError):
    """Raised when a move target cannot be parsed as grid coordinates."""


def parse_coordinate_target(target: str) -> tuple[int, int]:
    """
    Parse a move target into (x, y).

    Accepts "2,3", "2, 3", "(2,3)", "(2, 3)".
    Malformed targets (cardinals, wrong arity, non-integers) raise
    CoordinateParseError with ERR:INVALID_TARGET. Out-of-grid moves use
    ERR:INVALID_COORDINATES at runtime in move().
    """
    text = target.strip()
    if not text:
        raise CoordinateParseError("ERR:INVALID_TARGET: move requires a coordinate target 'x,y'")

    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()

    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise CoordinateParseError(
            f"ERR:INVALID_TARGET: move target must be 'x,y' (got {target!r})"
        )

    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise CoordinateParseError(
            f"ERR:INVALID_TARGET: coordinates must be integers (got {target!r})"
        ) from exc

    return x, y


def format_coordinate(x: int, y: int) -> str:
    """Format coordinates for user-facing result strings: (x, y)."""
    return f"({x}, {y})"
