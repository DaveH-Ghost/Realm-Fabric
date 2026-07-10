"""
Interact result/passive template placeholders (V0.4.0+).

Used by ``interact()`` when formatting ``ObjectAction.result`` and
``passive_result`` strings after effects run.
"""

from __future__ import annotations

from dataclasses import dataclass

from campaign_rpg_engine.coordinates import format_coordinate

INTERACT_TEMPLATE_VARS: tuple[tuple[str, str], ...] = (
    ("actor", "Acting agent's display name"),
    ("object", "Target object's display name"),
    ("object_start", "Object position (x,y) before effects run"),
    ("object_end", "Object position (x,y) after effects run"),
    ("actor_start", "Agent position (x,y) before effects run"),
    ("actor_end", "Agent position (x,y) after effects run"),
    ("object_start_area", "Area id where the object is before effects"),
    ("object_end_area", "Area id where the object is after effects"),
    ("actor_start_area", "Agent's area id before effects"),
    ("actor_end_area", "Agent's area id after effects"),
)


@dataclass(frozen=True)
class InteractTemplateContext:
    actor: str
    object_name: str
    object_start: tuple[int, int]
    object_end: tuple[int, int]
    actor_start: tuple[int, int]
    actor_end: tuple[int, int]
    object_start_area: str
    object_end_area: str
    actor_start_area: str
    actor_end_area: str


def interact_template_var_help() -> list[dict[str, str]]:
    """JSON-friendly list of placeholders for clients."""
    return [
        {
            "name": name,
            "placeholder": "{" + name + "}",
            "description": description,
        }
        for name, description in INTERACT_TEMPLATE_VARS
    ]


def format_interact_template(template: str, ctx: InteractTemplateContext) -> str:
    """Substitute ``{name}`` placeholders in *template*."""
    replacements = {
        "actor": ctx.actor,
        "object": ctx.object_name,
        "object_start": format_coordinate(*ctx.object_start),
        "object_end": format_coordinate(*ctx.object_end),
        "actor_start": format_coordinate(*ctx.actor_start),
        "actor_end": format_coordinate(*ctx.actor_end),
        "object_start_area": ctx.object_start_area,
        "object_end_area": ctx.object_end_area,
        "actor_start_area": ctx.actor_start_area,
        "actor_end_area": ctx.actor_end_area,
    }
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", value)
    return result
