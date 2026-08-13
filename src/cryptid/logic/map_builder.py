from PySide6.QtWidgets import QGraphicsScene
from board.canvas import PuzzleCanvas
from board.markers import MarkerItem
from board.pieces import HexPiece, find_hex_under_point
from logic.coord_mapping import cell_big_coords as _cell_big_coords, is_rotated_180
from logic.terrain_matrices import matrix_for
from typing import Optional
import numpy as np

# --------------------------
# Build current_map from board state + coordinate mapping
# --------------------------
class MapBuilder:
    SHAPE_TO_STRUCTURE = {
        "triangle": "abandonedshack",
        "circle": "standingstone",
        "octagon": "standingstone",  # octagon markers represent standing stones too
    }
    COLOR_HEX_TO_NAME = {"#000000": "black", "#ffffff": "white", "#0000ff": "blue", "#00aa00": "green"}

    def __init__(self, scene: QGraphicsScene, canvas: PuzzleCanvas, pieces: list[HexPiece], markers: list[MarkerItem]):
        self.scene = scene
        self.canvas = canvas
        self.pieces = pieces
        self.markers = markers

    def build_current_map(self) -> np.ndarray:
        rows = self.canvas.rows
        cols = self.canvas.cols
        big = np.full((rows*3, cols*6), "EMPTY", dtype="U120")

        for r in range(rows):
            for c in range(cols):
                item = self.canvas.occupied.get((r, c))
                if isinstance(item, HexPiece):
                    rotated_180 = is_rotated_180(item.rotation())
                    mat = matrix_for(item.matrix_id, rotated_180=rotated_180)
                    big[r*3:(r+1)*3, c*6:(c+1)*6] = mat

        for m in self.markers:
            # Use stored placement to avoid wrong tile when pieces overlap (e.g. blue standing stone at 2,5).
            slot_rc = self.canvas.marker_slot.get(m)
            if slot_rc is not None:
                sr, sc, cell_idx = slot_rc
                piece = self.canvas.occupied.get((sr, sc))
            else:
                p_scene = m.mapToScene(m.boundingRect().center())
                piece, cell_idx, _ = find_hex_under_point(p_scene, self.scene.items(p_scene))
                if piece is None or cell_idx is None:
                    continue
                slot = self.canvas.item_slot.get(piece)
                if slot is None:
                    continue
                sr, sc = slot
            if piece is None:
                continue
            structure = self.SHAPE_TO_STRUCTURE.get(m.shape_kind, "unknown")
            color_name = self.COLOR_HEX_TO_NAME.get(m.fill_color.lower(), m.fill_color.lower())
            rotated_180 = is_rotated_180(piece.rotation())
            coords = _cell_big_coords(sr, sc, cell_idx, rotated_180=rotated_180)
            if coords is None:
                continue
            Y, X = coords
            big[Y, X] = big[Y, X] + f"_{structure}_{color_name}"

        return big

    def cell_big_coords(self, piece: HexPiece, cell_idx: int) -> Optional[tuple[int,int]]:
        slot = self.canvas.item_slot.get(piece)
        if slot is None:
            return None
        sr, sc = slot
        rotated_180 = is_rotated_180(piece.rotation())
        return _cell_big_coords(sr, sc, cell_idx, rotated_180=rotated_180)
