from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Literal

from PySide6.QtCore import QLineF, QRectF, QPointF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from board.geometry import axial_to_pixel, hex_polygon, rotate_about
from board.terrain_paint import paint_terrain, color_hex_to_terrain
from settings.config import HEX_SIZE, PIECE_CORNER_DOT_R, TEXTURED_HEX_FILL
from settings.theme import PEN_BORDER, PEN_LABEL

# Bear/cougar: `inner_size = HEX_SIZE * INNER_DOTTED_HEX_SCALE`,
# `QPen(QColor(c.inner_dotted), 1, Qt.DashLine)` + `setCosmetic(True)` when `if c.inner_dotted:`.
# Map thumbnails use the same HexPiece.paint (preview canvas omits slot dashed grid).
INNER_DOTTED_HEX_SCALE = 0.8

# --------------------------
# Data model
# --------------------------
@dataclass(frozen=True)
class Cell:
    q: int
    r: int
    color: str
    inner_dotted: Optional[Literal["red", "black"]] = None


# --------------------------
# Path builders (used by slots + canvas)
# --------------------------
def build_piece_outer_path(cells: list["Cell"], hex_size: float | None = None) -> QPainterPath:
    """
    Outer silhouette path (united polygons) of a piece template.
    Used for drawing slot outlines / template bounding rect.
    """
    size = hex_size if hex_size is not None else HEX_SIZE
    union_path = QPainterPath()
    for c in cells:
        center = axial_to_pixel(c.q, c.r, size)
        poly = QPolygonF(hex_polygon(center, size))
        p = QPainterPath()
        p.addPolygon(poly)
        union_path = union_path.united(p)

    outer_poly = union_path.toFillPolygon()
    outline = QPainterPath()
    outline.addPolygon(outer_poly)
    return outline


def build_piece_inner_path(cells: list["Cell"], hex_size: float | None = None) -> QPainterPath:
    """
    Inner path: just all hex polygons (not united).
    Used for dashed inner outline of slots.
    """
    size = hex_size if hex_size is not None else HEX_SIZE
    path = QPainterPath()
    for c in cells:
        center = axial_to_pixel(c.q, c.r, size)
        poly = QPolygonF(hex_polygon(center, size))
        path.addPolygon(poly)
    return path

