from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsObject
from PySide6.QtGui import QPainterPath, QPen, QBrush
from PySide6.QtCore import QRectF, QPointF, Qt

from settings.config import SLOT_OVERLAP_X, SLOT_OVERLAP_Y
from board.markers import MARKER_SCALE_HOME, MARKER_Z_BANK, _grab_cursor
from settings.theme import (
    BORDER_Q,
    BACKGROUND_LIGHT_Q,
    PEN_BORDER_COSMETIC,
    PEN_BORDER_DASHED,
    CANVAS_RADIUS,
)

class PuzzleCanvas:
    def __init__(
        self,
        scene: QGraphicsScene,
        rect: QRectF,
        cols: int,
        rows: int,
        outer_path: QPainterPath,
        inner_path: QPainterPath,
        *,
        show_inner_slot_grid: bool = True,
    ):
        self.scene = scene
        self.rect = rect
        self.cols = cols
        self.rows = rows
        self.outer_path = outer_path
        self.inner_path = inner_path

        self.occupied: dict[tuple[int,int], QGraphicsObject] = {}
        self.item_slot: dict[QGraphicsObject, tuple[int,int]] = {}
        # Per sub-cell: (row, col, cell_idx) where cell_idx is index within the piece
        self.marker_occupied: dict[tuple[int,int,int], QGraphicsObject] = {}
        self.marker_slot: dict[QGraphicsObject, tuple[int,int,int]] = {}
        # Player chips: multiple per hex allowed
        self.chip_occupied: dict[tuple[int,int,int], list] = {}
        self.chip_slot: dict[QGraphicsObject, tuple[int,int,int]] = {}
        # Dimmed “at bank” ghost for structure markers (build mode); off for hotseat / simulation.
        self._marker_bank_home_shadow_enabled: bool = True

        path = QPainterPath()
        path.addRoundedRect(rect, CANVAS_RADIUS, CANVAS_RADIUS)

        bg = QGraphicsPathItem(path)
        bg.setPen(QPen(BORDER_Q, 1, Qt.PenStyle.SolidLine))
        bg.setBrush(QBrush(BACKGROUND_LIGHT_Q))
        bg.setZValue(-100)
        scene.addItem(bg)

        outer_pen = PEN_BORDER_COSMETIC

        outer_br = self.outer_path.boundingRect()
        self.template_w = outer_br.width()
        self.template_h = outer_br.height()

        self.step_x = self.template_w - SLOT_OVERLAP_X
        self.step_y = self.template_h - SLOT_OVERLAP_Y

        origin_x = rect.left() + 20
        origin_y = rect.top() + 20

        combined_outer = QPainterPath()

        for r in range(rows):
            for c in range(cols):
                x = origin_x + c * self.step_x
                y = origin_y + r * self.step_y
                dx = x - outer_br.left()
                dy = y - outer_br.top()
                combined_outer = combined_outer.united(self.outer_path.translated(dx, dy))

        outer_item = QGraphicsPathItem(combined_outer)
        outer_item.setPen(outer_pen); outer_item.setBrush(Qt.NoBrush); outer_item.setZValue(-98)
        scene.addItem(outer_item)

        # Per-hex dashed outlines inside each slot (see build_piece_inner_path in pieces.py).
        # Map thumbnails omit this so bear/cougar match HexPiece.paint only (inset black/red dashes).
        if show_inner_slot_grid:
            combined_inner = QPainterPath()
            for r in range(rows):
                for c in range(cols):
                    x = origin_x + c * self.step_x
                    y = origin_y + r * self.step_y
                    dx = x - outer_br.left()
                    dy = y - outer_br.top()
                    combined_inner.addPath(self.inner_path.translated(dx, dy))

            inner_item = QGraphicsPathItem(combined_inner)
            inner_item.setPen(PEN_BORDER_DASHED)
            inner_item.setBrush(Qt.NoBrush)
            inner_item.setZValue(-97)
            scene.addItem(inner_item)

    def contains_point(self, p_scene: QPointF) -> bool:
        return self.rect.contains(p_scene)

    def _grid_origin(self) -> tuple[float,float]:
        return (self.rect.left() + 20, self.rect.top() + 20)

    def _slot_for_point(self, p_scene: QPointF) -> tuple[int,int]:
        ox, oy = self._grid_origin()
        rel_x = p_scene.x() - ox
        rel_y = p_scene.y() - oy
        col = int(round((rel_x - self.template_w / 2) / self.step_x))
        row = int(round((rel_y - self.template_h / 2) / self.step_y))
        col = max(0, min(self.cols - 1, col))
        row = max(0, min(self.rows - 1, row))
        return (row, col)

    def is_free(self, row: int, col: int, ignore_item: QGraphicsObject | None = None) -> bool:
        cur = self.occupied.get((row, col))
        return (cur is None) or (ignore_item is not None and cur is ignore_item)

    def _notify_piece_reassigned(self, old_slot: tuple[int,int] | None, new_slot: tuple[int,int] | None) -> None:
        cb = getattr(self, "_on_piece_reassigned", None)
        if callable(cb) and old_slot != new_slot:
            cb(old_slot, new_slot)

    def _release_item_no_notify(self, item: QGraphicsObject) -> tuple[int,int] | None:
        slot = self.item_slot.pop(item, None)
        if slot is not None:
            self.occupied.pop(slot, None)
        return slot

    def release_item(self, item: QGraphicsObject):
        old_slot = self._release_item_no_notify(item)
        if old_slot is not None:
            self._notify_piece_reassigned(old_slot, None)

    def assign_item(self, item: QGraphicsObject, row: int, col: int):
        old_slot = self._release_item_no_notify(item)
        new_slot = (row, col)
        # Moving a hex to a different grid cell: markers still reference the old (row, col).
        # Send them home; otherwise they stay at stale scene positions (mess).
        if old_slot is not None and old_slot != new_slot:
            self.release_markers_on_slot(old_slot[0], old_slot[1])
        self.occupied[new_slot] = item
        self.item_slot[item] = new_slot
        self._notify_piece_reassigned(old_slot, new_slot)

    def is_marker_cell_free(self, row: int, col: int, cell_idx: int, ignore_item: QGraphicsObject | None = None) -> bool:
        cur = self.marker_occupied.get((row, col, cell_idx))
        return (cur is None) or (ignore_item is not None and cur is ignore_item)

    def assign_marker(self, item: QGraphicsObject, row: int, col: int, cell_idx: int):
        self.release_marker(item)
        if hasattr(item, "prepareGeometryChange"):
            item.prepareGeometryChange()
        self.marker_occupied[(row, col, cell_idx)] = item
        self.marker_slot[item] = (row, col, cell_idx)
        cb = getattr(self, "_on_marker_assigned", None)
        if callable(cb):
            cb()
        self._notify_figures_changed(row, col, cell_idx)

    def release_marker(self, item: QGraphicsObject):
        if item in self.marker_slot and hasattr(item, "prepareGeometryChange"):
            item.prepareGeometryChange()
        slot = self.marker_slot.pop(item, None)
        if slot is not None:
            self.marker_occupied.pop(slot, None)
            self._notify_figures_changed(slot[0], slot[1], slot[2])

    def _notify_figures_changed(self, row: int, col: int, cell_idx: int):
        cb = getattr(self, "_on_figures_changed", None)
        if callable(cb):
            cb(row, col, cell_idx)

    def release_chip(self, item: QGraphicsObject):
        slot = self.chip_slot.pop(item, None)
        had_slot = slot is not None
        if slot is not None:
            lst = self.chip_occupied.get(slot, [])
            if item in lst:
                lst.remove(item)
            if not lst:
                self.chip_occupied.pop(slot, None)
            self._notify_figures_changed(slot[0], slot[1], slot[2])
        cb = getattr(self, "_on_chip_released", None)
        if callable(cb) and had_slot:
            cb(item)

    def assign_chip(self, item: QGraphicsObject, row: int, col: int, cell_idx: int):
        self.release_chip(item)
        slot = (row, col, cell_idx)
        self.chip_occupied.setdefault(slot, []).append(item)
        self.chip_slot[item] = slot
        self._notify_figures_changed(row, col, cell_idx)
        cb = getattr(self, "_on_chip_assigned", None)
        if callable(cb):
            cb(item, row, col, cell_idx)

    def release_markers_on_slot(self, row: int, col: int) -> None:
        """When a piece is removed from the canvas, send any markers/chips on that slot home.

        Always runs even when the map is frozen: the substrate hex is gone, so figures must
        leave the cell (bank positions; overlapping dimmed copies are handled in MarkerItem).
        """
        for item, slot in list(self.marker_slot.items()):
            if slot[0] == row and slot[1] == col:
                self.release_marker(item)
                if hasattr(item, "_home_pos"):
                    item.setZValue(MARKER_Z_BANK)
                    if hasattr(item, "setScale"):
                        item.setScale(MARKER_SCALE_HOME)
                    item.setPos(item._home_pos)
                    if hasattr(item, "setCursor"):
                        item.setCursor(_grab_cursor())
        for item, slot in list(self.chip_slot.items()):
            if slot[0] == row and slot[1] == col:
                self.release_chip(item)
                if hasattr(item, "_home_pos"):
                    item.setZValue(MARKER_Z_BANK)
                    if hasattr(item, "setScale"):
                        item.setScale(MARKER_SCALE_HOME)
                    item.setPos(item._home_pos)
                    if hasattr(item, "setCursor"):
                        item.setCursor(_grab_cursor())

    def notify_undo_checkpoint(self) -> None:
        cb = getattr(self, "_on_undo_checkpoint", None)
        if callable(cb):
            cb()

    def snap_pos_for_item_to_slot(self, item: QGraphicsObject, row: int, col: int) -> QPointF:
        br_item = item.boundingRect()
        ox, oy = self._grid_origin()
        slot_x = ox + col * self.step_x
        slot_y = oy + row * self.step_y
        return QPointF(slot_x - br_item.left(), slot_y - br_item.top())
