"""Compat shim (1.6.0) — implementation lives in campaign_rpg_engine.templates.entity_templates."""

from __future__ import annotations

import sys

from campaign_rpg_engine.templates import entity_templates as _impl

sys.modules[__name__] = _impl
