"""Hotseat chip placement rules (Qt-free).

Initial sharing and additional sharing use the same square checks.
Question/Search start hexes cannot already contain a square.
Search auto-answers (other players' chips on the searched hex) do not use this module.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, NamedTuple


class OccupiedChip(NamedTuple):
    """One chip already on a hex. ``shape`` is question, circle, or square."""

    shape: str
    color: str


class PlaceDecision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    REUSE_CIRCLE = "reuse_circle"


def match_clue_to_grid(clue: str, grid: Any) -> str | None:
    """Resolve book clue text to a ConditionsGrid label (exact, strip, then case-fold)."""
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


def clue_holds_at_hex(clue: str, grid: Any, y: int, x: int) -> bool | None:
    """True/False if the clue maps to a grid label; None if it cannot be evaluated."""
    matched = match_clue_to_grid(clue, grid)
    if matched is None:
        return None
    return matched in grid.rules_true_at_hex(y, x)


def current_player_clue_holds(
    *,
    clue: str,
    current_map: Any,
    advanced_mode: bool,
    y: int,
    x: int,
) -> bool | None:
    """Evaluate the current player's clue on hex (y, x). None if the grid cannot be built."""
    from logic.conditions import compute_all_conditions

    try:
        grid = compute_all_conditions(current_map, advanced_mode=advanced_mode)
    except Exception:
        return None
    return clue_holds_at_hex(clue, grid, y, x)


def occupied_from_item(chip: Any) -> OccupiedChip:
    """Duck-typed chip → occupancy record."""
    if getattr(chip, "_question_mark", False):
        shape = "question"
    elif getattr(chip, "shape_kind", None) == "square":
        shape = "square"
    else:
        shape = "circle"
    color = (getattr(chip, "fill_color", "") or "").lower()
    return OccupiedChip(shape=shape, color=color)


def _norm_color(color: str) -> str:
    return (color or "").lower()


def _hex_has_square(occupied: Iterable[OccupiedChip]) -> bool:
    return any(chip.shape == "square" for chip in occupied)


def _hex_has_player_circle(occupied: Iterable[OccupiedChip], color: str) -> bool:
    return any(chip.shape == "circle" and chip.color == color for chip in occupied)


def evaluate_chip_placement(
    *,
    incoming_shape: str,
    incoming_color: str,
    occupied: Iterable[OccupiedChip],
    clue_holds: bool | None,
    allow_search_reuse: bool = False,
    max_chips: int = 4,
) -> PlaceDecision:
    """Decide whether a Hotseat bank/map drop may land on this hex.

    Squares (initial and additional sharing): clue must be false, no square
    already present, no circle of the incoming (current player) color.

    Question and Search: reject if a square is already present.
    Search also requires the current player's clue to be true.
    """
    shape = incoming_shape
    color = _norm_color(incoming_color)
    existing = tuple(occupied)

    if shape == "square":
        if clue_holds is not False:
            return PlaceDecision.REJECT
        if _hex_has_square(existing):
            return PlaceDecision.REJECT
        if _hex_has_player_circle(existing, color):
            return PlaceDecision.REJECT
        if any(chip.color == color for chip in existing):
            return PlaceDecision.REJECT
        if len(existing) >= max_chips:
            return PlaceDecision.REJECT
        return PlaceDecision.ALLOW

    if shape in ("question", "circle"):
        if _hex_has_square(existing):
            return PlaceDecision.REJECT
        if shape == "circle":
            if clue_holds is not True:
                return PlaceDecision.REJECT
            if allow_search_reuse and _hex_has_player_circle(existing, color):
                return PlaceDecision.REUSE_CIRCLE
        if len(existing) >= max_chips:
            return PlaceDecision.REJECT
        if any(chip.color == color for chip in existing):
            return PlaceDecision.REJECT
        return PlaceDecision.ALLOW

    return PlaceDecision.REJECT
