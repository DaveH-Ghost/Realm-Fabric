from dataclasses import dataclass, field
from typing import Optional

from src.memory import Memory
from src.turn_record import TurnRecord


@dataclass
class Agent:
    """
    Represents one agent in the simulation.

    Three text layers (mirrors objects for vision; personality is separate):
    - passive_description: glance text in other agents' passive vision
    - description: detailed text revealed by look (never includes personality)
    - personality: private LLM prompt text for this agent only (never in vision)
    """

    id: str
    """Unique identifier for the agent."""

    name: str
    """Display name of the agent (used in prompts and logging)."""

    personality: str
    """
    Private character instructions for the LLM when this agent acts.

    Included in this agent's prompt every turn. Never shown in passive vision
    and never revealed by look.
    """

    position: tuple[int, int]
    """Current grid position of the agent as (x, y)."""

    passive_description: str = ""
    """Glance-level text visible to other agents without looking."""

    description: str = ""
    """
    Detailed observable text revealed when another agent uses look.

    Hidden behind [?] in passive vision until examined (same rules as objects).
    """

    memory: Memory = field(default_factory=Memory)
    """Per-agent turn history and look knowledge (objects and other agents)."""

    passive_result: str = ""
    """
    Third-person summary of this agent's most recent successful action.

    Witnessed by other agents via memory modules (``broadcast_actor_turn``).
    Not shown in passive vision — only static pdesc/desc appear there.
    Replaced on each new successful action; not shown in look or personality.
    """

    last_action: Optional[str] = None
    """The action taken on the previous turn (retained for future use)."""

    appearance: str = ""
    """
    Client-only image path for grid visualization (e.g. ``tokens/explorer.png``).

    Ignored by the simulation, passive vision, and LLM prompts. Empty means
    no custom token image.
    """

    move_speed: Optional[int] = None
    """
    Max grid steps per move toward a target (5e: diagonal and orthogonal each cost 1).

    ``None`` = unlimited (teleport to target tile). Positive int = path at most that
    many steps; may stop short with a "towards" result.
    """
