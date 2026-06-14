"""
session.py

V0.3.0a — runtime session API for Realm-Fabric.

``Session`` owns ``Area`` state, the active agent, and orchestrates compound
turns and stepper-style edit commands. Intended as the single entry point for
CLI, web backends, and other clients.

V0.4.0c1 — multi-area sessions: ``areas``, ``agent_area``, ``active_area_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.agent import Agent
from src.game_profile import GameProfile, default_compound_profile
from src.llm.prompt_context import build_prompt_context
from src.llm.schemas import AgentCompoundTurn
from src.memory import TurnRecord
from src.simulation import next_turn_number_for_agent, run_compound_turn
from src.area import Area
from src.area_edit import (
    create_agent_from_args,
    create_object_from_args,
    delete_agent_by_id,
    delete_object_by_id,
    edit_agent_from_args,
    edit_object_from_args,
    format_agents_list,
    format_full_list,
    format_objects_list,
)
from src.session_area_edit import (
    create_area_from_args,
    delete_area_by_id,
    edit_area_from_args,
)
from src.snapshot import DEFAULT_AREA_ID

__all__ = [
    "CommandResult",
    "DEFAULT_AREA_ID",
    "Session",
    "SessionResult",
    "TurnResult",
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
    record: Optional[TurnRecord] = None
    agent: Optional[Agent] = None


@dataclass(frozen=True)
class CommandResult:
    """Outcome of ``run_command`` (area edits and read-only listings)."""

    ok: bool
    message: str


class Session:
    """
    Owns simulation state and exposes turn + command operations.

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
        active_agent_id: Optional[str] = None,
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

    def get_agent(self, name_or_id: str) -> Optional[Agent]:
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
            message=(
                f"Active agent: {agent.name} ({agent.id}) at {agent.position} "
                f"[{area_id}]"
            ),
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

    def emit_area_event(self, text: str) -> SessionResult:
        """
        Broadcast a room-wide narrator/GM event to all agents in the active area.

        Does not consume a turn or increment ``session_turn``.
        """
        cleaned = text.strip()
        if not cleaned:
            return SessionResult(ok=False, message="Event text cannot be empty.")

        area = self.area
        record = area.append_area_event(
            session_turn=self.session_turn,
            text=cleaned,
        )
        from src.observations import broadcast_area_event

        broadcast_area_event(
            area,
            session_turn=record.session_turn,
            text=record.text,
        )
        return SessionResult(ok=True, message=f"Area event: {record.text}")

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def build_prompt(self, name_or_id: Optional[str] = None) -> str:
        """Build the compound-turn LLM prompt for an agent (default: active)."""
        agent = self._resolve_agent_or_active(name_or_id)
        area = self.get_area_for_agent(agent)
        ctx = build_prompt_context(agent, area)
        return self.profile.build_prompt(
            ctx,
            include_examples=self.include_examples,
        )

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
        from src.snapshot import build_session_snapshot

        return build_session_snapshot(
            self,
            include_private=include_private,
            include_passive_vision=include_passive_vision,
        )

    def format_debug_state(self, name_or_id: Optional[str] = None) -> str:
        """Human-readable agent/area debug report (CLI ``state`` command)."""
        from src.memory_modules.registry import format_memory_module_label
        from src.memory_modules.rolling_summary import RollingSummaryModule
        from src.memory_modules.salient_turns import SalientTurnsModule

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
            lines.append(
                "Memory detail turns: "
                f"{detail_numbers if detail_numbers else '(none)'}"
            )
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

    def gate_agent_turn(self, name_or_id: Optional[str] = None) -> SessionResult:
        """Return ok=False if the agent cannot act yet (e.g. memory consolidation)."""
        agent = self._resolve_agent_or_active(name_or_id)
        return self._gate_agent_turn(agent)

    def run_compound_turn(
        self,
        turn: AgentCompoundTurn,
        *,
        agent_id: Optional[str] = None,
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
        )
        self.session_turn += 1
        return TurnResult(
            ok=True,
            message=record.result,
            record=record,
            agent=agent,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def run_command(self, line: str) -> CommandResult:
        """
        Parse and run a stepper-style command line.

        Supports area edits (``create-object``, ``edit-agent``, …) and
        read-only listings (``list``, ``objects``, ``agents``, ``effects``,
        ``memory-modules``). ``emit-event`` broadcasts room-wide events.
        Does not run ``step-compound`` or LLM turns — use ``run_compound_turn``
        for those.
        """
        line = line.strip()
        if not line:
            return CommandResult(ok=False, message="Empty command.")

        parts = line.split(None, 1)
        cmd = parts[0].lower().replace("-", "_")
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "create_object": self._cmd_create_object,
            "edit_object": self._cmd_edit_object,
            "delete_object": self._cmd_delete_object,
            "create_agent": self._cmd_create_agent,
            "edit_agent": self._cmd_edit_agent,
            "delete_agent": self._cmd_delete_agent,
            "objects": self._cmd_objects,
            "agents": self._cmd_agents,
            "list": self._cmd_list,
            "effects": self._cmd_effects,
            "memory_modules": self._cmd_memory_modules,
            "emit_event": self._cmd_emit_event,
            "active_area": self._cmd_active_area,
            "areas": self._cmd_areas,
            "create_area": self._cmd_create_area,
            "edit_area": self._cmd_edit_area,
            "delete_area": self._cmd_delete_area,
        }

        handler = handlers.get(cmd)
        if handler is None:
            return CommandResult(
                ok=False,
                message=f"Unknown command: {parts[0]!r}",
            )
        return handler(arg)

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

    def _resolve_agent_or_active(self, name_or_id: Optional[str]) -> Agent:
        if name_or_id is None:
            return self.get_active_agent()
        agent = self.get_agent(name_or_id)
        if agent is None:
            raise ValueError(f"Agent {name_or_id!r} not found.")
        return agent

    def _gate_agent_turn(self, agent: Agent) -> SessionResult:
        from src.memory_modules.rolling_summary import MemoryConsolidationError

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

    # ------------------------------------------------------------------
    # Internal — command handlers
    # ------------------------------------------------------------------

    def _cmd_create_object(self, arg: str) -> CommandResult:
        _obj, message = create_object_from_args(self.area, arg)
        ok = message.startswith("Created object")
        return CommandResult(ok=ok, message=message)

    def _cmd_edit_object(self, arg: str) -> CommandResult:
        message = edit_object_from_args(self.area, arg)
        ok = not message.startswith("Error") and not message.startswith("Unknown")
        return CommandResult(ok=ok, message=message)

    def _cmd_delete_object(self, arg: str) -> CommandResult:
        message = delete_object_by_id(self.area, arg)
        ok = message.startswith("Deleted object")
        return CommandResult(ok=ok, message=message)

    def _cmd_create_agent(self, arg: str) -> CommandResult:
        agent, message = create_agent_from_args(self.area, arg)
        if agent is not None:
            self._register_agent(agent)
        ok = agent is not None
        return CommandResult(ok=ok, message=message)

    def _cmd_edit_agent(self, arg: str) -> CommandResult:
        result = edit_agent_from_args(self.area, arg)
        if result.ok and result.agent is not None and result.old_name_lower:
            self._rename_agent_in_index(result.old_name_lower, result.agent)
        return CommandResult(ok=result.ok, message=result.message)

    def _cmd_delete_agent(self, arg: str) -> CommandResult:
        result = delete_agent_by_id(self.area, arg.strip())
        message = result.message
        if result.ok and result.deleted_agent is not None:
            self._unregister_agent(result.deleted_agent)
            if self.active_agent_id == result.deleted_agent.id:
                fallback = self._first_agent_in_area(self.active_area_id)
                if fallback is None:
                    for area_id in self.areas:
                        fallback = self._first_agent_in_area(area_id)
                        if fallback is not None:
                            break
                if fallback is None:
                    return CommandResult(
                        ok=False,
                        message=f"{message}\nNo agents remain in the session.",
                    )
                self.active_agent_id = fallback.id
                active = self.get_active_agent()
                message = (
                    f"{message}\n"
                    f"Active agent: {active.name} ({active.id}) at {active.position}"
                )
        return CommandResult(ok=result.ok, message=message)

    def _cmd_objects(self, _arg: str) -> CommandResult:
        return CommandResult(ok=True, message=format_objects_list(self.area))

    def _cmd_agents(self, _arg: str) -> CommandResult:
        return CommandResult(
            ok=True,
            message=format_agents_list(self.area, self.get_active_agent()),
        )

    def _cmd_list(self, _arg: str) -> CommandResult:
        return CommandResult(
            ok=True,
            message=format_full_list(self.area, self.get_active_agent()),
        )

    def _cmd_effects(self, _arg: str) -> CommandResult:
        from src.object_effects import format_effects_list

        return CommandResult(ok=True, message=format_effects_list())

    def _cmd_memory_modules(self, _arg: str) -> CommandResult:
        from src.memory_modules.registry import format_memory_modules_list

        return CommandResult(ok=True, message=format_memory_modules_list())

    def _cmd_emit_event(self, arg: str) -> CommandResult:
        from src.area_event import parse_area_event_arg

        text = parse_area_event_arg(arg)
        if not text:
            return CommandResult(
                ok=False,
                message='Usage: emit-event "Event description."',
            )
        result = self.emit_area_event(text)
        return CommandResult(ok=result.ok, message=result.message)

    def _cmd_active_area(self, arg: str) -> CommandResult:
        area_id = arg.strip()
        if not area_id:
            return CommandResult(
                ok=False,
                message=f"Usage: active-area <area_id>  (known: {', '.join(sorted(self.areas))})",
            )
        result = self.set_active_area(area_id)
        return CommandResult(ok=result.ok, message=result.message)

    def _cmd_areas(self, _arg: str) -> CommandResult:
        lines = ["Areas:"]
        for area_id in sorted(self.areas):
            marker = " *" if area_id == self.active_area_id else ""
            agent_count = len(self.areas[area_id].agents)
            obj_count = len(self.areas[area_id].get_objects())
            lines.append(
                f"  {area_id}{marker} — {agent_count} agent(s), {obj_count} object(s)"
            )
        return CommandResult(ok=True, message="\n".join(lines))

    def _cmd_create_area(self, arg: str) -> CommandResult:
        result = create_area_from_args(self, arg)
        return CommandResult(ok=result.ok, message=result.message)

    def _cmd_edit_area(self, arg: str) -> CommandResult:
        result = edit_area_from_args(self, arg)
        return CommandResult(ok=result.ok, message=result.message)

    def _cmd_delete_area(self, arg: str) -> CommandResult:
        result = delete_area_by_id(self, arg.strip())
        return CommandResult(ok=result.ok, message=result.message)
