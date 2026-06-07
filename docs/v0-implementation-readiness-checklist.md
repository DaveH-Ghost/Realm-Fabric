# Version 0 Implementation Readiness Checklist

> **Historical document.** V0 is shipped (tag `v0`). For **V0.1** (tag `v0.1.0`) see [v0.1-implementation-readiness-checklist.md](v0.1-implementation-readiness-checklist.md). **V0.2** Sections 1–3 are **implemented on `main`** (coordinate move, compound turns, object interact); **`v0.2.0` tag pending** — see [v0.2-implementation-readiness-checklist.md](v0.2-implementation-readiness-checklist.md) and [ROADMAP.md](ROADMAP.md).

**Purpose:**  
This checklist defines everything we must design, decide, and document *before* we wrote V0 code. It remains a design reference for the original single-agent foundation.

**Rule:** No code is written until every item on this checklist is checked off.

**Project Scope (Current Agreement):**
- One agent only
- Grid-based world
- Three actions: `move`, `look`, `speak`
- `speak` = the agent talking to itself (no other agents yet)
- Tiny starter world: one ball on the ground + one sign on the wall
- Using DeepSeek via OpenRouter (cheap, structured output may need defensive handling)
- Goal: Learning + enjoyment. Keep it small and understandable.

---

## Section 1: High-Level Scope & Goals

- [x] Define the single most important learning goal for Version 0

  **Agreed Goal for Version 0:**

  > “I want to learn how to build the simplest possible system where an agent can make reliable structured decisions in a small grid world. I want to clearly observe the full loop — prompt → reasoning → action → world change — and be able to modify the environment or the agent’s memory to see how its observations, reasoning, and behavior change. Most importantly, I want to develop real intuition for what makes structured output reliable (and unreliable) so I don’t get blocked later when trying to build more ambitious things.”
- [x] Define what "Version 0 is complete" looks like in concrete terms (success criteria)

  **Agreed Success Criteria for Version 0:**

  Version 0 will be considered complete when the following are true:

  - The full loop works end-to-end: prompt construction → LLM call → structured output parsing → action validation → world state update → next prompt.
  - Structured output reliability meets the targets defined in Section 11:
    - **Parse Success Rate** ≥ 92%
    - **Valid Action Rate** ≥ 80%
    - **Reasonable Action Rate** ≥ 70%
    (See “Agreed Targets for V0 (end-of-V0 goals)” in Section 11 for full definitions and evaluation method.)
  - When the model produces invalid or unusable output, there is clean fallback behavior so the simulation continues without crashing.
  - It is possible to manually run **50+ consecutive turns** while clearly observing the agent’s reasoning and behavior.
  - We can modify the environment, the agent’s memory, or the prompt and clearly observe how the agent’s observations, reasoning, and actions change as a result.
- [x] Explicitly list what is deliberately out of scope for Version 0 (and why)

  **Agreed Out of Scope for Version 0:**

  The following are explicitly out of scope. We will not design or implement these in Version 0:

  - Multiple agents interacting with each other
  - Objects that have behaviors or can be interacted with beyond being looked at (e.g. edible items, puzzle boxes, doors, containers, etc.)
  - Any form of visual interface (tokens, chat bubbles, Roll20-style view, etc.)
  - Anything recorded in `LONG_TERM_GOALS.md`

  **Why we are cutting these:**

  - Adding object interactions, multiple agents, or visual layers would significantly increase complexity.
  - Our primary goal right now is learning how to build a reliable structured decision loop in the simplest possible environment. Introducing these features early would work against that goal.
- [x] Confirm we are comfortable with one agent + talking to itself for the first implementation pass

  **Confirmed:** We are comfortable starting Version 0 with a single agent. The `speak` action will be used for the agent to talk to itself / narrate its thoughts and observations. We will add a second agent in a later iteration.

## Section 2: World Model

- [x] Define the grid size and coordinate system (e.g. 5x5, 10x10, etc.)

  **Agreed Decision:**

  - The playable area and coordinate system are now the same (no outer "wall layer" in coordinates).
  - Playable grid: 5×5
  - Coordinates: (0, 0) to (4, 4)
  - Coordinate system: Global coordinates
  - (0, 0) is the southwest corner. X increases eastward, Y increases northward.
  - The agent cannot move outside (0,0) – (4,4).
  - Room boundaries (walls) are **not** represented as objects in V0.
  - The room is described to the agent via a room description string injected into the prompt (e.g. "You are in a small room with a hardwood floor and four wooden walls").
- [x] Define how positions work (integers only? movement rules?)

  **Agreed Decision:**

  - Movement is limited to 1 tile per turn.
  - Only the 4 cardinal directions are allowed in Version 0: North, East, South, West (no diagonals).
  - Diagonal movement (8 directions) is deferred to a future version.
  - In V0 there are no blocking objects. Movement is restricted to the playable area (0,0) to (4,4). The agent simply cannot move outside these coordinates.
  - Coordinate orientation: (0,0) = southwest. Y increases north.
- [x] Define the Agent data model (position, name, any memory/state it needs)

  **Agreed Agent Data Model (V0):**

  ```python
  @dataclass
  class TurnRecord:
      turn_number: int
      action: str                    # "move", "look", or "speak"
      target: Optional[str]
      content: Optional[str]
      reasoning: str                 # The agent's private reasoning at the time
      result: str                    # What the simulation returned after the action

  @dataclass
  class Agent:
      id: str                          # Unique identifier
      name: str                        # Display name
      description: str                 # Core personality / character description (included in prompt)
      position: tuple[int, int]        # Current location on the grid
      memory: list[TurnRecord]         # Last 10 turns kept in full detail
      last_action: Optional[str]       # What the agent did on the previous turn (retained for potential future use in richer memory or prompt conditioning; currently underutilized in V0)
  ```

  **Memory Decision:**
  - Keep the last **10 turns** in full detail. No automatic summarization or multi-layer memory system in Version 0.
  - Each `TurnRecord` stores the action taken, the agent's private reasoning, and the exact result/feedback string returned by the simulation.
