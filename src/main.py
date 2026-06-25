"""
main.py

Entry point for manual stepping — V0.3.0d reference CLI on ``Session``.

Supports:
- step-compound         : manually simulate one compound turn (move / look / speak)
- step-nav / step-action: debug isolated phases without LLM
- list / objects / agents : list area entities (read-only, no turn)
- create-object / edit-object / delete-object : edit objects at runtime
- create-agent / edit-agent / delete-agent   : edit agents at runtime
- run                   : LLM turn for the active agent
- switch <name>         : change active agent without a turn (no LLM)
- quit / exit           : leave the simulation.
- vision / state        : print current passive vision or agent/area state.

Typing an agent's name (e.g. "Explorer") runs an LLM turn for that agent.
Use switch to inspect another agent's vision/state without consuming a turn.

Run with (from the project root):

    uv run python src/main.py
    uv run python src/main.py --with-fewshots
    uv run realm

Inside, use 'fewshots off' to toggle at runtime too.
"""

import argparse
import os
import string
import sys

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cmd

from src.agent import Agent
from src.compound_stepper import parse_compound_step_arg
from src.game_profile import default_compound_profile
from src.log_utils import close_file_logging, log_error, log_turn, setup_file_logging
from src.llm.schemas import AgentCompoundTurn
from src.perception import build_passive_vision
from src.session import Session
from src.simulation import execute_action_phase, execute_nav_phase


