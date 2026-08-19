"""Small hotseat helpers (color lookup, clue matching, bank preview pixmap)."""
from __future__ import annotations

from typing import Any

from PySide6.QtGui import QPixmap

from ui.shared.widgets.player_colors import (
    PLAYER_COLORS,
    get_player_circle_chip_pixmap,
    get_player_question_chip_pixmap,
    get_player_square_chip_pixmap,
)

from .constants import _HOTSEAT_CHIP_HOME_PX


def _hotseat_color_name_from_hex(color_hex: str) -> str:
    h = (color_hex or "").strip().lower()
    for name, hx in PLAYER_COLORS:
        if hx.lower() == h:
            return name
    return ""


def _hotseat_bank_carry_preview_pixmap(shape: str, color_hex: str) -> QPixmap:
    px = _HOTSEAT_CHIP_HOME_PX
    if shape == "question":
        return get_player_question_chip_pixmap("", px)
    cname = _hotseat_color_name_from_hex(color_hex)
    if shape == "circle":
        return get_player_circle_chip_pixmap(cname, px)
    return get_player_square_chip_pixmap(cname, px)


def _hotseat_match_clue_to_grid(clue: str, grid: Any) -> str | None:
    """Resolve book clue text to a ``ConditionsGrid`` label (exact, strip, then case-fold)."""
    from logic.chip_placement import match_clue_to_grid

    return match_clue_to_grid(clue, grid)
