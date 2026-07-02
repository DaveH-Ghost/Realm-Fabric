"""Project packaging and pyproject.toml metadata."""

import importlib
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_pyproject_version_is_semver():
    version = _load_pyproject()["project"]["version"]
    assert version == "0.7.0"
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version


def test_pyproject_declares_realm_console_script():
    data = _load_pyproject()
    assert data["project"]["scripts"]["realm"] == "src.main:main"
    assert data["tool"]["uv"]["package"] is True
    assert "hatchling" in data["build-system"]["requires"]


def test_hatch_includes_realm_fabric_and_profiles():
    data = _load_pyproject()
    wheel = data["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert "realm_fabric" in wheel["packages"]
    assert "src" in wheel["packages"]
    assert wheel["force-include"]["profiles"] == "profiles"


def test_realm_fabric_public_imports():
    expected_version = _load_pyproject()["project"]["version"]
    rf = importlib.import_module("realm_fabric")
    assert rf.__version__ == expected_version
    assert rf.Session is not None
    assert rf.GameProfile is not None
    assert rf.PromptContext is not None
    assert rf.AgentCompoundTurn is not None
    assert rf.register_interaction_handler is not None
    assert rf.list_registered_handlers is not None
    assert rf.default_compound_profile is not None
    assert rf.build_area_snapshot is not None
    assert rf.build_session_snapshot is not None
    assert rf.DEFAULT_AREA_ID == "room"
    assert "Session" in rf.__all__
    assert rf.WorldMutationResult is not None
    assert rf.ObjectAction is not None
    assert "WorldMutationResult" in rf.__all__


def test_load_profile_builtin():
    from realm_fabric import load_profile

    profile = load_profile("default_compound")
    assert profile.profile_id == "default_compound"
    assert profile.schema_id == "AgentCompoundTurn"
