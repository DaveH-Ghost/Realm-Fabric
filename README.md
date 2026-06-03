# Realm Fabric

A grid-based agent simulation framework designed around structured output and narrative roleplay.

**Current Status:** Early development (V0 phase)

This project is currently in the design and initial implementation phase, focused on building a reliable foundation for agent behavior using structured LLM output.

This project was made using the Grok Build CLI.

## Running / Testing (without LLM)

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it (Windows PowerShell):
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. In the project folder:
   ```powershell
   cd C:\Users\david\desktop\Projects\Git_Projects\Realm-Fabric
   uv sync
   ```

3. Run the interactive manual tester:
   ```powershell
   uv run python src/main.py
   ```

   Few-shot examples are disabled by default for token efficiency (saves ~50% tokens). Use `--with-fewshots` if you want the 4 examples included.

   Inside the `(realm)` prompt you can:
   - `state` — see current world/agent state
   - `vision` — see what the agent currently perceives
   - `prompt` — see the full prompt the LLM would receive
   - `step look obj_ball_01` — manually drive the agent (great for testing)
   - `Explorer` — (type the agent's name) to let the **LLM** decide the next action (requires OPENROUTER_API_KEY). Few-shot examples are OFF by default (saves ~50% tokens; current models perform well without them). Use `--with-fewshots` or `fewshots on` to enable.
   - `sign "new text here"` — simulate the human updating the sign (triggers the special "has changed" behavior)
   - `quit`

## Environment Variables & .env Files (Beginner Guide)

This project uses **environment variables** for things like API keys. We manage them with a library called `python-dotenv`.

### What are .env files?

A `.env` file is just a plain text file that looks like this:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
```

Each line is `KEY=VALUE`. These become available to your program as if you had set them in the operating system environment.

### Why use .env files?

- You don't want to hard-code secrets (API keys, passwords) into your source code.
- Different people/machines can have different values.
- You can have different settings for development vs production.

### How to set one up in this project

1. Copy the template that is safe to commit:
   ```powershell
   copy .env.example .env
   ```

2. Open the new `.env` file in a text editor and fill in the values.

3. Save it. The program will automatically pick it up.

**Important**: The file `.env` is listed in `.gitignore`, so Git will never commit your real keys.

### How this program loads .env files

When you trigger anything that needs the LLM (e.g. typing the agent's name in the stepper), the code in `src/llm/client.py` automatically runs:

```python
load_dotenv()                    # loads .env
load_dotenv(".env.local", override=True)   # then loads .env.local (if it exists)
```

This means:
- Values in `.env.local` will override values in `.env`
- You only need a `.env` file for basic use

### Can I have multiple .env files?

**Yes.** This is very common. Here are typical patterns:

| File                  | Purpose                              | Commit to Git? | Example use |
|-----------------------|--------------------------------------|----------------|-------------|
| `.env`                | Base settings for the project        | No (use .env.example instead) | Shared team defaults |
| `.env.local`          | Your personal overrides              | **Never**      | Your own API keys, local database URL |
| `.env.development`    | Development-specific settings        | Sometimes      | Debug flags, local services |
| `.env.production`     | Production settings                  | Sometimes      | Real production keys (usually managed by the server instead) |
| `.env.example`        | Template with placeholder values     | **Yes**        | Shows teammates what keys are needed |

You can load any of them explicitly like this (advanced):

```python
from dotenv import load_dotenv
load_dotenv(".env.development", override=True)
```

### Quick commands

```powershell
# Create your local file from the template
copy .env.example .env

# Edit it (add your real OPENROUTER_API_KEY)

# Then run the program - it will automatically read the .env file
uv run python src/main.py
```

### Without any .env file

You can still use almost everything:
- All the manual commands (`step ...`, `vision`, `state`, `sign`, etc.) work perfectly.
- The only thing that requires an `OPENROUTER_API_KEY` is when you type an agent's name (e.g. `Explorer`) to let the LLM actually decide what to do.

This design is intentional so you can explore and test the system without needing any paid services.

### Where the code actually reads the variables

Look at `src/llm/client.py`:

```python
from dotenv import load_dotenv
import os

load_dotenv()                    # loads .env + .env.local
api_key = os.getenv("OPENROUTER_API_KEY")
model   = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
```

`os.getenv("SOME_KEY")` looks for an environment variable. `load_dotenv()` populates those variables from the .env file(s) before the rest of the program runs.

That's the whole magic.

## Running tests
```powershell
uv run pytest
```

