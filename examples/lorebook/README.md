# Example lorebooks

SillyTavern-style JSON lorebooks for CampAIgn RPG Engine sessions.

## `campaign-rpg-engine-demo.lorebook.json`

A small three-entry book keyed to the **default demo room** (wooden room, ball, sign). Use it to try lorebooks without writing your own:

**campaign-rpg-studio** — Lorebooks tab → **Load lorebook** → choose this file, or **Load demo lorebook**.

**CLI:**

```
load-lorebook examples\lorebook\campaign-rpg-engine-demo.lorebook.json
```

Then add a **lorebook** slot in Prompt layout (pick `campaign-rpg-engine-demo`) or create entries in the Lorebooks tab.

Keywords match against enabled scan sources (agent text, area description, passive vision, memory, etc.). Look at the ball or mention it in area text to activate the ball entry.

## Create without a file

In **campaign-rpg-studio**, use **Create lorebook** for an empty book, then **Add entry** or edit in place.
