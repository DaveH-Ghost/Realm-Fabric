from dataclasses import dataclass
from typing import Optional

from src.agent import Agent
from src.memory import Memory
from src.object import Object
from src.object_action import ObjectAction
from src.area_event import (
    DEFAULT_MAX_RECENT_AREA_EVENTS,
    AreaEventRecord,
)

DEFAULT_AREA_DESCRIPTION = (
    "You are in a small room with a hardwood floor and four wooden walls."
)


@dataclass(frozen=True)
class GridBounds:
    """Playable grid bounds (inclusive on all sides)."""

    min_x: int = 0
    min_y: int = 0
    max_x: int = 4
    max_y: int = 4

    def __post_init__(self) -> None:
        if self.min_x > self.max_x or self.min_y > self.max_y:
            raise ValueError(
                f"Invalid grid bounds: min ({self.min_x}, {self.min_y}) "
                f"exceeds max ({self.max_x}, {self.max_y})"
            )

    @classmethod
    def square(
        cls,
        size: int,
        *,
        min_x: int = 0,
        min_y: int = 0,
    ) -> GridBounds:
        """Build a square grid of ``size`` tiles per side."""
        if size < 1:
            raise ValueError(f"Grid size must be at least 1 (got {size})")
        return cls(
            min_x=min_x,
            min_y=min_y,
            max_x=min_x + size - 1,
            max_y=min_y + size - 1,
        )

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1


class Area:
    """
    Represents one playable grid area.

    Grid bounds and room description are set at construction time so different
    games/scenarios can share the same engine without forking ``Area``.
    """

    def __init__(
        self,
        *,
        bounds: GridBounds | None = None,
        area_description: str = DEFAULT_AREA_DESCRIPTION,
    ) -> None:
        grid = bounds if bounds is not None else GridBounds()
        self.bounds = grid
        self.area_description = area_description
        self.agents: list[Agent] = []
        self.objects: list[Object] = []
        self._recent_events: list[AreaEventRecord] = []
        self._max_recent_events = DEFAULT_MAX_RECENT_AREA_EVENTS

    # Legacy aliases (square-grid tests and object_effects)
    @property
    def min_x(self) -> int:
        return self.bounds.min_x

    @property
    def min_y(self) -> int:
        return self.bounds.min_y

    @property
    def max_x(self) -> int:
        return self.bounds.max_x

    @property
    def max_y(self) -> int:
        return self.bounds.max_y

    @property
    def MIN_COORD(self) -> int:
        return self.bounds.min_x

    @property
    def MAX_COORD(self) -> int:
        return self.bounds.max_x

    @property
    def WIDTH(self) -> int:
        return self.bounds.width

    @property
    def HEIGHT(self) -> int:
        return self.bounds.height

    def format_grid_bounds_message(self) -> str:
        """Short bounds text for validation errors and prompts."""
        if (
            self.min_x == self.min_y
            and self.max_x == self.max_y
            and self.min_x == 0
        ):
            return f"Grid is {self.min_x}-{self.max_x} in both axes."
        return (
            f"Grid x is {self.min_x}-{self.max_x}, "
            f"y is {self.min_y}-{self.max_y}."
        )

    def format_move_coordinate_rule(self) -> str:
        """Tell the agent which coordinates are in bounds."""
        if self.min_x == self.max_x and self.min_y == self.max_y:
            label = f"({self.min_x}, {self.min_y})"
            return f"You may move only to {label}."
        return (
            "You may move to any coordinate (x, y) where "
            f"x is an integer from {self.min_x} to {self.max_x} and "
            f"y is an integer from {self.min_y} to {self.max_y}."
        )

    def format_grid_description(self) -> str:
        """Opening line describing grid size and coordinate system."""
        w, h = self.WIDTH, self.HEIGHT
        return (
            f"You exist inside a controlled {w}x{h} grid. "
            f"Your coordinates range from ({self.min_x}, {self.min_y}) in the "
            f"southwest corner to ({self.max_x}, {self.max_y}) in the northeast. "
            "Y increases northward."
        )

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the area."""
        self.agents.append(agent)

    def add_object(self, obj: Object) -> None:
        """Add an object to the area."""
        self.objects.append(obj)

    def remove_object(self, object_id: str) -> bool:
        """
        Remove an object by ID. Returns True if removed, False if not found.

        Clears looked_at / ever_looked for that object on all agents.
        """
        for i, obj in enumerate(self.objects):
            if obj.id == object_id:
                self.objects.pop(i)
                self.clear_object_examination_history(object_id)
                return True
        return False

    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent by ID. Returns True if removed, False if not found."""
        for i, agent in enumerate(self.agents):
            if agent.id == agent_id:
                self.agents.pop(i)
                return True
        return False

    def get_agents(self) -> list[Agent]:
        """Return a copy of all agents in the area."""
        return list(self.agents)

    def get_agent(self) -> Optional[Agent]:
        """
        Return the first agent in the world (backward compatibility for V0).

        For multi-agent sessions, prefer get_agents() or lookup helpers.
        Returns None if no agent exists.
        """
        if not self.agents:
            return None
        return self.agents[0]

    def get_agent_by_id(self, agent_id: str) -> Optional[Agent]:
        """Return the agent with the given ID, if it exists in the area."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Return the agent with the given display name (case-insensitive)."""
        name_lower = name.strip().lower()
        for agent in self.agents:
            if agent.name.lower() == name_lower:
                return agent
        return None

    def get_object_at(self, position: tuple[int, int]) -> Optional[Object]:
        """Return the object at a given position, if any."""
        for obj in self.objects:
            if obj.position == position:
                return obj
        return None

    def get_object_by_id(self, object_id: str) -> Optional[Object]:
        """Return the object with the given ID, if it exists in the area."""
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def get_objects(self) -> list[Object]:
        """Return all objects currently in the area."""
        return self.objects

    def is_valid_position(self, position: tuple[int, int]) -> bool:
        """Check whether a position is inside the playable grid."""
        x, y = position
        return (
            self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y
        )

    def get_area_description(self) -> str:
        """
        Return the static area description shown to the agent every turn.

        Walls and boundaries are conveyed through this text rather than as
        objects unless a game models them explicitly.
        """
        return self.area_description

    def invalidate_entity_knowledge(self, entity_id: str) -> None:
        """
        Remove up-to-date look knowledge for an object or agent across all agents.

        Call when an object's or agent's **desc** (detailed observable text) changes.
        Do not call agent.memory.invalidate_look directly.

        **Does not apply to `personality` edits** — personality is never revealed by look.

        Agents who had looked will see [?] [changed]; agents who never looked
        still see plain [?].
        """
        for agent in self.agents:
            if agent.memory.has_looked_at(entity_id):
                agent.memory.invalidate_look(entity_id)

    def clear_entity_examination_history(self, entity_id: str) -> None:
        """
        Clear looked_at and ever_looked for an entity across all agents.

        Used when detailed description/personality is removed so agents are not
        stuck in a stale state they cannot clear via look.
        """
        for agent in self.agents:
            agent.memory.clear_examination(entity_id)

    def invalidate_object_knowledge(self, object_id: str) -> None:
        """Alias for invalidate_entity_knowledge (objects)."""
        self.invalidate_entity_knowledge(object_id)

    def clear_object_examination_history(self, object_id: str) -> None:
        """Alias for clear_entity_examination_history (objects)."""
        self.clear_entity_examination_history(object_id)

    @property
    def recent_events(self) -> list[AreaEventRecord]:
        """Recent area-wide GM/narrator events (oldest first)."""
        return list(self._recent_events)

    def append_area_event(self, *, session_turn: int, text: str) -> AreaEventRecord:
        """Append a room-wide event; evict oldest when over capacity."""
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Area event text cannot be empty.")
        record = AreaEventRecord(session_turn=session_turn, text=cleaned)
        self._recent_events.append(record)
        overflow = len(self._recent_events) - self._max_recent_events
        if overflow > 0:
            self._recent_events = self._recent_events[overflow:]
        return record


