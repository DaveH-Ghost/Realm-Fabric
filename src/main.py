"""
main.py

Entry point for manual stepping in V0 (per readiness checklist).

Supports:
- step                  : advance one turn. For now you (the human) supply
                          the AgentTurn fields to simulate what the LLM would
                          have output. This lets us test the full loop
                          (action -> memory -> vision) without the LLM.
- sign "new text"       : debug command to update the wooden sign's description
                          and invalidate the agent's memory of it (triggers the
                          special "has changed" notification).
- quit / exit           : leave the simulation.
- vision / state        : print current passive vision or agent/world state.

Typing an agent's name (e.g. "Explorer") will automatically build a prompt
using the current world state and call the LLM to decide the next action.
This design makes it easy to support multiple agents later.

Future: real autonomous runs, better logging, etc.

Run with (from the project root):

    # Easiest way
    uv run python src/main.py

    # After `uv sync`, you can also do:
    # uv run realm
    # (if the entry point was picked up)

    # To use real LLM calls, copy .env.example to .env and add your OPENROUTER_API_KEY

"""

import os
import sys

# Ensure 'src' package is importable no matter how this script is launched
# (uv run, python src/main.py, double-click, etc.)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cmd
from src.world import create_initial_world
from src.simulation import step_turn
from src.llm.schemas import AgentTurn
from src.llm.prompt import build_prompt
from src.perception import build_passive_vision

# Lazy import for the client so you can run the manual stepper
# without an OPENROUTER_API_KEY
_get_next_action = None

def _get_llm_function():
    global _get_next_action
    if _get_next_action is None:
        from src.llm.client import get_next_action as _gn
        _get_next_action = _gn
    return _get_next_action


