"""
main.py

Entry point for manual stepping in V0.2.5 (single LLM call per compound turn).

Supports:
- step-compound         : manually simulate one compound turn (move / look / speak)
- step-nav / step-action: debug isolated phases without LLM
- list / objects / agents : list world entities (read-only, no turn)
- create-object / edit-object / delete-object : edit objects at runtime
- create-agent / edit-agent / delete-agent   : edit agents at runtime
- run                   : LLM turn for the active agent
- switch <name>         : change active agent without a turn (no LLM)
- quit / exit           : leave the simulation.
- vision / state        : print current passive vision or agent/world state.

Typing an agent's name (e.g. "Explorer") runs an LLM turn for that agent.
Use switch to inspect another agent's vision/state without consuming a turn.

Future: real autonomous runs, better logging, etc.

Run with (from the project root):

    # Easiest way (few-shots OFF by default for token efficiency)
    uv run python src/main.py

    # To include few-shot examples in the compound turn prompt:
    uv run python src/main.py --with-fewshots

    # After `uv sync`, you can also do:
    # uv run realm
    # (if the entry point was picked up)

    # To use real LLM calls, copy .env.example to .env and add your OPENROUTER_API_KEY

    # Inside, use 'fewshots off' to toggle at runtime too.

"""

import argparse
import os
import string
import sys

# Ensure 'src' package is importable no matter how this script is launched
# (uv run, python src/main.py, double-click, etc.)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cmd