- [x] Define the Object data model (id, name, description, location)

  **Agreed Decision for V0:**

  - Objects are simple single-tile entities only. No multi-tile / rectangular objects in V0.
  - Current objects in the world: the ball and the sign. The agent already knows its own position from the "You are at (x, y)" line at the top of passive vision.
  - Walls / room boundaries are **not** objects. They are described to the agent via a room description string in the prompt.
  - Proposed minimal Object model:

  ```python
  @dataclass
  class Object:
      id: str                    # Stable unique ID (e.g. "obj_ball_01", "obj_sign_01")
      name: str                  # Short name shown in vision
      description: str           # Text revealed when the agent uses the "look" action
      position: tuple[int, int]  # Grid coordinates (all objects are single-tile in V0)
  ```

  - `description` may be empty or short for simple objects.
  - The agent will only see the ball and the sign as objects in passive vision. Room walls are conveyed through the room description text. The agent already knows its own position from the "You are at (x, y)" line.
- [x] Define how the two starter objects (ball + sign) are represented

  **Agreed Details for V0:**

  **Ball**
  - id: `obj_ball_01`
  - name: `Ceramic Ball`
  - description: `A slightly worn ceramic ball. It has a few scuffs and feels light.`
  - position: `(2, 2)`

  **Sign**
  - id: `obj_sign_01`
  - name: `Wooden Sign`
  - description: `A simple wooden sign. It reads: "This is a controlled environment. You are the only one here. This sign may occasionally be updated with new information. When it changes, you will be notified."`
  - position: `(2, 4)`
  - Update method: The human can directly overwrite the sign’s `description` field via a command (no separate `text` field).
  - Change notification (sign-only in V0): Handled outside the core Object model as a special case. When the description is updated, the agent sees the neutral message **"Wooden Sign (obj_sign_01), (2, 4) - [?] The wooden sign has changed since you last looked at it."** in passive vision. The agent must use the `look` action again to read the current description.

  Note: No version or tracking fields were added to the general Object model for V0. The change detection logic is kept sign-specific to avoid unnecessary complexity.

  **Sign Change Special Case Containment Strategy (V0):**

  The sign update mechanism is the only human-to-agent communication channel in V0 and is triggered exclusively through the debugging `sign` command. To prevent the special case from leaking across the codebase, the following ownership rules apply:

  - **Memory module**: Owns the looked-at object list and provides a narrow method (e.g. `invalidate_look(object_id)`) to remove an object from the list. The sign uses this mechanism but the method itself is not sign-specific.
  - **Perception module**: Generates the special notification text (`[?] The wooden sign has changed since you last looked at it.`) when building passive vision. This check is isolated to the sign ID and only triggers when the sign is not currently in the looked-at list.
  - **Command / stepping layer** (`main.py` or equivalent): The `sign "{text}"` command updates the sign’s description in the World and then calls the memory invalidation method. This is the only place that initiates the sign change flow.
  - **World / Object model**: Contains no change detection or notification logic. The sign is treated like any other object.

  This containment is acceptable only because the feature is sign-only and debugging-only in V0. It should be revisited if a general “object has changed” system is implemented later.
- [x] Decide on initial world state (where the agent starts, where the objects are)

  **Agreed Initial World State (V0):**

  - Grid: 5×5 (coordinates (0,0) to (4,4))
  - (0,0) = Southwest corner. Y increases northward.
  - Agent starts at: `(1, 1)`
  - Ball (`obj_ball_01`) is at: `(2, 2)`
  - Sign (`obj_sign_01`) is at: `(2, 4)` (northern edge)
- [x] Decide whether the world state lives in simple Python objects, dataclasses, or something else for Version 0

  **Agreed Decision:**

  - Use Python **dataclasses** as the primary way to represent world state in V0.
  - `Agent` and `Object` will be defined as dataclasses.
  - A `World` class (can be a regular class or dataclass) will hold the overall state (agents, objects, grid rules, etc.).
  - This keeps things clean, readable, and easy to work with during early development.
- [x] Decide if we need any basic rules (e.g. can the agent occupy the same tile as the ball?)

  **Agreed Basic Rules for V0:**

  - The agent **can** occupy the same tile as the ball (the ball does not block movement).
  - The agent **cannot** move outside the playable area (0,0) to (4,4).
  - No other significant basic rules are needed at this stage. (The sign is placed on the edge and is not expected to be stood on.)

## Section 3: Actions (The Three Actions)

- [x] Define exact behavior and constraints for `move`
  - How far can the agent move per turn?
  - What happens if it tries to move off the grid or into an invalid space?

  **Agreed Behavior for `move` (V0):**

  - The agent may only move **1 tile per turn**.
  - Only the **4 cardinal directions** are allowed: North, East, South, West.
  - The prompt will only list directions the agent can currently move into.
  - If the model outputs an invalid direction (e.g. trying to move west when blocked), the move **fails**.
  - Preferred feedback style (narrative):  
    "You tried to move west, but were blocked by the west wall."
  - The agent’s position does **not** change on a failed move.
  - A failed move still counts as the agent’s action for the turn.

  **Example of how valid moves are presented in the prompt:**

  You can move in the following directions this turn:
  - north
  - east
  - south

  (Directions that are blocked or off the map are simply not listed.)

  **Example of what appears in the agent's action history after an invalid move:**

  - You tried to move west, but were blocked by the west wall.
- [x] Define exact behavior and constraints for `look`
  - What does the agent learn when looking at the ball?
  - What does the agent learn when looking at the sign?
  - What does the agent learn when looking at an empty tile?

  **Agreed Behavior for `look` (V0):**

  - The agent can only use `look` on objects that currently appear in its passive vision.
  - `look` cannot be used on empty tiles in V0 (this may become an "investigate" action in future versions).
  - When the agent uses `look` on an object, it receives the object's full current description. This information is stored in the agent's memory.
  - Using `look` on an object clears any `[?]` or "has changed" state for that object from the agent's perspective.

  **Passive Vision Format (V0):**

  Objects in passive vision follow this format:
  `{name} ({id}), {coordinates} - {description}|[?]`

  - If the agent has never looked at the object (or the description has changed since they last looked), the object shows `[?]` instead of the description.
  - Example: `Wooden Sign (obj_sign_01), (2, 4) - [?]`
  - Example when changed: `Wooden Sign (obj_sign_01), (2, 4) - [?] (has changed since you last looked at it)`
  - Once the agent has successfully looked at the object, the actual description is shown.
  - Example: `Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.`

  The agent is not listed as a separate entry in passive vision. Its position is already stated at the top ("You are at (x, y)").

  **Example Passive Vision Section in Prompt:**

  You are at (1, 1).
  Ceramic Ball (obj_ball_01), (2, 2) - [?]
  Wooden Sign (obj_sign_01), (2, 4) - [?] (has changed since you last looked at it)

  **Example after looking at the ball:**

  You are at (1, 1).
  Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
  Wooden Sign (obj_sign_01), (2, 4) - [?] (has changed since you last looked at it)

  **Prompt Guidance for `look`:**

  Objects shown with [?] have unknown or outdated descriptions. Use the `look` action on them to reveal their current description. Only objects currently visible in your passive vision can be looked at.
