from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np

from data.piece_defs import PIECE_MATRIX_IDS, PIECE_SPECS, cell_spec_to_terrain
from logic.coord_mapping import TILE_COLS, TILE_ROWS, visual_row_col_to_cell_index_map

MatrixId = Literal["A", "B", "C", "D", "E", "F"]


@lru_cache(maxsize=1)
def base_matrices() -> dict[MatrixId, np.ndarray]:
    """
    Build canonical (Qt 0°) terrain matrices for all pieces from piece definitions.
    """
    rowcol_to_idx = visual_row_col_to_cell_index_map()
    mats: dict[MatrixId, np.ndarray] = {}
    for i, matrix_id in enumerate(PIECE_MATRIX_IDS):
        specs = PIECE_SPECS[i]
        mat = np.empty((TILE_ROWS, TILE_COLS), dtype="U40")
        for r in range(TILE_ROWS):
            for c in range(TILE_COLS):
                idx = rowcol_to_idx[(r, c)]
                mat[r, c] = cell_spec_to_terrain(specs[idx])
        mats[matrix_id] = mat
    return mats


def matrix_for(matrix_id: MatrixId, *, rotated_180: bool = False) -> np.ndarray:
    """
    Get a terrain matrix for a given piece matrix_id, respecting tile rotation.
    """
    mat = base_matrices()[matrix_id].copy()
    if rotated_180:
        mat = np.flipud(np.fliplr(mat))
    return mat

