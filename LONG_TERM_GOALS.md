# Long Term Goals

**Purpose:**  
This document exists to capture big, exciting, "someday" dreams for this project without letting them pollute or over-scope the current version we're working on.

These are **aspirational goals**. They are not targets for Version 0, Version 0.1, or even Version 1 unless we explicitly decide to pull one in. They are recorded here so they aren't lost and so we can feel the satisfaction of moving them into the "Achieved" section when the time comes.

Treat this file like a trophy case. Checking something off here should feel like a real milestone.

---

## Dream Goals

These are currently out of scope. They represent the kind of experiences we eventually want to create.

### Foundational / Relatively Easier Goals

These are considered lower-complexity improvements that could be reasonable targets for V0.1 or V0.2.

- [ ] **"Object has changed since last looked at" system**  
  When an object’s description (or other observable state) changes after an agent has previously looked at it, the agent should be notified in passive vision using neutral language, for example:  
  *"The wooden sign has changed since you last looked at it."*  
  The agent would then need to use the `look` action again to see the current description.  
  In V0 this behavior would only apply to the sign (as a special case for human-to-agent communication). The long-term goal is to make this a general system that applies to any object whose description or state changes.  
  The purpose of this system is to encourage agents to intentionally use the `look` action to gather information, rather than having to constantly re-examine objects just in case something changed. It also keeps passive vision cleaner by avoiding constantly showing full updated descriptions for every changed object.

### More Complex Goals

- [ ] Multiple agents that can observe each other, start conversations, form relationships, and influence one another over time
- [ ] Objects that have their own behaviors and actions (examples: food that can be eaten and gives a taste description, a puzzle box with interactive mechanisms, a door that can be locked/unlocked, etc.)
- [ ] Rectangular / multi-tile objects (e.g. long walls, large furniture, 2x2 trees with 6x6 shadows) where objects occupy multiple grid tiles using size + bounding box definitions instead of single-tile objects
- [ ] A visual interface similar to Roll20 — a grid with tokens representing agents and objects, plus chat bubbles when agents speak
- [ ] Agents that can create or modify objects in the world (with some form of validation or rules)
- [ ] Richer memory systems (beliefs, relationships, long-term goals, emotional state)
- [ ] The ability for agents to develop and pursue their own goals over many turns instead of only reacting to the current situation

---

## Achieved Goals

This section is for goals that have actually been completed. When something moves here, it should feel like a genuine accomplishment.

*(Nothing here yet — this is the exciting part.)*

---

## How to Use This Document

- Add new dream goals whenever they come up during development or daydreaming.
- Do **not** use these goals to justify adding scope to the current version.
- When we decide a dream is worth actively working toward, we should first create a proper design document for it (not just check it off).
- Moving something from "Dream Goals" to "Achieved" should be celebrated.

---

*This file is meant to stay fun and inspiring. It is not a roadmap.*