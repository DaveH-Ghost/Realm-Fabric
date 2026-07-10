# Compound turns

Running agent turns with **`AgentCompoundTurn`** — the structured output shape for every agent action.

---

## Turn shape

```json
{
  "reasoning": "Private thoughts for this turn (~400 chars max).",
  "move": "2,1",
  "look": "obj_sign_01",
  "say": "Hello there.",
  "action": "interact",
  "target": "obj_chest_01",
  "verb": "open"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `reasoning` | string | LLM-only; not shown to other agents |
| `move` | `"x,y"`, entity id, or `null` | Stay put when null |
| `look` | entity id or `null` | After move; updates look knowledge |
| `say` | string or `null` | Witnessed dialogue (~500 chars max) |
| `action` | `"interact"` \| `"emote"` \| `"none"` | Turn-ending action |
| `target` | string or `null` | Object/agent id for interact; emote target text |
| `verb` | string or `null` | Object action name (interact) or past-tense emote verb |

Full schema reference: [docs/schemas/README.md](../schemas/README.md).

Legacy compact keys (`move`, `look`, `say`, etc.) are normalized on import. **`speak` as action is removed** — use `say` for dialogue.

---

## NPC turn (LLM)

```python
from campaign_rpg_engine import Session, load_profile

session = Session.from_profile(load_profile("default_compound"))

# 1. Gate (memory consolidation, etc.)
gate = session.gate_agent_turn(agent_id)
if not gate.ok:
    raise RuntimeError(gate.message)

# 2. Build prompt and call your LLM (OpenRouter in reference apps)
prompt = session.build_prompt(agent_id)

# 3. Parse response into AgentCompoundTurn, then run
from campaign_rpg_engine import AgentCompoundTurn

compound_turn = AgentCompoundTurn.model_validate(llm_json)
result = session.run_compound_turn(compound_turn, agent_id=agent_id)
if result.ok:
    record = result.record  # TurnRecord with steps
```

**Environment:** set `OPENROUTER_API_KEY` (and optional `OPENROUTER_MODEL`) for reference LLM clients. See root [`.env.example`](../../.env.example).

**Reference implementation:** [CampAIgn-RPG-Studio `backend/turn_runner.py`](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/blob/main/backend/turn_runner.py).

---

## Player turn (manual)

Mark the human agent at create time:

```python
session.create_agent(
    name="Player",
    position=(0, 0),
    is_player=True,
    personality="...",
)
```

Run turns without an LLM:

```python
compound_turn = AgentCompoundTurn(
    reasoning="I'll check the sign.",
    move="1,0",
    look="obj_sign_01",
    say=None,
    action="none",
    target=None,
    verb=None,
)
result = session.run_compound_turn(compound_turn, agent_id=player.id)
```

`POST /api/turn/manual` on [CampAIgn-RPG-Studio](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio) accepts the same JSON under `"turn"`.

---

## Active agent

- `session.active_agent_id` — default for `build_prompt()` and `run_compound_turn()` when `agent_id` omitted
- `session.set_active_agent(name_or_id)` — switch who acts next
- `session.get_agent(name_or_id)` — resolve by display name or `agent_*` id

---

## Movement notes

- **`move_speed`** on agents enables Chebyshev pathing toward the target tile or entity
- **`interact`** action can path toward the object (replaces explicit move that turn)
- Objects **block movement** by default; exceptions via `movement_exceptions`

Details: [v0.6.0 changelog](../changelog/v0.6.0-changelog.md).

---

## Related

- [Overview](overview.md)
- [Persistence & snapshots](persistence.md) — `snapshot()` after a turn
