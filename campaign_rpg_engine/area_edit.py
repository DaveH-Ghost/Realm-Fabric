"""Compat shim (1.6.0) — implementation lives in campaign_rpg_engine.edit.area_edit."""

from __future__ import annotations

import sys

from campaign_rpg_engine.edit import area_edit as _impl

sys.modules[__name__] = _impl
