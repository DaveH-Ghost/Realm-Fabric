# LLM turn schemas

Structured JSON the LLM (or a player client) returns for one agent turn.

---

## Current (use this)

| Schema | Runtime | App import |
|--------|---------|------------|
| **`AgentCompoundTurn`** | [`src/llm/schemas.py`](../../src/llm/schemas.py) | `from campaign_rpg_engine import AgentCompoundTurn` |

**Since V0.2.5:** one LLM call per turn — move → look → say → action in a single object.

**Field names (V0.4.4+):** `move`, `look`, `say`, `action`, `verb`, `target`, `reasoning`.

Legacy keys (`move_target`, `look_target`, `content`, `turn_action`, `action_name`) are normalized on parse.

**Guide:** [Compound turns](../guides/turns.md)  
**Reference copy:** [AgentCompoundTurn.py](AgentCompoundTurn.py) (readable mirror; may lag runtime slightly)

---

## Example JSON

```json
{
  "reasoning": "I'll walk over and read the sign.",
  "move": "2,1",
  "look": "obj_sign_01",
  "say": null,
  "action": "none",
  "target": null,
  "verb": null
}
```

Interact example:

```json
{
  "reasoning": "The chest is in range.",
  "move": null,
  "look": null,
  "say": null,
  "action": "interact",
  "target": "obj_chest_01",
  "verb": "open"
}
```

---

## Historical (do not implement)

These files document **superseded** designs. Kept for archaeology and old checklists.

| File | Era | Replaced by |
|------|-----|-------------|
| [AgentTurn.py](AgentTurn.py) | V0 / V0.1 | V0.2 two-phase, then `AgentCompoundTurn` |
| [AgentNavigationTurn.py](AgentNavigationTurn.py) | V0.2 navigation phase | `AgentCompoundTurn` (V0.2.5) |
| [AgentActionTurn.py](AgentActionTurn.py) | V0.2 action phase | `AgentCompoundTurn` (V0.2.5) |

See [v0.2.5 changelog](../changelog/v0.2.5-changelog.md).

---

## Validation notes

- **`reasoning`** and **`say`** are truncated at sentence boundaries (not hard-rejected) — V0.4.1+
- **`move`** accepts `"x,y"`, `obj_*`, `agent_*` — validated in runtime
- **`action: "speak"`** is invalid — use **`say`** for dialogue (V0.4.2+)
- Visibility, range, and interact legality are checked at **simulation** time, not only in Pydantic
