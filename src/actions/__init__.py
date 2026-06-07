"""
Actions package.

Contains move, speak, and interact implementations. Look is implemented in
perception.py (perform_look) because it shares vision/memory logic.
"""

from src.actions.interact import interact as do_interact
from src.actions.move import move as do_move
from src.actions.speak import speak as do_speak

__all__ = ["do_interact", "do_move", "do_speak"]
