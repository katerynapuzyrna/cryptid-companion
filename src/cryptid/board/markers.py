from PySide6.QtWidgets import QGraphicsObject, QGraphicsItem
from PySide6.QtGui import (
    QBrush,
    QPen,
    QColor,
    QFont,
    QPainterPath,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtCore import QPointF, QRectF, Qt


def _grab_cursor():
    return Qt.CursorShape.OpenHandCursor
from typing import Callable, Literal, Optional

from settings.config import MARKER_SIZE
from settings.theme import PEN_BORDER
from board.pieces import find_hex_under_point, HexPiece


MARKER_SCALE_HOME = 1.5   # 1.5x bigger in marker bank
MARKER_SCALE_CANVAS = 1.0  # normal size when placed on canvas

# Canvas scale when several figures share one hex cell (marker + chips; see BoardBuilder._relayout_hex_figures).
MARKER_SCALE_CANVAS_HEX_2 = 0.75
MARKER_SCALE_CANVAS_HEX_3 = 0.65
MARKER_SCALE_CANVAS_HEX_4 = 0.6
MARKER_SCALE_CANVAS_HEX_5_PLUS = 0.5


def marker_scale_canvas_for_hex_figure_count(count: int) -> float:
    """Scale for markers/chips when ``count`` figures occupy the same hex cell."""
    if count <= 1:
        return float(MARKER_SCALE_CANVAS)
    if count == 2:
        s = MARKER_SCALE_CANVAS_HEX_2
    elif count == 3:
        s = MARKER_SCALE_CANVAS_HEX_3
    elif count == 4:
        s = MARKER_SCALE_CANVAS_HEX_4
    else:
        s = MARKER_SCALE_CANVAS_HEX_5_PLUS
    return float(s * MARKER_SCALE_CANVAS)


MARKER_Z_BANK = 1500       # above structures proxy (1000) so bank markers receive hover/cursor
MARKER_Z_DRAGGING = 6000   # above placed markers (5000) so dragged marker overlaps them
CHIP_Z_DRAGGING = 20000    # above highlight overlay (10000) and question picker proxy (16000)

# Hotseat bank chip placeholder: QPainter opacity on dimmed pixmap (see HotseatGameplaySidebar.sync_hotseat_*).
BANK_HOME_SHADOW_OPACITY = 0.38
# Squared scene distance: marker center off home → show bank shadow (assigned on map, or dragging from bank).
_BANK_HOME_SHADOW_OFF_HOME_EPS2 = 9.0  # 3 px
# If release movement is below this (squared scene distance), treat as click / double-click, not a drag.
_CHIP_RELEASE_MOVE_EPS2 = 25.0  # 5 px — avoids wrong hex when Qt nudges the item slightly


class MarkerItem(QGraphicsObject):
    def __init__(self, shape_kind: Literal["circle", "triangle", "octagon"], color: str):
        super().__init__()
        self.shape_kind = shape_kind
        self.fill_color = color
        self._home_pos = QPointF(0, 0)
        self._canvas = None
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(_grab_cursor())
        self.setTransformOriginPoint(QPointF(0, 0))
        self.setScale(MARKER_SCALE_HOME)

    def set_canvas(self, canvas):
        self._canvas = canvas

    def set_home_pos(self, p: QPointF):
        self._home_pos = QPointF(p)

    def _should_draw_bank_home_shadow(self) -> bool:
        """True while the marker is on a hex or any time it has left its bank position (incl. drag before drop)."""
        canvas = self._canvas
        if canvas is None or self.scene() is None:
            return False
        if not getattr(canvas, "_marker_bank_home_shadow_enabled", True):
            return False
        if self in canvas.marker_slot:
            return True
        center = self.mapToScene(QPointF(0, 0))
        dx = center.x() - self._home_pos.x()
        dy = center.y() - self._home_pos.y()
        return dx * dx + dy * dy > _BANK_HOME_SHADOW_OFF_HOME_EPS2

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            a = self._should_draw_bank_home_shadow()
            prev = getattr(self, "_prev_bank_shadow_include", None)
            if (prev is None and a) or (prev is not None and a != prev):
                self.prepareGeometryChange()
            self._prev_bank_shadow_include = a
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            new_pos = value
            delta = new_pos - self.pos()
            # Only the core hit shape — not sceneBoundingRect(), which includes the bank ghost
            # and can prevent or corrupt setPos(_home_pos) when the tile is removed from canvas.
            r = self.mapRectToScene(self.shape().boundingRect())
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
        result = super().itemChange(change, value)
        return result

    def mousePressEvent(self, event):
        self._z_before_drag = self.zValue()
        self.setZValue(MARKER_Z_DRAGGING)
        super().mousePressEvent(event)

    def boundingRect(self) -> QRectF:
        s = MARKER_SIZE
        r = QRectF(-s, -s, 2 * s, 2 * s)
        canvas = self._canvas
        if canvas is not None and self._should_draw_bank_home_shadow():
            hp = self.mapFromScene(self._home_pos)
            sc = float(self.scale()) or 1.0
            margin = MARKER_SIZE * max(MARKER_SCALE_HOME, sc) * 1.25
            r = r.united(
                QRectF(hp.x() - margin, hp.y() - margin, 2 * margin, 2 * margin)
            )
        return r

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self.shape_kind == "circle":
            s = MARKER_SIZE
            path.addEllipse(QRectF(-s, -s, 2 * s, 2 * s))
        elif self.shape_kind == "triangle":
            s = MARKER_SIZE
            pts = QPolygonF(
                [QPointF(0, -s), QPointF(s * 0.9, s * 0.8), QPointF(-s * 0.9, s * 0.8)]
            )
            path.addPolygon(pts)
        else:  # octagon
            s = MARKER_SIZE
            inner = s * 0.7
            pts = QPolygonF(
                [
                    QPointF(0, -s),
                    QPointF(inner, -inner),
                    QPointF(s, 0),
                    QPointF(inner, inner),
                    QPointF(0, s),
                    QPointF(-inner, inner),
                    QPointF(-s, 0),
                    QPointF(-inner, -inner),
                ]
            )
            path.addPolygon(pts)
        return path

    def _draw_marker_body(self, painter) -> None:
        """Fill + stroke for the marker shape at the origin (item coordinates)."""
        if self.shape_kind == "circle":
            s = MARKER_SIZE
            painter.drawEllipse(QRectF(-s, -s, 2 * s, 2 * s))
        elif self.shape_kind == "triangle":
            s = MARKER_SIZE
            pts = QPolygonF(
                [QPointF(0, -s), QPointF(s * 0.9, s * 0.8), QPointF(-s * 0.9, s * 0.8)]
            )
            painter.drawPolygon(pts)
        else:  # octagon
            s = MARKER_SIZE
            inner = s * 0.7
            pts = QPolygonF(
                [
                    QPointF(0, -s),
                    QPointF(inner, -inner),
                    QPointF(s, 0),
                    QPointF(inner, inner),
                    QPointF(0, s),
                    QPointF(-inner, inner),
                    QPointF(-s, 0),
                    QPointF(-inner, -inner),
                ]
            )
            painter.drawPolygon(pts)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_BORDER)
        painter.setBrush(QBrush(QColor(self.fill_color)))

        # Dim when placed on a non-highlighted hex and solve mode is active (or 0 targets = full map dimmed)
        on_non_highlighted = False
        show_highlights = getattr(self._canvas, "_show_highlights", True)
        zero_targets_dim_full = getattr(self._canvas, "_zero_targets_dim_full_map", False)
        if self._canvas and show_highlights:
            any_highlights = zero_targets_dim_full or any(
                isinstance(it, HexPiece) and it.highlighted
                for it in self._canvas.item_slot
            )
            if any_highlights:
                slot = self._canvas.marker_slot.get(self)
                if slot is not None:
                    row, col, cell_idx = slot
                    piece = self._canvas.occupied.get((row, col))
                    if piece is None or cell_idx not in getattr(piece, "highlighted", set()):
                        on_non_highlighted = True

        if on_non_highlighted:
            painter.save()
            painter.setOpacity(0.5)
        self._draw_marker_body(painter)
        if on_non_highlighted:
            painter.restore()

        # Bank “shadow” at home while on a hex or off home (same 0.38 as hotseat chip bank pixmap).
        canvas = self._canvas
        if canvas is not None and self._should_draw_bank_home_shadow():
            painter.save()
            painter.setOpacity(BANK_HOME_SHADOW_OPACITY)
            painter.setPen(PEN_BORDER)
            painter.setBrush(QBrush(QColor(self.fill_color)))
            painter.translate(self.mapFromScene(self._home_pos))
            sc = float(self.scale())
            if sc > 1e-9:
                painter.scale(MARKER_SCALE_HOME / sc, MARKER_SCALE_HOME / sc)
            self._draw_marker_body(painter)
            painter.restore()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setZValue(getattr(self, "_z_before_drag", MARKER_Z_BANK))
        scene = self.scene()
        if scene is None:
            return
        p_scene = self.mapToScene(QPointF(0, 0))
        piece, idx, snap_center = find_hex_under_point(p_scene, scene.items(p_scene))
        if self._canvas is not None:
            old_slot = self._canvas.marker_slot.get(self)
            if piece is None:
                self._canvas.release_marker(self)
                self.setZValue(MARKER_Z_BANK)
                self.setScale(MARKER_SCALE_HOME)
                self.setPos(self._home_pos)
                self.setCursor(_grab_cursor())
                new_slot = None
            else:
                slot = self._canvas.item_slot.get(piece)
                if slot is None:
                    self._canvas.release_marker(self)
                    self.setZValue(MARKER_Z_BANK)
                    self.setScale(MARKER_SCALE_HOME)
                    self.setPos(self._home_pos)
                    self.setCursor(_grab_cursor())
                    new_slot = None
                elif not self._canvas.is_marker_cell_free(slot[0], slot[1], idx, ignore_item=self):
                    self._canvas.release_marker(self)
                    self.setZValue(MARKER_Z_BANK)
                    self.setScale(MARKER_SCALE_HOME)
                    self.setPos(self._home_pos)
                    self.setCursor(_grab_cursor())
                    new_slot = None
                else:
                    self._canvas.release_marker(self)
                    self._canvas.assign_marker(self, slot[0], slot[1], idx)  # explicitly stack piece behind marker
                    new_slot = (slot[0], slot[1], idx)

            # If the marker actually changed hex (including to/from bank), notify canvas so
            # higher-level code can auto-clear highlights. Dropping back on the same hex is ignored.
            if old_slot != new_slot:
                cb = getattr(self._canvas, "_on_marker_reassigned", None)
                if callable(cb):
                    cb(old_slot, new_slot)
        else:
            if piece is not None:
                self.setPos(snap_center)
            else:
                self.setPos(self._home_pos)
        if self._canvas is not None:
            self._canvas.notify_undo_checkpoint()


