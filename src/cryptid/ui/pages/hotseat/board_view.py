"""Hotseat board QGraphicsView (pickers, chip strip proxy, bank carry)."""
from __future__ import annotations

import math
from typing import Any, Callable, Literal

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QWidget,
)

from board.board_builder import BoardBuilder
from board.board_view import BoardView
from board.markers import MARKER_SCALE_CANVAS, ChipItem
from board.pieces import find_hex_under_point
from logic.conditions import compute_all_conditions
from ui.shared.widgets.player_colors import get_player_color_hex

from .chip_widgets import _HotseatChipDragLabel, _hotseat_chip_drag_label_movable
from .constants import (
    _HOTSEAT_CHIP_MIME,
    _HOTSEAT_MAP_CHIP_STRIP_GAP_SCENE,
    _HOTSEAT_MAP_CHIP_STRIP_PROXY_Z,
    _HOTSEAT_MAP_CHIP_STRIP_VIEWPORT_GAP_PX,
    _HOTSEAT_QPICK_PROXY_Z,
    _HOTSEAT_VIEW_MAP_INSET_PX,
    _HOTSEAT_VIEW_VIEWPORT_FRAME_MARGIN_PX,
    _QWIDGETSIZE_MAX,
)
from .helpers import _hotseat_bank_carry_preview_pixmap, _hotseat_match_clue_to_grid
from .pickers import _build_hotseat_question_picker_widget, _build_hotseat_search_picker_widget
from .sidebar import HotseatGameplaySidebar