- [x] Define exact behavior and constraints for `speak`
  - What is the expected output (length, style)?
  - How is spoken text stored/remembered?
  - Is there any world effect from speaking (for now)?

  **Agreed Behavior for `speak` (V0):**

  - The agent may only speak **up to five sentences** per turn.
  - All text provided in the `speak` action is treated as verbal dialogue.
  - Speaking has no *direct mechanical effect* on objects or the environment in V0. However, your words are recorded and may influence how the simulation responds over time (for example, through updates to the sign).
  - Spoken text is stored in the agent's action history (just like `move` and `look` results).
  - No emote or action detection / stripping is performed in V0. The model is simply instructed that all text is treated as dialogue.

  **Example of how `speak` appears in the prompt:**

  You may speak this turn (maximum 5 sentences). All text in the speak action is treated as verbal dialogue. Your words have no direct mechanical effect on the world, but what you say is recorded and may influence how the simulation responds (for example, through updates to the sign).

  **Example of what gets recorded in the agent's action history after speaking:**

  - You said: "This ball feels familiar. I wonder where it came from."
- [x] Define what each action returns to the agent after execution (for memory / next prompt)

  **Agreed Decision:**

  - After each action is executed, the simulation produces a `result` string that is recorded in the agent's action history.
  - The agent's private `reasoning` (from its `AgentTurn` output) is also stored in the history for that turn.
  - This allows the agent to remember both **what** it did and **why** it chose to do it.
  - The result string is the primary piece of feedback the agent receives about the outcome of its action.

  **Final `result` strings for V0:**

  **move**
  - Success: "You moved {direction} to ({x}, {y})."
    Example: "You moved north to (2, 3)."
  - Failure (blocked by wall): "You tried to move {direction}, but were blocked by the {wall_name}."
    Example: "You tried to move west, but were blocked by the west wall."
  - Failure (off map): "You tried to move {direction}, but that direction is outside the room."

  **look**
  - Returns the full current description of the target.
  - Example: "You looked at the wooden sign. It reads: \"This is a controlled environment. You are the only one here...\""
  - For empty tiles (if allowed): "You looked at the space to your east. You see an empty space."

  **speak**
  - "You said: \"<exact spoken text>\""
    Example: "You said: \"This ball feels familiar. I wonder where it came from.\""

  Note: In V0, all text provided in the speak action is treated as verbal dialogue. No emote or action detection/stripping is performed.
- [x] Decide how action failures are communicated back to the agent

  **Agreed Decision:**

  - Action failures are communicated to the agent **through the `result` string** in the action history.
  - There is no separate error channel or special failure field.
  - The quality and clarity of the `result` string is the primary way the agent learns that an action did not succeed (and why).
  - This applies to all actions (`move`, `look`, `speak`).

## Section 4: Agent Turn Schema (Structured Output)

- [x] Finalize the Pydantic model the LLM must return every turn

  **Agreed Model:**

  The canonical model is defined in `docs/schemas/AgentTurn.py`.

  The model (`AgentTurn`) contains:
  - `reasoning`: str (required)
  - `action`: Literal["move", "look", "speak"]
  - `target`: Optional[str]
  - `content`: Optional[str]
  - `confidence`: Optional[str]
  - `emotion`: Optional[str]

- [x] Decide on required vs optional fields (`reasoning`, `action`, `target`, `content`, etc.)

  **Agreed Fields:**

  - Required: `reasoning` and `action`
  - Optional: `target`, `content`, `confidence`, `emotion`
  - `confidence` and `emotion` are kept for V0 (they can be removed later if they prove problematic during testing).

- [x] Define validation rules for each field (especially `target` depending on action)

  **Agreed Validation Rules:**

  - `move`: `target` must be one of "north", "east", "south", or "west".
  - `speak`: `content` is limited to a maximum of 5 sentences **and** 280 characters. Pure dialogue is encouraged via prompt only; no runtime emote/action detection.
  - `reasoning`: Limited to a maximum of 400 characters (to help control overall prompt token usage).
  - `confidence` and `emotion`: Limited to a maximum of 3 words each.
  - Full validators (including the new limits and heuristics) are implemented in `docs/schemas/AgentTurn.py`.
  - Note: Runtime checks (such as whether a `look` target is currently visible in passive vision) are performed by the action execution layer, not by the Pydantic model.

- [x] Define what happens when the model returns invalid JSON or invalid actions (fallback behavior)

  **Agreed Decision:**

  - When the model produces invalid output (invalid JSON, unknown action, invalid target, content validation failure, etc.), the simulation does **not** require the agent to output a special "confused" action.
  - Instead, the failure is recorded in the agent's action history via the `result` string using this format:
    ```
    This action wasn't recognized, ERR:{error name}, {error description}
    ```
  - The agent's position and state do not change on these failures (unless the failure itself implies a change, which is rare).
  - This is consistent with how other action failures (e.g. blocked movement) are already handled.

