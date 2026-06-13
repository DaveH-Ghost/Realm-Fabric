"""
session.py

V0.3.0a — runtime session API for Realm-Fabric.

``Session`` owns ``Area`` state, the active agent, and orchestrates compound
turns and stepper-style edit commands. Intended as the single entry point for
CLI, web backends, and other clients.
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
        area: Area,
        *,
        profile: GameProfile | None = None,
        active_agent_id: Optional[str] = None,
        include_examples: bool = False,
    ) -> None:
        self.profile = profile or default_compound_profile()
        self.area = area
        self.include_examples = include_examples
        self.session_turn = 0
        self._agents_by_name: dict[str, Agent] = {}
        self._rebuild_agent_name_index()
        if active_agent_id is None:
            if not area.agents:
                raise ValueError("Area has no agents")
            active_agent_id = area.agents[0].id
        agent = self.get_agent(active_agent_id)
        if agent is None:
            raise ValueError(f"Unknown active_agent_id: {active_agent_id!r}")
        self.active_agent_id = agent.id

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
    # Agent resolution
    # ------------------------------------------------------------------

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
            return self.area.get_agent_by_id(key)
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
        return SessionResult(
            ok=True,
            message=f"Active agent: {agent.name} ({agent.id}) at {agent.position}",
        )

    def emit_area_event(self, text: str) -> SessionResult:
        """
        Broadcast a room-wide narrator/GM event to all agents.

        Does not consume a turn or increment ``session_turn``.
        """
        cleaned = text.strip()
        if not cleaned:
            return SessionResult(ok=False, message="Event text cannot be empty.")

        record = self.area.append_area_event(
            session_turn=self.session_turn,
            text=cleaned,
        )
        from src.observations import broadcast_area_event

        broadcast_area_event(
            self.area,
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
        ctx = build_prompt_context(agent, self.area)
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
        JSON-friendly view of the session's area for web clients.

        Omits ``personality`` and other LLM-only agent fields unless
        ``include_private`` is true. Includes ``passive_vision`` for the
        active agent by default.
        """
        from src.snapshot import build_area_snapshot

        return build_area_snapshot(
            self.area,
            active_agent_id=self.active_agent_id,
            session_turn=self.session_turn,
            include_private=include_private,
            include_passive_vision=include_passive_vision,
        )

    def format_debug_state(self, name_or_id: Optional[str] = None) -> str:
        """Human-readable agent/area debug report (CLI ``state`` command)."""
        from src.memory_modules.registry import format_memory_module_label
        from src.memory_modules.rolling_summary import RollingSummaryModule
        from src.memory_modules.salient_turns import SalientTurnsModule

        agent = self._resolve_agent_or_active(name_or_id)
        lines = [
            f"Session turns (log label): {self.session_turn}",
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
        objs = [(o.name, o.id, o.position) for o in self.area.get_objects()]
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

        gate = self._gate_agent_turn(agent)
        if not gate.ok:
            return TurnResult(ok=False, message=gate.message, agent=agent)

        turn_number = next_turn_number_for_agent(agent)
        pending_session = self.session_turn + 1
        record = run_compound_turn(
            agent,
            self.area,
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
        self._agents_by_name = {a.name.lower(): a for a in self.area.agents}

    def _register_agent(self, agent: Agent) -> None:
        self._agents_by_name[agent.name.lower()] = agent

    def _unregister_agent(self, agent: Agent) -> None:
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
                self.active_agent_id = self.area.agents[0].id
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