def create_area(
    *,
    width: int = 5,
    height: int = 5,
    min_x: int = 0,
    min_y: int = 0,
    area_description: str = DEFAULT_AREA_DESCRIPTION,
) -> Area:
    """Create an empty area with the given grid size and area text."""
    return Area(
        bounds=GridBounds(
            min_x=min_x,
            min_y=min_y,
            max_x=min_x + width - 1,
            max_y=min_y + height - 1,
        ),
        area_description=area_description,
    )


def create_initial_area() -> Area:
    """
    Create and return the starting demo area.

    Same layout as V0 (Explorer at (1,1), ball at (2,2), sign at (2,4)).
    Explorer uses the V0.1 three-layer text model: `passive_description`,
    `description`, and `personality` (V0's single description field split).
    """
    area = create_area(
        width=5,
        height=5,
        area_description=DEFAULT_AREA_DESCRIPTION,
    )

    agent = Agent(
        id="agent_01",
        name="Explorer",
        passive_description="A curious explorer in the room.",
        description=(
            "A traveler in worn boots and a dusty coat, watching the room "
            "with careful attention."
        ),
        personality=(
            "You are a curious explorer placed in a small, controlled room. "
            "Your goal is to understand your environment through careful "
            "observation and deliberate action."
        ),
        position=(1, 1),
        memory=Memory(),
        last_action=None,
    )
    area.add_agent(agent)

    ball = Object(
        id="obj_ball_01",
        name="Ceramic Ball",
        description="A slightly worn ceramic ball. It has a few scuffs and feels light.",
        position=(2, 2),
        actions={
            "kick": ObjectAction(
                name="kick",
                range=1,
                result="You kick the {object}. It rolls from {start} to {end}.",
                passive_result="{actor} kicks the {object}. It rolls from {start} to {end}.",
                effects=["random_move_self"],
            ),
        },
    )
    area.add_object(ball)

    sign = Object(
        id="obj_sign_01",
        name="Wooden Sign",
        passive_description="A simple wooden sign on the wall.",
        description=(
            'It reads: "This room is a test environment. Please interact with the world to make it more interesting."'
        ),
        position=(2, 4),
    )
    area.add_object(sign)

    return area
