"""Hotseat UI adapter for shared chip-placement rules."""
from __future__ import annotations

from typing import Any

from logic.chip_placement import (
    PlaceDecision,
    current_player_clue_holds,
    evaluate_chip_placement,
    occupied_from_item,
)


def incoming_shape_from_chip(chip: Any) -> str:
    return occupied_from_item(chip).shape


def clue_holds_on_piece(view: Any, piece: Any, cell_idx: int) -> bool | None:
    """Whether the current player's clue is true on the hex under ``piece`` / ``cell_idx``."""
    bb = getattr(view, "_hotseat_board_builder", None)
    sb = getattr(view, "_gameplay_sidebar", None)
    if bb is None or bb.controller is None or sb is None:
        return None
    coords = bb.controller.cell_big_coords(piece, cell_idx)
    if coords is None:
        return None
    y, x = coords
    clue = sb.clue_text_for_player(getattr(sb, "_turn_index", 0)) or ""
    return current_player_clue_holds(
        clue=clue,
        current_map=bb.controller.build_current_map(),
        advanced_mode=bool(getattr(view, "_hotseat_advanced_mode", False)),
        y=y,
        x=x,
    )


def evaluate_hotseat_drop(
    view: Any,
    shape: str,
    color: str,
    piece: Any,
    cell_idx: int,
    existing: list[Any],
    *,
    allow_search_reuse: bool = False,
) -> PlaceDecision:
    clue_holds: bool | None = None
    if shape in ("circle", "square"):
        clue_holds = clue_holds_on_piece(view, piece, cell_idx)
    return evaluate_chip_placement(
        incoming_shape=shape,
        incoming_color=color,
        occupied=tuple(occupied_from_item(c) for c in existing),
        clue_holds=clue_holds,
        allow_search_reuse=allow_search_reuse,
    )


def validate_hotseat_map_drop(
    view: Any, chip: Any, hex_slot: tuple[int, int, int], existing: list[Any]
) -> bool:
    """True if a chip already on the map may be dropped on ``hex_slot``."""
    bb = getattr(view, "_hotseat_board_builder", None)
    if bb is None or bb.canvas is None:
        return False
    row, col, cell_idx = hex_slot
    piece = bb.canvas.occupied.get((row, col))
    if piece is None:
        return False
    decision = evaluate_hotseat_drop(
        view,
        incoming_shape_from_chip(chip),
        getattr(chip, "fill_color", "") or "",
        piece,
        cell_idx,
        existing,
        allow_search_reuse=False,
    )
    return decision is PlaceDecision.ALLOW
