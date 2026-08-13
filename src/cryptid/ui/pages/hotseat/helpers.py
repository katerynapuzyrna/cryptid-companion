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
    c = (clue or "").strip()
    if not c:
        return None
    if c in grid:
        return c
    labels = getattr(grid, "labels", None)
    if not labels:
        return None
    for lab in labels:
        if lab.strip() == c:
            return lab
    c_low = c.lower()
    for lab in labels:
        if lab.strip().lower() == c_low:
            return lab
    return None
