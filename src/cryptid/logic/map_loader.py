"""Helpers for loading map data (grid3x2, structures) onto the board."""

from typing import Any
import numpy as np

from data.piece_defs import PIECE_MATRIX_IDS
from logic.coord_mapping import (
    TILE_COLS,
    TILE_ROWS,
    big_coords_to_cell_index,
    cell_big_coords,
    cell_index_for_visual_row_col as _cell_index_for_visual_row_col,
)
from logic.terrain_matrices import matrix_for


def parse_tile_id(tile_id: str) -> tuple[int, bool]:
    """Return (piece_index_0based, rotated_180).
    JSON: '2t' = map tile 2 rotated 180°; '4' = tile 4, no rotation."""
    s = (tile_id or "1").strip().lower()
    rotated = s.endswith("t")
    num_str = s.rstrip("t").strip()
    try:
        num = int(num_str)
    except ValueError:
        num = 1
    num = max(1, min(6, num))
    return (num - 1, rotated)


def slot_for_tile_id(grid3x2: list[list[str]], tile_id: str) -> tuple[int, int] | None:
    """Return (row, col) where grid3x2[row][col] matches tile_id."""
    for r in range(len(grid3x2)):
        for c in range(len(grid3x2[r])):
            if grid3x2[r][c] == tile_id:
                return (r, c)
    return None


def cell_index_for_visual_row_col(
    row: int,
    col: int,
    *,
    piece_rotated_180: bool = False,
    rotated_180: bool | None = None,
) -> int | None:
    """
    Compatibility wrapper.

    Old call sites used `piece_rotated_180=...`; new unified naming is `rotated_180=...`.
    """
    use_rot = piece_rotated_180 if rotated_180 is None else rotated_180
    return _cell_index_for_visual_row_col(row, col, rotated_180=use_rot)


COLOR_NAME_TO_HEX = {
    "green": "#00aa00",
    "blue": "#0000ff",
    "white": "#ffffff",
    "black": "#000000",
}

SHAPE_TO_STRUCTURE = {
    "triangle": "abandonedshack",
    "circle": "standingstone",
    "octagon": "standingstone",
}


def build_map_from_data(map_data: dict[str, Any]) -> np.ndarray:
    """Build the terrain/structure array from map_data (no board). Same format as MapBuilder.build_current_map()."""
    rows, cols = 3, 2
    big = np.full((rows * 3, cols * 6), "EMPTY", dtype="U120")

    grid3x2 = map_data.get("grid3x2") or []
    default_grid = [["1", "2"], ["3", "4"], ["5", "6"]]
    for r in range(rows):
        row_data = grid3x2[r] if r < len(grid3x2) else default_grid[r]
        for c in range(cols):
            tile_id = (row_data[c] if c < len(row_data) else default_grid[r][c]).strip()
            if not tile_id:
                continue
            piece_idx, rotated = parse_tile_id(tile_id)
            matrix_id = PIECE_MATRIX_IDS[piece_idx]
            mat = matrix_for(matrix_id, rotated_180=rotated)
            big[r * 3 : (r + 1) * 3, c * 6 : (c + 1) * 6] = mat

    for struct in map_data.get("structures") or []:
        tile_id = struct.get("tileId") or ""
        slot = slot_for_tile_id(grid3x2, tile_id)
        if slot is None:
            continue
        row, col = slot
        slot_tile_id = (grid3x2[row][col] if row < len(grid3x2) and col < len(grid3x2[row]) else "").strip().lower()
        piece_rotated_180 = slot_tile_id.endswith("t")
        for pl in struct.get("placements") or []:
            if not isinstance(pl, dict):
                continue
            visual_row = pl.get("q", 0)
            visual_col = pl.get("r", 0)
            color = (pl.get("color") or "white").strip().lower()
            shape = (pl.get("shape") or "octagon").strip().lower()
            if shape == "circle":
                shape = "octagon"
            cell_idx = cell_index_for_visual_row_col(
                visual_row, visual_col, rotated_180=piece_rotated_180
            )
            if cell_idx is None:
                continue
            coords = cell_big_coords(row, col, cell_idx, rotated_180=piece_rotated_180)
            if coords is None:
                continue
            Y, X = coords
            structure = SHAPE_TO_STRUCTURE.get(shape, "standingstone")
            big[Y, X] = big[Y, X] + f"_{structure}_{color}"

    return big


def targets_to_highlighted_cells(
    targets: set[tuple[int, int]], map_data: dict[str, Any]
) -> set[tuple[int, int, int]]:
    """Convert (Y, X) big coords to (slot_row, slot_col, cell_idx) for map card preview."""
    grid3x2 = map_data.get("grid3x2") or []
    default_grid = [["1", "2"], ["3", "4"], ["5", "6"]]
    result: set[tuple[int, int, int]] = set()
    for Y, X in targets:
        row, col = Y // 3, X // 6
        if not (0 <= row < 3 and 0 <= col < 2):
            continue
        row_data = grid3x2[row] if row < len(grid3x2) else default_grid[row]
        slot_tile_id = (row_data[col] if col < len(row_data) else default_grid[row][col]).strip().lower()
        if not slot_tile_id:
            continue
        piece_rotated_180 = slot_tile_id.endswith("t")
        cell_idx = big_coords_to_cell_index(Y, X, rotated_180=piece_rotated_180)
        if cell_idx is not None and 0 <= cell_idx < 18:
            result.add((row, col, cell_idx))
    return result
