"""Session-level lorebooks (SillyTavern-style world info, V0.5.0)."""
from __future__ import annotations

from campaign_rpg_engine.lorebook.import_st import (
    derive_lorebook_id_from_filename,
    load_lorebook_from_dict,
    load_lorebook_from_path,
)
from campaign_rpg_engine.lorebook.matcher import build_scan_corpus, match_lorebook_entries, render_lorebook
from campaign_rpg_engine.lorebook.models import Lorebook, LoreEntry, DEFAULT_LOREBOOK_CHAR_BUDGET
from campaign_rpg_engine.lorebook.scan_config import LorebookScanConfig, describe_scan_sources
from campaign_rpg_engine.lorebook.st_defaults import ST_ENTRY_DEFAULTS, new_st_entry_dict, with_st_entry_defaults

__all__ = [
    "DEFAULT_LOREBOOK_CHAR_BUDGET",
    "Lorebook",
    "LoreEntry",
    "LorebookScanConfig",
    "ST_ENTRY_DEFAULTS",
    "build_scan_corpus",
    "derive_lorebook_id_from_filename",
    "describe_scan_sources",
    "load_lorebook_from_dict",
    "load_lorebook_from_path",
    "match_lorebook_entries",
    "render_lorebook",
    "new_st_entry_dict",
    "with_st_entry_defaults",
]