# --------------------------
# Player chips (circles, squares; multiple per hex allowed)
# --------------------------
class ChipItem(QGraphicsObject):
    """Player chips: circles and squares, same size as markers, multiple per hex allowed."""

    def __init__(
        self,
        shape_kind: Literal["circle", "square"],
        color: str,
        *,
        question_mark: bool = False,
    ):
        super().__init__()
        self.shape_kind = shape_kind
        self.fill_color = color
        self._question_mark = question_mark
        self._hotseat_from_sharing_bank: bool = False
        self._home_pos = QPointF(0, 0)
        self._hotseat_home_fn: Optional[Callable[[], QPointF]] = None
        self._position_change_notify: Optional[Callable[[], None]] = None
        self._canvas = None
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setCursor(_grab_cursor())
        self.setTransformOriginPoint(QPointF(0, 0))
        self.setScale(MARKER_SCALE_HOME)
        self._history_pulse_alpha: float = 0.0

    def set_canvas(self, canvas):
        self._canvas = canvas

    def set_home_pos(self, p: QPointF):
        self._home_pos = QPointF(p)
        self._hotseat_home_fn = None

    def set_hotseat_home_resolver(self, fn: Optional[Callable[[], QPointF]]) -> None:
        """Play Hotseat: recompute drop-off position over the On your turn chip previews."""
        self._hotseat_home_fn = fn

    def set_position_change_notify(self, fn: Optional[Callable[[], None]]) -> None:
        """Optional callback after the item's position has changed (e.g. keep a widget aligned while dragging)."""
        self._position_change_notify = fn

    def _notify_dropped_hotseat_home(self) -> None:
        """Play Hotseat: chip was released off-hex onto its bank/home position (e.g. On your turn row)."""
        canvas = self._canvas
        if canvas is None:
            return
        cb = getattr(canvas, "_on_chip_dropped_hotseat_home", None)
        if callable(cb):
            cb(self)

    def _apply_bank_home_after_release_off_hex(self) -> None:
        """Remove hotseat scene chip before moving to bank coords so only the dimmed strip shows (like sharing square)."""
        self._notify_dropped_hotseat_home()
        if self.scene() is None:
            return
        self.setZValue(MARKER_Z_BANK)
        self.setScale(MARKER_SCALE_HOME)
        self.setPos(self._chip_home_scene_pos())
        self.setCursor(_grab_cursor())

    def resolve_hotseat_question(
        self,
        color_hex: str,
        *,
        shape_kind: Literal["circle", "square"],
    ) -> None:
        """Turn a gray question chip into a normal chip: circle = yes/could be, square = no (Play Hotseat)."""
        self.fill_color = color_hex
        self._question_mark = False
        self.shape_kind = shape_kind
        self.update()

    def _chip_home_scene_pos(self) -> QPointF:
        if self._hotseat_home_fn is not None:
            return self._hotseat_home_fn()
        return self._home_pos

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            new_pos = value
            delta = new_pos - self.pos()
            r = self.sceneBoundingRect()
            proposed = r.translated(delta.x(), delta.y())
            sr = QRectF(self.scene().sceneRect())
            if self._hotseat_home_fn is not None:
                try:
                    hp = self._hotseat_home_fn()
                except Exception:
                    hp = None
                if hp is not None:
                    pad = 120.0
                    new_right = max(sr.right(), hp.x() + pad)
                    new_top = min(sr.top(), hp.y() - pad)
                    new_bottom = max(sr.bottom(), hp.y() + pad)
                    sr = QRectF(sr.left(), new_top, new_right - sr.left(), new_bottom - new_top)
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
        result = super().itemChange(change, value)
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self._position_change_notify is not None
        ):
            self._position_change_notify()
        return result

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._z_before_drag = self.zValue()
            self.setZValue(CHIP_Z_DRAGGING)
            self._drag_scene_pos_start = QPointF(self.pos())
        super().mousePressEvent(event)

    def boundingRect(self) -> QRectF:
        s = MARKER_SIZE
        base = QRectF(-s, -s, 2 * s, 2 * s)
        if getattr(self, "_history_pulse_alpha", 0.0) > 0.0:
            pad = 8.0
            return base.adjusted(-pad, -pad, pad, pad)
        return base

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        # Hit area stays the chip body (not the pulse ring).
        s = MARKER_SIZE
        body = QRectF(-s, -s, 2 * s, 2 * s)
        if self.shape_kind == "circle":
            path.addEllipse(body)
        else:  # square
            path.addRect(body)
        return path

    def set_history_pulse(self, alpha: float) -> None:
        """0..1 ring opacity for turn-history focus pulse; 0 clears."""
        new_a = max(0.0, min(1.0, float(alpha)))
        old_a = float(getattr(self, "_history_pulse_alpha", 0.0))
        if (old_a > 0.0) != (new_a > 0.0):
            self.prepareGeometryChange()
        self._history_pulse_alpha = new_a
        self.update()

    def clear_history_pulse(self) -> None:
        self.set_history_pulse(0.0)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_BORDER)
        base = QColor(self.fill_color)
        s = MARKER_SIZE
        r = QRectF(-s, -s, 2 * s, 2 * s)
        cx = r.center().x()
        cy = r.center().y()
        radius = max(r.width(), r.height()) / 2
        # Volumetric fill: light from top-left, darker at edges
        grad = QRadialGradient(cx, cy, radius, cx - 3, cy - 3, 0)
        grad.setColorAt(0, base.lighter(140))
        grad.setColorAt(0.6, base)
        grad.setColorAt(1, base.darker(120))
        painter.setBrush(QBrush(grad))
        if self.shape_kind == "circle":
            painter.drawEllipse(r)
        else:
            painter.drawRect(r)
        if self._question_mark and self.shape_kind == "circle":
            painter.save()
            font = QFont()
            font.setBold(True)
            font.setPixelSize(max(6, int(round(MARKER_SIZE * 0.85))))
            painter.setFont(font)
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "?")
            painter.restore()
        pulse = float(getattr(self, "_history_pulse_alpha", 0.0))
        if pulse > 0.0:
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Soft dark-gray outer glow + tighter ring.
            outer = QColor(70, 70, 70, int(110 * pulse))
            inner = QColor(45, 45, 45, int(235 * pulse))
            ring = r.adjusted(-4.0, -4.0, 4.0, 4.0)
            pen_outer = QPen(outer)
            pen_outer.setWidthF(4.5)
            painter.setPen(pen_outer)
            if self.shape_kind == "circle":
                painter.drawEllipse(ring)
            else:
                painter.drawRect(ring)
            pen_inner = QPen(inner)
            pen_inner.setWidthF(2.0)
            painter.setPen(pen_inner)
            if self.shape_kind == "circle":
                painter.drawEllipse(ring)
            else:
                painter.drawRect(ring)
            painter.restore()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.setZValue(getattr(self, "_z_before_drag", 0))
        # Double-click (or plain click) often moves the item by a few px; re-hit-testing then
        # picks the wrong HexPiece (e.g. first in z-order). Skip placement when not a real drag.
        if self._canvas is not None and self._canvas.chip_slot.get(self) is not None:
            start = getattr(self, "_drag_scene_pos_start", None)
            if start is not None:
                d = self.pos() - start
                if d.x() * d.x() + d.y() * d.y() <= _CHIP_RELEASE_MOVE_EPS2:
                    return
        scene = self.scene()
        if scene is None:
            return
        p_scene = self.mapToScene(QPointF(0, 0))
        piece, idx, snap_center = find_hex_under_point(p_scene, scene.items(p_scene))
        if self._canvas is not None:
            if piece is None:
                self._canvas.release_chip(self)
                self._apply_bank_home_after_release_off_hex()
            else:
                slot = self._canvas.item_slot.get(piece)
                if slot is None:
                    self._canvas.release_chip(self)
                    self._apply_bank_home_after_release_off_hex()
                else:
                    hex_slot = (slot[0], slot[1], idx)
                    old_slot = self._canvas.chip_slot.get(self)
                    if old_slot == hex_slot:
                        # Dropped back onto the same hex: re-assign to trigger relayout
                        # so the chip snaps back to its arranged position instead of
                        # staying where the cursor was.
                        self._canvas.assign_chip(self, hex_slot[0], hex_slot[1], hex_slot[2])
                        self._canvas.notify_undo_checkpoint()
                        return
                    self._canvas.release_chip(self)
                    existing = self._canvas.chip_occupied.get(hex_slot, [])
                    validate = getattr(self._canvas, "_validate_chip_drop", None)
                    if callable(validate):
                        try:
                            valid = bool(validate(self, hex_slot, existing))
                        except Exception:
                            valid = False
                        if not valid:
                            # Snap back so an illegal hex does not undo the chip.
                            if old_slot is not None:
                                self._canvas.assign_chip(
                                    self, old_slot[0], old_slot[1], old_slot[2]
                                )
                            else:
                                self._apply_bank_home_after_release_off_hex()
                        else:
                            self._canvas.assign_chip(self, slot[0], slot[1], idx)
                    else:
                        # Deduction / default: max 1 square, max 1 chip per color, max 4 chips
                        n_square = sum(1 for c in existing if c.shape_kind == "square")
                        colors_used = {c.fill_color for c in existing}
                        would_add_square = 1 if self.shape_kind == "square" else 0
                        total_after = len(existing) + 1
                        squares_after = n_square + would_add_square
                        valid = (
                            total_after <= 4
                            and squares_after <= 1
                            and self.fill_color not in colors_used
                        )
                        if not valid:
                            self._apply_bank_home_after_release_off_hex()
                        else:
                            self._canvas.assign_chip(self, slot[0], slot[1], idx)
        else:
            if piece is not None:
                self.setPos(snap_center)
            else:
                self.setPos(self._chip_home_scene_pos())
        if self._canvas is not None:
            self._canvas.notify_undo_checkpoint()