# --------------------------
# Puzzle piece item
# --------------------------
class HexPiece(QGraphicsObject):
    _FRONT_Z_START = 1
    _FRONT_Z_MAX = 4000  # keep below markers (5000) and highlight overlay (10000)
    _front_z_next = _FRONT_Z_START

    def __init__(self, cells: list[Cell], name: str, matrix_id: Literal["A", "B", "C", "D", "E", "F"]):
        super().__init__()
        self.cells = cells
        self.name = name
        self.matrix_id = matrix_id

        self._canvas = None
        self._home_pos = QPointF(0, 0)
        # After on-canvas double-click (rotate), the next release only re-snaps and would
        # otherwise call _next_front_z() again, recording a spurious second undo step.
        self._skip_front_z_and_undo_on_next_release = False
        self._press_scene_pos = QPointF()
        self._press_slot: tuple[int, int] | None = None
        self._press_rot = 0

        self.highlighted: set[int] = set()
        # Setup mark (white orientation dot). Tutorials terrain legends turn this off.
        self.show_corner_mark = True
        # Terrain fill. Tutorials animal-territory legends use outline only.
        self.show_terrain_fill = True

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        br = self._compute_local_bounding_rect()
        self.setTransformOriginPoint(br.center())
        self.setRotation(0)

    @classmethod
    def _next_front_z(cls, scene) -> int:
        """
        Return a zValue that places this piece above other pieces.
        Keeps z below markers/overlay. If we run out of room, renormalize all pieces.
        """
        z = cls._front_z_next
        if z > cls._FRONT_Z_MAX:
            cls._front_z_next = cls._FRONT_Z_START
            z = cls._front_z_next
            if scene is not None:
                # Reset all piece z to avoid unbounded growth.
                for it in scene.items():
                    if isinstance(it, HexPiece):
                        it.setZValue(0)
        cls._front_z_next = z + 1
        return z

    def clear_highlight(self):
        if self.highlighted:
            self.highlighted.clear()
            self.update()

    def _compute_local_bounding_rect(self) -> QRectF:
        xs, ys = [], []
        for c in self.cells:
            p = axial_to_pixel(c.q, c.r, HEX_SIZE)
            poly = hex_polygon(p, HEX_SIZE)
            xs += [pt.x() for pt in poly]
            ys += [pt.y() for pt in poly]
        if not xs:
            return QRectF(0, 0, 1, 1)
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def boundingRect(self) -> QRectF:
        return self._compute_local_bounding_rect()

    def set_home_pos(self, p: QPointF):
        self._home_pos = QPointF(p)

    def set_canvas(self, canvas):
        # typed as "PuzzleCanvas" in the file that imports it (board.canvas),
        # but we keep it runtime-light here.
        self._canvas = canvas

    def _pick_hex_center_by_visual_corner(
        self,
        corner: Literal["top_left", "top_right", "bottom_right"],
    ) -> QPointF:
        if not self.cells:
            return QPointF(0, 0)

        origin = self.transformOriginPoint()
        rad = math.radians(self.rotation() % 360)

        best_idx = 0
        best_rot = None

        def better(a: QPointF, b: QPointF) -> bool:
            if corner == "top_left":
                return (a.x() < b.x() - 1e-9) or (abs(a.x() - b.x()) < 1e-9 and a.y() < b.y() - 1e-9)
            if corner == "top_right":
                return (a.x() > b.x() + 1e-9) or (abs(a.x() - b.x()) < 1e-9 and a.y() < b.y() - 1e-9)
            return (a.x() > b.x() + 1e-9) or (abs(a.x() - b.x()) < 1e-9 and a.y() > b.y() + 1e-9)

        for i, c in enumerate(self.cells):
            center_local = axial_to_pixel(c.q, c.r, HEX_SIZE)
            center_rot = rotate_about(center_local, origin, rad)
            if best_rot is None or better(center_rot, best_rot):
                best_rot = center_rot
                best_idx = i

        winner = self.cells[best_idx]
        return axial_to_pixel(winner.q, winner.r, HEX_SIZE)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setPen(PEN_BORDER)

        # Check if any piece on canvas has highlights (solve mode) and highlights are shown,
        # or 0 target hexes (full map dimmed)
        any_highlights = False
        show_highlights = getattr(self._canvas, "_show_highlights", True)
        zero_targets_dim_full = getattr(self._canvas, "_zero_targets_dim_full_map", False)
        if self._canvas and show_highlights:
            if zero_targets_dim_full:
                any_highlights = True
            else:
                for item in self._canvas.item_slot:
                    if isinstance(item, HexPiece) and item.highlighted:
                        any_highlights = True
                        break

        # First pass: terrain fills (bear/cougar inner dotted follows)
        for idx, c in enumerate(self.cells):
            center = axial_to_pixel(c.q, c.r, HEX_SIZE)
            poly = hex_polygon(center, HEX_SIZE)
            # Build hex path for textured paint
            hex_path = QPainterPath()
            hex_path.addPolygon(QPolygonF(poly))

            if any_highlights and idx not in self.highlighted:
                painter.save()
                painter.setOpacity(0.5)  # More transparent when highlights are active

            if not self.show_terrain_fill:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(PEN_BORDER)
                painter.drawPolygon(poly)
            elif TEXTURED_HEX_FILL:
                terrain = color_hex_to_terrain(c.color)
                if terrain is not None:
                    seed = (hash(self.name or "") + idx) * 31
                    paint_terrain(
                        painter,
                        hex_path,
                        terrain,
                        seed=seed,
                        outline=False,
                    )
                else:
                    painter.setBrush(QBrush(QColor(c.color)))
                    painter.setPen(PEN_BORDER)
                    painter.drawPolygon(poly)
            else:
                painter.setBrush(QBrush(QColor(c.color)))
                painter.setPen(PEN_BORDER)
                painter.drawPolygon(poly)

            if any_highlights and idx not in self.highlighted:
                painter.restore()

        for idx, c in enumerate(self.cells):
            if c.inner_dotted:
                center = axial_to_pixel(c.q, c.r, HEX_SIZE)
                inner_size = HEX_SIZE * INNER_DOTTED_HEX_SCALE
                dotted_pen = QPen(QColor(c.inner_dotted), 1, Qt.DashLine)
                dotted_pen.setCosmetic(True)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(dotted_pen)
                if any_highlights and idx not in self.highlighted:
                    painter.save()
                    painter.setOpacity(0.5)
                painter.drawPolygon(QPolygonF(hex_polygon(center, inner_size)))
                if any_highlights and idx not in self.highlighted:
                    painter.restore()

        # Highlights are drawn by HighlightOverlay (scene-level) so borders
        # are never overlapped by adjacent pieces.

        # corner dot
        if self.show_corner_mark:
            rot = self.rotation() % 360
            dot_center = (
                self._pick_hex_center_by_visual_corner("top_left")
                if abs(rot) < 1e-6
                else self._pick_hex_center_by_visual_corner("bottom_right")
            )
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(dot_center, PIECE_CORNER_DOT_R, PIECE_CORNER_DOT_R)

        # number label (top-right by default)
        if self.name:
            label_center = self._pick_hex_center_by_visual_corner("top_right")
            font = QFont()
            font.setPointSize(int(16 * 0.7))
            font.setBold(True)
            #font.setWeight(QFont.Black)
            painter.setFont(font)
            painter.setPen(PEN_LABEL)

            painter.save()
            if any_highlights:
                painter.setOpacity(0.5)
            painter.translate(label_center)
            if abs(rot - 180) < 1e-6:
                painter.rotate(180)
            painter.drawText(
                QRectF(-HEX_SIZE, -HEX_SIZE, 2 * HEX_SIZE, 2 * HEX_SIZE),
                Qt.AlignCenter,
                str(self.name),
            )
            painter.restore()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            new_pos = value
            delta = new_pos - self.pos()
            r = self.sceneBoundingRect()
            proposed = r.translated(delta.x(), delta.y())
            sr = self.scene().sceneRect()
            dx, dy = delta.x(), delta.y()
            if proposed.left() < sr.left():
                dx += sr.left() - proposed.left()
            if proposed.right() > sr.right():
                dx += sr.right() - proposed.right()
            if proposed.top() < sr.top():
                dy += sr.top() - proposed.top()
            if proposed.bottom() > sr.bottom():
                dy += sr.bottom() - proposed.bottom()
            return self.pos() + QPointF(dx, dy)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._z_before_drag = self.zValue()
        self._drag_raised = False  # raise z only when actually moving, not on double-click
        self._press_scene_pos = event.scenePos()
        if self._canvas is not None:
            self._press_slot = self._canvas.item_slot.get(self)
        else:
            self._press_slot = None
        self._press_rot = round(self.rotation()) % 360
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not getattr(self, "_drag_raised", False):
            self._drag_raised = True
            self.setZValue(15000)  # above overlay (10000), markers (5000) while dragging
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        assigned_to_canvas = False

        if self._canvas is not None:
            drop_point = self.mapToScene(self.boundingRect().center())
            if self._canvas.contains_point(drop_point):
                row, col = self._canvas._slot_for_point(drop_point)
                if self._canvas.is_free(row, col, ignore_item=self):
                    self.setPos(self._canvas.snap_pos_for_item_to_slot(self, row, col))
                    self._canvas.assign_item(self, row, col)
                    assigned_to_canvas = True
                else:
                    prev = self._canvas.item_slot.get(self)
                    if prev is not None:
                        pr, pc = prev
                        self.setPos(self._canvas.snap_pos_for_item_to_slot(self, pr, pc))
                        assigned_to_canvas = True
            else:
                slot = self._canvas.item_slot.get(self)
                if slot is not None:
                    self._canvas.release_markers_on_slot(slot[0], slot[1])
                self._canvas.release_item(self)

        if not assigned_to_canvas:
            self.setPos(self._home_pos)
            self.setZValue(getattr(self, "_z_before_drag", 0))
            if self._canvas is not None:
                self._canvas.notify_undo_checkpoint()
            self._skip_front_z_and_undo_on_next_release = False
            return

        if self._skip_front_z_and_undo_on_next_release:
            self._skip_front_z_and_undo_on_next_release = False
            return

        # Same-hex tap without real drag (first click of double-click, or tiny jitter):
        # skip _next_front_z + undo — otherwise place + rotate needs three undos to get home.
        _NO_DRAG_PX = 5.0
        if (
            self._press_slot is not None
            and self._canvas is not None
            and self._canvas.item_slot.get(self) == self._press_slot
            and round(self.rotation()) % 360 == self._press_rot
            and QLineF(self._press_scene_pos, event.scenePos()).length() < _NO_DRAG_PX
        ):
            return

        # Keep the last-moved piece above other pieces (but still below markers/overlay).
        self.setZValue(self._next_front_z(self.scene()))
        if self._canvas is not None:
            self._canvas.notify_undo_checkpoint()

    def rotate_180(self):
        self.setRotation((self.rotation() + 180) % 360)

    def mouseDoubleClickEvent(self, event):
        if self._canvas and getattr(self._canvas, "_is_map_frozen", lambda: False)():
            super().mouseDoubleClickEvent(event)
            return
        self.rotate_180()
        slot = self._canvas.item_slot.get(self) if self._canvas else None
        if slot:
            # boundingRect() changes with rotation; snap now so undo matches the state after
            # mouseReleaseEvent (which re-snaps), avoiding two undo steps for one rotation.
            r, c = slot
            self.setPos(self._canvas.snap_pos_for_item_to_slot(self, r, c))
        # Lower piece z so it stays below markers; raise markers on this piece above it
        self.setZValue(self._next_front_z(self.scene()))
        if slot:
            for m, mslot in list(self._canvas.marker_slot.items()):
                if mslot[0] == slot[0] and mslot[1] == slot[1]:
                    m.setZValue(5000)
                    self.stackBefore(m)
        super().mouseDoubleClickEvent(event)
        if self._canvas is not None:
            self._canvas.notify_undo_checkpoint()
        if slot is not None:
            self._skip_front_z_and_undo_on_next_release = True


# --------------------------
# Helpers
# --------------------------
def find_hex_under_point(p_scene: QPointF, items: list[QGraphicsItem]):
    """
    Finds which HexPiece hex cell contains p_scene.
    Items should be in stacking order (topmost first), e.g. scene.items(p_scene).
    Returns the topmost piece's hex so markers are not placed on hexes under another piece.
    """
    for it in items:
        if not isinstance(it, HexPiece):
            continue

        for idx, c in enumerate(it.cells):
            center_local = axial_to_pixel(c.q, c.r, HEX_SIZE)
            poly_local = QPolygonF(hex_polygon(center_local, HEX_SIZE))
            poly_scene = QPolygonF([it.mapToScene(pt) for pt in poly_local])

            if poly_scene.containsPoint(p_scene, Qt.OddEvenFill):
                center_scene = it.mapToScene(center_local)
                return (it, idx, center_scene)

    return (None, None, QPointF())
