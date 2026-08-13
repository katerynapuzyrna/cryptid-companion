"""Non-interactive graphics view and 1:1 map preview widget for map cards."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QGraphicsView

from .scene import build_map_preview_scene


class NonInteractiveGraphicsView(QGraphicsView):
    """QGraphicsView that forwards mouse events to parent widget for card selection."""

    def mousePressEvent(self, event):
        """Forward mouse events to parent widget."""
        if self.parent():
            parent_pos = self.mapToParent(event.pos() if hasattr(event, "pos") else event.position().toPoint())
            parent_event = QMouseEvent(
                event.type(),
                parent_pos,
                event.button(),
                event.buttons(),
                event.modifiers(),
            )
            self.parent().mousePressEvent(parent_event)
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        """Block wheel events to prevent map movement when hovering over map card."""
        event.ignore()


class MapCanvasPreviewWidget(QWidget):
    """
    Shows the same canvas as build mode at the same size (1:1): 3x2 board
    with pieces and markers from map_data.
    """

    def __init__(self, map_data: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self._view = NonInteractiveGraphicsView(self)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setInteractive(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        scene, canvas, overlay = build_map_preview_scene(map_data)
        self._scene = scene
        self._canvas = canvas
        self._highlight_overlay = overlay
        self._view.setScene(scene)
        cw = int(canvas.rect.width())
        ch = int(canvas.rect.height())
        self._view.setFixedSize(cw, ch)
        self.setMinimumSize(cw, ch)

    def mousePressEvent(self, event):
        """Forward mouse events to MapCard (may be grandparent) so clicks on the map trigger card selection."""
        from .card import MapCard

        card = self.parent()
        while card and not isinstance(card, MapCard):
            card = card.parent()
        if card:
            pos_in_card = self.mapTo(card, event.pos() if hasattr(event, "pos") else event.position().toPoint())
            card.mousePressEvent(
                QMouseEvent(
                    event.type(),
                    pos_in_card,
                    event.button(),
                    event.buttons(),
                    event.modifiers(),
                )
            )
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        """Block wheel events to prevent map movement when hovering over map card."""
        event.ignore()

    def apply_highlights(self, highlighted_cells: set[tuple[int, int, int]]) -> None:
        """Set highlighted cells on preview pieces. Each tuple is (slot_row, slot_col, cell_idx)."""
        self._canvas._zero_targets_dim_full_map = len(highlighted_cells) == 0
        for piece in list(self._canvas.item_slot.keys()):
            piece.highlighted.clear()
        for row, col, cell_idx in highlighted_cells:
            piece = self._canvas.occupied.get((row, col))
            if piece is not None:
                piece.highlighted.add(cell_idx)
        for piece in self._canvas.item_slot:
            piece.update()
        for marker in self._canvas.marker_slot:
            marker.update()
        if self._highlight_overlay:
            self._highlight_overlay.update_highlights()

    def clear_highlights(self) -> None:
        """Clear all highlights from preview pieces."""
        self._canvas._zero_targets_dim_full_map = False
        for piece in self._canvas.item_slot:
            piece.highlighted.clear()
            piece.update()
        for marker in self._canvas.marker_slot:
            marker.update()
        if self._highlight_overlay:
            self._highlight_overlay.update_highlights()
