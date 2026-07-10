"""
Relative compass bearings for passive vision (V0.4.1c).

Grid matches campaign-rpg-studio rendering: origin top-left, X increases east, Y increases south.
"""

from __future__ import annotations

from campaign_rpg_engine.grid import chebyshev_distance

PRIMARY_ZONE_RATIO = 2.5
DIAGONAL_ZONE_LOW = 0.4
DIAGONAL_ZONE_HIGH = 2.5


def relative_compass_direction(dx: int, dy: int) -> str | None:
    """
    Classify offset (dx, dy) into one of eight compass labels.

    *dx* / *dy* are target minus observer (east-positive, south-positive).
    Returns ``None`` when both offsets are zero (same tile).
    """
    if dx == 0 and dy == 0:
        return None

    abs_dx = abs(dx)
    abs_dy = abs(dy)

    if -dy > PRIMARY_ZONE_RATIO * abs_dx:
        return "North"
    if dy > PRIMARY_ZONE_RATIO * abs_dx:
        return "South"
    if dx > PRIMARY_ZONE_RATIO * abs_dy:
        return "East"
    if -dx > PRIMARY_ZONE_RATIO * abs_dy:
        return "West"
    if -dy > DIAGONAL_ZONE_LOW * dx and -dy < DIAGONAL_ZONE_HIGH * dx:
        return "North-East"
    if -dy > DIAGONAL_ZONE_LOW * -dx and -dy < DIAGONAL_ZONE_HIGH * -dx:
        return "North-West"
    if dy > DIAGONAL_ZONE_LOW * dx and dy < DIAGONAL_ZONE_HIGH * dx:
        return "South-East"
    if dy > DIAGONAL_ZONE_LOW * -dx and dy < DIAGONAL_ZONE_HIGH * -dx:
        return "South-West"

    if abs_dx >= abs_dy:
        return "East" if dx > 0 else "West"
    return "South" if dy > 0 else "North"


def format_relative_bearing_phrase(
    observer: tuple[int, int],
    target: tuple[int, int],
    *,
    units: str,
    units_per_tile: int,
) -> str | None:
    """Return ``South-East of you, 15 ft away`` or ``on your tile`` when co-located."""
    dx = target[0] - observer[0]
    dy = target[1] - observer[1]
    direction = relative_compass_direction(dx, dy)
    if direction is None:
        return "on your tile"
    tile_distance = chebyshev_distance(observer, target)
    distance = tile_distance * units_per_tile
    unit_label = units.strip()
    if not unit_label:
        return f"{direction} of you, {distance} away"
    return f"{direction} of you, {distance} {unit_label} away"


def format_action_range_label(
    range_tiles: int,
    *,
    vision_units: str = "",
    units_per_tile: int | None = None,
) -> str:
    """
    Prompt label for an object action Chebyshev range.

    When session units and/or units per tile are set, range is shown in world
    units (range_tiles × units_per_tile). Otherwise uses tile count.
    """
    if range_tiles == 0:
        return "same tile"
    unit_label = vision_units.strip()
    use_units = bool(unit_label) or units_per_tile is not None
    if not use_units:
        return f"range {range_tiles}"
    per_tile = 1 if units_per_tile is None else units_per_tile
    distance = range_tiles * per_tile
    if unit_label:
        return f"range {distance} {unit_label}"
    return f"range {distance}"