- [x] Decide on a clear "confused" or error action if the model fails

  **Agreed Decision:**

  - There is no "confused" action type that the agent is expected to output.
  - All model failures are handled by the simulation and communicated through the `result` string (see item above).
  - No additional prompt guidance will be added in V0 instructing the agent how to react to these error messages (we can add this later if testing shows the agent is confused or loops on errors).

  **Initial Error Codes for V0:**

  - `INVALID_JSON` — Model output was not valid JSON or failed Pydantic schema validation.
  - `UNKNOWN_ACTION` — The `action` field contained a value that is not one of the allowed actions.
  - `INVALID_TARGET` — The `target` was invalid or inappropriate for the chosen action.
  - `CONTENT_TOO_LONG` — The `content` field exceeded the allowed length (more than 5 sentences or 280 characters for `speak`).
  - `INVALID_CONTENT` — A field contained disallowed content (e.g. `confidence` or `emotion` longer than 3 words).
  - `REASONING_TOO_LONG` — The `reasoning` field exceeded the 400-character limit.

  **Known Limitations (V0) — Structured Output Validation**

  Speak `content` is not checked for emotes, action markers, or parenthetical asides at validation time. The prompt asks for verbal dialogue only; occasional non-dialogue text may appear in `passive_result` for other agents.

## Section 5: Perception (What the Agent Sees)

- [x] Define exactly what information the agent receives about the world each turn (passive perception)

  **Agreed Approach:**

  The agent receives a structured passive vision block each turn. This includes:
  - The agent's current position.
  - All visible objects using the format: `{name} ({id}), {coordinates} - {description}|[?]`
  - The agent is not listed as an object in passive vision. Its position is already stated at the top ("You are at (x, y)").
  - A separate room description string (e.g. "You are in a small room with a hardwood floor and four wooden walls").

  Objects the agent has not yet looked at (or that have changed since last looked at) are marked with `[?]`. The agent must use the `look` action to reveal the full description.

- [x] Decide how the grid, agent position, and objects are described in text

  **Agreed Format:**

  Passive vision uses this consistent format for objects:
  `{name} ({id}), {coordinates} - {description}|[?]`

  Example:
  - `Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.`
  - `Wooden Sign (obj_sign_01), (2, 4) - [?] (has changed since you last looked at it)`

  The agent is not shown as a separate entry in passive vision. Its current position is stated at the top of the vision block ("You are at (x, y)").

  Room boundaries are conveyed through the room description string rather than as objects.

- [x] Decide how much detail to give about the ball and sign before the agent has `look`ed at them

  **Agreed Approach:**

  Before the agent has used `look` on an object, it appears with `[?]` instead of its description in passive vision. This signals that more information is available via the `look` action.

  Once the agent has successfully looked at an object, its full description is shown in future passive vision.

- [x] Decide whether action hints ("You can move here", "You can look at the sign") are included

  **Agreed Decision:**

  Traditional action hints of the form "You can move here" or "You can look at the sign" will **not** be used.

  Instead, a dedicated **Available Actions** section will be included in the prompt (separate from passive vision). This section will explicitly list the actions the agent can take this turn, including valid movement directions and a rule for which objects can be looked at (via the `[?]` tag).

- [x] Keep token usage in mind — define rough target size for perception text

  **Agreed Targets for V0:**

  - **Passive Vision**: Target **under 250 tokens** (ideally 120–180 tokens with current scope and short descriptions).
  - **Total Prompt**: Target **under 2,000 tokens** per turn.
  - **Ideal operating range**: **1,200 – 1,600 tokens** (including passive vision, room description, available actions, recent history, and reasoning).

  These targets will be measured once we have a working prompt builder and can be adjusted if needed. The goal is to stay cheap and fast on DeepSeek while giving the agent enough context.

## Section 6: Memory (For One Agent)

- [x] Memory approach for V0

  **Agreed Approach:**

  The agent maintains a very minimal memory system consisting of two main parts:

  - **Last 10 turns**: Kept in full detail. Each turn stores the action taken, the agent's private reasoning, and the result/feedback from the simulation. This gives the agent short-term continuity and a sense of why it made recent decisions.

  - **List of looked-at objects**: A simple list of object IDs the agent has previously used the `look` action on. This list directly controls passive vision:
    - If an object ID is on the list → its current description is shown in passive vision.
    - If an object ID is not on the list (or has been removed) → the object appears with `[?]` (or the "has changed" variant for the sign).

  **Special case — The sign**: When the sign is updated by the human, it is removed from the agent's looked-at list. This causes it to reappear in passive vision with the format `Wooden Sign (obj_sign_01), (2, 4) - [?] The wooden sign has changed since you last looked at it.`, prompting the agent to look at it again if it wants current information.

  **What is explicitly not included in V0**:
  - No automatic summarization or rolling summaries.
  - No long-term or compressed memory.
  - No per-agent stored copies of object descriptions (the current description is always pulled from the world if the object is on the looked-at list).
  - No additional dynamic memory (reflections, beliefs, inferred facts, goals, emotional state, etc.).

  Spoken text is stored as part of the normal action history result (no special memory treatment).

## Section 7: Prompt Design

- [x] Decide the overall structure of the prompt sent to DeepSeek

  **Agreed Prompt Structure for V0 (high-level order):**

  1. **Character Description**  
     The agent’s own personality/description. Kept in its own dedicated section so it can be easily modified for experimentation and expanded in the future.

  2. **System Instructions / Rules**  
     Core rules of the simulation, how actions work, output format requirements, general behavioral guidelines, etc.

  3. **Room Description**  
     Static flavor text about the environment (e.g. "You are in a small room with a hardwood floor and four wooden walls.").

  4. **Current Passive Vision**  
     What the agent sees right now, using the defined format (`{name} ({id}), {coordinates} - {description}|[?]`). The agent’s position is stated at the top ("You are at (x, y)"), so the agent is not listed as a separate object in passive vision.

  5. **Available Actions This Turn**  
     Explicit list of valid actions the agent can take right now (valid movement directions + objects it can look at).

  6. **Recent History**  
     The last 10 turns, including the agent’s reasoning and the result of each action.

  **Canonical Format for Recent History entries (V0):**

  Each turn in the history is rendered as:

  ```
  Turn 3:
  Action: look
  Target: obj_sign_01
  Reasoning: The wooden sign shows [?], which means I haven't properly examined it yet.
  Result: You looked at the wooden sign. It reads: "This is a controlled environment..."
  ```

  Rules:
  - Always include `Action`, `Reasoning`, and `Result`.
  - Only include `Target` when it is not null.
  - Spoken content appears naturally inside the `Result` (e.g. `You said: "..."`).
  - Turns are shown oldest first.

  7. **Current Instructions / Reminders**  
     Any turn-specific notes (e.g. "You may only speak up to 5 sentences").

     **Note:** This section is intentionally minimal in V0. It currently contains only the speak limit reminder. Additional turn-specific guidance can be added here in the future if testing reveals the need.

  8. **Output Format**  
     Reminder of the exact JSON structure the model must follow.

  **Canonical Format for "Available Actions This Turn" (V0):**

  The block must follow this structure:

  ```
  You can move in the following directions this turn:
  - north
  - east
  - south
  - west

  You can look at anything with the [?] tag.
  ```

  Rules:
  - Only list directions the agent can legally move this turn (within the 0–4 grid).
  - Use the exact phrasing and bullet style shown above.
  - Never list specific objects under “You can look at”. The agent already sees which objects have the `[?]` tag in the Passive Vision section.
  - If no valid moves exist this turn, the movement section may be omitted.
