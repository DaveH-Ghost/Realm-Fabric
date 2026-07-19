"""
game_profile.py

V0.3.0c — bundled prompt templates, few-shots, and default area factory.

Profiles customize prompt *layout* and scenario defaults. The engine always
builds ``PromptContext`` from live sim state; profiles never compute game rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area, create_initial_area
from campaign_rpg_engine.llm.prompt_context import PromptContext
from campaign_rpg_engine.llm.schemas import AgentCompoundTurn
from campaign_rpg_engine.prompt_template import PromptTemplate


def _resolve_profiles_root() -> Path:
    return Path(__file__).resolve().parent.parent / "profiles"


_PROFILES_ROOT = _resolve_profiles_root()

_SCHEMA_REGISTRY: dict[str, type[AgentCompoundTurn]] = {
    "AgentCompoundTurn": AgentCompoundTurn,
}


@dataclass(frozen=True)
class GameProfile:
    """
    Game/scenario configuration for Session and downstream apps.

    ``schema_id`` is metadata for now (V0.4 will make it swappable).
    """

    profile_id: str
    schema_id: str
    template: PromptTemplate
    create_area: Callable[[], Area]
    few_shot_examples: str = ""
    include_examples_default: bool = False

    def turn_schema(self) -> type[AgentCompoundTurn]:
        """Return the Pydantic model for LLM turn validation."""
        try:
            return _SCHEMA_REGISTRY[self.schema_id]
        except KeyError as exc:
            raise ValueError(
                f"Unknown schema_id {self.schema_id!r} for profile {self.profile_id!r}"
            ) from exc

    def build_prompt(
        self,
        ctx: PromptContext,
        *,
        include_examples: bool | None = None,
        blocks: list | None = None,
        agent: Agent | None = None,
        area: Area | None = None,
        vision_units: str = "",
        units_per_tile: int | None = None,
        coordinate_mode: str = "full",
        lorebooks: dict | None = None,
        lorebook_char_budget: int | None = None,
        lorebook_scan_config=None,
        passive_vision: str = "",
        session: object | None = None,
    ) -> str:
        """Assemble the LLM prompt from engine-built context."""
        from campaign_rpg_engine.lorebook.models import DEFAULT_LOREBOOK_CHAR_BUDGET
        from campaign_rpg_engine.prompt_blocks import render_prompt_blocks

        show_examples = (
            self.include_examples_default if include_examples is None else include_examples
        )
        use_blocks = blocks
        budget = (
            DEFAULT_LOREBOOK_CHAR_BUDGET if lorebook_char_budget is None else lorebook_char_budget
        )
        if use_blocks is None:
            prompt = self.template.render_context(ctx)
        else:
            prompt = render_prompt_blocks(
                use_blocks,
                ctx,
                agent=agent,
                area=area,
                session=session,
                vision_units=vision_units,
                units_per_tile=units_per_tile,
                coordinate_mode=coordinate_mode,
                lorebooks=lorebooks,
                lorebook_char_budget=budget,
                lorebook_scan_config=lorebook_scan_config,
                passive_vision=passive_vision or ctx.passive_vision,
            )
        if show_examples and self.few_shot_examples.strip():
            prompt = (
                f"{prompt}\n\nHere are compound turn examples:\n{self.few_shot_examples.strip()}"
            )
        return prompt.strip()


def _load_profile_dir(
    profile_id: str,
    directory: Path,
    *,
    schema_id: str,
    create_area: Callable[[], Area],
    include_examples_default: bool = False,
) -> GameProfile:
    template = PromptTemplate.from_file(directory / "template.txt")
    few_shots_path = directory / "few_shots.txt"
    few_shots = (
        few_shots_path.read_text(encoding="utf-8").strip() if few_shots_path.is_file() else ""
    )
    return GameProfile(
        profile_id=profile_id,
        schema_id=schema_id,
        template=template,
        create_area=create_area,
        few_shot_examples=few_shots,
        include_examples_default=include_examples_default,
    )


def default_compound_profile() -> GameProfile:
    """Reference profile — same compound prompt behavior as pre-0.3.0c."""
    return load_profile("default_compound")


_BUILTIN_PROFILE_IDS = frozenset({"default_compound"})


def load_profile(name_or_path: str | Path) -> GameProfile:
    """
    Load a ``GameProfile`` by built-in id or directory path.

    Built-in ids resolve under ``profiles/`` at the project/package root.
    Directory paths must contain ``template.txt`` (and optional ``few_shots.txt``).
    """
    if isinstance(name_or_path, Path):
        directory = name_or_path
        profile_id = directory.name
    else:
        raw = name_or_path.strip()
        path_candidate = Path(raw)
        if path_candidate.is_dir():
            directory = path_candidate.resolve()
            profile_id = directory.name
        elif raw in _BUILTIN_PROFILE_IDS or (_PROFILES_ROOT / raw).is_dir():
            profile_id = raw
            directory = (_PROFILES_ROOT / profile_id).resolve()
        else:
            raise ValueError(f"Unknown profile: {name_or_path!r}")

    if not (directory / "template.txt").is_file():
        raise ValueError(f"Profile directory {directory} is missing template.txt")

    return _load_profile_dir(
        profile_id,
        directory,
        schema_id="AgentCompoundTurn",
        create_area=create_initial_area,
    )
