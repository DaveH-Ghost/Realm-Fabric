from __future__ import annotations

from dataclasses import dataclass, field

from campaign_rpg_engine.grid import chebyshev_distance
from campaign_rpg_engine.object_action import ObjectAction


@dataclass
class Object:
    """
    Represents an object in the area with an axis-aligned grid footprint.

    Objects occupy one or more grid tiles (``width`` × ``height`` anchored at
    ``position``) and carry two optional description layers (V0.1):
    - passive_description: visible at a glance (no look required)
    - description: detailed text revealed by the `look` action

    V0.2 adds declarative ``actions`` (e.g. eat with delete_self effect).
    """

    id: str
    """Stable unique identifier for the object (e.g. 'obj_ball_01', 'obj_sign_01')."""

    name: str
    """Short, human-readable name shown in passive vision (e.g. 'Ceramic Ball')."""

    description: str
    """
    Detailed description revealed when the agent uses `look`.

    When non-empty and not yet examined, passive vision shows [?] (optionally
    with passive_description). Empty detailed description means no [?] tag.
    """

    position: tuple[int, int]
    """Top-left anchor of the footprint as (x, y)."""

    passive_description: str = ""
    """
    Glance-level description visible without looking.

    Shown in passive vision even when the agent has not used `look`. When both
    passive and detailed descriptions exist, never-examined objects show
    "[?] {passive_description}"; stale knowledge shows "[?] [changed] {passive}".
    """

    actions: dict[str, ObjectAction] = field(default_factory=dict)
    """Named interactions keyed by action name (unique per object)."""

    appearance: str = ""
    """
    Client-only image path for grid visualization (e.g. ``tokens/ball.png``).

    Ignored by the simulation, passive vision, and LLM prompts. Empty means
    no custom token image.
    """

    blocks_movement: bool = True
    """When True, other movers cannot enter any footprint tile (unless excepted)."""

    movement_exceptions: list[str] = field(default_factory=list)
    """Entity ids allowed to pass through or stand on this object's tiles."""

    width: int = 1
    """Footprint width in tiles (extends +x from anchor)."""

    height: int = 1
    """Footprint height in tiles (extends +y from anchor)."""

    hidden: bool = False
    """When True, hidden from agent passive vision and look (GM tooling still sees it)."""

    private_data: str = ""
    """
    Opaque app-owned text (health, durability, etc.).

    Serialized in snapshots/saves for custom clients. Not used by the engine,
    LLM prompts, or CLI.
    """


def object_footprint_tiles(obj: Object) -> list[tuple[int, int]]:
    """Return every grid tile occupied by *obj*."""
    ax, ay = obj.position
    return [(ax + dx, ay + dy) for dx in range(obj.width) for dy in range(obj.height)]


def object_occupies_tile(obj: Object, x: int, y: int) -> bool:
    """Return True if *(x, y)* lies inside *obj*'s footprint."""
    ax, ay = obj.position
    return ax <= x < ax + obj.width and ay <= y < ay + obj.height


def chebyshev_distance_to_object(pos: tuple[int, int], obj: Object) -> int:
    """Chebyshev distance from *pos* to the nearest tile of *obj*'s footprint."""
    return min(chebyshev_distance(pos, tile) for tile in object_footprint_tiles(obj))


def nearest_footprint_tile_to(observer: tuple[int, int], obj: Object) -> tuple[int, int]:
    """Return the footprint tile closest to *observer*.

    Primary sort: Chebyshev distance. Ties: Manhattan distance, then lower (x, y).
    """
    ox, oy = observer
    best_tile: tuple[int, int] | None = None
    best_key: tuple[int, int, tuple[int, int]] | None = None
    for tx, ty in object_footprint_tiles(obj):
        dx = abs(tx - ox)
        dy = abs(ty - oy)
        key = (max(dx, dy), dx + dy, (tx, ty))
        if best_key is None or key < best_key:
            best_key = key
            best_tile = (tx, ty)
    assert best_tile is not None
    return best_tile


def format_object_footprint_size(obj: Object) -> str:
    """Return a footprint size label for multi-tile objects (e.g. ``3×2 tiles``)."""
    if obj.width == 1 and obj.height == 1:
        return ""
    return f"{obj.width}×{obj.height} tiles"


def object_footprint_fits_bounds(obj: Object, area) -> bool:
    """Return True when every footprint tile is inside *area*'s grid."""
    return all(area.is_valid_position((x, y)) for x, y in object_footprint_tiles(obj))