- [x] Decide how much history (if any) we include in the prompt

  **Agreed Approach for V0:**

  Include the last 10 turns in full detail in the prompt.

  Each turn in the history includes:
  - The action taken
  - The agent's private reasoning at the time
  - The result/feedback returned by the simulation

  This gives the agent good short-term continuity and context for its recent decisions without overcomplicating the prompt. No additional summarization or older history is included in V0.
- [x] Define rough token budget targets per turn (we want to stay cheap)

  **Agreed Targets for V0:**

  - **Passive Vision**: Target **under 250 tokens** (ideally 120–180 tokens with current scope and short descriptions).
  - **Total Prompt**: Target **under 2,000 tokens** per turn.
  - **Ideal operating range**: **1,200 – 1,600 tokens** (including passive vision, room description, available actions, recent history, and reasoning).

  These targets will be measured once we have a working prompt builder and can be adjusted if needed. The goal is to stay cheap and fast on DeepSeek while giving the agent enough context.
- [x] Decide whether we will use few-shot examples in Version 0

  **Agreed Decision for V0:**

  Use **4 few-shot examples** in the prompt.

  These examples should focus on the most important and error-prone behaviors in V0:
  - Correct use of `speak` (pure dialogue only, max 5 sentences)
  - Using the `look` action when seeing objects marked with `[?]`
  - Choosing valid movement directions
  - Proper response when the sign has been updated

  The examples should be high quality and representative rather than trying to cover every possible situation. We can adjust the number or content later based on testing results.

  **Final 4 Few-Shot Examples (V0):**

  **Example 1: Correct use of `speak` (pure dialogue only)**

  Context:
  You are at (1, 1).
  Ceramic Ball (obj_ball_01), (2, 2) - [?]
  Wooden Sign (obj_sign_01), (2, 4) - A simple wooden sign. It reads: "This is a controlled environment..."
  You can move in the following directions this turn:
  - north
  - east
  - south
  - west
  You can look at anything with the [?] tag.

  Output:
  {
    "reasoning": "I notice the ball has a [?] tag. I should comment on that and consider looking at it soon.",
    "action": "speak",
    "target": null,
    "content": "That ball has a question mark next to it. I wonder what happens if I look at it.",
    "confidence": "curious",
    "emotion": "intrigued"
  }

  **Example 2: Using `look` when seeing `[?]`**

  Context:
  You are at (2, 3).
  Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
  Wooden Sign (obj_sign_01), (2, 4) - [?]
  You can move in the following directions this turn:
  - north
  - east
  - south
  - west
  You can look at anything with the [?] tag.

  Output:
  {
    "reasoning": "The wooden sign shows [?], which means I haven't properly examined it yet. I should look at it to get the current information.",
    "action": "look",
    "target": "obj_sign_01",
    "content": null,
    "confidence": "decided",
    "emotion": "curious"
  }

  **Example 3: Choosing a valid `move` direction**

  Context:
  You are at (2, 2).
  Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
  Wooden Sign (obj_sign_01), (2, 4) - A simple wooden sign. It reads: "..."
  You can move in the following directions this turn:
  - north
  - east
  - south
  - west

  Output:
  {
    "reasoning": "I want to get closer to the sign so I can examine it more easily. Moving north is the most direct option.",
    "action": "move",
    "target": "north",
    "content": null,
    "confidence": "certain",
    "emotion": "focused"
  }

  **Example 4: Responding to the sign being updated**

  Context:
  You are at (1, 1).
  Ceramic Ball (obj_ball_01), (2, 2) - A slightly worn ceramic ball. It has a few scuffs and feels light.
  Wooden Sign (obj_sign_01), (2, 4) - [?] The wooden sign has changed since you last looked at it.
  You can move in the following directions this turn:
  - north
  - east
  - south
  - west
  You can look at anything with the [?] tag.

  Output:
  {
    "reasoning": "The sign now shows that it has changed since I last looked at it. I should examine it again to see the new message.",
    "action": "look",
    "target": "obj_sign_01",
    "content": null,
    "confidence": "curious",
    "emotion": "alert"
  }
- [x] Plan how we will log the full prompt + model response for debugging

  **Agreed Approach for V0:**

  - For V0, the primary focus is **rich, verbose console output** on every turn. This will be the main way we observe and debug the system during manual stepping.
  - For each turn, the following will be printed clearly to the console:
    - Turn number
    - The full prompt sent to the model
    - The raw model output (the exact JSON string returned)
    - The parsed `AgentTurn` (after Pydantic validation)
    - The resulting `result` string that was written to the agent's action history
    - Any errors or fallback behavior (e.g. invalid JSON, unknown action, etc.)
    - Token usage (prompt tokens + completion tokens), when available

  - In addition, the same data will be written to a log file for later review and persistence.
  - The console output should be human-readable and well separated between turns to make live observation easy.

  This will be critical for debugging the agent's behavior and the reliability of the structured output.

## Section 8: Model Integration & Error Handling