class ManualStepper(cmd.Cmd):
    """Reference CLI client — all simulation state lives on ``Session``."""

    identchars = string.ascii_letters + string.digits + "_-"

    intro = (
        "Realm-Fabric V0.3 Manual Stepper\n"
        "Type 'help' or '?' for commands.\n"
        "- 'step-compound ...'   : manual compound turn (e.g. step-compound 2,3 look obj_ball_01 speak Hi)\n"
        "- 'run' : LLM turn for the active agent\n"
        "- Type an agent's name (e.g. 'Explorer') : LLM turn for that agent\n"
        "- 'switch <name>' : change active agent (no turn, no LLM)\n"
        "- 'list' / 'objects' / 'agents' / 'effects' : list area entities (no turn)\n"
        "- 'create-object' / 'edit-object' / 'delete-object' : edit objects (see 'effects')\n"
        "- 'create-agent' / 'edit-agent' / 'delete-agent' : edit agents (see 'memory-modules')\n"
        "- 'add-memory-module <path>' : load a custom memory module from a .py file\n"
        "- 'load-lorebook <path>' : load a SillyTavern lorebook JSON file\n"
        "- 'lorebooks' : list loaded lorebooks\n"
        "- 'emit-event \"...\"' : room-wide event all agents perceive (no turn)\n"
        "- 'prompt' : show the full prompt that would be sent to the LLM\n"
        "- 'fewshots on/off' : toggle few-shot examples in prompts (off by default)\n"
        "- 'export-session <path>' / 'import-session <path>' : save/load full session JSON\n"
        "Sign updates: edit-object obj_sign_01 desc \"new text\" (pdesc for glance text)\n"
        "CLI flags: --log , --with-fewshots\n"
        "Example: Explorer\n"
        "Example: step-compound 2,3 look obj_ball_01 speak Hello.\n"
        "Example: list\n"
        "Example: edit-object obj_sign_01 desc \"Updated sign text.\"\n"
    )
    prompt = "(realm) "

    def __init__(
        self,
        include_examples: bool = False,
        *,
        session: Session | None = None,
    ):
        super().__init__()
        self.session = session or Session.from_profile(
            default_compound_profile(),
            include_examples=include_examples,
        )

    # ------------------------------------------------------------------
    # Session delegation (backward compat for tests)
    # ------------------------------------------------------------------

    @property
    def area(self):
        return self.session.area

    @property
    def agent(self) -> Agent:
        return self.session.get_active_agent()

    @agent.setter
    def agent(self, agent: Agent) -> None:
        self.session.active_agent_id = agent.id

    @property
    def session_turn(self) -> int:
        return self.session.session_turn

    @property
    def include_examples(self) -> bool:
        return self.session.include_examples

    @include_examples.setter
    def include_examples(self, value: bool) -> None:
        self.session.include_examples = value

    def _print_command(self, line: str) -> None:
        result = self.session.run_command(line.strip())
        print(result.message)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def do_run(self, arg):
        """
        Run an LLM turn for the currently active agent.

        Usage:
            run
        """
        if arg.strip():
            print("Usage: run  (no arguments — uses the active agent)")
            return
        self._run_llm_turn_for_agent(self.agent)

    def do_switch(self, arg):
        """
        Change the active agent without consuming a turn or calling the LLM.

        Usage:
            switch Goblin
            switch Explorer
        """
        name = arg.strip()
        if not name:
            print("Usage: switch <agent name>")
            print("Use 'agents' or 'list' to see agent names.")
            return

        result = self.session.set_active_agent(name)
        if not result.ok:
            print(f"Agent '{name}' not found. Use 'agents' or 'list' to see agents.")
            return
        print(result.message)

    def do_vision(self, arg):
        """Show current passive vision."""
        area = self.session.get_area_for_agent(self.agent)
        print(build_passive_vision(self.agent, area))

    def do_prompt(self, arg):
        """Show the compound turn prompt for the active agent."""
        prompt = self.session.build_prompt()
        print(
            f"[Compound turn prompt - {len(prompt)} chars] "
            f"(fewshots={'on' if self.include_examples else 'off'})\n"
        )
        print(prompt)

    def do_state(self, arg):
        """Print basic agent and area state (for the currently active agent)."""
        print(self.session.format_debug_state())

    def do_objects(self, arg):
        """List all objects in the area. Does not consume a turn."""
        self._print_command("objects")

    def do_effects(self, arg):
        """List registered object interaction effects (read-only)."""
        self._print_command("effects")

    def do_memory_modules(self, arg):
        """List registered agent memory modules (read-only)."""
        self._print_command("memory-modules")

    def do_add_memory_module(self, arg):
        """Load a custom memory module from a .py file. Usage: add-memory-module <path>"""
        path = arg.strip()
        if not path:
            print("Usage: add-memory-module <path>")
            return
        from src.memory_modules.registry import register_memory_module_from_path

        try:
            module_id = register_memory_module_from_path(path)
        except (OSError, ValueError, TypeError) as exc:
            print(f"Could not load memory module: {exc}")
            return
        print(f"Loaded memory module {module_id!r} from {path}")

    def do_load_lorebook(self, arg):
        """Load a SillyTavern lorebook JSON file. Usage: load-lorebook <path>"""
        path = arg.strip()
        if not path:
            print("Usage: load-lorebook <path>")
            return
        try:
            book = self.session.load_lorebook_from_path(path)
        except (OSError, ValueError, TypeError) as exc:
            print(f"Could not load lorebook: {exc}")
            return
        print(
            f"Loaded lorebook {book.id!r} ({book.name}, {len(book.entries)} entries) from {path}"
        )

    def do_lorebooks(self, arg):
        """List loaded lorebooks (read-only)."""
        from src.lorebook.listing import format_lorebooks_list

        print(format_lorebooks_list(self.session.list_lorebooks()))

    def do_agents(self, arg):
        """List all agents in the active area. Does not consume a turn."""
        self._print_command("agents")

    def do_areas(self, arg):
        """List all areas in the session ( * marks active edit scope)."""
        self._print_command("areas")

    def do_active_area(self, arg):
        """
        Change the active area (GM edit / emit scope) without a turn.

        Usage:
            active-area room
            active-area hall
        """
        area_id = arg.strip()
        if not area_id:
            print("Usage: active-area <area_id>  (see 'areas')")
            return
        self._print_command(f"active-area {area_id}")

    def do_create_area(self, arg):
        """
        Add a new empty area to the session.

        Usage:
            create-area id attic desc "A dusty attic." width 6 height 6
        """
        self._print_command(f"create-area {arg}")

    def do_edit_area(self, arg):
        """
        Edit an area's description and/or grid bounds.

        Usage:
            edit-area hall desc "A longer hall."
            edit-area attic width 8 height 8
        """
        self._print_command(f"edit-area {arg}")

    def do_delete_area(self, arg):
        """
        Delete an empty area (no agents or objects).

        Usage:
            delete-area attic
        """
        self._print_command(f"delete-area {arg}")

    def do_list(self, arg):
        """List all agents and objects. Does not consume a turn."""
        self._print_command("list")

    def do_create_object(self, arg):
        """Create a new object in the area."""
        self._print_command(f"create-object {arg}")

    def do_emit_event(self, arg):
        """Broadcast a room-wide event to all agents (no turn consumed)."""
        self._print_command(f"emit-event {arg}")

    def do_edit_object(self, arg):
        """Edit an existing object by id."""
        self._print_command(f"edit-object {arg}")

    def do_delete_object(self, arg):
        """Delete an object by id."""
        self._print_command(f"delete-object {arg}")

    def do_create_agent(self, arg):
        """Create a new agent in the area. Does not change the active agent."""
        self._print_command(f"create-agent {arg}")

    def do_edit_agent(self, arg):
        """Edit an existing agent by id."""
        self._print_command(f"edit-agent {arg}")

    def do_delete_agent(self, arg):
        """Delete an agent by id. Cannot delete the last agent."""
        self._print_command(f"delete-agent {arg}")

    def do_fewshots(self, arg):
        """
        Toggle or show the few-shot examples setting for prompts.

        Usage:
            fewshots
            fewshots on
            fewshots off
        """
        arg = arg.strip().lower()
        if arg in ("on", "yes", "true", "1", "enable"):
            self.include_examples = True
            print("Few-shot examples: ENABLED (included in compound turn prompts)")
        elif arg in ("off", "no", "false", "0", "disable"):
            self.include_examples = False
            print("Few-shot examples: DISABLED (removed from prompts to save tokens)")
        else:
            status = "ENABLED" if self.include_examples else "DISABLED"
            print(f"Few-shot examples are currently {status}.")
            print("Use 'fewshots on' or 'fewshots off' to change.")

    def do_step_compound(self, arg):
        """
        Manually simulate one compound turn without the LLM.

        Usage:
            step-compound 2,3 look obj_ball_01 speak Hello.
            step-compound - look obj_ball_01
            step-compound 2,3 interact obj_cookie_01 eat
        """
        if not arg.strip():
            print(
                "Usage: step-compound <move|-|[stay]> [look ID] "
                "[speak text... | interact OBJ_ID ACTION]"
            )
            return
        try:
            parsed = parse_compound_step_arg(arg)
        except Exception as e:
            log_error("Invalid step-compound", e)
            print(f"Invalid step-compound: {e}")
            return
        self._run_manual_compound(parsed.turn)

    def do_step_nav(self, arg):
        """
        Debug: run navigation move only (no TurnRecord, no session_turn increment).

        Usage:
            step-nav 2,3
            step-nav -
        """
        if arg.strip().lower() in ("-", "stay", ""):
            print("Staying in place (no move).")
            return
        nav = AgentCompoundTurn(
            reasoning="[manual step-nav]",
            move=arg.strip(),
            action="none",
        )
        for step in execute_nav_phase(self.agent, self.session.get_area_for_agent(self.agent), nav):
            print(step.result)

    def do_step_action(self, arg):
        """
        Debug: run action phase only from current position (no TurnRecord).

        Usage:
            step-action look obj_ball_01
            step-action speak Hello there.
            step-action interact obj_cookie_01 eat
        """
        try:
            parsed = parse_compound_step_arg(f"- {arg}" if arg.strip() else "-")
        except Exception as e:
            print(f"Invalid step-action: {e}")
            return
        for step in execute_action_phase(self.agent, self.session.get_area_for_agent(self.agent), parsed.turn):
            print(step.result)

    def _run_manual_compound(self, turn: AgentCompoundTurn) -> None:
        agent = self.agent
        gate = self.session.gate_agent_turn()
        if not gate.ok:
            print(gate.message)
            return
        turn_number = agent.memory.turn_count + 1
        result = self.session.run_compound_turn(turn)
        if not result.ok or result.record is None:
            print(result.message)
            return
        log_turn(
            self.session_turn,
            result=(
                f"Agent: {agent.name} (turn {turn_number})\n"
                f"Steps: {len(result.record.steps)}\n"
                f"Result: {result.record.result}"
            ),
            always_to_file=False,
        )
        print(result.message)

    def onecmd(self, line):
        """Support hyphenated commands like create-object and edit-agent."""
        line = self.precmd(line)
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.postcmd(self.emptyline(), line)
        if not cmd:
            return self.postcmd(self.default(line), line)
        self.lastcmd = line
        func = getattr(self, "do_" + cmd.replace("-", "_").lower(), None)
        if func is None:
            return self.postcmd(self.default(line), line)
        return self.postcmd(func(arg), line)

    def do_help(self, arg):
        """Show help; supports hyphenated command names."""
        if arg:
            arg = arg.replace("-", "_")
        return super().do_help(arg)

    def do_export_session(self, arg):
        """Write the full session to a JSON file. Usage: export-session path.json"""
        path = arg.strip()
        if not path:
            print("Usage: export-session <path>")
            return
        import json

        try:
            data = self.session.to_save_dict()
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
                handle.write("\n")
        except OSError as exc:
            print(f"Could not write session file: {exc}")
            return
        except Exception as exc:
            print(f"Export failed: {exc}")
            return
        print(
            f"Session exported to {path} "
            f"(turn {self.session.session_turn}, "
            f"{len(self.session.areas)} area(s), "
            f"{sum(len(a.agents) for a in self.session.areas.values())} agent(s))."
        )

    def do_import_session(self, arg):
        """Load a session from a JSON file. Usage: import-session path.json"""
        path = arg.strip()
        if not path:
            print("Usage: import-session <path>")
            return
        import json

        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            print(f"Could not read session file: {exc}")
            return
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}")
            return
        try:
            self.session = Session.from_snapshot(data)
        except (ValueError, TypeError) as exc:
            print(f"Import failed: {exc}")
            return
        agent = self.session.get_active_agent()
        print(
            f"Session imported from {path} "
            f"(turn {self.session.session_turn}, active agent {agent.name}, "
            f"{len(self.session.areas)} area(s))."
        )

    def do_quit(self, arg):
        """Exit the simulator."""
        print("Goodbye.")
        return True

    def do_exit(self, arg):
        """Exit the simulator."""
        return self.do_quit(arg)

    def do_EOF(self, arg):
        """Ctrl-D to exit."""
        print()
        return self.do_quit(arg)

    def default(self, line: str):
        """Typing an agent name runs an LLM turn for that agent."""
        line = line.strip()
        if not line:
            return

        agent = self.session.get_agent(line)
        if agent is not None:
            self._run_llm_turn_for_agent(agent)
            return

        super().default(line)

    def _run_llm_turn_for_agent(self, agent: Agent):
        """Single LLM call for one compound agent turn."""
        self.agent = agent
        gate = self.session.gate_agent_turn()
        if not gate.ok:
            print(gate.message)
            return

        print(f"\n=== Running LLM for {agent.name} ===")

        try:
            from src.llm.client import get_compound_turn

            prompt = self.session.build_prompt()
            print(
                f"Prompt: {len(prompt)} chars "
                f"(fewshots={'on' if self.include_examples else 'off'})"
            )
            print("Calling LLM...")
            response = get_compound_turn(prompt)
            compound_turn: AgentCompoundTurn = response.parsed
            turn_number = agent.memory.turn_count + 1
            pending_session = self.session_turn + 1

            log_turn(
                pending_session,
                phase="compound",
                prompt=prompt,
                raw_output=response.raw_response,
                parsed_turn=compound_turn.model_dump(),
                tokens={
                    "prompt": response.prompt_tokens,
                    "completion": response.completion_tokens,
                    "total": response.total_tokens,
                }
                if response.total_tokens is not None
                else None,
                always_to_file=False,
            )

            result = self.session.run_compound_turn(compound_turn)
            if not result.ok or result.record is None:
                print(result.message)
                return

            print(
                f"\n--- {agent.name} turn {turn_number} "
                f"(session {self.session_turn}) ---"
            )
            for step in result.record.steps:
                print(f"  [{step.kind}] {step.result}")
            print(f"Composite: {result.message}")
            print()

        except Exception as e:
            log_error(f"LLM call failed for {agent.name}", e)
            import traceback

            traceback.print_exc()


def main():
    """Entry point for the manual stepper (used by ``uv run realm``)."""
    parser = argparse.ArgumentParser(description="Realm-Fabric V0.3 Manual Stepper")
    parser.add_argument(
        "--log",
        action="store_true",
        help="Enable full logging of every turn to a timestamped file in logs/",
    )
    parser.add_argument(
        "--with-fewshots",
        action="store_true",
        help="Include few-shot examples in the compound turn prompt (off by default)",
    )
    args = parser.parse_args()

    log_path = None
    if args.log:
        log_path = setup_file_logging()

    try:
        stepper = ManualStepper(include_examples=args.with_fewshots)
        stepper.cmdloop()
    finally:
        if log_path:
            close_file_logging()
            print(f"\nFull log written to: {log_path}")


if __name__ == "__main__":
    main()