from src.log_utils import close_file_logging, log_error, log_turn, setup_file_logging
from src.world import create_initial_world
from src.compound_stepper import parse_compound_step_arg
from src.simulation import (
    execute_action_phase,
    execute_nav_phase,
    next_turn_number_for_agent,
    run_compound_turn,
)
from src.llm.schemas import AgentCompoundTurn
from src.llm.prompt import build_compound_prompt
from src.perception import build_passive_vision
from src.world_edit import (
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

# Lazy import for the client so you can run the manual stepper
# without an OPENROUTER_API_KEY


class ManualStepper(cmd.Cmd):
    # Allow hyphenated commands (create-object, edit-agent, etc.)
    identchars = string.ascii_letters + string.digits + "_-"

    intro = (
        "Realm-Fabric V0.2.5 Manual Stepper\n"
        "Type 'help' or '?' for commands.\n"
        "- 'step-compound ...'   : manual compound turn (e.g. step-compound 2,3 look obj_ball_01 speak Hi)\n"
        "- 'run' : LLM turn for the active agent\n"
        "- Type an agent's name (e.g. 'Explorer') : LLM turn for that agent\n"
        "- 'switch <name>' : change active agent (no turn, no LLM)\n"
        "- 'list' / 'objects' / 'agents' / 'effects' : list world entities (no turn)\n"
        "- 'create-object' / 'edit-object' / 'delete-object' : edit objects (see 'effects')\n"
        "- 'create-agent' / 'edit-agent' / 'delete-agent' : edit agents (see 'memory-modules')\n"
        "- 'prompt' : show the full prompt that would be sent to the LLM\n"
        "- 'fewshots on/off' : toggle few-shot examples in prompts (off by default)\n"
        "Sign updates: edit-object obj_sign_01 desc \"new text\" (pdesc for glance text)\n"
        "CLI flags: --log , --with-fewshots\n"
        "Example: Explorer\n"
        "Example: step-compound 2,3 look obj_ball_01 speak Hello.\n"
        "Example: list\n"
        "Example: edit-object obj_sign_01 desc \"Updated sign text.\"\n"
    )
    prompt = "(realm) "

    def __init__(self, include_examples: bool = False):
        super().__init__()
        self.world = create_initial_world()
        # Case-insensitive name dispatch for default() and switch
        self.agents: dict[str, "Agent"] = {}
        self._rebuild_agents_dict_from_world()
        self.agent = self.world.get_agent()  # current active agent
        self.session_turn = 0  # console/log label only; not stored in TurnRecord
        self.include_examples = include_examples  # for prompt builder, toggleable for experiments

    # ------------------------------------------------------------------
    # Agent dict sync (Section 3)
    # ------------------------------------------------------------------

    def _register_agent(self, agent: "Agent") -> None:
        """Add an agent to the name dispatch dict after create-agent."""
        self.agents[agent.name.lower()] = agent

    def _unregister_agent(self, agent: "Agent") -> None:
        """Remove an agent from the dict after delete-agent."""
        self.agents.pop(agent.name.lower(), None)

    def _rename_agent_in_dict(self, old_name_lower: str, agent: "Agent") -> None:
        """Update dict keys after edit-agent name change."""
        if old_name_lower in self.agents:
            del self.agents[old_name_lower]
        self.agents[agent.name.lower()] = agent

    def _resolve_agent_by_name(self, name: str) -> "Agent | None":
        """Case-insensitive agent lookup via dispatch dict (rebuilds if stale)."""
        key = name.strip().lower()
        agent = self.agents.get(key)
        if agent is not None:
            return agent
        self._rebuild_agents_dict_from_world()
        return self.agents.get(key)

    def _rebuild_agents_dict_from_world(self) -> None:
        """Rebuild name dispatch dict from world.agents."""
        self.agents = {a.name.lower(): a for a in self.world.agents}

    def do_run(self, arg):
        """
        Run an LLM turn for the currently active agent.

        Same as typing the active agent's name, but does not require
        remembering which agent is active after switch.

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

        Typing an agent's name still runs an LLM turn — switch is separate.

        Usage:
            switch Goblin
            switch Explorer
        """
        name = arg.strip()
        if not name:
            print("Usage: switch <agent name>")
            print("Use 'agents' or 'list' to see agent names.")
            return

        agent = self._resolve_agent_by_name(name)
        if agent is None:
            print(f"Agent '{name}' not found. Use 'agents' or 'list' to see agents.")
            return

        self.agent = agent
        print(f"Active agent: {agent.name} ({agent.id}) at {agent.position}")

    def do_vision(self, arg):
        """Show current passive vision."""
        print(build_passive_vision(self.agent, self.world))

    def do_prompt(self, arg):
        """Show the compound turn prompt for the active agent."""
        prompt = build_compound_prompt(
            self.agent, self.world, include_examples=self.include_examples
        )
        print(
            f"[Compound turn prompt - {len(prompt)} chars] "
            f"(fewshots={'on' if self.include_examples else 'off'})\n"
        )
        print(prompt)

    def do_state(self, arg):
        """Print basic agent and world state (for the currently active agent)."""
        print(f"Session turns (log label): {self.session_turn}")
        print(
            f"Active agent: {self.agent.name} ({self.agent.id}) at {self.agent.position}"
        )
        from src.memory_modules.registry import format_memory_module_label
        from src.memory_modules.rolling_summary import RollingSummaryModule
        from src.memory_modules.salient_turns import SalientTurnsModule

        print(format_memory_module_label(self.agent.memory.module))
        if isinstance(self.agent.memory.module, SalientTurnsModule):
            print(f"Memory char budget: {self.agent.memory.module.char_budget}")
        if isinstance(self.agent.memory.module, RollingSummaryModule):
            module = self.agent.memory.module
            print(f"Memory summary interval: {module.summary_interval}")
            print(f"Memory summary max chars: {module.max_summary_chars}")
            print(f"Memory summary detail tail: {module.summary_tail}")
            print(f"Memory consolidation: {module.consolidation_state}")
            last_summarized = module.last_summarized_turn_number
            print(
                "Memory last summarized at turn: "
                f"{last_summarized if last_summarized else '(never)'}"
            )
            detail_numbers = [t.turn_number for t in module.stored_turns]
            print(
                "Memory detail turns: "
                f"{detail_numbers if detail_numbers else '(none)'}"
            )
            if module.summary:
                print(f"Rolling summary length: {len(module.summary)} chars")
        print(f"Memory own turns (total): {self.agent.memory.turn_count}")
        print(f"Looked at (current): {sorted(self.agent.memory.looked_at)}")
        print(f"Ever looked at: {sorted(self.agent.memory.ever_looked)}")
        print(f"Few-shots in prompts: {'on' if self.include_examples else 'off'}")
        if self.agent.memory.turns:
            last = self.agent.memory.turns[-1]
            print(f"Last turn ({last.turn_number}) steps:")
            for step in last.steps:
                target = f" target={step.target}" if step.target else ""
                content = f" content={step.content!r}" if step.content else ""
                print(f"  - {step.kind}{target}{content}: {step.result}")
            print(f"Composite result: {last.result}")
        print(f"passive_result: {self.agent.passive_result or '(none)'}")
        objs = [(o.name, o.id, o.position) for o in self.world.get_objects()]
        print(f"Objects: {objs}")

    def do_objects(self, arg):
        """List all objects in the world (id, name, position, actions). Does not consume a turn."""
        print(format_objects_list(self.world))

    def do_effects(self, arg):
        """List registered object interaction effects (read-only). Does not consume a turn."""
        from src.object_effects import format_effects_list

        print(format_effects_list())

    def do_memory_modules(self, arg):
        """List registered agent memory modules (read-only). Does not consume a turn."""
        from src.memory_modules.registry import format_memory_modules_list

        print(format_memory_modules_list())

    def do_agents(self, arg):
        """List all agents in the world (id, name, position, active marker). Does not consume a turn."""
        print(format_agents_list(self.world, self.agent))

    def do_list(self, arg):
        """List all agents and objects (same as running agents then objects). Does not consume a turn."""
        print(format_full_list(self.world, self.agent))

    def do_create_object(self, arg):
        """
        Create a new object in the world.

        Usage:
            create-object name "Ceramic Ball" pdesc "A ball on the floor." desc "A worn ball." at 2,2
            create-object name "Cookie" pdesc "A cookie." desc "Tasty." at 2,2 action eat range 1 \\
                effect delete_self result "You ate the cookie." passive "{actor} ate the cookie."
        """
        obj, message = create_object_from_args(self.world, arg)
        print(message)

    def do_edit_object(self, arg):
        """
        Edit an existing object by id.

        Usage:
            edit-object obj_ball_01 pdesc "A ball." desc "New description."
            edit-object obj_ball_01 name "Old Ball" pos 3,3
            edit-object obj_cookie_01 add-action eat range 1 effect delete_self result "..." passive "..."
            edit-object obj_cookie_01 remove-action eat
        """
        print(edit_object_from_args(self.world, arg))

    def do_delete_object(self, arg):
        """
        Delete an object by id.

        Usage:
            delete-object obj_ball_01
        """
        print(delete_object_by_id(self.world, arg))

    def do_create_agent(self, arg):
        """
        Create a new agent in the world. Does not change the active agent.

        Usage:
            create-agent name "Goblin" pdesc "A short figure." desc "A grumpy goblin." personality "You are a grumpy goblin." at 0,3
            create-agent name "Scribe" personality "Quiet." memory salient_turns memory-budget 2500 at 2,2
            create-agent name "Archivist" personality "..." memory rolling_summary at 1,1
            create-agent name "Archivist" personality "..." memory rolling_summary memory-summary-interval 15 memory-summary-max 5000 memory-summary-tail 3 at 1,1
        """
        agent, message = create_agent_from_args(self.world, arg)
        if agent is not None:
            self._register_agent(agent)
        print(message)

    def do_edit_agent(self, arg):
        """
        Edit an existing agent by id.

        Usage:
            edit-agent agent_01 desc "Updated appearance." personality "Updated personality."
            edit-agent agent_01 name "Scout" pos 2,1

        Memory module cannot be changed here (set only at create-agent).
        """
        result = edit_agent_from_args(self.world, arg)
        if result.ok and result.agent is not None and result.old_name_lower:
            self._rename_agent_in_dict(result.old_name_lower, result.agent)
        print(result.message)

    def do_delete_agent(self, arg):
        """
        Delete an agent by id. Cannot delete the last agent.

        Usage:
            delete-agent agent_goblin_01
        """
        result = delete_agent_by_id(self.world, arg.strip())
        reassigned_active = False
        if result.ok and result.deleted_agent is not None:
            self._unregister_agent(result.deleted_agent)
            if self.agent.id == result.deleted_agent.id:
                self.agent = self.world.agents[0]
                reassigned_active = True
        print(result.message)
        if reassigned_active:
            print(
                f"Active agent: {self.agent.name} ({self.agent.id}) "
                f"at {self.agent.position}"
            )

    def do_fewshots(self, arg):
        """
        Toggle or show the few-shot examples setting for prompts.
        (Default is now OFF for token efficiency.)

        Usage:
            fewshots          # show current state
            fewshots on       # enable nav + action few-shot examples
            fewshots off      # disable
        """
        arg = arg.strip().lower()
        if arg in ("on", "yes", "true", "1", "enable"):
            self.include_examples = True
            print("Few-shot examples: ENABLED (included in navigation and action prompts)")
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
            step-compound 2,3
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
        Debug: run navigation move only.

        Does not create a TurnRecord or increment session_turn. Position changes
        persist — use step-compound for a full recorded turn.

        Usage:
            step-nav 2,3
            step-nav -
        """
        move_target = None if arg.strip().lower() in ("-", "stay", "") else arg.strip()
        if arg.strip().lower() in ("-", "stay"):
            print("Staying in place (no move).")
            return
        nav = AgentCompoundTurn(
            reasoning="[manual step-nav]",
            move_target=move_target or None,
            turn_action="none",
        )
        steps = execute_nav_phase(self.agent, self.world, nav)
        for step in steps:
            print(step.result)

    def do_step_action(self, arg):
        """
        Debug: run action phase only from current position.

        Does not create a TurnRecord or increment session_turn. Side effects
        (look memory, passive_result) may persist — use step-compound for a
        full recorded turn.

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
        steps = execute_action_phase(self.agent, self.world, parsed.turn)
        for step in steps:
            print(step.result)

    def _gate_agent_turn(self, agent: "Agent") -> bool:
        """Return False if the agent cannot act yet (e.g. memory consolidation)."""
        from src.memory_modules.rolling_summary import MemoryConsolidationError

        try:
            agent.memory.ensure_ready_for_turn()
        except MemoryConsolidationError as exc:
            print(f"\nCannot run turn for {agent.name}: {exc}")
            return False
        return True

    def _run_manual_compound(self, turn: AgentCompoundTurn) -> None:
        agent = self.agent
        if not self._gate_agent_turn(agent):
            return
        turn_number = next_turn_number_for_agent(agent)
        record = run_compound_turn(
            agent, self.world, turn, turn_number, session_turn=self.session_turn + 1
        )
        self.session_turn += 1
        log_turn(
            self.session_turn,
            result=(
                f"Agent: {agent.name} (turn {turn_number})\n"
                f"Steps: {len(record.steps)}\n"
                f"Result: {record.result}"
            ),
            always_to_file=False,
        )
        print(record.result)

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

    # ------------------------------------------------------------------
    # LLM-driven turns by typing agent name (supports future multi-agent)
    # ------------------------------------------------------------------

    def default(self, line: str):
        """
        If the user types an agent's name (instead of a built-in command),
        run that agent using the LLM to decide its action.
        This is the main way to let agents "think" autonomously.
        """
        line = line.strip()
        if not line:
            return

        agent = self._resolve_agent_by_name(line)
        if agent is not None:
            self._run_llm_turn_for_agent(agent)
            return

        # Not an agent name — let cmd.Cmd handle it (unknown command)
        super().default(line)

    def _run_llm_turn_for_agent(self, agent: "Agent"):
        """Single LLM call for one compound agent turn."""
        self.agent = agent
        if not self._gate_agent_turn(agent):
            return
        print(f"\n=== Running LLM for {agent.name} ===")

        try:
            from src.llm.client import get_compound_turn

            prompt = build_compound_prompt(
                agent, self.world, include_examples=self.include_examples
            )
            print(
                f"Prompt: {len(prompt)} chars "
                f"(fewshots={'on' if self.include_examples else 'off'})"
            )
            print("Calling LLM...")
            response = get_compound_turn(prompt)
            compound_turn: AgentCompoundTurn = response.parsed

            turn_number = next_turn_number_for_agent(agent)
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

            record = run_compound_turn(
                agent,
                self.world,
                compound_turn,
                turn_number,
                session_turn=pending_session,
            )
            self.session_turn += 1

            print(f"\n--- {agent.name} turn {turn_number} (session {self.session_turn}) ---")
            for step in record.steps:
                print(f"  [{step.kind}] {step.result}")
            print(f"Composite: {record.result}")
            print()

        except Exception as e:
            log_error(f"LLM call failed for {agent.name}", e)
            import traceback
            traceback.print_exc()


def main():
    """Entry point for the manual stepper (used by `uv run realm`)."""
    parser = argparse.ArgumentParser(description="Realm-Fabric V0.2.5 Manual Stepper")
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