- [x] Decide how we will call DeepSeek (raw HTTP, OpenAI-compatible client, LangChain, etc.)

  **Agreed Decision for V0:**

  Use the **OpenAI-compatible client** (via the official `openai` Python package), pointed at OpenRouter’s base URL.

  Reasons:
  - OpenRouter fully supports the OpenAI Chat Completions format.
  - It is simple, familiar, and has minimal boilerplate.
  - It avoids pulling in heavier frameworks like LangChain for V0.
  - Easy to swap to raw `httpx` later if more control is needed.

  We will likely wrap this client in a small `LLMClient` class later (see later item in this section) for better separation of concerns, but for now the direct OpenAI-compatible client is sufficient.
- [x] Decide on timeout, retry, and error handling strategy

  **Agreed Strategy for V0:**

  - **Retries**: Allow **1 retry** on transient errors.
  - **Timeout**: No automatic timeout on LLM calls. A hanging request can be interrupted via keyboard input from the console.
  - **Error Handling**:
    - Any LLM-related error (rate limits, invalid requests, model downtime, authentication issues, network errors, etc.) should **pause the simulation**.
    - The error must be clearly logged to both the **console** and the **log file**.
    - Because V0 is designed for manual stepping (one turn at a time), an error should **end the current turn** gracefully rather than crashing the program.
    - The user can then inspect the error and decide how to proceed (e.g., fix the prompt, wait and retry manually, or adjust the sign).

  This approach prioritizes visibility and control during manual testing over full automation.
- [x] Plan how we will parse and validate the model's output

  **Agreed Approach for V0:**

  - Use **Pydantic strict validation** against the `AgentTurn` model.
  - On success: Proceed normally with the parsed `AgentTurn` object.
  - On failure (either JSON parsing failure or Pydantic validation error):
    - Log the **full raw model response** + the exact error details to both the **console** and the **log file**.
    - Generate a standardized error message in the `result` string using the agreed format:
      ```
      This action wasn't recognized, ERR:{error name}, {error description}
      ```
    - End the current turn gracefully (do not crash the simulation).
    - The agent will see the error in its action history on the next turn.

  - Raw response logging is only performed on failure for now (successes are visible via the rich console output).

  This keeps the system robust while maintaining good visibility during manual stepping. We can revisit logging behavior later if needed.
- [x] Decide on a clean place to put all LLM-related code (separation of concerns)

  **Agreed Decision for V0:**

  Create a dedicated module (e.g. `llm/` or `client/`) to contain all LLM-related code.

  This module should include:
  - OpenAI-compatible client setup (pointed at OpenRouter)
  - A thin wrapper class (e.g. `LLMClient`) responsible for:
    - Making model calls
    - Handling the agreed retry logic (1 retry)
    - Catching and logging errors
    - Returning structured data to the rest of the system

  The rest of the codebase (simulation, perception, action handling, etc.) should only interact with this module through a narrow, well-defined interface. They should not directly import or use the OpenAI client.

  This provides good separation of concerns without over-engineering for V0. We can refine the structure later as the project grows.

## Section 9: Observability & Debugging (Very Important)

- [x] Define what gets logged every turn (prompt, output, world state before/after, action result)

  **Agreed Approach for V0:**

  - On normal/successful turns: No file logging by default. All relevant information (prompt, model output, parsed result, action history, etc.) is printed to the console in a rich, readable format.
  - When the `--log` flag is passed at startup: Full context for every turn is also written to a timestamped log file in `logs/`.
  - On errors or failures (LLM errors, invalid output, etc.): Full context is always logged to both the console and a log file (regardless of the `--log` flag).

- [x] Decide on a logging approach (rich console, structured JSON logs, both?)

  **Agreed Approach for V0:**

  - **Console logging**: Rich and verbose on every turn. This is the primary debugging tool during manual stepping. It should clearly show the prompt, model response, reasoning, result, and any errors in an easy-to-read format.
  - **File logging**:
    - By default: Only errors and failures are written to file.
    - With the `--log` startup flag: The entire run (all turns, prompts, model outputs, reasoning, results, and action history) is written to a timestamped file in `logs/`.
    - Full-run logging is primarily intended to support offline evaluation of the Reasonable Action Rate (see Section 11).

- [x] Make sure we can easily review why the agent did what it did

  **Agreed Approach for V0:**

  - The main way to understand the agent’s decisions is through the rich console output on each turn.
  - Each turn’s output will include the agent’s `reasoning` + the `result` of the action.
  - The last 10 turns of history (with reasoning and results) are also printed as part of the console output.
  - When an error occurs, the full context is logged to both console and file so it can be reviewed later.
  - No complex log querying tools are needed for V0 — the combination of rich per-turn console output + error-only file logs should be sufficient.

## Section 10: Project Structure & Tech Decisions

- [x] Finalize the top-level folder structure for the project

  **Agreed Folder Structure for V0:**

  ```
  ai_simulation_v0/
  ├── src/
  │   ├── __init__.py
  │   ├── main.py                    # Entry point for manual stepping
  │   ├── simulation.py              # Main simulation / turn loop
  │   ├── world.py                   # World class (grid, agents, objects)
  │   ├── agent.py                   # Agent dataclass + logic
  │   ├── object.py                  # Object dataclass
  │   ├── perception.py              # Passive vision + look logic
  │   ├── memory.py                  # Last 10 turns + looked-at objects list
  │   ├── actions/                   # Action implementations
  │   │   ├── __init__.py
  │   │   ├── move.py
  │   │   ├── look.py
  │   │   └── speak.py
  │   ├── llm/                       # All LLM-related code (separation of concerns)
  │   │   ├── __init__.py
  │   │   ├── client.py              # LLMClient wrapper
  │   │   └── schemas.py             # AgentTurn Pydantic model
  │   ├── log_utils/                 # Logging utilities (renamed from 'logging/' to avoid shadowing the stdlib 'logging' module)
  │   │   └── logger.py
  │   └── utils/
  │       └── ids.py
  ├── docs/
  │   ├── v0-implementation-readiness-checklist.md
  │   └── schemas/
  │       └── AgentTurn.py           # Working copy / design reference (will be synced to src/llm/schemas.py later)
  ├── pyproject.toml
  └── README.md
  ```

  Notes:
  - A working copy of the schema lives in `docs/schemas/AgentTurn.py` during the design phase.
  - Once we begin implementation, the authoritative version will live in `src/llm/schemas.py`.
  - No additional top-level folders (e.g. `tests/`, `data/`) are planned for V0 to keep complexity low.
