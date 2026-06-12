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
from src.llm.prompt import build_compound_prompt
from src.llm.schemas import AgentCompoundTurn
from src.memory import TurnRecord
from src.simulation import next_turn_number_for_agent, run_compound_turn
from src.area import Area, create_initial_area
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
        active_agent_id: Optional[str] = None,
        include_examples: bool = False,
    ) -> None:
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
    def from_default(cls, *, include_examples: bool = False) -> Session:
        """Create a session with the standard demo area (Explorer, ball, sign)."""
        return cls(create_initial_area(), include_examples=include_examples)

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

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    def build_prompt(self, name_or_id: Optional[str] = None) -> str:
        """Build the compound-turn LLM prompt for an agent (default: active)."""
        agent = self._resolve_agent_or_active(name_or_id)
        return build_compound_prompt(
            agent,
            self.area,
            include_examples=self.include_examples,
        )

    # ------------------------------------------------------------------
    # Turns
    # ------------------------------------------------------------------

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
        ``memory-modules``). Does not run ``step-compound`` or LLM turns —
        use ``run_compound_turn`` for those.
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
