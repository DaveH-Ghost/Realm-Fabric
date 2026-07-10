"""
Actions package.

Contains move, speak, and interact implementations. Look is implemented in
perception.py (perform_look) because it shares vision/memory logic.
"""
from __future__ import annotations

from campaign_rpg_engine.actions.emote import emote as do_emote
from campaign_rpg_engine.actions.interact import interact as do_interact
from campaign_rpg_engine.actions.interact import interact_phases as do_interact_phases
from campaign_rpg_engine.actions.move import move as do_move
from campaign_rpg_engine.actions.speak import speak as do_speak

__all__ = ["do_emote", "do_interact", "do_interact_phases", "do_move", "do_speak"]