- [x] Decide on core dependencies (Pydantic version, OpenRouter client library, logging library, etc.)

  **Agreed Core Dependencies for V0:**

  - `pydantic` (>= 2.0) — For data models and strict validation of the `AgentTurn` schema.
  - `openai` — OpenAI-compatible client library, used to call DeepSeek via OpenRouter.
  - `rich` — For rich, verbose console output during manual stepping and debugging.
  - `python-dotenv` (recommended) — For loading environment variables (e.g. API keys) from a `.env` file.

  These dependencies are intentionally kept minimal for V0. Additional libraries (e.g. testing frameworks, CLI tools, or more advanced LLM frameworks) can be added later if needed.
- [x] Decide how world state will be stored in Version 0 (in-memory is acceptable)

  **Agreed Decision for V0:**

  - World state will be stored **entirely in memory**.
  - Core domain objects (`Agent` and `Object`) will be defined as **dataclasses**.
  - A `World` class (or dataclass) will hold the full simulation state (agents, objects, grid rules, etc.).
  - **No persistence** (saving or loading world state to files or a database) is required for V0.
  - This keeps the implementation simple and focused on manual stepping and debugging during early development. Persistence can be added in a future version if needed.
- [x] Decide whether we want a simple CLI or just a script we run manually at first

  **Agreed Decision for V0:**

  Use a simple script (e.g. `main.py`) for manual stepping. No full CLI framework (such as Typer or Click) is needed for V0.

  The script will support the following commands:

  - `step` — Advance the simulation by one turn (agent acts, simulation updates, output is printed).
  - `quit` — Exit the simulation.
  - `sign "{new sign description}"` — Update the text on the wooden sign. This is a special debugging/testing command that allows the human to directly communicate with the agent by changing the sign's description. When used, the sign is removed from the agent's "looked at" list so it reappears with the "has changed" state in passive vision.

  The script can also be started with the `--log` flag. When present, the entire run is saved to a timestamped file in `logs/`. This is mainly intended to support offline evaluation of action reasonableness (see Section 11).

  This keeps the interface minimal and easy to use while manually stepping through runs during development and testing.
- [x] Confirm we will keep the simulation engine separate from the LLM calling code

  **Agreed Decision:**

  The simulation engine (world state, actions, perception, memory, turn logic, etc.) will be kept completely separate from the LLM calling code.

  All code that interacts with the model (OpenAI-compatible client, prompt construction, response handling, retries, error handling, etc.) will live in a dedicated `llm/` module (or similar), wrapped behind a thin `LLMClient` interface.

  The rest of the system will only interact with the LLM layer through this narrow interface. This separation was already decided in Section 8 and is now formally confirmed here for the project structure.

## Section 11: Testing & Validation Strategy

- [x] Define how we will test the structured output loop without a full world yet (if possible)

  **Agreed Approach for V0:**

  Create a simple, standalone test script (e.g. `test_structured_output.py`) whose only purpose is to test whether the model can reliably produce valid `AgentTurn` outputs.

  Characteristics of the test:
  - It builds a minimal prompt using a **hardcoded scenario** containing only the ball and the sign (no dynamic scenarios or variations for V0).
  - It uses the same prompt assembly logic and `LLMClient` that the real simulation will use.
  - It sends the prompt to the model, attempts to parse the response into the `AgentTurn` Pydantic model, and reports success or failure.
  - On failure, it prints the raw model output and the exact validation errors.
  - On success, it prints the parsed `AgentTurn`.

  Purpose:
  - Allow quick, cheap, isolated testing of prompt quality and structured output reliability.
  - Make it easy to iterate on the prompt and few-shot examples without running the full simulation.
  - Keep the test extremely simple (one fixed scenario) to avoid wasting LLM calls during early development.
- [x] Decide what "good enough" structured output reliability looks like for DeepSeek

  **Agreed Targets for V0 (end-of-V0 goals):**

  - **Parse Success Rate**: ≥ 92%  
    (Responses must be valid JSON and pass Pydantic validation against the `AgentTurn` model.)

  - **Valid Action Rate**: ≥ 80%  
    (Of the responses that parse successfully, the chosen `action` + `target` must be legal in the current state.)

  - **Reasonable / Sensible Action Rate**: ≥ 70%  
    (Of the valid actions, the choice should feel contextually reasonable. This is more qualitative but still worth tracking during testing.)

  **Reasonable Action Rubric (V0):**

  An action is considered **reasonable** if it meets all of the following criteria:

  1. **Contextually relevant** — The action responds to something the agent can currently observe (via passive vision or recent history) and is not random or disconnected from the situation.
  2. **Not obviously pointless** — The action does not appear to be a waste of a turn with no plausible upside (e.g. repeatedly moving back and forth between the same tiles with no new information).
  3. **Respects known constraints and signals** — The agent does not ignore clear, recently observed information (e.g. repeatedly ignoring `[?]` tags after previously using `look` successfully).
  4. **Stays within V0 rules** — For `speak`, the output remains pure verbal dialogue.

  **How to evaluate reasonableness in practice:**

  - Full simulation runs can produce a complete log of every turn (prompt, model output, reasoning, result, and action history) when logging is enabled.
  - These logs can be fed into a fresh Grok chat along with the rubric above for independent judgment.
  - For obviously wrong or clearly reasonable actions, the human running the simulation can mark them directly without needing an AI review.
  - Borderline cases should be noted so the rubric can be refined after the first batch of tests.

  **How to evaluate the overall targets:**

  - Use the simple structured output test script (hardcoded ball + sign scenario) for the Parse Success Rate and Valid Action Rate.
  - Use full simulation runs (with logging enabled when needed) for the Reasonable Action Rate.
  - Run **20–30 manual tests** across a few different situations.
  - These are **end-of-V0 targets**, not starting targets. It is expected to be lower while still iterating on the prompt and few-shot examples.
  - If these targets are consistently met after reasonable prompt work, that is considered “good enough” to proceed with building the full simulation.
  - If the numbers remain significantly below target after effort, we should re-evaluate the prompting approach or model choice before moving forward.
