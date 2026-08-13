"""Scene-level overlay that draws hex highlights on top of all pieces.

This ensures green highlight borders are never overlapped by adjacent pieces,
since each piece paints its own fill and would otherwise cover neighbours' borders.
"""

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QPainter, QPolygonF
from PySide6.QtWidgets import QGraphicsObject

from board.geometry import axial_to_pixel, hex_polygon
from settings.config import HEX_SIZE
from settings.theme import PEN_HIGHLIGHT


class HighlightOverlay(QGraphicsObject):
    """Draws highlight outlines in scene coordinates, always on top of pieces."""

    def __init__(self, canvas, pieces: list):
        super().__init__()
        self._canvas = canvas
        self._pieces = pieces
        self.setZValue(10000)  # Above all pieces
        self.setFlag(self.GraphicsItemFlag.ItemHasNoContents, False)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setAcceptHoverEvents(False)

    def update_highlights(self) -> None:
        """Refresh from current piece highlighted state. Call after solve/clear."""
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._canvas.rect if self._canvas else QRectF()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setBrush(Qt.NoBrush)
        painter.setPen(PEN_HIGHLIGHT)

        for piece in self._pieces:
            if self._canvas.item_slot.get(piece) is None:
                continue
            for idx in piece.highlighted:
                if idx >= len(piece.cells):
                    continue
                c = piece.cells[idx]
                center_local = axial_to_pixel(c.q, c.r, HEX_SIZE)
                poly_local = hex_polygon(center_local, HEX_SIZE)
                poly_scene = QPolygonF([piece.mapToScene(pt) for pt in poly_local])
                painter.drawPolygon(poly_scene)
