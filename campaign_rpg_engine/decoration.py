"""Scene decorations — visual-only map layers (not simulation entities)."""

from __future__ import annotations

DECORATION_KIND_SPRITE = "sprite"
DECORATION_KIND_BACKGROUND = "background"
VALID_DECORATION_KINDS = frozenset({DECORATION_KIND_SPRITE, DECORATION_KIND_BACKGROUND})
DEFAULT_BACKGROUND_Z_INDEX = -1000
VALID_REPEAT_VALUES = frozenset({"repeat", "repeat-x", "repeat-y", "no-repeat"})


class Decoration:
    """Purely visual layer on an area grid (ignored by LLM prompts and turns)."""

    def __init__(
        self,
        *,
        id: str,
        kind: str,
        image: str,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        z_index: int = 0,
        repeat: str = "repeat",
    ) -> None:
        self.id = id
        self.kind = kind
        self.image = image
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.z_index = z_index
        self.repeat = repeat
