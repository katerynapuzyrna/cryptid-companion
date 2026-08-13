from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from board.markers import MarkerItem, MARKER_Z_BANK
from board.pieces import HexPiece, Cell
from data.piece_defs import PIECE_SPECS, PIECE_NUMS, PIECE_MATRIX_IDS

# --------------------------
# Pieces / markers creation
# --------------------------
def make_puzzle_pieces() -> list[HexPiece]:
    pieces: list[HexPiece] = []

    for i, specs in enumerate(PIECE_SPECS):
        cells = [Cell(s.q, s.r, s.color, inner_dotted=s.inner_dotted) for s in specs]
        pieces.append(HexPiece(cells, PIECE_NUMS[i], PIECE_MATRIX_IDS[i]))

    return pieces


def add_markers(
    scene: QGraphicsScene,
    start_x: float,
    y_octagons: float,
    y_triangles: float,
) -> list:
    """
    Always creates ALL markers.
    Octagons in row 1, triangles in row 2.
    Black ones are marked as advanced_only.
    Visibility is controlled by UI.
    """
    colors_basic = ["#ffffff", "#0000ff", "#00aa00"]
    color_black = "#000000"
    pad = 45
    markers = []
    idx = 0

    for color in colors_basic:
        m = MarkerItem(shape_kind="octagon", color=color)
        m.advanced_only = False
        pos = QPointF(start_x + idx * pad, y_octagons)
        m.setPos(pos)
        m.set_home_pos(pos)
        scene.addItem(m)
        m.setZValue(MARKER_Z_BANK)
        markers.append(m)
        idx += 1

    m = MarkerItem(shape_kind="octagon", color=color_black)
    m.advanced_only = True
    pos = QPointF(start_x + idx * pad, y_octagons)
    m.setPos(pos)
    m.set_home_pos(pos)
    scene.addItem(m)
    m.setZValue(MARKER_Z_BANK)
    markers.append(m)
    idx = 0

    for color in colors_basic:
        m = MarkerItem(shape_kind="triangle", color=color)
        m.advanced_only = False
        pos = QPointF(start_x + idx * pad, y_triangles)
        m.setPos(pos)
        m.set_home_pos(pos)
        scene.addItem(m)
        m.setZValue(MARKER_Z_BANK)
        markers.append(m)
        idx += 1

    m = MarkerItem(shape_kind="triangle", color=color_black)
    m.advanced_only = True
    pos = QPointF(start_x + idx * pad, y_triangles)
    m.setPos(pos)
    m.set_home_pos(pos)
    scene.addItem(m)
    m.setZValue(MARKER_Z_BANK)
    markers.append(m)

    return markers