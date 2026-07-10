"""
Parse manual compound-turn argument strings (legacy CLI format).

Used by tests and apps that accept stepper-style compound lines.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Optional

from campaign_rpg_engine.llm.schemas import AgentCompoundTurn


@dataclass
class ParsedCompoundStep:
    turn: AgentCompoundTurn


def parse_compound_step_arg(arg: str) -> ParsedCompoundStep:
    """
    Parse a compound-turn argument string.

    Examples:
        2,3 look obj_ball_01 speak Hello.
        - look obj_ball_01
        2,3 interact obj_cookie_01 eat
        emote obj_sign_01 pointed
        2,3
        stay speak Hi there.
    """
    tokens = shlex.split(arg) if arg.strip() else []
    if not tokens:
        raise ValueError("compound step requires at least one token (use '-' or 'stay' for no move)")

    move_target: Optional[str] = None
    look_target: Optional[str] = None
    speak_content: Optional[str] = None
    interact_target: Optional[str] = None
    interact_action: Optional[str] = None
    emote_target: Optional[str] = None
    emote_action: Optional[str] = None
    idx = 0

    first = tokens[0].lower()
    if first in ("-", "stay", "null", "none"):
        move_target = None
        idx = 1
    elif first in ("look", "speak", "interact", "emote"):
        move_target = None
    else:
        move_target = tokens[0]
        idx = 1

    while idx < len(tokens):
        cmd = tokens[idx].lower()
        if cmd == "look":
            idx += 1
            if idx >= len(tokens):
                raise ValueError("look requires a target id")
            look_target = tokens[idx]
            idx += 1
        elif cmd == "speak":
            idx += 1
            if idx >= len(tokens):
                raise ValueError("speak requires content")
            speak_content = " ".join(tokens[idx:])
            idx = len(tokens)
        elif cmd == "interact":
            idx += 1
            if idx + 1 >= len(tokens):
                raise ValueError("interact requires object id and action name")
            interact_target = tokens[idx]
            interact_action = tokens[idx + 1]
            idx += 2
        elif cmd == "emote":
            idx += 1
            if idx + 1 >= len(tokens):
                raise ValueError("emote requires target and past-tense action name")
            emote_target = tokens[idx]
            emote_action = tokens[idx + 1]
            idx += 2
        else:
            raise ValueError(f"Unknown token '{tokens[idx]}' in compound step")

    if interact_target:
        turn_action = "interact"
        target = interact_target
        action_name = interact_action
    elif emote_target:
        turn_action = "emote"
        target = emote_target
        action_name = emote_action
    else:
        turn_action = "none"
        target = None
        action_name = None

    turn = AgentCompoundTurn(
        reasoning="[manual compound step]",
        move=move_target,
        look=look_target,
        say=speak_content,
        action=turn_action,
        target=target,
        verb=action_name,
    )

    return ParsedCompoundStep(turn=turn)