class ManualStepper(cmd.Cmd):
    intro = (
        "Realm-Fabric V0 Manual Stepper\n"
        "Type 'help' or '?' for commands.\n"
        "- 'step <action> ...'   : manually simulate a turn (for testing)\n"
        "- Type an agent's name (e.g. 'Explorer') : let the LLM decide its action\n"
        "- 'prompt' : show the full prompt that would be sent to the LLM\n"
        "- 'sign \"new text\"' : debug command to update the sign\n"
        "Example: Explorer\n"
        "Example: step look obj_ball_01\n"
    )
    prompt = "(realm) "

    def __init__(self):
        super().__init__()
        self.world = create_initial_world()
        # Support multiple agents by name (case-insensitive lookup)
        self.agents: dict[str, "Agent"] = {
            a.name.lower(): a for a in self.world.agents
        }
        self.agent = self.world.get_agent()  # current active agent
        self.turn_number = 0

    def do_vision(self, arg):
        """Show current passive vision."""
        print(build_passive_vision(self.agent, self.world))

    def do_prompt(self, arg):
        """Show the full prompt that would be sent to the LLM right now."""
        prompt = build_prompt(self.agent, self.world)
        print(f"[Full prompt - {len(prompt)} characters]\n")
        print(prompt)

    def do_state(self, arg):
        """Print basic agent and world state (for the currently active agent)."""
        print(f"Turn: {self.turn_number}")
        print(f"Active agent: {self.agent.name} at {self.agent.position}")
        print(f"Memory turns: {self.agent.memory.turn_count}")
        print(f"Looked at: {sorted(self.agent.memory.looked_at)}")
        objs = [(o.name, o.position) for o in self.world.get_objects()]
        print(f"Objects: {objs}")

    def do_agents(self, arg):
        """List all agents in the world and which one is active."""
        print("Agents in world:")
        for name_lower, ag in self.agents.items():
            marker = " (active)" if ag is self.agent else ""
            print(f"  - {ag.name}{marker} at {ag.position}")

    def do_step(self, arg):
        """
        Manually simulate one turn for the currently active agent.
        Use this for testing specific behaviors without calling the LLM.

        Usage:
            step move north
            step look obj_ball_01
            step speak This is what I say.
        """
        if not arg:
            print("Usage: step <move|look|speak> [target_or_content...]")
            return

        parts = arg.split(maxsplit=1)
        action = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        target = None
        content = None

        if action == "move":
            target = rest.strip() or None
        elif action == "look":
            target = rest.strip() or None
        elif action == "speak":
            content = rest.strip() or None
        else:
            print(f"Unknown action '{action}'. Use move, look, or speak.")
            return

        try:
            turn = AgentTurn(
                reasoning="[manual step - no real reasoning]",
                action=action,
                target=target,
                content=content,
            )
        except Exception as e:
            print(f"Invalid turn data: {e}")
            return

        self.turn_number += 1

        # Build and show the prompt that would be sent to the model
        full_prompt = build_prompt(self.agent, self.world)
        print(f"\n[PROMPT that would be sent to LLM - {len(full_prompt)} chars]")
        print(full_prompt[:800] + "\n... [truncated for display] ...\n")

        record = step_turn(self.agent, self.world, turn, self.turn_number)

        print(f"--- Turn {self.turn_number} ---")
        print(f"Action: {record.action} target={record.target} content={record.content}")
        print(f"Reasoning: {record.reasoning}")
        print(f"Result: {record.result}")
        print()

    def do_sign(self, arg):
        """
        Debug command: update the wooden sign's description.

        Usage:
            sign This is the new text on the sign.
        """
        if not arg:
            print("Usage: sign <new description text>")
            return

        sign = self.world.get_object_by_id("obj_sign_01")
        if sign is None:
            print("Sign not found!")
            return

        old = sign.description
        sign.description = arg
        self.agent.memory.invalidate_look("obj_sign_01")

        print("Sign updated.")
        print(f"Old: {old[:60]}...")
        print(f"New: {arg[:60]}...")
        print("The agent's memory of the sign has been invalidated.")

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

        name_lower = line.lower()
        if name_lower in self.agents:
            self._run_llm_turn_for_agent(self.agents[name_lower])
            return

        # Not an agent name — let cmd.Cmd handle it (unknown command)
        super().default(line)

    def _run_llm_turn_for_agent(self, agent: "Agent"):
        """Build prompt, call LLM, execute the resulting turn."""
        print(f"\n=== Running LLM for {agent.name} ===")

        try:
            prompt = build_prompt(agent, self.world)
            print(f"Prompt length: {len(prompt)} chars (type 'prompt' to view full)")

            print("Calling LLM...")
            get_next_action = _get_llm_function()
            llm_response = get_next_action(prompt)
            turn = llm_response.turn

            # === Rich logging as per readiness checklist ===
            print("\n" + "=" * 60)
            print(f"FULL PROMPT (turn {self.turn_number + 1})")
            print("=" * 60)
            print(prompt)
            print("=" * 60)

            print(f"\nRAW LLM RESPONSE (model={llm_response.model}):\n{llm_response.raw_response}")
            print("=" * 60)

            print(f"\nPARSED TURN: action={turn.action} target={turn.target}")
            print(f"Reasoning: {turn.reasoning}")

            # Log token usage if available (standard OpenAI/OpenRouter usage fields)
            if llm_response.total_tokens is not None:
                print(f"\nTOKEN USAGE: input (prompt)={llm_response.prompt_tokens} + "
                      f"output (completion)={llm_response.completion_tokens} = "
                      f"total={llm_response.total_tokens}")

            self.turn_number += 1
            record = step_turn(agent, self.world, turn, self.turn_number)

            print(f"\n--- Turn {self.turn_number} result ---")
            print(f"Action: {record.action}")
            print(f"Result: {record.result}")
            print()

            # Make this agent the active one for subsequent vision/state commands
            self.agent = agent

        except Exception as e:
            print(f"LLM call failed: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Entry point for the manual stepper (used by `uv run realm`)."""
    ManualStepper().cmdloop()


if __name__ == "__main__":
    main()
