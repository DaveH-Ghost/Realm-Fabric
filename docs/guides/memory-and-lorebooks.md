# Memory & lorebooks

Optional subsystems that shape what agents **remember** and what **world info** enters the LLM prompt.

---

## Memory modules

Each agent has a **`Memory`** instance backed by a pluggable module:

| Built-in id | Behavior |
|-------------|----------|
| `recent_turns` | Sliding window of recent turns (default) |
| `salient_turns` | Char-budget retention with salience |
| `rolling_summary` | Periodic LLM consolidation into summary + detail tail |

### Create agent with module

```python
session.create_agent(
    name="Scout",
    position=(0, 0),
    personality="Curious.",
    memory_module="salient_turns",
    memory_budget=2000,
)
```

### Custom modules

```python
from campaign_rpg_engine import register_memory_module_from_path

register_memory_module_from_path("path/to/my_module.py")
```

Module must expose `create_module(**config) -> MemoryModule`.  
Example: [CampAIgn-RPG-Studio fixtures/custom_memory](https://github.com/DaveH-Ghost/CampAIgn-RPG-Studio/tree/main/fixtures/custom_memory) (upload via Settings in the GM app).

Saves store **`module_id` + state** — not source code. Import fails if the module is not registered.

See [v0.4.6 changelog](../changelog/v0.4.6-changelog.md).

---

## Lorebooks

SillyTavern-style keyword / constant world-info entries loaded into the session.

```python
from campaign_rpg_engine import load_lorebook_from_path

session.load_lorebook_from_path("world.lorebook.json")
```

Add a **`lorebook`** block to the session prompt layout (per book id) to inject matched entries at turn time. Not in the default profile layout.

See [v0.5.0 changelog](../changelog/v0.5.0-changelog.md) and [examples/lorebook](../../examples/lorebook/).

---

## Prompt blocks

Sessions render prompts from an ordered list of blocks (slots + editable sections) instead of a single template file.

```python
from campaign_rpg_engine import default_prompt_blocks, validate_prompt_blocks

blocks = default_prompt_blocks()
err = session.set_prompt_blocks(blocks)
prompt = session.build_prompt()
```

Slot catalog and preview helpers: `prompt_block_catalog()`, `PromptBlock` type in `campaign_rpg_engine`.

GM editing UI lives in campaign-rpg-studio; apps can set blocks programmatically or ship defaults in profiles.

See [v0.4.1 changelog](../changelog/v0.4.1-changelog.md).

---

## Related

- [Compound turns](turns.md) — memory ingests turn records
- [API reference](api-reference.md) — lorebook and prompt exports
