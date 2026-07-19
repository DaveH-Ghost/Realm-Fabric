# Session turn flow

Happy path for an NPC (LLM) compound turn hosted by Studio or any app.

```mermaid
sequenceDiagram
  participant Host as Studio_or_app
  participant Session as Session
  participant LLM as get_compound_turn
  participant Sim as run_compound_turn

  Host->>Session: build_prompt(agent_id)
  Session-->>Host: prompt text
  Host->>LLM: get_compound_turn(prompt)
  Note over LLM: budget check then HTTP
  LLM-->>Host: AgentCompoundTurn
  Host->>Sim: session.run_compound_turn(turn)
  Sim-->>Host: SessionResult + TurnRecord
  Host->>Session: snapshot(include_private)
  Session-->>Host: state for UI / clients
```

Key modules:

- Prompt assembly: `session.py`, `prompt_blocks.py`, `llm/prompt_context.py`
- LLM: `llm/client.py` (providers, token budget, JSON brace repair)
- Simulation: `simulation.py`, `actions/`
