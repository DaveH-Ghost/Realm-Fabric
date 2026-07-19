"""
session.py

V0.3.0a — runtime session API for CampAIgn-RPG-Engine.

``Session`` owns ``Area`` state, the active agent, and orchestrates compound
turns and stepper-style edit commands. Intended as the single entry point for
CLI, web backends, and other clients.

V0.4.0c1 — multi-area sessions: ``areas``, ``agent_area``, ``active_area_id``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.edit.area_edit import (
    delete_agent_by_id,
)
from campaign_rpg_engine.edit.decoration_edit import (
    DecorationMutationResult,
    add_decoration_to_area,
    remove_decoration_from_area,
    reorder_decoration_in_area,
    update_decoration_in_area,
)
from campaign_rpg_engine.edit.session_area_edit import (
    create_area_in_session,
    delete_area_by_id,
    edit_area_in_session,
)
from campaign_rpg_engine.edit.world_edit_api import (
    WorldMutationResult,
    add_object_action_to_object,
    create_agent_in_area,
    create_object_in_area,
    delete_object_in_session,
    edit_object_with_fields,
    find_object_in_session,
)
from campaign_rpg_engine.game_profile import GameProfile, default_compound_profile
from campaign_rpg_engine.llm.prompt_context import build_prompt_context
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.memory import TurnRecord
from campaign_rpg_engine.object import Object
from campaign_rpg_engine.object_action import ObjectAction
from campaign_rpg_engine.simulation import next_turn_number_for_agent, run_compound_turn
from campaign_rpg_engine.snapshot import DEFAULT_AREA_ID

__all__ = [
    "DEFAULT_AREA_ID",
    "DecorationMutationResult",
    "Session",
    "SessionResult",
    "TurnResult",
    "WorldMutationResult",
]


@dataclass(frozen=True)
class SessionResult:
    """Outcome of a session operation that does not produce a turn record."""

    ok: bool
    message: str


@dataclass(frozen=True)
class TurnResult:
    """Outcome of ``run_compound_turn``."""

    ok: bool
    message: str
    record: TurnRecord | None = None
    agent: Agent | None = None


class Session:
    """
    Owns simulation state and exposes turn + typed world-editing operations.

    Does not perform HTTP or CLI I/O — callers format ``message`` for display.
    """

    def __init__(
        self,
        area: Area | None = None,
        *,
        areas: dict[str, Area] | None = None,
        active_area_id: str | None = None,
        agent_area: dict[str, str] | None = None,
        profile: GameProfile | None = None,
        active_agent_id: str | None = None,
        include_examples: bool = False,
    ) -> None:
        self.profile = profile or default_compound_profile()
        self.include_examples = include_examples
        self.session_turn = 0
        self._agents_by_name: dict[str, Agent] = {}

        if areas is not None:
            if not areas:
                raise ValueError("areas must not be empty")
            self.areas = dict(areas)
        elif area is not None:
            resolved_area_id = active_area_id or DEFAULT_AREA_ID
            self.areas = {resolved_area_id: area}
        else:
            raise ValueError("Session requires area or areas")

        if active_area_id is None:
            self.active_area_id = next(iter(self.areas))
        else:
            if active_area_id not in self.areas:
                raise ValueError(f"Unknown active_area_id: {active_area_id!r}")
            self.active_area_id = active_area_id

        if agent_area is None:
            self.agent_area: dict[str, str] = {}
            for area_id, area_obj in self.areas.items():
                for agent in area_obj.agents:
                    self.agent_area[agent.id] = area_id
        else:
            self.agent_area = dict(agent_area)

        self._rebuild_agent_name_index()
        if active_agent_id is None:
            first_area = next(iter(self.areas.values()))
            if not first_area.agents:
                raise ValueError("Session has no agents")
            active_agent_id = first_area.agents[0].id
        agent = self.get_agent(active_agent_id)
        if agent is None:
            raise ValueError(f"Unknown active_agent_id: {active_agent_id!r}")
        self.active_agent_id = agent.id
        self._prompt_blocks: list | None = None
        self.vision_units: str = ""
        self.vision_units_per_tile: int | None = None
        from campaign_rpg_engine.coordinate_mode import COORDINATE_MODE_FULL

        self.coordinate_mode: str = COORDINATE_MODE_FULL
        from campaign_rpg_engine.lorebook.models import DEFAULT_LOREBOOK_CHAR_BUDGET, Lorebook

        self._lorebooks: dict[str, Lorebook] = {}
        self.lorebook_char_budget = DEFAULT_LOREBOOK_CHAR_BUDGET
        from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig

        self.lorebook_scan_config = LorebookScanConfig()
        self.extensions: dict[str, Any] = {}

    def get_extension(self, plugin_id: str) -> Any:
        """Return plugin-owned session extension data (default ``None``)."""
        return self.extensions.get(plugin_id)

    def set_extension(self, plugin_id: str, value: Any) -> None:
        """Set plugin-owned session extension data."""
        if value is None:
            self.extensions.pop(plugin_id, None)
        else:
            self.extensions[plugin_id] = value

    def _emit_event(self, event: str, **payload: Any) -> None:
        from campaign_rpg_engine.events.registry import emit_session_event

        emit_session_event(self, event, **payload)

    @property
    def area(self) -> Area:
        """Active area (GM edit / emit scope). Backward compat with V0.3."""
        return self.areas[self.active_area_id]

    @classmethod
    def from_default(
        cls,
        *,
        profile: GameProfile | None = None,
        include_examples: bool = False,
    ) -> Session:
        """Create a session with the profile's default demo area."""
        prof = profile or default_compound_profile()
        return cls(
            prof.create_area(),
            profile=prof,
            include_examples=include_examples,
        )

    @classmethod
    def from_profile(
        cls,
        profile: GameProfile,
        *,
        include_examples: bool = False,
    ) -> Session:
        """Create a session from a profile's default area factory."""
        return cls(
            profile.create_area(),
            profile=profile,
            include_examples=include_examples,
        )

    # ------------------------------------------------------------------
    # Area / agent resolution
    # ------------------------------------------------------------------

    def get_area_for_agent(self, agent: Agent) -> Area:
        """Return the area where ``agent`` currently lives."""
        area_id = self.agent_area.get(agent.id)
        if area_id is None:
            raise RuntimeError(f"Agent {agent.id!r} has no area mapping")
        return self.areas[area_id]

    def get_active_agent(self) -> Agent:
        agent = self.get_agent(self.active_agent_id)
        if agent is None:
            raise RuntimeError(f"Active agent missing: {self.active_agent_id!r}")
        return agent

    def get_agent(self, name_or_id: str) -> Agent | None:
        """Resolve an agent by id (``agent_*``) or display name (case-insensitive)."""
        key = name_or_id.strip()
        if not key:
            return None
        if key.startswith("agent_"):
            for area in self.areas.values():
                agent = area.get_agent_by_id(key)
                if agent is not None:
                    return agent
            return None
        name_key = key.lower()
        agent = self._agents_by_name.get(name_key)
        if agent is not None:
            return agent
        self._rebuild_agent_name_index()
        return self._agents_by_name.get(name_key)

    def set_active_agent(self, name_or_id: str) -> SessionResult:
        """Change the active agent without consuming a turn."""
        agent = self.get_agent(name_or_id)
        if agent is None:
            return SessionResult(
                ok=False,
                message=f"Agent {name_or_id!r} not found.",
            )
        self.active_agent_id = agent.id
        area_id = self.agent_area.get(agent.id, "?")
        return SessionResult(
            ok=True,
            message=(f"Active agent: {agent.name} ({agent.id}) at {agent.position} [{area_id}]"),
        )

    def set_active_area(self, area_id: str) -> SessionResult:
        """Change GM edit / emit scope without consuming a turn."""
        cleaned = area_id.strip()
        if cleaned not in self.areas:
            return SessionResult(
                ok=False,
                message=f"Unknown area {area_id!r}. Known: {', '.join(sorted(self.areas))}.",
            )
        self.active_area_id = cleaned
        return SessionResult(ok=True, message=f"Active area: {cleaned}")

    def transfer_agent(
        self,
        agent_id: str,
        dest_area_id: str,
        position: tuple[int, int],
    ) -> SessionResult:
        """
        Move an agent to another area at ``position`` (internal API for effects).

        Removes the agent from its current area, validates destination bounds,
        and updates ``agent_area``.
        """
        source_area_id = self.agent_area.get(agent_id)
        if source_area_id is None:
            return SessionResult(ok=False, message=f"Agent {agent_id!r} not found.")
        if dest_area_id not in self.areas:
            return SessionResult(
                ok=False,
                message=f"Unknown destination area {dest_area_id!r}.",
            )
        dest_area = self.areas[dest_area_id]
        if not dest_area.is_valid_position(position):
            return SessionResult(
                ok=False,
                message=f"Position {position} is outside {dest_area_id} bounds.",
            )

        source_area = self.areas[source_area_id]
        agent = source_area.get_agent_by_id(agent_id)
        if agent is None:
            return SessionResult(ok=False, message=f"Agent {agent_id!r} not found.")

        if not source_area.remove_agent(agent_id):
            return SessionResult(ok=False, message=f"Agent {agent_id!r} not found.")

        agent.position = position
        dest_area.add_agent(agent)
        self.agent_area[agent_id] = dest_area_id
        return SessionResult(
            ok=True,
            message=(
                f"Transferred {agent.name} ({agent_id}) "
                f"from {source_area_id} to {dest_area_id} at {position}."
            ),
        )

    def find_object(self, object_id: str) -> tuple[str, Object] | None:
        """Return ``(area_id, object)`` for ``object_id`` anywhere in the session."""
        cleaned = object_id.strip()
        for area_id, area in self.areas.items():
            obj = area.get_object_by_id(cleaned)
            if obj is not None:
                return area_id, obj
        return None

    def transfer_object(
        self,
        object_id: str,
        dest_area_id: str,
        position: tuple[int, int],
    ) -> SessionResult:
        """Move an object to another area at ``position`` (internal / edit-object API)."""
        located = self.find_object(object_id)
        if located is None:
            return SessionResult(ok=False, message=f"Object {object_id!r} not found.")
        source_area_id, obj = located
        if dest_area_id not in self.areas:
            return SessionResult(
                ok=False,
                message=f"Unknown destination area {dest_area_id!r}.",
            )
        dest_area = self.areas[dest_area_id]
        if not dest_area.is_valid_position(position):
            return SessionResult(
                ok=False,
                message=(f"Invalid position {position}. {dest_area.format_grid_bounds_message()}"),
            )
        from campaign_rpg_engine.object import object_footprint_fits_bounds

        original_pos = obj.position
        obj.position = position
        if not object_footprint_fits_bounds(obj, dest_area):
            obj.position = original_pos
            return SessionResult(
                ok=False,
                message=(
                    f"Footprint ({obj.width}x{obj.height}) at {position} extends outside "
                    f"{dest_area_id}. {dest_area.format_grid_bounds_message()}"
                ),
            )

        if source_area_id == dest_area_id and original_pos == position:
            return SessionResult(
                ok=True,
                message=f"Object {object_id} already in {dest_area_id} at {position}.",
            )

        source_area = self.areas[source_area_id]
        for index, candidate in enumerate(source_area.objects):
            if candidate.id == object_id:
                source_area.objects.pop(index)
                break
        dest_area.add_object(obj)
        return SessionResult(
            ok=True,
            message=(
                f"Moved object {object_id} from {source_area_id} to {dest_area_id} at {position}."
            ),
        )

    def emit_area_event(
        self,
        text: str,
        *,
        agent_ids: Sequence[str] | None = None,
    ) -> SessionResult:
        """
        Emit a narrator/GM event into agent memory.

        When *agent_ids* is omitted or empty, all agents in the **active area**
        receive the event and it is appended to that area's ``recent_events``.
        When *agent_ids* is set, only those agents receive the event (resolved
        by id or name across the session); other agents are unaffected and the
        event is not added to ``recent_events``.
        """
        cleaned = text.strip()
        if not cleaned:
            return SessionResult(ok=False, message="Event text cannot be empty.")

        broadcast = not agent_ids
        if broadcast:
            recipients = list(self.area.agents)
        else:
            recipients = []
            for raw_id in agent_ids:
                key = raw_id.strip()
                if not key:
                    continue
                agent = self.get_agent(key)
                if agent is None:
                    return SessionResult(
                        ok=False,
                        message=f"Agent {key!r} not found.",
                    )
                if agent not in recipients:
                    recipients.append(agent)

            if not recipients:
                return SessionResult(
                    ok=False,
                    message="No agents specified for targeted event.",
                )

        session_turn = self.session_turn
        if broadcast:
            record = self.area.append_area_event(
                session_turn=session_turn,
                text=cleaned,
            )
            session_turn = record.session_turn

        from campaign_rpg_engine.observations import broadcast_area_event

        broadcast_area_event(
            session_turn=session_turn,
            text=cleaned,
            agents=recipients,
        )

        if broadcast:
            return SessionResult(ok=True, message=f"Area event: {cleaned}")

        names = ", ".join(agent.name for agent in recipients)
        return SessionResult(ok=True, message=f"Area event to {names}: {cleaned}")

    def set_entity_private_data(self, entity_id: str, private_data: str) -> SessionResult:
        """
        Set app-owned private data on an agent or object.

        Not exposed via CLI; intended for custom clients and campaign-rpg-studio storage.
        """
        cleaned_id = entity_id.strip()
        if not cleaned_id:
            return SessionResult(ok=False, message="Entity id is required.")

        for area in self.areas.values():
            obj = area.get_object_by_id(cleaned_id)
            if obj is not None:
                obj.private_data = private_data
                return SessionResult(
                    ok=True,
                    message=f"Updated private data for {cleaned_id}.",
                )
            agent = area.get_agent_by_id(cleaned_id)
            if agent is not None:
                agent.private_data = private_data
                return SessionResult(
                    ok=True,
                    message=f"Updated private data for {cleaned_id}.",
                )

        return SessionResult(
            ok=False,
            message=f"Entity {cleaned_id!r} not found.",
        )

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def build_prompt(self, name_or_id: str | None = None) -> str:
        """Build the compound-turn LLM prompt for an agent (default: active)."""
        agent = self._resolve_agent_or_active(name_or_id)
        area = self.get_area_for_agent(agent)
        ctx = build_prompt_context(agent, area)
        return self.profile.build_prompt(
            ctx,
            include_examples=self.include_examples,
            blocks=self.get_prompt_blocks(),
            agent=agent,
            area=area,
            session=self,
            vision_units=self.vision_units,
            units_per_tile=self.vision_units_per_tile,
            coordinate_mode=self.coordinate_mode,
            lorebooks=self._lorebooks,
            lorebook_char_budget=self.lorebook_char_budget,
            lorebook_scan_config=self.lorebook_scan_config,
            passive_vision=ctx.passive_vision,
        )

    def list_lorebooks(self) -> list:
        """Return loaded lorebooks sorted by id."""
        from campaign_rpg_engine.lorebook.models import Lorebook

        books: list[Lorebook] = list(self._lorebooks.values())
        return sorted(books, key=lambda book: book.id)

    def get_lorebook(self, book_id: str):
        return self._lorebooks.get(book_id)

    def load_lorebook_from_path(self, path: str):
        """Load a SillyTavern lorebook JSON file into the session (overwrites same id)."""
        from campaign_rpg_engine.lorebook import load_lorebook_from_path

        book = load_lorebook_from_path(path)
        self._lorebooks[book.id] = book
        return book

    def load_lorebook_from_dict(self, data: dict, *, filename: str = ""):
        """Load lorebook data (ST ``entries`` shape) into the session."""
        from campaign_rpg_engine.lorebook import load_lorebook_from_dict

        book = load_lorebook_from_dict(data, filename=filename)
        self._lorebooks[book.id] = book
        return book

    def update_lorebook(self, book) -> None:
        """Replace a lorebook by id."""
        self._lorebooks[book.id] = book

    def remove_lorebook(self, book_id: str) -> bool:
        return self._lorebooks.pop(book_id, None) is not None

    def get_prompt_blocks(self) -> list:
        """Return the session prompt layout (custom or profile default)."""
        from campaign_rpg_engine.prompt_blocks import default_prompt_blocks

        if self._prompt_blocks is not None:
            return list(self._prompt_blocks)
        return default_prompt_blocks()

    def set_prompt_blocks(self, blocks: list) -> str | None:
        """Replace the session prompt layout. Returns an error message or None."""
        from campaign_rpg_engine.prompt_blocks import validate_prompt_blocks

        err = validate_prompt_blocks(blocks)
        if err:
            return err
        self._prompt_blocks = list(blocks)
        return None

    def reset_prompt_blocks(self) -> None:
        """Restore the profile default prompt layout."""
        self._prompt_blocks = None

    def prompt_blocks_use_default(self) -> bool:
        return self._prompt_blocks is None

    def set_vision_units(
        self,
        units: str,
        units_per_tile: int | None,
    ) -> str | None:
        """Update passive-vision distance labels for campaign-rpg-studio."""
        cleaned = units.strip()
        if cleaned and not cleaned.isalpha():
            return "Units must contain letters only."
        if units_per_tile is not None and units_per_tile <= 0:
            return "Units per tile must be a positive number."
        self.vision_units = cleaned
        self.vision_units_per_tile = units_per_tile
        return None

    def set_coordinate_mode(self, mode: str) -> str | None:
        """Set how coordinates appear in LLM prompts (``full`` or ``relative``)."""
        from campaign_rpg_engine.coordinate_mode import (
            SUPPORTED_COORDINATE_MODES,
            normalize_coordinate_mode,
        )

        cleaned = (mode or "").strip().lower()
        if cleaned and cleaned not in SUPPORTED_COORDINATE_MODES:
            supported = ", ".join(sorted(SUPPORTED_COORDINATE_MODES))
            return f"coordinate_mode must be one of: {supported}."
        self.coordinate_mode = normalize_coordinate_mode(cleaned or None)
        return None

    def build_prompt_context_for_agent(self, name_or_id: str | None = None):
        """Build ``PromptContext`` for an agent (default: active)."""
        agent = self._resolve_agent_or_active(name_or_id)
        area = self.get_area_for_agent(agent)
        return build_prompt_context(agent, area)

    def snapshot(
        self,
        *,
        include_private: bool = False,
        include_passive_vision: bool = True,
    ) -> dict:
        """
        JSON-friendly view of the session for web clients.

        Omits ``personality`` and other LLM-only agent fields unless
        ``include_private`` is true. Includes ``passive_vision`` for the
        active agent by default.
        """
        from campaign_rpg_engine.snapshot import build_session_snapshot

        return build_session_snapshot(
            self,
            include_private=include_private,
            include_passive_vision=include_passive_vision,
        )

    def to_save_dict(self) -> dict:
        """Full session save document for CLI export and campaign-rpg-studio download."""
        from campaign_rpg_engine.session_persistence import build_save_snapshot

        return build_save_snapshot(self)

    @classmethod
    def from_snapshot(cls, data: dict) -> Session:
        """Restore a session from a save document produced by :meth:`to_save_dict`."""
        from campaign_rpg_engine.session_persistence import load_session_from_snapshot

        session = load_session_from_snapshot(data)
        if not isinstance(session, cls):
            raise TypeError(f"Expected Session, got {type(session)!r}")
        return session

    def format_debug_state(self, name_or_id: str | None = None) -> str:
        """Human-readable agent/area debug report (CLI ``state`` command)."""
        from campaign_rpg_engine.memory_modules.registry import format_memory_module_label
        from campaign_rpg_engine.memory_modules.rolling_summary import RollingSummaryModule
        from campaign_rpg_engine.memory_modules.salient_turns import SalientTurnsModule

        agent = self._resolve_agent_or_active(name_or_id)
        area = self.get_area_for_agent(agent)
        area_id = self.agent_area.get(agent.id, "?")
        lines = [
            f"Session turns (log label): {self.session_turn}",
            f"Active area (edit scope): {self.active_area_id}",
            f"Agent area: {area_id}",
            f"Active agent: {agent.name} ({agent.id}) at {agent.position}",
            format_memory_module_label(agent.memory.module),
        ]
        module = agent.memory.module
        if isinstance(module, SalientTurnsModule):
            lines.append(f"Memory char budget: {module.char_budget}")
        if isinstance(module, RollingSummaryModule):
            lines.append(f"Memory summary interval: {module.summary_interval}")
            lines.append(f"Memory summary max chars: {module.max_summary_chars}")
            lines.append(f"Memory summary detail tail: {module.summary_tail}")
            lines.append(f"Memory consolidation: {module.consolidation_state}")
            last_summarized = module.last_summarized_turn_number
            lines.append(
                "Memory last summarized at turn: "
                f"{last_summarized if last_summarized else '(never)'}"
            )
            detail_numbers = [t.turn_number for t in module.stored_turns]
            lines.append(f"Memory detail turns: {detail_numbers if detail_numbers else '(none)'}")
            if module.summary:
                lines.append(f"Rolling summary length: {len(module.summary)} chars")
        lines.extend(
            [
                f"Memory own turns (total): {agent.memory.turn_count}",
                f"Looked at (current): {sorted(agent.memory.looked_at)}",
                f"Ever looked at: {sorted(agent.memory.ever_looked)}",
                f"Few-shots in prompts: {'on' if self.include_examples else 'off'}",
            ]
        )
        if agent.memory.turns:
            last = agent.memory.turns[-1]
            lines.append(f"Last turn ({last.turn_number}) steps:")
            for step in last.steps:
                target = f" target={step.target}" if step.target else ""
                content = f" content={step.content!r}" if step.content else ""
                lines.append(f"  - {step.kind}{target}{content}: {step.result}")
            lines.append(f"Composite result: {last.result}")
        lines.append(f"passive_result: {agent.passive_result or '(none)'}")
        objs = [(o.name, o.id, o.position) for o in area.get_objects()]
        lines.append(f"Objects: {objs}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------

    def gate_agent_turn(self, name_or_id: str | None = None) -> SessionResult:
        """Return ok=False if the agent cannot act yet (e.g. memory consolidation)."""
        agent = self._resolve_agent_or_active(name_or_id)
        return self._gate_agent_turn(agent)

    def run_compound_turn(
        self,
        turn: AgentCompoundTurn,
        *,
        agent_id: str | None = None,
    ) -> TurnResult:
        """
        Execute one compound turn for an agent (default: active).

        Increments ``session_turn`` on success (console/log label for witnesses).
        """
        agent = self._resolve_agent_or_active(agent_id)
        self.active_agent_id = agent.id
        area = self.get_area_for_agent(agent)

        gate = self._gate_agent_turn(agent)
        if not gate.ok:
            return TurnResult(ok=False, message=gate.message, agent=agent)

        turn_number = next_turn_number_for_agent(agent)
        pending_session = self.session_turn + 1
        record = run_compound_turn(
            agent,
            area,
            turn,
            turn_number,
            session_turn=pending_session,
            session=self,
            source_area_id=self.agent_area.get(agent.id),
        )
        self.session_turn += 1
        return TurnResult(
            ok=True,
            message=record.result,
            record=record,
            agent=agent,
        )

    # ------------------------------------------------------------------
    # Internal — agent index
    # ------------------------------------------------------------------

    def _rebuild_agent_name_index(self) -> None:
        self._agents_by_name = {}
        for area in self.areas.values():
            for agent in area.agents:
                self._agents_by_name[agent.name.lower()] = agent

    def _register_agent(self, agent: Agent, area_id: str | None = None) -> None:
        resolved = area_id or self.active_area_id
        self.agent_area[agent.id] = resolved
        self._agents_by_name[agent.name.lower()] = agent

    def _unregister_agent(self, agent: Agent) -> None:
        self.agent_area.pop(agent.id, None)
        self._agents_by_name.pop(agent.name.lower(), None)

    def _rename_agent_in_index(self, old_name_lower: str, agent: Agent) -> None:
        if old_name_lower in self._agents_by_name:
            del self._agents_by_name[old_name_lower]
        self._agents_by_name[agent.name.lower()] = agent

    def _resolve_agent_or_active(self, name_or_id: str | None) -> Agent:
        if name_or_id is None:
            return self.get_active_agent()
        agent = self.get_agent(name_or_id)
        if agent is None:
            raise ValueError(f"Agent {name_or_id!r} not found.")
        return agent

    def _gate_agent_turn(self, agent: Agent) -> SessionResult:
        from campaign_rpg_engine.memory_modules.rolling_summary import MemoryConsolidationError

        try:
            agent.memory.ensure_ready_for_turn()
        except MemoryConsolidationError as exc:
            return SessionResult(
                ok=False,
                message=f"Cannot run turn for {agent.name}: {exc}",
            )
        return SessionResult(ok=True, message="")

    def _first_agent_in_area(self, area_id: str) -> Agent | None:
        area = self.areas.get(area_id)
        if area is None or not area.agents:
            return None
        return area.agents[0]

    def _resolve_edit_area(self, area_id: str | None) -> tuple[Area | None, str | None]:
        resolved = area_id or self.active_area_id
        area = self.areas.get(resolved)
        if area is None:
            return None, f"Unknown area {resolved!r}."
        return area, None

    # ------------------------------------------------------------------
    # Typed world-editing API (V0.7.0)
    # ------------------------------------------------------------------

    def create_object(
        self,
        *,
        name: str,
        position: tuple[int, int],
        area_id: str | None = None,
        description: str = "",
        passive_description: str = "",
        appearance: str = "",
        width: int = 1,
        height: int = 1,
        blocks_movement: bool | None = None,
        movement_exceptions: list[str] | None = None,
        hidden: bool | None = None,
        actions: dict[str, ObjectAction] | None = None,
        object_id: str | None = None,
    ) -> WorldMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return WorldMutationResult(ok=False, message=err or "Unknown area.")
        obj, message = create_object_in_area(
            area,
            name=name,
            position=position,
            description=description,
            passive_description=passive_description,
            appearance=appearance,
            width=width,
            height=height,
            blocks_movement=blocks_movement,
            movement_exceptions=movement_exceptions,
            hidden=hidden,
            actions=actions,
            object_id=object_id,
            session=self,
        )
        resolved_area = area_id or self.active_area_id
        result = WorldMutationResult(
            ok=obj is not None,
            message=message,
            object=obj,
            area_id=resolved_area,
        )
        if result.ok and obj is not None:
            self._emit_event("object_created", object=obj, area_id=resolved_area)
        return result

    def create_agent(
        self,
        *,
        name: str,
        position: tuple[int, int],
        area_id: str | None = None,
        personality: str = "",
        passive_description: str = "",
        description: str = "",
        appearance: str = "",
        move_speed: int | None = None,
        memory_module: str | None = None,
        memory_window: int | None = None,
        memory_budget: int | None = None,
        memory_summary_interval: int | None = None,
        memory_summary_max: int | None = None,
        memory_summary_tail: int | None = None,
        blocks_movement: bool | None = None,
        movement_exceptions: list[str] | None = None,
        is_player: bool | None = None,
    ) -> WorldMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return WorldMutationResult(ok=False, message=err or "Unknown area.")
        agent, message = create_agent_in_area(
            area,
            name=name,
            position=position,
            personality=personality,
            passive_description=passive_description,
            description=description,
            appearance=appearance,
            move_speed=move_speed,
            memory_module=memory_module,
            memory_window=memory_window,
            memory_budget=memory_budget,
            memory_summary_interval=memory_summary_interval,
            memory_summary_max=memory_summary_max,
            memory_summary_tail=memory_summary_tail,
            blocks_movement=blocks_movement,
            movement_exceptions=movement_exceptions,
            is_player=is_player,
        )
        if agent is not None:
            self._register_agent(agent, area_id=area_id)
        resolved_area = area_id or self.active_area_id
        result = WorldMutationResult(
            ok=agent is not None,
            message=message,
            agent=agent,
            area_id=resolved_area,
        )
        if result.ok and agent is not None:
            self._emit_event("agent_created", agent=agent, area_id=resolved_area)
        return result

    def delete_object(self, object_id: str) -> WorldMutationResult:
        located = find_object_in_session(self, object_id.strip())
        ok, message = delete_object_in_session(self, object_id)
        result = WorldMutationResult(ok=ok, message=message)
        if result.ok and located is not None:
            area_id, _area, obj = located
            self._emit_event("object_removed", object=obj, object_id=object_id, area_id=area_id)
        return result

    def delete_agent(self, agent_id: str) -> WorldMutationResult:
        delete_result = delete_agent_by_id(self.area, agent_id.strip())
        message = delete_result.message
        deleted_agent = delete_result.deleted_agent
        if delete_result.ok and deleted_agent is not None:
            self._unregister_agent(deleted_agent)
            if self.active_agent_id == deleted_agent.id:
                fallback = self._first_agent_in_area(self.active_area_id)
                if fallback is None:
                    for aid in self.areas:
                        fallback = self._first_agent_in_area(aid)
                        if fallback is not None:
                            break
                if fallback is None:
                    return WorldMutationResult(
                        ok=False,
                        message=f"{message}\nNo agents remain in the session.",
                    )
                self.active_agent_id = fallback.id
                active = self.get_active_agent()
                message = (
                    f"{message}\nActive agent: {active.name} ({active.id}) at {active.position}"
                )
        mutation = WorldMutationResult(
            ok=delete_result.ok,
            message=message,
            agent=deleted_agent,
        )
        if mutation.ok and deleted_agent is not None:
            self._emit_event("agent_removed", agent=deleted_agent)
        return mutation

    def add_object_action(self, object_id: str, action: ObjectAction) -> WorldMutationResult:
        located = find_object_in_session(self, object_id.strip())
        if located is None:
            return WorldMutationResult(
                ok=False,
                message=f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids.",
            )
        area_id, _area, obj = located
        if action.name in obj.actions:
            return WorldMutationResult(
                ok=False,
                message=f"Object {obj.id} already has action '{action.name}'.",
            )
        err = add_object_action_to_object(obj, action)
        if err:
            return WorldMutationResult(ok=False, message=err)
        return WorldMutationResult(
            ok=True,
            message=f"Added action '{action.name}' to {obj.id}.",
            object=obj,
            area_id=area_id,
        )

    def remove_object_action(self, object_id: str, action_name: str) -> WorldMutationResult:
        located = find_object_in_session(self, object_id.strip())
        if located is None:
            return WorldMutationResult(
                ok=False,
                message=f"Object '{object_id}' not found. Use 'objects' or 'list' to look up ids.",
            )
        area_id, _area, obj = located
        if action_name not in obj.actions:
            return WorldMutationResult(
                ok=False,
                message=f"Object {obj.id} has no action '{action_name}'.",
            )
        del obj.actions[action_name]
        return WorldMutationResult(
            ok=True,
            message=f"Removed action '{action_name}' from {obj.id}.",
            object=obj,
            area_id=area_id,
        )

    def edit_object(
        self,
        object_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        passive_description: str | None = None,
        appearance: str | None = None,
        position: tuple[int, int] | None = None,
        target_area_id: str | None = None,
        width: int | None = None,
        height: int | None = None,
        blocks_movement: bool | None = None,
        movement_exceptions: list[str] | None = None,
        hidden: bool | None = None,
    ) -> WorldMutationResult:
        fields: dict[str, str] = {}
        if name is not None:
            fields["name"] = name
        if description is not None:
            fields["desc"] = description
        if passive_description is not None:
            fields["pdesc"] = passive_description
        if appearance is not None:
            fields["appearance"] = appearance
        if position is not None:
            fields["pos"] = f"{position[0]},{position[1]}"
        if target_area_id is not None:
            fields["area"] = target_area_id
        if width is not None:
            fields["width"] = str(width)
        if height is not None:
            fields["height"] = str(height)
        if blocks_movement is not None:
            fields["blocks-movement"] = "true" if blocks_movement else "false"
        if movement_exceptions is not None:
            fields["movement-exception"] = ",".join(movement_exceptions)
        if hidden is not None:
            fields["hidden"] = "true" if hidden else "false"
        result = edit_object_with_fields(self, object_id, fields)
        if result.ok and result.object is not None:
            self._emit_event(
                "object_edited",
                object=result.object,
                area_id=result.area_id,
            )
        return result

    def create_area(
        self,
        area_id: str,
        *,
        description: str = "",
        width: int = 5,
        height: int = 5,
        min_x: int = 0,
        min_y: int = 0,
    ) -> WorldMutationResult:
        result = create_area_in_session(
            self,
            area_id,
            description=description,
            width=width,
            height=height,
            min_x=min_x,
            min_y=min_y,
        )
        return WorldMutationResult(
            ok=result.ok,
            message=result.message,
            area_id=result.area_id,
        )

    def edit_area(
        self,
        area_id: str,
        *,
        description: str | None = None,
        width: int | None = None,
        height: int | None = None,
        min_x: int | None = None,
        min_y: int | None = None,
        max_x: int | None = None,
        max_y: int | None = None,
    ) -> WorldMutationResult:
        result = edit_area_in_session(
            self,
            area_id,
            description=description,
            width=width,
            height=height,
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
        )
        return WorldMutationResult(
            ok=result.ok,
            message=result.message,
            area_id=result.area_id,
        )

    def delete_area(self, area_id: str) -> WorldMutationResult:
        result = delete_area_by_id(self, area_id.strip())
        return WorldMutationResult(
            ok=result.ok,
            message=result.message,
            area_id=result.area_id,
        )

    def edit_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        passive_description: str | None = None,
        appearance: str | None = None,
        personality: str | None = None,
        move_speed: int | None = None,
        position: tuple[int, int] | None = None,
        area_id: str | None = None,
        blocks_movement: bool | None = None,
        movement_exceptions: list[str] | None = None,
        is_player: bool | None = None,
    ) -> WorldMutationResult:
        from campaign_rpg_engine.edit.area_edit import (
            _apply_agent_content_fields,
            _apply_agent_location_fields,
        )

        cleaned = agent_id.strip()
        if not cleaned.startswith("agent_"):
            return WorldMutationResult(
                ok=False,
                message=(
                    "Commands require agent id (e.g. agent_01), not display name. "
                    "Use 'agents' or 'list' to look up ids."
                ),
            )

        located_area_id = self.agent_area.get(cleaned)
        if located_area_id is None or located_area_id not in self.areas:
            return WorldMutationResult(
                ok=False,
                message=(f"Agent '{cleaned}' not found. Use 'agents' or 'list' to look up ids."),
            )
        area = self.areas[located_area_id]
        agent = area.get_agent_by_id(cleaned)
        if agent is None:
            return WorldMutationResult(
                ok=False,
                message=(f"Agent '{cleaned}' not found. Use 'agents' or 'list' to look up ids."),
            )

        fields: dict[str, str] = {}
        if name is not None:
            fields["name"] = name
        if passive_description is not None:
            fields["pdesc"] = passive_description
        if description is not None:
            fields["desc"] = description
        if appearance is not None:
            fields["appearance"] = appearance
        if personality is not None:
            fields["personality"] = personality
        if move_speed is not None:
            fields["move-speed"] = str(move_speed)
        if position is not None:
            fields["pos"] = f"{position[0]},{position[1]}"
        if area_id is not None:
            fields["area"] = area_id.strip()
        if blocks_movement is not None:
            fields["blocks-movement"] = "true" if blocks_movement else "false"
        if movement_exceptions is not None:
            fields["movement-exception"] = ",".join(movement_exceptions)
        if is_player is not None:
            fields["player"] = "true" if is_player else "false"

        if not fields:
            return WorldMutationResult(
                ok=False,
                message=(
                    "At least one field to change is required "
                    "(name, pdesc, desc, appearance, personality, move-speed, area, pos, or player)."
                ),
            )

        old_name_lower = agent.name.lower()
        changes: list[str] = []

        location_err = _apply_agent_location_fields(
            self, cleaned, located_area_id, agent, fields, changes
        )
        if location_err:
            return WorldMutationResult(ok=False, message=location_err)

        current_area_id = located_area_id
        if "area" in fields and fields["area"].strip() != located_area_id:
            current_area_id = fields["area"].strip()
        current_area = self.areas[current_area_id]

        content_err = _apply_agent_content_fields(current_area, agent, cleaned, fields, changes)
        if content_err:
            return WorldMutationResult(ok=False, message=content_err)

        if not changes:
            return WorldMutationResult(ok=False, message=f"No changes applied to {cleaned}.")

        if "name" in changes:
            self._rename_agent_in_index(old_name_lower, agent)

        mutation = WorldMutationResult(
            ok=True,
            message=f"Updated agent {cleaned} ({', '.join(changes)}).",
            agent=agent,
            area_id=current_area_id,
        )
        self._emit_event("agent_edited", agent=agent, area_id=current_area_id)
        if position is not None or "pos" in fields or "area" in fields:
            self._emit_event("agent_moved", agent=agent, area_id=current_area_id)
        return mutation

    # ------------------------------------------------------------------
    # Scene decorations (V1.3.0) — visual-only; excluded from LLM prompts
    # ------------------------------------------------------------------

    def create_decoration(
        self,
        *,
        kind: str,
        image: str,
        area_id: str | None = None,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        z_index: int | None = None,
        repeat: str = "repeat",
        decoration_id: str | None = None,
        label: str = "decor",
    ) -> DecorationMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return DecorationMutationResult(ok=False, message=err or "Unknown area.")
        decoration, message = add_decoration_to_area(
            area,
            kind=kind,
            image=image,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            repeat=repeat,
            decoration_id=decoration_id,
            label=label,
        )
        resolved_area = area_id or self.active_area_id
        return DecorationMutationResult(
            ok=decoration is not None,
            message=message,
            decoration=decoration,
            area_id=resolved_area,
        )

    def update_decoration(
        self,
        decoration_id: str,
        *,
        area_id: str | None = None,
        image: str | None = None,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
        z_index: int | None = None,
        repeat: str | None = None,
    ) -> DecorationMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return DecorationMutationResult(ok=False, message=err or "Unknown area.")
        decoration, message = update_decoration_in_area(
            area,
            decoration_id.strip(),
            image=image,
            x=x,
            y=y,
            width=width,
            height=height,
            z_index=z_index,
            repeat=repeat,
        )
        resolved_area = area_id or self.active_area_id
        return DecorationMutationResult(
            ok=decoration is not None,
            message=message,
            decoration=decoration,
            area_id=resolved_area,
        )

    def delete_decoration(
        self,
        decoration_id: str,
        *,
        area_id: str | None = None,
    ) -> DecorationMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return DecorationMutationResult(ok=False, message=err or "Unknown area.")
        ok, message = remove_decoration_from_area(area, decoration_id.strip())
        resolved_area = area_id or self.active_area_id
        return DecorationMutationResult(
            ok=ok,
            message=message,
            area_id=resolved_area,
        )

    def reorder_decoration(
        self,
        decoration_id: str,
        direction: str,
        *,
        area_id: str | None = None,
    ) -> DecorationMutationResult:
        area, err = self._resolve_edit_area(area_id)
        if area is None:
            return DecorationMutationResult(ok=False, message=err or "Unknown area.")
        direction_clean = direction.strip().lower()
        if direction_clean not in ("up", "down"):
            return DecorationMutationResult(
                ok=False,
                message=f"Invalid direction {direction!r} (use 'up' or 'down').",
            )
        ok, message = reorder_decoration_in_area(
            area,
            decoration_id.strip(),
            direction_clean,  # type: ignore[arg-type]
        )
        decoration = area.get_decoration_by_id(decoration_id.strip()) if ok else None
        resolved_area = area_id or self.active_area_id
        return DecorationMutationResult(
            ok=ok,
            message=message,
            decoration=decoration,
            area_id=resolved_area,
        )
