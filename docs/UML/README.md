# UML diagrams (Mermaid)

Visual architecture for CampAIgn-RPG-Engine **1.6.0+**. Diagrams use [Mermaid](https://mermaid.js.org/) and render on GitHub.

## Index

| Doc | Contents |
|-----|----------|
| [AUDIT-1.6.0.md](AUDIT-1.6.0.md) | Pre-cleanup hotspots, move/keep list, non-goals |
| [01-system-overview.md](01-system-overview.md) | Engine library vs Studio GM host vs future clients |
| [02-session-turn-flow.md](02-session-turn-flow.md) | Prompt → LLM → compound turn → snapshot |
| [03-package-layout.md](03-package-layout.md) | Package layout after `edit/` + `templates/` |
| [04-edit-mutation-stack.md](04-edit-mutation-stack.md) | Session typed APIs vs edit helpers vs Studio CLI |

## How to edit

- Prefer small diagrams with clear node IDs (no spaces in Mermaid IDs).
- Keep diagrams aligned with code; update when packages move again.
