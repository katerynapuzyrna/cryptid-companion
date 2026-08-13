from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

from data.piece_defs import PIECE_SPECS
from settings.config import GRID_ROT_RAD, HEX_SIZE

# ------------------------------------------------------------
# Centralized coordinate/rotation mapping
#
# Canonical conventions:
# - Tile-local "visual row/col" is a 3x6 grid (row 0..2, col 0..5)
#   describing how the tile looks on screen at Qt rotation 0°.
# - Qt rotation 180° corresponds to flipping that visual grid:
#     row' = 2 - row, col' = 5 - col
#
# These helpers are used to keep:
# - marker placement (maps.json q/r)
# - current_map (big Y/X)
# - highlights (big Y/X <-> cell_idx)
# consistent with Qt rotation without double/triple flips.
# ------------------------------------------------------------

TILE_ROWS = 3
TILE_COLS = 6


def is_rotated_180(rotation_deg: float) -> bool:
    """True when Qt rotation is effectively 180° (mod 360)."""
    rot = rotation_deg % 360
    return abs(rot - 180) < 1e-6


def _axial_to_pixel_xy(q: int, r: int, size: float = HEX_SIZE) -> tuple[float, float]:
    """Numeric version of board.geometry.axial_to_pixel (no Qt types)."""
    x = size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
    y = size * (3 / 2 * r)
    c = math.cos(GRID_ROT_RAD)
    s = math.sin(GRID_ROT_RAD)
    return (x * c - y * s, x * s + y * c)


def _flip_rc(row: int, col: int) -> tuple[int, int]:
    return (TILE_ROWS - 1 - row, TILE_COLS - 1 - col)


@lru_cache(maxsize=1)
def visual_row_col_to_cell_index_map() -> dict[tuple[int, int], int]:
    """
    Build mapping (visual_row, visual_col) -> cell_idx.

    We derive it from the canonical tile shape using axial coordinates, sorting
    by pixel y then x (same idea as previous loader code), then slicing into 3 rows
    of 6 cells each.
    """
    specs = PIECE_SPECS[0]
    positions: list[tuple[float, float, int]] = []
    for idx, s in enumerate(specs):
        x, y = _axial_to_pixel_xy(s.q, s.r, HEX_SIZE)
        positions.append((y, x, idx))
    positions.sort(key=lambda t: (t[0], t[1]))

    top18 = positions[: TILE_ROWS * TILE_COLS]
    row_col_to_idx: dict[tuple[int, int], int] = {}
    for row in range(TILE_ROWS):
        start = row * TILE_COLS
        end = start + TILE_COLS
        row_cells = sorted(top18[start:end], key=lambda t: t[1])
        for col, (_, _, idx) in enumerate(row_cells):
            row_col_to_idx[(row, col)] = idx
    return row_col_to_idx


@lru_cache(maxsize=1)
def cell_index_to_visual_row_col_map() -> dict[int, tuple[int, int]]:
    mapping = visual_row_col_to_cell_index_map()
    inv: dict[int, tuple[int, int]] = {}
    for (r, c), idx in mapping.items():
        inv[idx] = (r, c)
    return inv


def cell_index_for_visual_row_col(
    row: int, col: int, *, rotated_180: bool = False
) -> Optional[int]:
    """
    Convert a tile-relative (row,col) as SHOWN ON SCREEN to a cell_idx.

    If the tile is rotated 180°, the same on-screen (row,col) corresponds to the
    opposite canonical cell.
    """
    if rotated_180:
        row, col = _flip_rc(row, col)
    return visual_row_col_to_cell_index_map().get((row, col))


def visual_row_col_for_cell_index(
    cell_idx: int, *, rotated_180: bool = False
) -> Optional[tuple[int, int]]:
    """Inverse of cell_index_for_visual_row_col."""
    rc = cell_index_to_visual_row_col_map().get(cell_idx)
    if rc is None:
        return None
    row, col = rc
    if rotated_180:
        row, col = _flip_rc(row, col)
    return (row, col)


def cell_big_coords(
    slot_row: int, slot_col: int, cell_idx: int, *, rotated_180: bool = False
) -> Optional[tuple[int, int]]:
    """
    Convert (slot_row, slot_col, cell_idx) to big-map coords (Y,X).
    """
    rc = cell_index_to_visual_row_col_map().get(cell_idx)
    if rc is None:
        return None
    row, col = rc
    if rotated_180:
        row, col = _flip_rc(row, col)
    return (slot_row * TILE_ROWS + row, slot_col * TILE_COLS + col)


def big_coords_to_cell_index(
    Y: int, X: int, *, rotated_180: bool = False
) -> Optional[int]:
    """
    Convert big-map coords (Y,X) to cell_idx within its tile, given that tile's rotation.
    """
    row = Y % TILE_ROWS
    col = X % TILE_COLS
    if rotated_180:
        row, col = _flip_rc(row, col)
    return visual_row_col_to_cell_index_map().get((row, col))

