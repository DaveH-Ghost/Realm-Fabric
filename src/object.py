from dataclasses import dataclass, field

from src.object_action import ObjectAction


@dataclass
class Object:
    """
    Represents a simple, single-tile object in the area.

    Objects occupy one grid tile and carry two optional description layers (V0.1):
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
    """The grid coordinates of the object as (x, y)."""

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
    """When True, other movers cannot enter this object's tile (unless excepted)."""

    movement_exceptions: list[str] = field(default_factory=list)
    """Entity ids allowed to pass through or stand on this object's tile."""