- [x] Plan a way to manually step the simulation turn-by-turn during development

  **Agreed Approach for V0:**

  A simple manual stepping script will be the primary way to run and debug the simulation during V0.

  Supported commands during a run:
  - `step` — Advance the simulation by one turn. This will:
    - Build and print the full prompt sent to the model.
    - Print the raw LLM response (the JSON).
    - Execute the action and print the result that gets written to the agent’s action history.
  - `sign "{new text}"` — Update the sign’s description. This command does **not** consume a turn. It is purely a debugging/testing tool that allows the human to inject new information for the agent to discover.
  - `quit` — Exit the simulation.

  The simulation can be started with the `--log` flag (e.g. `python main.py --log`). When enabled:
  - Every turn’s full context is written to a timestamped file in `logs/`.
  - This is primarily useful for later offline review, especially for evaluating the Reasonable Action Rate using the rubric in Section 11.

  The goal is to make every turn very transparent for debugging. Because V0 is focused on learning and manual testing, the output does not need to be clean or summarized — printing the raw prompt, raw model output, and the resulting action history entry is acceptable and even desirable.
- [x] Define how we will catch and handle common model mistakes (bad targets, invalid actions, etc.)

  **Agreed Approach for V0:**

  All model mistakes and invalid actions are caught during parsing/validation or during action execution. They are **not** handled by having the agent output a special "confused" action.

  Instead:
  - The simulation detects the problem.
  - The error is logged to both the console and the log file (full context including raw model output when relevant).
  - A clear error message is written into the agent's action history via the `result` string using this format:
    ```
    This action wasn't recognized, ERR:{error name}, {error description}
    ```

  Initial error codes defined for V0:
  - `INVALID_JSON` — The model output was not valid JSON or failed basic parsing.
  - `UNKNOWN_ACTION` — The `action` field contained a value that is not one of the allowed actions (`move`, `look`, `speak`).
  - `INVALID_TARGET` — The `target` was invalid or inappropriate for the chosen action (e.g. bad direction, unknown object ID).
  - `CONTENT_TOO_LONG` — The `content` field exceeded the allowed length (more than 5 sentences or 280 characters for `speak`).
  - `INVALID_CONTENT` — A field contained disallowed content (e.g. `confidence` or `emotion` longer than 3 words).
  - `REASONING_TOO_LONG` — The `reasoning` field exceeded the 400-character limit.

  On any of these errors:
  - The current turn ends gracefully.
  - The agent's state (position, memory, etc.) does not change as a result of the failed action.
  - The agent sees the error message in its action history on the next turn and can react to it.

## Section 12: Final Readiness

- [x] Review the entire checklist and confirm nothing critical is missing

  **Status:** Complete

  **Summary of Review Performed:**
  - All major gaps identified in the Readiness Gap Report have been closed (memory length + TurnRecord, success criteria, Available Actions format, sign special case containment, validators, action history format, reasonable action rubric + evaluation method).
  - Recent Verifier feedback (open look checkbox, last_action field, thin "Current Instructions / Reminders" section) has been addressed. Pure-dialogue emote heuristic removed after false-positive failures in live testing.
  - A "Known Limitations (V0)" subsection was added in Section 4.
  - All sections 1–11 are now marked complete in the status summary.

  **Remaining Minor Items Noted (for awareness, not blockers):**
  - "Current Instructions / Reminders" section remains intentionally minimal.
  - Actual token usage against the full proposed prompt structure has never been measured.
  - Long-term storage strategy for the four few-shot examples is not yet decided.

  **Completion Note:** User confirmed on 2026-05-31 that no critical items remain. Item marked complete.

- [x] Confirm we have a shared understanding of the architecture

  **Status:** Complete

  **Completion Note:** User confirmed on 2026-05-31 that the architecture walkthrough (World Model, Agent, Memory, Perception, Actions, LLM Layer, Project Structure, Observability, and Turn Flow) matches their understanding. Item marked complete.

- [x] Confirm we are ready to begin implementation

  **Status:** Complete

  **Completion Note:** Final review completed by the Verifier on 2026-05-31. The Verifier recommended marking this item complete. No critical or high-risk issues remain. Section 12 is now fully complete. Implementation may begin.

---

## Notes

- This checklist is intentionally small. We are deliberately cutting scope to make the first version understandable and enjoyable.
- Any item that feels too big or unclear should be split or discussed before being marked complete.
- We can add new items to this checklist if we discover gaps while working through it.

**Current Status:**  

**Section 1: High-Level Scope & Goals** — ✅ Complete

**Section 2: World Model** — ✅ Complete

**Section 3: Actions (The Three Actions)** — ✅ Complete

**Section 4: Agent Turn Schema (Structured Output)** — ✅ Complete

**Section 5: Perception (What the Agent Sees)** — ✅ Complete

**Section 6: Memory (For One Agent)** — ✅ Complete

**Section 7: Prompt Design** — ✅ Complete

**Section 8: Model Integration & Error Handling** — ✅ Complete

**Section 9: Observability & Debugging (Very Important)** — ✅ Complete

**Section 10: Project Structure & Tech Decisions** — ✅ Complete

**Section 11: Testing & Validation Strategy** — ✅ Complete

Completed in Section 11:
- Isolated structured output test script (hardcoded ball + sign scenario, one-shot manual testing)
- Reliability targets for DeepSeek (≥92% parse success, ≥80% valid actions, ≥70% reasonable actions) — defined as the authoritative success criteria in Section 11
- Reasonable Action Rubric + evaluation method using simulation logs (human review or separate Grok chat)
- Manual stepping workflow defined (step prints full prompt + raw LLM response + action result; sign command does not consume a turn; `--log` flag for full-run logging)
- Error handling for model mistakes defined (via result string with ERR: codes, logged to console + file, graceful turn end)
- Action history format in prompts finalized
- Logging strategy updated (default = errors only; `--log` flag enables full-run persistence for review and reasonableness evaluation)

**Section 12: Final Readiness** — ✅ Complete

All three items in Section 12 have been completed following the Verifier's final review.

Important note: Walls/room boundaries are **not** objects in V0. They are described via a room description string in the prompt.