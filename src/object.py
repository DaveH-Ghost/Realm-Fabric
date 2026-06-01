from dataclasses import dataclass


@dataclass
class Object:
    """
    Represents a simple, single-tile object in the world.

    In Version 0, objects are very basic:
    - They occupy exactly one grid tile.
    - They have a stable ID, a short display name, and a description.
    - The description is only revealed when the agent uses the `look` action.
    - Objects do not have behavior or interactions yet (those are out of scope for V0).

    This class is intentionally kept minimal. It is just a data container.
    """

    id: str
    """Stable unique identifier for the object (e.g. 'obj_ball_01', 'obj_sign_01')."""

    name: str
    """Short, human-readable name shown in passive vision (e.g. 'Ceramic Ball')."""

    description: str
    """
    The full description of the object.

    This is what the agent receives when they successfully use the `look` action
    on this object. Before looking, the agent only sees '[?]' in passive vision.
    """

    position: tuple[int, int]
    """The grid coordinates of the object as (x, y)."""