class HotseatBoardView(BoardView):
    """Board graphics view for Play Hotseat (question picker + map chip strip use ``QGraphicsProxyWidget``)."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        # State must exist before any call that can trigger viewportEvent (setAcceptDrops, mouse tracking, …).
        self._gameplay_sidebar: HotseatGameplaySidebar | None = None
        self._terrain_fit_rect: QRectF | None = None
        self._hotseat_board_builder: BoardBuilder | None = None
        self._map_chip_strip_proxy: QGraphicsProxyWidget | None = None
        self._qpick_overlay: QFrame | None = None
        self._qpick_proxy: QGraphicsProxyWidget | None = None
        self._qpick_chip: ChipItem | None = None
        self._qpick_dimmed_chips: list[tuple[Any, float]] = []
        self._hotseat_advanced_mode: bool = False
        #: In-proxy bank chip interaction: (shape, color_hex) while ``grabMouse`` on viewport.
        self._hotseat_bank_carry: tuple[str, str] | None = None
        #: Press on bank chip label + drag threshold (global pos); proxy often stops sending moves to the label.
        self._pending_bank_chip_drag: tuple[str, str, QPoint] | None = None
        #: Top-level pixmap under the cursor while carrying from the bank (``QCursor`` is size-limited on Windows).
        self._hotseat_carry_preview: QLabel | None = None
        #: Map-strip proxy item cursor (QGraphicsView shows item cursors; viewport/QLabel do not).
        self._hotseat_strip_proxy_cursor_set: bool = False
        #: Question/search picker ring proxy cursor (same embedding issue as the strip).
        self._hotseat_qpick_proxy_cursor_set: bool = False
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        m = _HOTSEAT_VIEW_VIEWPORT_FRAME_MARGIN_PX
        self.setViewportMargins(m, m, m, m)

    def _notify_end_turn_eligibility_changed(self) -> None:
        fn = getattr(self, "_end_turn_eligibility_cb", None)
        if callable(fn):
            fn()

    def arm_bank_chip_drag(self, shape: str, color_hex: str, global_press: QPoint) -> None:
        self._pending_bank_chip_drag = (shape, color_hex, global_press)

    def clear_pending_bank_chip_drag(self) -> None:
        self._pending_bank_chip_drag = None

    def _ensure_hotseat_carry_preview(self) -> QLabel:
        w = self._hotseat_carry_preview
        if w is None:
            w = QLabel()
            w.setWindowFlags(
                Qt.WindowType.ToolTip
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self._hotseat_carry_preview = w
        return w

    def _show_hotseat_carry_preview(self, shape: str, color_hex: str) -> None:
        pix = _hotseat_bank_carry_preview_pixmap(shape, color_hex)
        lab = self._ensure_hotseat_carry_preview()
        lab.setPixmap(pix)
        lab.adjustSize()
        gp = QCursor.pos()
        lab.move(
            gp.x() - pix.width() // 2,
            gp.y() - pix.height() // 2,
        )
        lab.show()

    def _sync_hotseat_carry_preview_pos(self, global_pt: QPoint) -> None:
        lab = self._hotseat_carry_preview
        if lab is None or not lab.isVisible():
            return
        pm = lab.pixmap()
        if pm is None or pm.isNull():
            return
        w, h = pm.width(), pm.height()
        lab.move(global_pt.x() - w // 2, global_pt.y() - h // 2)

    def _hide_hotseat_carry_preview(self) -> None:
        lab = self._hotseat_carry_preview
        if lab is not None:
            lab.hide()

    def begin_hotseat_bank_chip_carry(
        self,
        shape: str,
        color_hex: str,
        *,
        trust_bank_drag: bool = False,
    ) -> None:
        """Start placing a bank chip: mouse is captured by the map until release (reliable with sidebar proxy)."""
        if self._hotseat_board_builder is None:
            return
        if shape == "question" and self._gameplay_sidebar is not None:
            if not self._gameplay_sidebar.may_drag_question_chip_from_bank():
                return
        if shape == "circle" and self._gameplay_sidebar is not None:
            if not self._gameplay_sidebar.may_drag_search_chip_from_bank():
                return
        if shape == "square" and self._gameplay_sidebar is not None:
            if not self._gameplay_sidebar.may_drag_sharing_chip_from_bank():
                return
        if shape not in ("question", "circle", "square"):
            return
        if not trust_bank_drag and not (
            QApplication.mouseButtons() & Qt.MouseButton.LeftButton
        ):
            return
        self._pending_bank_chip_drag = None
        if self._hotseat_bank_carry is not None:
            self.cancel_hotseat_bank_chip_carry()
        self._hotseat_bank_carry = (shape, color_hex)
        sb = self._gameplay_sidebar
        if sb is not None:
            if shape == "square":
                sb._hotseat_sharing_square_carry = True
                sb.sync_hotseat_sharing_bank_visibility()
            elif shape == "question":
                sb._hotseat_question_carry = True
                sb.sync_hotseat_question_bank_visibility()
            elif shape == "circle":
                sb._hotseat_search_carry = True
                sb.sync_hotseat_search_bank_visibility()
        self._show_hotseat_carry_preview(shape, color_hex)
        # QGraphicsView delivers mouse to the viewport; grab must match or release never arrives.
        self.viewport().grabMouse()
        px = self._map_chip_strip_proxy
        if px is not None and self._hotseat_strip_proxy_cursor_set:
            px.unsetCursor()
            self._hotseat_strip_proxy_cursor_set = False
        qpx = self._qpick_proxy
        if qpx is not None and self._hotseat_qpick_proxy_cursor_set:
            qpx.unsetCursor()
            self._hotseat_qpick_proxy_cursor_set = False
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        self._notify_end_turn_eligibility_changed()

    def cancel_hotseat_bank_chip_carry(self) -> None:
        sb = self._gameplay_sidebar
        if sb is not None and self._hotseat_bank_carry is not None:
            _shape, _ = self._hotseat_bank_carry
            if _shape == "square":
                sb._hotseat_sharing_square_carry = False
                sb.sync_hotseat_sharing_bank_visibility()
            elif _shape == "question":
                sb._hotseat_question_carry = False
                sb.sync_hotseat_question_bank_visibility()
            elif _shape == "circle":
                sb._hotseat_search_carry = False
                sb.sync_hotseat_search_bank_visibility()
        self._hotseat_bank_carry = None
        self._hide_hotseat_carry_preview()
        grab = QWidget.mouseGrabber()
        if grab is self.viewport():
            self.viewport().releaseMouse()
        elif grab is self:
            self.releaseMouse()
        self.viewport().unsetCursor()
        self._notify_end_turn_eligibility_changed()

    def _finish_hotseat_bank_carry_at_global(self, global_pt: QPoint) -> None:
        if self._hotseat_bank_carry is None:
            return
        shape, color_hex = self._hotseat_bank_carry
        sb = self._gameplay_sidebar
        if sb is not None:
            if shape == "square":
                sb._hotseat_sharing_square_carry = False
                sb.sync_hotseat_sharing_bank_visibility()
            elif shape == "question":
                sb._hotseat_question_carry = False
                sb.sync_hotseat_question_bank_visibility()
            elif shape == "circle":
                sb._hotseat_search_carry = False
                sb.sync_hotseat_search_bank_visibility()
        # Clear carry state and release mouse grab, but keep the preview
        # visible until the new ChipItem is in the scene (avoids flash).
        self._hotseat_bank_carry = None
        grab = QWidget.mouseGrabber()
        if grab is self.viewport():
            self.viewport().releaseMouse()
        elif grab is self:
            self.releaseMouse()
        self.viewport().unsetCursor()
        scene_pos = self._scene_pos_from_global(global_pt)
        self._try_place_hotseat_bank_chip(shape, color_hex, scene_pos)
        self._hide_hotseat_carry_preview()
        self.viewport().update()
        self._notify_end_turn_eligibility_changed()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        pend = self._pending_bank_chip_drag
        if pend is not None:
            et = event.type()
            if et == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
                if event.buttons() & Qt.MouseButton.LeftButton:
                    g = event.globalPosition().toPoint()
                    if (
                        g - pend[2]
                    ).manhattanLength() >= QApplication.startDragDistance():
                        shape, color_hex, _ = pend
                        self._pending_bank_chip_drag = None
                        self.begin_hotseat_bank_chip_carry(
                            shape, color_hex, trust_bank_drag=True
                        )
            elif et == QEvent.Type.MouseButtonRelease and isinstance(
                event, QMouseEvent
            ):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._pending_bank_chip_drag = None
        if (
            event.type() == QEvent.Type.MouseMove
            and isinstance(event, QMouseEvent)
            and self._hotseat_bank_carry is None
            and (
                self._map_chip_strip_proxy is not None
                or self._qpick_proxy is not None
            )
        ):
            self.sync_hotseat_embedded_proxy_cursors()
        if self._hotseat_bank_carry is not None:
            if event.type() == QEvent.Type.MouseMove and isinstance(
                event, QMouseEvent
            ):
                self._sync_hotseat_carry_preview_pos(
                    event.globalPosition().toPoint()
                )
        if watched is self.viewport() and self._hotseat_bank_carry is not None:
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(
                event, QMouseEvent
            ):
                if event.button() == Qt.MouseButton.RightButton:
                    self.cancel_hotseat_bank_chip_carry()
                    return True
            if event.type() == QEvent.Type.MouseButtonRelease and isinstance(
                event, QMouseEvent
            ):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._finish_hotseat_bank_carry_at_global(
                        event.globalPosition().toPoint()
                    )
                    return True
        return super().eventFilter(watched, event)

    def _hotseat_strip_chip_at_global(
        self, strip_root: QWidget, global_pos: QPoint
    ) -> _HotseatChipDragLabel | None:
        """Bank chip: ``childAt`` when mapped point lies in-strip, else ``widgetAt`` + ``isAncestorOf``."""
        lf = strip_root.mapFromGlobal(global_pos)
        fw, fh = strip_root.width(), strip_root.height()
        if fw > 0 and fh > 0 and 0 <= lf.x() < fw and 0 <= lf.y() < fh:
            child = strip_root.childAt(lf)
            node: QWidget | None = child
            while node is not None:
                if isinstance(node, _HotseatChipDragLabel):
                    return node
                if node is strip_root:
                    break
                node = node.parentWidget()
        at = QApplication.widgetAt(global_pos)
        if at is not None and strip_root.isAncestorOf(at):
            node = at
            while node is not None:
                if isinstance(node, _HotseatChipDragLabel):
                    return node
                node = node.parentWidget()
        return None

    def sync_hotseat_map_strip_proxy_item_cursor(self) -> None:
        """Apply open-hand/arrow on the strip ``QGraphicsProxyWidget`` (reliable in QGraphicsView)."""
        p = self._map_chip_strip_proxy
        if p is None:
            return
        if self._hotseat_bank_carry is not None:
            if self._hotseat_strip_proxy_cursor_set:
                p.unsetCursor()
                self._hotseat_strip_proxy_cursor_set = False
            return
        w = p.widget()
        if w is None:
            return
        if w.width() <= 0 or w.height() <= 0:
            if self._hotseat_strip_proxy_cursor_set:
                p.unsetCursor()
                self._hotseat_strip_proxy_cursor_set = False
            return
        gw = QCursor.pos()
        chip = self._hotseat_strip_chip_at_global(w, gw)
        if chip is None:
            if self._hotseat_strip_proxy_cursor_set:
                p.unsetCursor()
                self._hotseat_strip_proxy_cursor_set = False
            return
        if _hotseat_chip_drag_label_movable(chip, self._gameplay_sidebar):
            p.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            p.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self._hotseat_strip_proxy_cursor_set = True

    def sync_hotseat_qpick_proxy_item_cursor(self) -> None:
        """Apply widget cursors on the question/search picker ``QGraphicsProxyWidget``."""
        p = self._qpick_proxy
        if p is None:
            return
        if self._hotseat_bank_carry is not None:
            if self._hotseat_qpick_proxy_cursor_set:
                p.unsetCursor()
                self._hotseat_qpick_proxy_cursor_set = False
            return
        w = p.widget()
        if w is None:
            return
        lf = w.mapFromGlobal(QCursor.pos())
        fw, fh = w.width(), w.height()
        if fw <= 0 or fh <= 0 or not (
            0 <= lf.x() < fw and 0 <= lf.y() < fh
        ):
            if self._hotseat_qpick_proxy_cursor_set:
                p.unsetCursor()
                self._hotseat_qpick_proxy_cursor_set = False
            return
        child = w.childAt(lf)
        target: QWidget = child if child is not None else w
        p.setCursor(target.cursor())
        self._hotseat_qpick_proxy_cursor_set = True

    def sync_hotseat_embedded_proxy_cursors(self) -> None:
        """Sync cursors on in-scene embedded widgets (child cursors do not propagate to the proxy item)."""
        self.sync_hotseat_map_strip_proxy_item_cursor()
        self.sync_hotseat_qpick_proxy_item_cursor()

    def terrain_scene_rect_excluding_ui_proxies(self) -> QRectF:
        """Bounding rect of map/terrain only (excludes question-picker and map chip strip proxies)."""
        skip: set[int] = set()
        qpx = self._qpick_proxy
        if qpx is not None:
            skip.add(id(qpx))
        msp = self._map_chip_strip_proxy
        if msp is not None:
            skip.add(id(msp))
        br = QRectF()
        any_valid = False
        sc = self.scene()
        if sc is None:
            return br
        for it in sc.items():
            if id(it) in skip:
                continue
            r = it.sceneBoundingRect()
            if r.isValid():
                br = r if not any_valid else br.united(r)
                any_valid = True
        return br.normalized() if any_valid else QRectF()

    def set_hotseat_board_builder(self, bb: BoardBuilder | None) -> None:
        if bb is None:
            self.cancel_hotseat_bank_chip_carry()
        prev = self._hotseat_board_builder
        if prev is not None and prev.canvas is not None:
            setattr(prev.canvas, "_on_chip_dropped_hotseat_home", None)
        self._hotseat_board_builder = bb
        if bb is not None and bb.canvas is not None:
            bb.canvas._on_chip_dropped_hotseat_home = self._on_hotseat_chip_dropped_home

    def undo_hotseat_additional_sharing_square(self) -> None:
        """Return the current turn's additional-sharing square chip to its home (no other chips affected)."""
        bb = self._hotseat_board_builder
        if bb is None or bb.canvas is None:
            return
        canvas = bb.canvas
        for ch in list(canvas.chip_slot.keys()):
            if getattr(ch, "_hotseat_from_sharing_bank", False) and getattr(ch, "shape_kind", None) == "square":
                try:
                    canvas.release_chip(ch)
                    ch._apply_bank_home_after_release_off_hex()
                    canvas.notify_undo_checkpoint()
                except Exception:
                    pass
                break

    def _clear_question_picker_state(self) -> None:
        """Drop chip/overlay references; remove overlay widget (scene may be cleared next)."""
        chip = self._qpick_chip
        self._qpick_chip = None
        if chip is not None:
            chip.set_position_change_notify(None)
        self._destroy_question_picker_overlay()

    def _on_hotseat_chip_dropped_home(self, chip: ChipItem) -> None:
        """Chip returned to the map chip strip — close meeple bar if open, then remove from scene.

        The strip label will create a fresh ChipItem on the next drag; leaving the
        old item in the scene would produce a duplicate.
        """
        if self._qpick_chip is chip:
            self._remove_question_picker_overlay_only()
        sb = self._gameplay_sidebar
        if sb is not None and getattr(chip, "_hotseat_from_sharing_bank", False):
            sb._hotseat_sharing_square_used = False
            sb.sync_hotseat_sharing_bank_visibility()
        sc = chip.scene()
        if sc is not None:
            sc.removeItem(chip)
        self._notify_end_turn_eligibility_changed()

    def _destroy_question_picker_overlay(self) -> None:
        for ch_item, z in self._qpick_dimmed_chips:
            ch_item.setZValue(z)
        self._qpick_dimmed_chips = []

        if self._qpick_proxy is not None and self._hotseat_qpick_proxy_cursor_set:
            self._qpick_proxy.unsetCursor()
            self._hotseat_qpick_proxy_cursor_set = False

        proxy = self._qpick_proxy
        ov = self._qpick_overlay
        self._qpick_proxy = None
        self._qpick_overlay = None
        if proxy is not None:
            proxy.setWidget(None)
            if proxy.scene() is not None:
                proxy.scene().removeItem(proxy)
            proxy.deleteLater()
        if ov is not None:
            ov.hide()
            ov.deleteLater()
        self.viewport().unsetCursor()

    def _dismiss_question_target_picker(self, cancel_chip: bool) -> None:
        """Remove the picker UI; optionally return the gray chip to the panel."""
        chip = self._qpick_chip
        self._qpick_chip = None
        if chip is not None:
            chip.set_position_change_notify(None)
        self._destroy_question_picker_overlay()
        bb = self._hotseat_board_builder
        if cancel_chip and chip is not None and bb is not None and bb.canvas is not None:
            bb.canvas.release_chip(chip)
            sc = chip.scene()
            if sc is not None:
                sc.removeItem(chip)
            bb.canvas.notify_undo_checkpoint()
        elif chip is not None:
            chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        sb = self._gameplay_sidebar
        if sb is not None:
            sb.sync_hotseat_question_bank_visibility()
            sb.sync_hotseat_search_bank_visibility()
        self._notify_end_turn_eligibility_changed()

    def _remove_question_picker_overlay_only(self) -> None:
        chip = self._qpick_chip
        self._qpick_chip = None
        if chip is not None:
            chip.set_position_change_notify(None)
        self._destroy_question_picker_overlay()
        self._notify_end_turn_eligibility_changed()

    def _place_question_picker_overlay(self) -> None:
        """Center the circular picker on the gray chip."""
        proxy = self._qpick_proxy
        chip = self._qpick_chip
        if proxy is None or chip is None or chip.scene() is None:
            return
        chip_center = chip.mapToScene(QPointF(0, 0))
        w = proxy.widget()
        if w is None:
            return
        proxy.setPos(
            chip_center.x() - w.width() / 2.0,
            chip_center.y() - w.height() / 2.0,
        )

    def _open_question_target_picker(self, chip: ChipItem) -> None:
        self._dismiss_question_target_picker(cancel_chip=True)
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or sc is None:
            return
        others = sb.other_player_slots()
        if not others:
            return

        disabled_players: set[int] = set()
        try:
            slot0 = bb.canvas.chip_slot.get(chip)
            if slot0 is not None:
                hex_slot0 = (slot0[0], slot0[1], slot0[2])
                occ0 = [
                    c
                    for c in bb.canvas.chip_occupied.get(hex_slot0, [])
                    if c is not chip
                ]
                circle_colors = {
                    (getattr(c, "fill_color", "") or "").lower()
                    for c in occ0
                    if getattr(c, "shape_kind", None) == "circle"
                    and not getattr(c, "_question_mark", False)
                }
                for pl_idx, cname in others:
                    hx0 = get_player_color_hex(cname).lower()
                    if hx0 in circle_colors:
                        disabled_players.add(pl_idx)
        except Exception:
            disabled_players = set()

        def do_cancel() -> None:
            self._dismiss_question_target_picker(cancel_chip=True)

        def do_ok(answered_player_idx: int, cname: str) -> None:
            hx = get_player_color_hex(cname)
            slot = bb.canvas.chip_slot.get(chip)
            existing: list[ChipItem] = []
            if slot is not None:
                hex_slot = (slot[0], slot[1], slot[2])
                existing = [
                    c
                    for c in bb.canvas.chip_occupied.get(hex_slot, [])
                    if c is not chip
                ]
                if hx.lower() in {(c.fill_color or "").lower() for c in existing}:
                    self._notify_end_turn_eligibility_changed()
                    return
            shape: Literal["circle", "square"] = "circle"
            clue = sb.clue_text_for_player(answered_player_idx)
            ctrl = bb.controller
            if clue and slot is not None and ctrl is not None:
                r, c0, cell_idx = slot
                piece = bb.canvas.occupied.get((r, c0))
                if piece is not None:
                    coords = ctrl.cell_big_coords(piece, cell_idx)
                    if coords is not None:
                        y, x = coords
                        try:
                            grid = compute_all_conditions(
                                ctrl.build_current_map(),
                                advanced_mode=self._hotseat_advanced_mode,
                            )
                            matched = _hotseat_match_clue_to_grid(clue, grid)
                            if matched is not None:
                                shape = (
                                    "circle"
                                    if matched in grid.rules_true_at_hex(y, x)
                                    else "square"
                                )
                        except Exception:
                            pass
            if shape == "square":
                n_square = sum(
                    1 for c in existing if c.shape_kind == "square"
                )
                if n_square >= 1:
                    self._notify_end_turn_eligibility_changed()
                    return
            chip.resolve_hotseat_question(hx, shape_kind=shape)
            chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            chip.setCursor(Qt.CursorShape.OpenHandCursor)
            self._remove_question_picker_overlay_only()
            if slot is not None:
                bb._relayout_hex_figures(slot[0], slot[1], slot[2])
            bb.canvas.notify_undo_checkpoint()
            sb._hotseat_question_used = True
            # Win: all players have circles on this hex after resolving a Question to a circle.
            try:
                if slot is not None and chip.shape_kind == "circle":
                    hex_slot2 = (slot[0], slot[1], slot[2])
                    occ2 = bb.canvas.chip_occupied.get(hex_slot2, [])
                    n_circles = sum(
                        1
                        for c in occ2
                        if getattr(c, "shape_kind", None) == "circle"
                        and not getattr(c, "_question_mark", False)
                    )
                    if n_circles == getattr(sb, "_n", 0):
                        cb = getattr(self, "_hotseat_game_finished_cb", None)
                        if callable(cb):
                            cb(winner_index=getattr(sb, "_turn_index", 0))
            except Exception:
                pass
            resolved_square = chip.shape_kind == "square"
            if resolved_square:
                sb._hotseat_map_strip_sharing_question_row = True
                sb._hotseat_map_strip_sharing_search_row = False
            else:
                sb._hotseat_map_strip_sharing_question_row = False
                sb._hotseat_map_strip_sharing_search_row = False
            sb.sync_hotseat_question_bank_visibility()
            sb.sync_hotseat_search_bank_visibility()
            sb.sync_hotseat_map_strip_sharing_rows()
            sb.sync_hotseat_sharing_bank_visibility()
            sb._schedule_map_chip_strip_layout_bump()
            # Strip height changed (Additional sharing row); refit view so strip proxy
            # geometry matches window coords (otherwise mapFromGlobal/enterEvent miss until
            # some unrelated hover forces layout).
            sb.geometry_needs_update.emit()

        frame = _build_hotseat_question_picker_widget(
            others,
            disabled_players=disabled_players,
            on_cancel=do_cancel,
            on_ok=do_ok,
        )
        frame.setVisible(False)
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(frame)
        proxy.setZValue(_HOTSEAT_QPICK_PROXY_Z)
        sc.addItem(proxy)
        self._qpick_proxy = proxy
        self._qpick_overlay = frame
        self._qpick_chip = chip

        self._qpick_dimmed_chips = []
        for ch_item in list(bb.canvas.chip_slot.keys()):
            if ch_item is not chip:
                self._qpick_dimmed_chips.append((ch_item, ch_item.zValue()))
                ch_item.setZValue(0)
        chip.set_position_change_notify(self._place_question_picker_overlay)
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        chip.setCursor(Qt.CursorShape.OpenHandCursor)
        self._place_question_picker_overlay()
        frame.setVisible(True)
        self._notify_end_turn_eligibility_changed()

    def _open_search_picker(self, chip: ChipItem) -> None:
        """Show a Cancel/OK overlay on the search chip; OK triggers the full search sequence."""
        self._dismiss_question_target_picker(cancel_chip=True)
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or sc is None:
            return

        def do_cancel() -> None:
            self._dismiss_question_target_picker(cancel_chip=True)

        def do_ok() -> None:
            slot = bb.canvas.chip_slot.get(chip)
            if slot is None:
                self._notify_end_turn_eligibility_changed()
                return
            r, c0, cell_idx = slot
            piece = bb.canvas.occupied.get((r, c0))
            ctrl = bb.controller
            if piece is None or ctrl is None:
                self._notify_end_turn_eligibility_changed()
                return
            coords = ctrl.cell_big_coords(piece, cell_idx)
            if coords is None:
                self._notify_end_turn_eligibility_changed()
                return
            y, x = coords
            try:
                grid = compute_all_conditions(
                    ctrl.build_current_map(),
                    advanced_mode=self._hotseat_advanced_mode,
                )
            except Exception:
                self._notify_end_turn_eligibility_changed()
                return

            chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            chip.setCursor(Qt.CursorShape.OpenHandCursor)
            self._remove_question_picker_overlay_only()

            clockwise = sb.other_player_slots_clockwise()
            placed_square = False
            already_circle_colors: set[str] = set()
            try:
                hex_slot0 = (r, c0, cell_idx)
                occ0 = bb.canvas.chip_occupied.get(hex_slot0, [])
                already_circle_colors = {
                    (getattr(c, "fill_color", "") or "").lower()
                    for c in occ0
                    if getattr(c, "shape_kind", None) == "circle"
                    and not getattr(c, "_question_mark", False)
                }
            except Exception:
                already_circle_colors = set()
            for pl_idx, cname in clockwise:
                hx = get_player_color_hex(cname)
                if hx.lower() in already_circle_colors:
                    continue
                clue = sb.clue_text_for_player(pl_idx)
                matched = _hotseat_match_clue_to_grid(clue, grid)
                if matched is None:
                    continue
                is_true = matched in grid.rules_true_at_hex(y, x)
                shape: Literal["circle", "square"] = "circle" if is_true else "square"
                if shape == "square":
                    placed_square = True
                new_chip = ChipItem(shape, hx)
                new_chip.set_canvas(bb.canvas)
                new_chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                new_chip.setCursor(Qt.CursorShape.OpenHandCursor)
                view = self

                def _make_home(kind: str, _sb: Any = sb, _v: Any = view) -> Callable[[], QPointF]:
                    def _home() -> QPointF:
                        return _sb.hotseat_chip_home_scene(_v, kind)
                    return _home

                new_chip.set_hotseat_home_resolver(_make_home("search"))
                new_chip.setZValue(5000)
                new_chip.setScale(MARKER_SCALE_CANVAS)
                sc.addItem(new_chip)
                bb.canvas.assign_chip(new_chip, r, c0, cell_idx)
                bb._relayout_hex_figures(r, c0, cell_idx)
                if shape == "circle":
                    already_circle_colors.add(hx.lower())
                if not is_true:
                    break

            bb._relayout_hex_figures(r, c0, cell_idx)
            bb.canvas.notify_undo_checkpoint()
            sb._hotseat_search_used = True
            # Win: all players have circles on this hex after Search.
            try:
                hex_slot = (r, c0, cell_idx)
                occ = bb.canvas.chip_occupied.get(hex_slot, [])
                n_circles = sum(
                    1
                    for c in occ
                    if getattr(c, "shape_kind", None) == "circle"
                    and not getattr(c, "_question_mark", False)
                )
                if n_circles == getattr(sb, "_n", 0):
                    cb = getattr(self, "_hotseat_game_finished_cb", None)
                    if callable(cb):
                        cb(winner_index=getattr(sb, "_turn_index", 0))
            except Exception:
                pass
            if placed_square:
                sb._hotseat_map_strip_sharing_search_row = True
                sb._hotseat_map_strip_sharing_question_row = False
            else:
                sb._hotseat_map_strip_sharing_search_row = False
                sb._hotseat_map_strip_sharing_question_row = False
            sb.sync_hotseat_search_bank_visibility()
            sb.sync_hotseat_question_bank_visibility()
            sb.sync_hotseat_map_strip_sharing_rows()
            sb.sync_hotseat_sharing_bank_visibility()
            if placed_square:
                sb._schedule_map_chip_strip_layout_bump()
            sb.geometry_needs_update.emit()

        frame = _build_hotseat_search_picker_widget(
            on_cancel=do_cancel, on_ok=do_ok
        )
        frame.setVisible(False)
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(frame)
        proxy.setZValue(_HOTSEAT_QPICK_PROXY_Z)
        sc.addItem(proxy)
        self._qpick_proxy = proxy
        self._qpick_overlay = frame
        self._qpick_chip = chip

        self._qpick_dimmed_chips = []
        for ch_item in list(bb.canvas.chip_slot.keys()):
            if ch_item is not chip:
                self._qpick_dimmed_chips.append((ch_item, ch_item.zValue()))
                ch_item.setZValue(0)
        chip.set_position_change_notify(self._place_question_picker_overlay)
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        chip.setCursor(Qt.CursorShape.OpenHandCursor)
        self._place_question_picker_overlay()
        frame.setVisible(True)
        self._notify_end_turn_eligibility_changed()

    def set_gameplay_sidebar(self, sidebar: HotseatGameplaySidebar) -> None:
        self._gameplay_sidebar = sidebar
        sidebar.hotseat_board_view = self

    def detach_map_chip_strip_proxy(self) -> None:
        p = self._map_chip_strip_proxy
        self._map_chip_strip_proxy = None
        if p is not None and self._hotseat_strip_proxy_cursor_set:
            p.unsetCursor()
            self._hotseat_strip_proxy_cursor_set = False
        if p is None:
            return
        w = p.widget()
        p.setWidget(None)
        sb = self._gameplay_sidebar
        if w is not None and sb is not None:
            w.setParent(sb)
            w.setMinimumWidth(0)
            w.setMaximumWidth(_QWIDGETSIZE_MAX)
        if p.scene() is not None:
            p.scene().removeItem(p)
        p.deleteLater()

    def set_map_chip_strip_proxy_widget(self, w: QWidget | None) -> None:
        self.detach_map_chip_strip_proxy()
        if w is None:
            return
        sc = self.scene()
        if sc is None:
            return
        w.setParent(None)
        w.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        p = QGraphicsProxyWidget()
        p.setWidget(w)
        p.setAcceptHoverEvents(True)
        p.setZValue(_HOTSEAT_MAP_CHIP_STRIP_PROXY_Z)
        p.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        sc.addItem(p)
        self._map_chip_strip_proxy = p
        w.show()
        self.layout_map_chip_strip_proxy()

    def layout_map_chip_strip_proxy(self) -> None:
        p = self._map_chip_strip_proxy
        if p is None:
            return
        w = p.widget()
        if w is None:
            return
        w.adjustSize()
        bb = self._hotseat_board_builder
        canvas_rect = QRectF()
        if bb is not None and getattr(bb, "canvas", None) is not None:
            cr = bb.canvas.rect
            if cr.isValid():
                canvas_rect = QRectF(cr)
        if not canvas_rect.isValid():
            t = self.terrain_scene_rect_excluding_ui_proxies()
            if t.isValid():
                canvas_rect = t
        if not canvas_rect.isValid():
            return
        cw = int(round(canvas_rect.width()))
        if cw > 0:
            w.setFixedWidth(cw)
        w.adjustSize()
        x = canvas_rect.left()
        y = canvas_rect.bottom() + _HOTSEAT_MAP_CHIP_STRIP_GAP_SCENE
        p.setPos(x, y)
        # Strip moved/resized without a mouse move: refresh proxy cursors (child cursors do not propagate).
        self.sync_hotseat_embedded_proxy_cursors()

    def hotseat_map_strip_reserve_viewport_px(self) -> int:
        """Bottom band of the viewport reserved for the map chip strip (0 if none)."""
        return self._map_strip_viewport_reserve_px()

    def _map_strip_viewport_reserve_px(self) -> int:
        def _reserve_from_height(h: int) -> int:
            if h < 2:
                return 0
            return (
                int(math.ceil(_HOTSEAT_MAP_CHIP_STRIP_GAP_SCENE))
                + int(h)
                + _HOTSEAT_MAP_CHIP_STRIP_VIEWPORT_GAP_PX
            )

        p = self._map_chip_strip_proxy
        if p is not None:
            w = p.widget()
            if w is None or not w.isVisible():
                return 0
            h = w.height()
            if h < 2:
                h = w.sizeHint().height()
            return _reserve_from_height(h)

        sb = self._gameplay_sidebar
        if sb is None:
            return 0
        ms = sb.map_chip_strip
        if ms is None:
            return 0
        bb = self._hotseat_board_builder
        canvas_rect = QRectF()
        if bb is not None and getattr(bb, "canvas", None) is not None:
            cr = bb.canvas.rect
            if cr.isValid():
                canvas_rect = QRectF(cr)
        if not canvas_rect.isValid():
            t = self.terrain_scene_rect_excluding_ui_proxies()
            if t.isValid():
                canvas_rect = t
        cw = int(round(canvas_rect.width())) if canvas_rect.isValid() else 0
        if cw > 0:
            ms.setFixedWidth(cw)
        ms.adjustSize()
        h = max(ms.height(), ms.sizeHint().height())
        return _reserve_from_height(h)

    def hotseat_canvas_fit_rect(self) -> QRectF | None:
        """Puzzle canvas rect in scene coords (terrain only; excludes tray and UI proxies)."""
        bb = self._hotseat_board_builder
        if bb is not None and getattr(bb, "canvas", None) is not None:
            cr = bb.canvas.rect
            if cr.isValid():
                return QRectF(cr)
        t = self.terrain_scene_rect_excluding_ui_proxies()
        return QRectF(t) if t.isValid() else None

    def set_terrain_fit_rect(self, rect: QRectF | None) -> None:
        """Store the terrain bounding rect used by ``_apply_fit`` on every resize."""
        self._terrain_fit_rect = rect
        self._apply_fit()

    def _apply_fit(self) -> None:
        """1:1 map scale (scene units = viewport pixels).

        Inset by ``_HOTSEAT_VIEW_MAP_INSET_PX`` on each side of the viewport, then center the
        canvas horizontally. Viewport margins (see ``__init__``) keep the scene clear of the
        QGraphicsView QSS border so the canvas stroke is not overlapped by the outer frame.

        The chip strip uses ``ItemIgnoresTransformations`` and sits in scene space below the canvas.
        """
        r = self._terrain_fit_rect
        if r is None or not r.isValid():
            return
        vp = self.viewport()
        if vp is None or vp.width() < 2 or vp.height() < 2:
            return
        self.resetTransform()
        d = float(_HOTSEAT_VIEW_MAP_INSET_PX)
        cw = r.width()
        vw = float(vp.width())
        inner_w = max(1.0, vw- 2.0 * d)
        if inner_w >= cw:
            ox = d + (inner_w - cw) / 2.0
        else:
            ox = 0
        self.setTransform(QTransform.fromTranslate(ox - r.left(), -r.top()))
        self._sync_hotseat_scene_rect()

    def _sync_hotseat_scene_rect(self) -> None:
        """Match ``BoardView.resizeEvent`` logic, but only after the view transform is current.

        ``BoardView`` runs ``mapToScene(viewport)`` *before* our ``_apply_fit`` runs, so the
        scene rect was computed with a stale transform and could clip the map (top/left cut off).
        """
        if self.scene() is None:
            return
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        br = self.scene().itemsBoundingRect()
        if br.isValid():
            self.scene().setSceneRect(visible.united(br))
        else:
            self.scene().setSceneRect(visible if visible.isValid() else QRectF())

    def resizeEvent(self, event: QResizeEvent) -> None:
        # Call QGraphicsView only — skip BoardView.resizeEvent so we don't set sceneRect
        # before _apply_fit updates the transform (see _sync_hotseat_scene_rect).
        QGraphicsView.resizeEvent(self, event)
        self._apply_fit()
        self.layout_map_chip_strip_proxy()
        self._place_question_picker_overlay()
        if self._on_resize:
            self._on_resize()

    def showEvent(self, event: QShowEvent) -> None:
        QGraphicsView.showEvent(self, event)
        self._apply_fit()
        self.layout_map_chip_strip_proxy()
        self._place_question_picker_overlay()

    def viewportEvent(self, event: QEvent) -> bool:
        """Optional ``QDrag``/drop path (e.g. external sources); bank chips use grab-based carry."""
        if getattr(self, "_hotseat_board_builder", None) is not None:
            if isinstance(event, QDragEnterEvent):
                if event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME):
                    event.acceptProposedAction()
                    return True
            if isinstance(event, QDragMoveEvent):
                if event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME):
                    event.acceptProposedAction()
                    return True
            if isinstance(event, QDropEvent):
                if event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME):
                    self.dropEvent(event)
                    return True
        return super().viewportEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._hotseat_bank_carry is not None
            and event.button() == Qt.MouseButton.RightButton
        ):
            self.cancel_hotseat_bank_chip_carry()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._hotseat_bank_carry is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._finish_hotseat_bank_carry_at_global(
                event.globalPosition().toPoint()
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _scene_pos_from_global(self, global_pt: QPoint) -> QPointF:
        vp = self.viewport()
        return self.mapToScene(vp.mapFromGlobal(global_pt))

    def _scene_pos_from_drop_event(self, event: QDropEvent) -> QPointF:
        """Map drop point to scene. Do not use ``globalPosition()`` — some PySide6 ``QDropEvent`` bindings lack it."""
        gpm = getattr(event, "globalPos", None)
        if callable(gpm):
            gpt = gpm()
            if isinstance(gpt, QPoint):
                return self._scene_pos_from_global(gpt)
            return self._scene_pos_from_global(QPoint(int(gpt.x()), int(gpt.y())))
        pos_m = getattr(event, "position", None)
        if callable(pos_m):
            pf = pos_m()
            p = pf.toPoint()
        else:
            p = event.pos()
        vp_pt = self.viewport().mapFrom(self, p)
        return self.mapToScene(vp_pt)

    def _try_place_hotseat_bank_chip(
        self, shape: str, color_hex: str, scene_pos: QPointF
    ) -> bool:
        try:
            bb = self._hotseat_board_builder
            if bb is None or bb.canvas is None:
                return False
            if shape not in ("question", "circle", "square"):
                return False
            sc = self.scene()
            if sc is None:
                return False
            piece, idx, snap_center = find_hex_under_point(scene_pos, sc.items(scene_pos))
            if piece is None:
                return False
            slot = bb.canvas.item_slot.get(piece)
            if slot is None:
                return False
            # Hotseat rule enforcement:
            # - Search (circle) must be placed on a hex that fits the current player's clue.
            # - Additional sharing (square) must be placed on a hex that does NOT fit the current player's clue.
            # If we can't evaluate the clue for any reason, do not block placement.
            sb = self._gameplay_sidebar
            ctrl = bb.controller
            if sb is not None and ctrl is not None and shape in ("circle", "square"):
                coords = ctrl.cell_big_coords(piece, idx)
                if coords is not None:
                    y, x = coords
                    try:
                        clue = sb.clue_text_for_player(getattr(sb, "_turn_index", 0))
                        if clue:
                            grid = compute_all_conditions(
                                ctrl.build_current_map(),
                                advanced_mode=self._hotseat_advanced_mode,
                            )
                            matched = _hotseat_match_clue_to_grid(clue, grid)
                            if matched is not None:
                                fits = matched in grid.rules_true_at_hex(y, x)
                                if shape == "circle" and not fits:
                                    return False
                                if shape == "square" and fits:
                                    return False
                    except Exception:
                        pass
            hex_slot = (slot[0], slot[1], idx)
            existing = bb.canvas.chip_occupied.get(hex_slot, [])
            # Hotseat rule: can't place a gray (?) or search circle on a hex that already has a square.
            if shape in ("question", "circle") and any(
                getattr(c, "shape_kind", None) == "square" for c in existing
            ):
                return False
            n_square = sum(1 for c in existing if c.shape_kind == "square")
            colors_used = {(c.fill_color or "").lower() for c in existing}
            would_add_square = 1 if shape == "square" else 0
            total_after = len(existing) + 1
            squares_after = n_square + would_add_square
            ch = color_hex.lower()
            # Hotseat: allow Search to target a hex where this color already has a circle.
            # Instead of placing a duplicate chip, reuse the existing circle and open the Search picker.
            if shape == "circle" and ch in colors_used:
                try:
                    existing_circle = next(
                        c
                        for c in existing
                        if getattr(c, "shape_kind", None) == "circle"
                        and not getattr(c, "_question_mark", False)
                        and (getattr(c, "fill_color", "") or "").lower() == ch
                    )
                    self._open_search_picker(existing_circle)
                    return True
                except StopIteration:
                    pass
            valid = (
                total_after <= 4
                and squares_after <= 1
                and ch not in colors_used
            )
            if not valid:
                return False
            if shape == "square" and sb is not None:
                if not sb.may_drag_sharing_chip_from_bank():
                    return False
            if shape == "question":
                chip = ChipItem("circle", color_hex, question_mark=True)
                home_kind: Literal["question", "search", "share"] = "question"
            else:
                chip = ChipItem(shape, color_hex)
                home_kind = "search" if shape == "circle" else "share"
            if shape == "square":
                chip._hotseat_from_sharing_bank = True
            chip.set_canvas(bb.canvas)
            # Question/Search chips: fixed after placement (existing behavior).
            # Additional sharing square: keep movable so the player can reposition or send it home.
            if shape != "square":
                chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                chip.setCursor(Qt.CursorShape.ArrowCursor)
            if sb is not None:
                view = self

                def _home() -> QPointF:
                    return sb.hotseat_chip_home_scene(view, home_kind)

                chip.set_hotseat_home_resolver(_home)
            else:
                chip.set_home_pos(QPointF(0, 0))
            chip.setZValue(5000)
            chip.setPos(snap_center)
            chip.setScale(MARKER_SCALE_CANVAS)
            sc.addItem(chip)
            bb.canvas.assign_chip(chip, slot[0], slot[1], idx)
            bb.canvas.notify_undo_checkpoint()
            if shape == "question":
                self._open_question_target_picker(chip)
            elif shape == "circle":
                self._open_search_picker(chip)
            elif shape == "square" and sb is not None:
                sb._hotseat_sharing_square_used = True
                sb.sync_hotseat_sharing_bank_visibility()
            vp = self.viewport()
            if vp is not None:
                vp.update()
            return True
        finally:
            self._notify_end_turn_eligibility_changed()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        # QGraphicsView can emit "leave before enter" at viewport edges; skip the view's DnD bookkeeping.
        if (
            self._hotseat_board_builder is not None
            and event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME)
        ):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if (
            self._hotseat_board_builder is not None
            and event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME)
        ):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(_HOTSEAT_CHIP_MIME):
            super().dropEvent(event)
            return
        try:
            raw = bytes(event.mimeData().data(_HOTSEAT_CHIP_MIME)).decode("utf-8")
            parts = raw.split("|", 2)
            if len(parts) < 2:
                event.ignore()
                return
            shape, color_hex = parts[0], parts[1]
            if shape not in ("question", "circle", "square"):
                event.ignore()
                return
        except (UnicodeDecodeError, ValueError):
            event.ignore()
            return
        scene_pos = self._scene_pos_from_drop_event(event)
        if self._try_place_hotseat_bank_chip(shape, color_hex, scene_pos):
            event.acceptProposedAction()
            vp = self.viewport()
            if vp is not None:
                vp.update()
        else:
            event.ignore()

