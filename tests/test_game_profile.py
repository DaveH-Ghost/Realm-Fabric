"""GameProfile and prompt templates (V0.3.0c)."""

from src.area import create_initial_area
from src.game_profile import GameProfile, default_compound_profile, load_profile
from src.llm.prompt import build_compound_prompt
from src.llm.prompt_context import build_prompt_context
from src.llm.schemas import AgentCompoundTurn
from src.prompt_template import PromptTemplate
from src.session import Session


def test_default_profile_prompt_contains_required_sections():
    session = Session.from_default()
    prompt = session.build_prompt()
    assert "Passive Vision:" in prompt
    assert "Memory:" in prompt
    assert '"move"' in prompt
    assert '"action"' in prompt


def test_default_profile_matches_build_compound_prompt():
    session = Session.from_default()
    agent = session.get_active_agent()
    legacy = build_compound_prompt(agent, session.area)
    via_profile = session.build_prompt()
    assert via_profile == legacy


def test_default_profile_with_examples():
    session = Session.from_default(include_examples=True)
    prompt = session.build_prompt()
    assert "Example 1: Move, look, and speak" in prompt


def test_default_profile_schema_id():
    profile = default_compound_profile()
    assert profile.schema_id == "AgentCompoundTurn"
    assert profile.turn_schema() is AgentCompoundTurn


def test_default_profile_area_factory_matches_create_initial_area():
    profile = default_compound_profile()
    from_profile = profile.create_area()
    from_helper = create_initial_area()

    assert from_profile.bounds == from_helper.bounds
    assert from_profile.area_description == from_helper.area_description
    assert len(from_profile.agents) == len(from_helper.agents)
    assert len(from_profile.get_objects()) == len(from_helper.get_objects())

    pa = from_profile.get_agent()
    ha = from_helper.get_agent()
    assert pa.id == ha.id
    assert pa.name == ha.name
    assert pa.position == ha.position

    profile_ids = {o.id for o in from_profile.get_objects()}
    helper_ids = {o.id for o in from_helper.get_objects()}
    assert profile_ids == helper_ids


def test_session_from_profile():
    profile = default_compound_profile()
    session = Session.from_profile(profile)
    assert session.profile.profile_id == "default_compound"
    assert session.get_active_agent().name == "Explorer"


def test_custom_minimal_template_injects_context():
    area = create_initial_area()
    agent = area.get_agent()
    ctx = build_prompt_context(agent, area)

    template = PromptTemplate(
        "{{character}}\n---\n{{passive_vision}}\n---\n{{memory}}\n---\n{{output_format}}"
    )
    profile = GameProfile(
        profile_id="test_minimal",
        schema_id="AgentCompoundTurn",
        template=template,
        create_area=create_initial_area,
    )

    prompt = profile.build_prompt(ctx)
    assert "You are Explorer." in prompt
    assert "You are at (1, 1)" in prompt
    assert '"move"' in prompt
    assert "---" in prompt


def test_load_profile_by_path():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    profile_dir = root / "profiles" / "default_compound"
    profile = load_profile(profile_dir)
    assert profile.profile_id == "default_compound"
    assert profile.template.text.strip().startswith("{{character}}")


def test_load_profile_unknown_raises():
    import pytest

    with pytest.raises(ValueError, match="Unknown profile"):
        load_profile("not_a_real_profile_xyz")


def test_prompt_template_rules_alias():
    area = create_initial_area()
    agent = area.get_agent()
    ctx = build_prompt_context(agent, area)
    template = PromptTemplate("RULES:\n{{rules}}")
    rendered = template.render_context(ctx)
    assert "compound turn" in rendered.lower()
