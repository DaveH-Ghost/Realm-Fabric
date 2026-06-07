from dataclasses import dataclass
from typing import Optional

from src.agent import Agent
from src.memory import Memory
from src.object import Object
from src.object_action import ObjectAction


class World:
    """
    Represents the entire simulation world.

    The World holds all state:
    - All agents (V0.1: multiple agents with independent memory)
    - All objects in the environment
    - Grid rules and boundaries

    The default initial world (create_initial_world) matches V0:
    - 5x5 grid (coordinates 0-4 in both x and y)
    - (0, 0) is the southwest corner. Y increases northward.
    - One starting agent (Explorer), a ceramic ball, and a wooden sign.
    - Additional agents and objects may be added at runtime via stepper commands.
    - No blocking objects. Agents can occupy the same tile as objects or each other.
    - Room boundaries are not represented as objects. They are described
      to the agent via a static room description string in the prompt.
    """

    # Grid constants (as defined in the V0 readiness checklist)
    WIDTH: int = 5
    HEIGHT: int = 5
    MIN_COORD: int = 0
    MAX_COORD: int = 4

    def __init__(self):
        self.agents: list[Agent] = []
        self.objects: list[Object] = []

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the world."""
        self.agents.append(agent)

    def add_object(self, obj: Object) -> None:
        """Add an object to the world."""
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
        """Return a copy of all agents in the world."""
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
        """Return the agent with the given ID, if it exists in the world."""
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
        """Return the object with the given ID, if it exists in the world."""
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def get_objects(self) -> list[Object]:
        """Return all objects currently in the world."""
        return self.objects

    def is_valid_position(self, position: tuple[int, int]) -> bool:
        """Check whether a position is inside the playable grid."""
        x, y = position
        return (
            self.MIN_COORD <= x <= self.MAX_COORD
            and self.MIN_COORD <= y <= self.MAX_COORD
        )

    def get_room_description(self) -> str:
        """
        Return the static room description shown to the agent every turn.

        In V0, walls and room boundaries are conveyed through this text
        rather than being modeled as objects.
        """
        return (
            "You are in a small room with a hardwood floor and four wooden walls."
        )

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


# =============================================================================
# Initial World State (as defined in the V0 readiness checklist)
# =============================================================================

def create_initial_world() -> World:
    """
    Create and return the starting world state.

    Same layout as V0 (Explorer at (1,1), ball at (2,2), sign at (2,4)).
    Explorer uses the V0.1 three-layer text model: `passive_description`,
    `description`, and `personality` (V0's single description field split).
    """
    world = World()

    # Create the agent
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
    world.add_agent(agent)

    # Create the ceramic ball
    ball = Object(
        id="obj_ball_01",
        name="Ceramic Ball",
        description="A slightly worn ceramic ball. It has a few scuffs and feels light.",
        position=(2, 2),
        actions={
            "kick": ObjectAction(
                name="kick",
                range=1,
                result="You kick the {object}.",
                passive_result="{actor} kicks the {object}.",
                effects=["random_move_self"],
            ),
        },
    )
    world.add_object(ball)

    sign = Object(
        id="obj_sign_01",
        name="Wooden Sign",
        passive_description="A simple wooden sign on the wall.",
        description=(
            'It reads: "This is a controlled environment. '
            'You are the only one here. This sign may occasionally be updated '
            'with new information. When it changes, you will be notified."'
        ),
        position=(2, 4),
    )
    world.add_object(sign)

    return world
