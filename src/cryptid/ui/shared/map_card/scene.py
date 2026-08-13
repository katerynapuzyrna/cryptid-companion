"""Build QGraphicsScene preview of a map (3x2 board, same as build mode)."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsItem

from board.factory import make_puzzle_pieces
from board.highlight_overlay import HighlightOverlay
from board.pieces import build_piece_outer_path, build_piece_inner_path
from board.canvas import PuzzleCanvas
from board.markers import MarkerItem, MARKER_SCALE_CANVAS
from board.geometry import axial_to_pixel
from settings.config import SLOT_OVERLAP_X, SLOT_OVERLAP_Y, HEX_SIZE

_PREVIEW_CANVAS_SIZE: tuple[int, int] | None = None

_VISUAL_ROW_COL_TO_CELL_INDEX: dict[tuple[int, int], int] = {}

TILE_ROWS = 3
TILE_COLS = 6


def _get_preview_canvas_size() -> tuple[int, int]:
    """Return (width, height) used by MapCanvasPreviewWidget for the 3x2 preview."""
    global _PREVIEW_CANVAS_SIZE
    if _PREVIEW_CANVAS_SIZE is not None:
        return _PREVIEW_CANVAS_SIZE

    pieces = make_puzzle_pieces()
    outer_path = build_piece_outer_path(pieces[0].cells)
    br = outer_path.boundingRect()

    step_x = br.width() - SLOT_OVERLAP_X
    step_y = br.height() - SLOT_OVERLAP_Y
    pad = 20

    canvas_cols, canvas_rows = 2, 3
    board_w = (canvas_cols - 1) * step_x + br.width()
    board_h = (canvas_rows - 1) * step_y + br.height()
    canvas_w = pad * 2 + board_w
    canvas_h = pad * 2 + board_h

    _PREVIEW_CANVAS_SIZE = (int(canvas_w), int(canvas_h))
    return _PREVIEW_CANVAS_SIZE


def _build_visual_row_col_mapping() -> dict[tuple[int, int], int]:
    """Build (row, col) -> cell_index for the tile as displayed on screen (0°)."""
    if _VISUAL_ROW_COL_TO_CELL_INDEX:
        return _VISUAL_ROW_COL_TO_CELL_INDEX
    pieces = make_puzzle_pieces()
    piece = pieces[0]
    positions = []
    for idx, cell in enumerate(piece.cells):
        pt = axial_to_pixel(cell.q, cell.r, HEX_SIZE)
        positions.append((pt.y(), pt.x(), idx))
    positions.sort(key=lambda t: (t[0], t[1]))
    top18 = positions[: TILE_ROWS * TILE_COLS]
    row_col_to_idx = {}
    for row in range(TILE_ROWS):
        start = row * TILE_COLS
        end = start + TILE_COLS
        row_cells = sorted(top18[start:end], key=lambda t: t[1])
        for col, (_, _, idx) in enumerate(row_cells):
            row_col_to_idx[(row, col)] = idx
    _VISUAL_ROW_COL_TO_CELL_INDEX.clear()
    _VISUAL_ROW_COL_TO_CELL_INDEX.update(row_col_to_idx)
    return row_col_to_idx


def _parse_tile_id(tile_id: str) -> tuple[int, bool]:
    """Return (piece_index_0based, rotated_180)."""
    s = (tile_id or "1").strip().lower()
    rotated = s.endswith("t")
    num_str = s.rstrip("t").strip()
    try:
        num = int(num_str)
    except ValueError:
        num = 1
    num = max(1, min(6, num))
    return (num - 1, rotated)


def _slot_for_tile_id(grid3x2: list[list[str]], tile_id: str) -> tuple[int, int] | None:
    """Return (row, col) where grid3x2[row][col] matches tile_id."""
    for r in range(len(grid3x2)):
        for c in range(len(grid3x2[r])):
            if grid3x2[r][c] == tile_id:
                return (r, c)
    return None


def _cell_index_for_visual_row_col(
    row: int, col: int, *, piece_rotated_180: bool = False
) -> int | None:
    """Cell index for the hex at (row, col) relative to the tile as shown on screen."""
    mapping = _build_visual_row_col_mapping()
    if piece_rotated_180:
        row = TILE_ROWS - 1 - row
        col = TILE_COLS - 1 - col
    return mapping.get((row, col))


def build_map_preview_scene(map_data: dict[str, Any]) -> tuple[QGraphicsScene, PuzzleCanvas, HighlightOverlay]:
    """
    Build a scene with the same canvas as build mode: 3x2 slots, pieces placed
    per grid3x2, markers per structures. All items are non-interactive.

    Bear/cougar inner dotted matches ``HexPiece.paint`` (not the gray slot grid); see
    ``board.pieces.INNER_DOTTED_HEX_SCALE`` and the ``if c.inner_dotted`` branch there.
    """
    scene = QGraphicsScene()
    pieces = make_puzzle_pieces()
    outer_path = build_piece_outer_path(pieces[0].cells)
    inner_path = build_piece_inner_path(pieces[0].cells)
    canvas_cols, canvas_rows = 2, 3
    template_br = outer_path.boundingRect()
    step_x = template_br.width() - SLOT_OVERLAP_X
    step_y = template_br.height() - SLOT_OVERLAP_Y
    pad = 20
    board_w = (canvas_cols - 1) * step_x + template_br.width()
    board_h = (canvas_rows - 1) * step_y + template_br.height()
    canvas_w = pad * 2 + board_w
    canvas_h = pad * 2 + board_h
    start_x = start_y = 20
    canvas_rect = QRectF(start_x, start_y, canvas_w, canvas_h)

    canvas = PuzzleCanvas(
        scene,
        canvas_rect,
        canvas_cols,
        canvas_rows,
        outer_path,
        inner_path,
        show_inner_slot_grid=False,
    )
    for p in pieces:
        p.set_canvas(canvas)
        p.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        p.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        p.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        p.setCursor(Qt.CursorShape.ArrowCursor)

    grid3x2 = map_data.get("grid3x2") or []
    default_grid = [["1", "2"], ["3", "4"], ["5", "6"]]
    for r in range(3):
        row_data = grid3x2[r] if r < len(grid3x2) else default_grid[r]
        for c in range(2):
            tile_id = (row_data[c] if c < len(row_data) else default_grid[r][c]).strip()
            if not tile_id:
                continue
            piece_idx, rotated = _parse_tile_id(tile_id)
            piece = pieces[piece_idx]
            piece.setRotation(180 if rotated else 0)
            pos = canvas.snap_pos_for_item_to_slot(piece, r, c)
            piece.setPos(pos)
            canvas.assign_item(piece, r, c)
            scene.addItem(piece)

    for struct in map_data.get("structures") or []:
        tile_id = struct.get("tileId") or ""
        slot = _slot_for_tile_id(grid3x2, tile_id)
        if slot is None:
            continue
        row, col = slot
        piece = canvas.occupied.get((row, col))
        if piece is None:
            continue
        slot_tile_id = (grid3x2[row][col] if row < len(grid3x2) and col < len(grid3x2[row]) else "").strip().lower()
        piece_rotated_180 = slot_tile_id.endswith("t")
        for pl in struct.get("placements") or []:
            if not isinstance(pl, dict):
                continue
            visual_row = pl.get("q", 0)
            visual_col = pl.get("r", 0)
            color = (pl.get("color") or "white").strip().lower()
            shape = (pl.get("shape") or "octagon").strip().lower()
            if shape not in ("circle", "triangle", "octagon"):
                shape = "octagon"
            cell_idx = _cell_index_for_visual_row_col(
                visual_row, visual_col, piece_rotated_180=piece_rotated_180
            )
            if cell_idx is None:
                continue
            if not canvas.is_marker_cell_free(row, col, cell_idx):
                continue
            marker = MarkerItem(shape_kind=shape, color=color)
            marker.set_canvas(canvas)
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            marker.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            marker.setCursor(Qt.CursorShape.ArrowCursor)
            marker.setScale(MARKER_SCALE_CANVAS)
            cell = piece.cells[cell_idx]
            center_local = axial_to_pixel(cell.q, cell.r, HEX_SIZE)
            center_scene = piece.mapToScene(center_local)
            marker.setPos(center_scene)
            canvas.assign_marker(marker, row, col, cell_idx)
            marker.setZValue(5000)
            scene.addItem(marker)
            piece.stackBefore(marker)

    pieces_on_canvas = list(canvas.occupied.values())
    overlay = HighlightOverlay(canvas, pieces_on_canvas)
    scene.addItem(overlay)

    scene.setSceneRect(canvas_rect)
    return scene, canvas, overlay
