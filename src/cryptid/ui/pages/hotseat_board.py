"""Dedicated Play Hotseat board: map + turn / current-player panels."""
from __future__ import annotations

import math
import os
import random
import time
from enum import Enum, auto
from typing import Any, Callable, Literal

from PySide6.QtCore import (
    QEvent,
    QEventLoop,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QTimer,
    Signal,
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
    QFont,
    QFontMetrics,
    QMouseEvent,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QResizeEvent,
    QShowEvent,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QScrollArea,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from board.board_builder import BoardBuilder
from board.geometry import axial_to_pixel
from board.board_view import BoardView
from board.markers import MARKER_SCALE_CANVAS, MARKER_SCALE_HOME, MARKER_Z_BANK, ChipItem
from board.pieces import find_hex_under_point
from settings.config import CLUES_ICONS_DIR, HEX_SIZE, ICON_CLUE, ICON_HELP, MARKER_SIZE
from settings.theme import CANVAS_RADIUS

# Set CRYPTID_DEBUG_HOTSEAT_STRIP_CURSOR=1 to print strip proxy cursor decisions (throttled).
_HOTSEAT_DEBUG_STRIP_CURSOR = os.environ.get(
    "CRYPTID_DEBUG_HOTSEAT_STRIP_CURSOR", ""
).lower() in ("1", "true", "yes")
from settings.strings import (
    END_HOTSEAT_CONFIRM_MSG,
    END_HOTSEAT_CONFIRM_TITLE,
    HOTSEAT_END_TURN_DISABLED_TOOLTIP,
    TOOLTIP_UNDO,
)
from logic.clue_grid import get_slot_for_clue_label
from logic.clues import get_clues_for_map
from logic.conditions import all_condition_labels, compute_all_conditions
from logic.hints import filter_clue_labels_by_hint, get_hint_description, get_hint_id_for_map
from ui.shared.widgets import HoverTooltipManager
from ui.shared.widgets.player_colors import (
    PLAYER_COLORS,
    get_player_circle_chip_pixmap,
    get_player_color_hex,
    get_player_meeple_pixmap,
    get_player_question_chip_pixmap,
    get_player_square_chip_pixmap,
)

# Match map canvas: MARKER_SCALE_HOME × 1.0 (same as MARKER_SCALE_CANVAS multiplier on the board).
_HOTSEAT_VIEW_SCALE = 1.0
_HOTSEAT_CHIP_HOME_PX = int(
    round(MARKER_SIZE * 2 * MARKER_SCALE_HOME * _HOTSEAT_VIEW_SCALE)
)
# Map chip strip uses the same multiplier as the sidebar bank.
_HOTSEAT_MAP_CHIP_STRIP_VIEW_SCALE = 1.0
_HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX = int(
    round(MARKER_SIZE * 2 * MARKER_SCALE_HOME * _HOTSEAT_MAP_CHIP_STRIP_VIEW_SCALE)
)
_HOTSEAT_CHIP_MIME = "application/x-cryptid-hotseat-chip"
_HOTSEAT_QPICK_PROXY_Z = 16000
# Single Question-row chip: solid neutral gray on the map (matches unknown-player chip tone).
_HOTSEAT_QUESTION_CHIP_HEX = "#98a4ac"
# Circular meeple-picker: distance from chip center to button center (scene px).
_HOTSEAT_QPICK_RING_RADIUS = 40
_HOTSEAT_QPICK_MEEPLE_ICON_PX = 29
_HOTSEAT_QPICK_MEEPLE_BTN_PX = 36
_HOTSEAT_QPICK_ACTION_ICON_PX = 29
# Map chip strip: scene proxy, fixed on-screen size (ItemIgnoresTransformations); below question picker in Z.
_HOTSEAT_MAP_CHIP_STRIP_PROXY_Z = 12000
_HOTSEAT_MAP_CHIP_STRIP_GAP_SCENE = 8
# Padding below the strip inside the viewport (px); too small clips content (proxy / DPI).
_HOTSEAT_MAP_CHIP_STRIP_VIEWPORT_GAP_PX = 16
# Padding inside the viewport when centering the canvas (scene px at 1:1); avoids the canvas
# rounded-rect stroke sitting on the last pixel beside the viewport edge.
_HOTSEAT_VIEW_MAP_INSET_PX = 8
# Margins between the QGraphicsView widget edge (incl. QSS border) and the viewport; keeps the
# scene from painting under the outer frame so the canvas border is not overlapped by the view border.
_HOTSEAT_VIEW_VIEWPORT_FRAME_MARGIN_PX = 0

_QWIDGETSIZE_MAX = 16777215


def _hotseat_color_name_from_hex(color_hex: str) -> str:
    h = (color_hex or "").strip().lower()
    for name, hx in PLAYER_COLORS:
        if hx.lower() == h:
            return name
    return ""


def _hotseat_bank_carry_preview_pixmap(shape: str, color_hex: str) -> QPixmap:
    px = _HOTSEAT_CHIP_HOME_PX
    if shape == "question":
        return get_player_question_chip_pixmap("", px)
    cname = _hotseat_color_name_from_hex(color_hex)
    if shape == "circle":
        return get_player_circle_chip_pixmap(cname, px)
    return get_player_square_chip_pixmap(cname, px)


def _hotseat_match_clue_to_grid(clue: str, grid: Any) -> str | None:
    """Resolve book clue text to a ``ConditionsGrid`` label (exact, strip, then case-fold)."""
    c = (clue or "").strip()
    if not c:
        return None
    if c in grid:
        return c
    labels = getattr(grid, "labels", None)
    if not labels:
        return None
    for lab in labels:
        if lab.strip() == c:
            return lab
    c_low = c.lower()
    for lab in labels:
        if lab.strip().lower() == c_low:
            return lab
    return None

# Turn-status dots (Active / Waiting / Done)
_STATUS_BLUE = "#3498db"
_STATUS_GREEN = "#2ecc71"
_TURN_STATUS_DOT_PX = 16
_HISTORY_CHIP_PULSE_MS = 2000
_HISTORY_DIM_Z = 11000.0
# Above the dim overlay, below the map chip strip proxy (12000).
_HISTORY_CHIP_FOCUS_Z = 11500.0
# Black overlay alpha ≈ dim map to ~45–50% perceived brightness.
_HISTORY_DIM_ALPHA = 0.52
_POSSIBLE_CLUE_ICON_PX = 32
# Fixed columns so advanced (48) / basic (23) icons wrap into rows in the sidebar.
_POSSIBLE_CLUE_COLS = 16

# Cached clue-slot pixmaps for the Possible clues panel (slot -> pixmap).
_HOTSEAT_CLUE_ICON_CACHE: dict[int, QPixmap] | None = None


def _load_hotseat_clue_icon_pixmaps() -> dict[int, QPixmap]:
    global _HOTSEAT_CLUE_ICON_CACHE
    if _HOTSEAT_CLUE_ICON_CACHE is not None:
        return _HOTSEAT_CLUE_ICON_CACHE
    result: dict[int, QPixmap] = {}
    if CLUES_ICONS_DIR.is_dir():
        for f in CLUES_ICONS_DIR.iterdir():
            if f.suffix.lower() not in (".svg", ".png"):
                continue
            stem = f.stem
            if "_" not in stem:
                continue
            try:
                n = int(stem.split("_", 1)[0])
            except ValueError:
                continue
            pix = QPixmap(str(f))
            if not pix.isNull():
                result[n] = pix.scaled(
                    _POSSIBLE_CLUE_ICON_PX,
                    _POSSIBLE_CLUE_ICON_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
    _HOTSEAT_CLUE_ICON_CACHE = result
    return result


def _hotseat_default_clue_pixmap() -> QPixmap:
    if not ICON_CLUE.exists():
        return QPixmap()
    pix = QPixmap(str(ICON_CLUE))
    if pix.isNull():
        return pix
    return pix.scaled(
        _POSSIBLE_CLUE_ICON_PX,
        _POSSIBLE_CLUE_ICON_PX,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# shape_kind, color_hex, row, col, cell_idx
HistoryChipRef = tuple[str, str, int, int, int]


class _HistoryChipIconLabel(QLabel):
    """Clickable chip thumbnail in the turn-history table."""

    clicked = Signal(object)

    def __init__(
        self, payload: HistoryChipRef, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._payload = payload
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._payload)
            event.accept()
            return
        super().mousePressEvent(event)


class _FlowLayout(QLayout):
    """Left-to-right wrapping layout (turn-order chips)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        h_spacing: int = 6,
        v_spacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _horizontal_spacing(self) -> int:
        return self._h_spacing

    def _vertical_spacing(self) -> int:
        return self._v_spacing

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_h = 0
        space_x = self._horizontal_spacing()
        space_y = self._vertical_spacing()
        for item in self._items:
            wid = item.widget()
            if wid is not None and wid.isHidden():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + space_x
            if line_h > 0 and next_x - space_x > effective.right() + 1 and x > effective.x():
                x = effective.x()
                y = y + line_h + space_y
                next_x = x + hint.width() + space_x
                line_h = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


class _TurnStatus(Enum):
    ACTIVE = auto()
    WAITING = auto()
    DONE = auto()


def _status_dot_pixmap(kind: _TurnStatus, diameter: int = 14) -> QPixmap:
    pix = QPixmap(diameter, diameter)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    blue = QColor(_STATUS_BLUE)
    green = QColor(_STATUS_GREEN)
    r = diameter / 2.0
    cx, cy = r, r
    if kind is _TurnStatus.ACTIVE:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blue))
        p.drawEllipse(1, 1, diameter - 2, diameter - 2)
    elif kind is _TurnStatus.WAITING:
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(blue, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(2, 2, diameter - 4, diameter - 4)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(green))
        p.drawEllipse(1, 1, diameter - 2, diameter - 2)
    p.end()
    return pix


class _HotseatChipDragLabel(QLabel):
    """Bank chip row: after drag threshold, map view grabs mouse and places chip on release (proxy-safe)."""

    def __init__(
        self,
        shape: str,
        color_hex: str,
        parent: QWidget | None = None,
        *,
        hotseat_sidebar: HotseatGameplaySidebar | None = None,
    ) -> None:
        super().__init__(parent)
        self._shape = shape
        self._color_hex = color_hex
        self._hotseat_sidebar_ref = hotseat_sidebar
        self._shadow = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # Center pixmap in label so circle / square chips align on one baseline in a row.
        self.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

    def set_shadow(self, shadow: bool) -> None:
        self._shadow = shadow
        self._apply_cursor()

    def _apply_cursor(self) -> None:
        c = Qt.CursorShape.ArrowCursor if self._shadow else Qt.CursorShape.OpenHandCursor
        self.setCursor(c)

    def _hotseat_sidebar_ancestor(self) -> HotseatGameplaySidebar | None:
        if self._hotseat_sidebar_ref is not None:
            return self._hotseat_sidebar_ref
        w: QWidget | None = self.parentWidget()
        while w is not None:
            if isinstance(w, HotseatGameplaySidebar):
                return w
            w = w.parentWidget()
        return None

    def set_hotseat_chip(self, shape: str, color_hex: str) -> None:
        self._shape = shape
        self._color_hex = color_hex

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._shadow:
                super().mousePressEvent(event)
                return
            sb = self._hotseat_sidebar_ancestor()
            view = sb.hotseat_board_view if sb is not None else None
            if view is not None:
                if self._shape == "question":
                    if sb is not None and not sb.may_drag_question_chip_from_bank():
                        super().mousePressEvent(event)
                        return
                if self._shape == "circle":
                    if sb is not None and not sb.may_drag_search_chip_from_bank():
                        super().mousePressEvent(event)
                        return
                if self._shape == "square":
                    if sb is not None and not sb.may_drag_sharing_chip_from_bank():
                        super().mousePressEvent(event)
                        return
                view.arm_bank_chip_drag(
                    self._shape,
                    self._color_hex,
                    event.globalPosition().toPoint(),
                )
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            sb = self._hotseat_sidebar_ancestor()
            view = sb.hotseat_board_view if sb is not None else None
            if view is not None:
                view.clear_pending_bank_chip_drag()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)


def _build_hotseat_question_picker_widget(
    others: list[tuple[int, str]],
    *,
    disabled_players: set[int] | None = None,
    on_cancel: Callable[[], None],
    on_ok: Callable[[int, str], None],
) -> QFrame:
    """Circular ring of meeple buttons + cancel / OK around the gray chip."""
    n = len(others)
    btn_sz = _HOTSEAT_QPICK_MEEPLE_BTN_PX
    meeple_px = _HOTSEAT_QPICK_MEEPLE_ICON_PX
    action_ic = _HOTSEAT_QPICK_ACTION_ICON_PX
    R = _HOTSEAT_QPICK_RING_RADIUS
    widget_sz = 2 * (R + btn_sz // 2) + 4
    cx = widget_sz / 2.0
    cy = widget_sz / 2.0

    frame = QFrame()
    frame.setObjectName("hotseatQuestionPickRing")
    frame.setFixedSize(widget_sz, widget_sz)
    frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    frame.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    frame.setMouseTracking(True)
    frame.setCursor(Qt.CursorShape.OpenHandCursor)
    frame.setStyleSheet(
        "QFrame#hotseatQuestionPickRing { background: transparent; border: none; }\n"
        "QFrame#hotseatQuestionPickRing QToolButton {"
        "  background: transparent; border: 1px solid transparent;"
        "  border-radius: %dpx; padding: 0px; }\n"
        "QFrame#hotseatQuestionPickRing QToolButton:hover {"
        "  background: rgba(255,255,255,0.5); }\n"
        "QFrame#hotseatQuestionPickRing QToolButton[hotseatDisabled='true']:hover {"
        "  background: transparent; }\n"
        "QFrame#hotseatQuestionPickRing QToolButton:checked {"
        "  background: rgba(255,255,255,0.85);"
        "  border: 1px solid #2f7d77; }"
        % (btn_sz // 2)
    )

    _btn_pol = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    grp = QButtonGroup(frame)
    grp.setExclusive(True)
    btn_PLAYER: dict[QAbstractButton, tuple[int, str]] = {}

    def _pos(angle_rad: float) -> tuple[int, int]:
        """Button top-left for an angle (radians, 0 = top, clockwise)."""
        x = cx + R * math.sin(angle_rad) - btn_sz / 2.0
        y = cy - R * math.cos(angle_rad) - btn_sz / 2.0
        return int(round(x)), int(round(y))

    if n == 1:
        meeple_angles = [0.0]
    else:
        spread = min(math.pi, max(math.pi / 2, (n - 1) * math.radians(50)))
        meeple_angles = [
            -spread / 2 + i * spread / (n - 1) for i in range(n)
        ]

    for i, (pl_idx, cname) in enumerate(others):
        tb = QToolButton(frame)
        tb.setCheckable(True)
        tb.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        tb.setMouseTracking(True)
        tb.setIcon(QIcon(get_player_meeple_pixmap(cname, meeple_px)))
        tb.setIconSize(QSize(meeple_px, meeple_px))
        tb.setFixedSize(btn_sz, btn_sz)
        tb.setSizePolicy(_btn_pol)
        tb.setCursor(Qt.CursorShape.PointingHandCursor)
        if disabled_players is not None and pl_idx in disabled_players:
            # Keep normal visuals, but prevent selection and show default cursor.
            tb.setProperty("hotseatDisabled", "true")
            tb.setCheckable(False)
            tb.setCursor(Qt.CursorShape.ArrowCursor)
        bx, by = _pos(meeple_angles[i])
        tb.move(bx, by)
        grp.addButton(tb)
        btn_PLAYER[tb] = (pl_idx, cname)

    b_ok = QToolButton(frame)
    b_ok.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    b_ok.setMouseTracking(True)
    b_ok.setIcon(QIcon(":/assets/icons/ok_circle.svg"))
    b_ok.setIconSize(QSize(action_ic, action_ic))
    b_ok.setFixedSize(btn_sz, btn_sz)
    b_ok.setSizePolicy(_btn_pol)
    b_ok.setCursor(Qt.CursorShape.ArrowCursor)
    b_ok.setEnabled(False)
    bx, by = _pos(math.radians(145))
    b_ok.move(bx, by)

    def on_meeple_clicked(_btn: QAbstractButton) -> None:
        enabled = grp.checkedButton() is not None
        b_ok.setEnabled(enabled)
        b_ok.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        )
        # Re-polish after enabled-state flips so :hover style is reliable.
        ok_style = b_ok.style()
        ok_style.unpolish(b_ok)
        ok_style.polish(b_ok)
        b_ok.update()

    grp.buttonClicked.connect(on_meeple_clicked)

    b_cancel = QToolButton(frame)
    b_cancel.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    b_cancel.setMouseTracking(True)
    b_cancel.setIcon(QIcon(":/assets/icons/cancel_circle.svg"))
    b_cancel.setIconSize(QSize(action_ic, action_ic))
    b_cancel.setFixedSize(btn_sz, btn_sz)
    b_cancel.setSizePolicy(_btn_pol)
    b_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    b_cancel.clicked.connect(on_cancel)
    bx, by = _pos(math.radians(215))
    b_cancel.move(bx, by)

    def do_ok() -> None:
        b = grp.checkedButton()
        if b is None:
            return
        pl_idx, cname = btn_PLAYER[b]
        on_ok(pl_idx, cname)

    b_ok.clicked.connect(do_ok)
    return frame


def _build_hotseat_search_picker_widget(
    *,
    on_cancel: Callable[[], None],
    on_ok: Callable[[], None],
) -> QFrame:
    """Minimal circular picker with only Cancel + OK for the Search action."""
    btn_sz = _HOTSEAT_QPICK_MEEPLE_BTN_PX
    action_ic = _HOTSEAT_QPICK_ACTION_ICON_PX
    R = _HOTSEAT_QPICK_RING_RADIUS
    widget_sz = 2 * (R + btn_sz // 2) + 4
    cx = widget_sz / 2.0
    cy = widget_sz / 2.0

    frame = QFrame()
    frame.setObjectName("hotseatSearchPickRing")
    frame.setFixedSize(widget_sz, widget_sz)
    frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    frame.setCursor(Qt.CursorShape.OpenHandCursor)
    frame.setStyleSheet(
        "QFrame#hotseatSearchPickRing { background: transparent; border: none; }\n"
        "QFrame#hotseatSearchPickRing QToolButton {"
        "  background: transparent; border: 1px solid transparent;"
        "  border-radius: %dpx; padding: 0px; }\n"
        "QFrame#hotseatSearchPickRing QToolButton:hover {"
        "  background: rgba(255,255,255,0.5); }\n"
        % (btn_sz // 2)
    )

    _btn_pol = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _pos(angle_rad: float) -> tuple[int, int]:
        x = cx + R * math.sin(angle_rad) - btn_sz / 2.0
        y = cy - R * math.cos(angle_rad) - btn_sz / 2.0
        return int(round(x)), int(round(y))

    b_ok = QToolButton(frame)
    b_ok.setIcon(QIcon(":/assets/icons/ok_circle.svg"))
    b_ok.setIconSize(QSize(action_ic, action_ic))
    b_ok.setFixedSize(btn_sz, btn_sz)
    b_ok.setSizePolicy(_btn_pol)
    b_ok.setCursor(Qt.CursorShape.PointingHandCursor)
    bx, by = _pos(math.radians(145))
    b_ok.move(bx, by)

    b_cancel = QToolButton(frame)
    b_cancel.setIcon(QIcon(":/assets/icons/cancel_circle.svg"))
    b_cancel.setIconSize(QSize(action_ic, action_ic))
    b_cancel.setFixedSize(btn_sz, btn_sz)
    b_cancel.setSizePolicy(_btn_pol)
    b_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
    bx, by = _pos(math.radians(215))
    b_cancel.move(bx, by)

    b_ok.clicked.connect(on_ok)
    b_cancel.clicked.connect(on_cancel)
    return frame


class _OrDivider(QWidget):
    """Vertical line with 'OR' in a circle at the vertical center."""

    _LINE_COLOR = "#98a4ac"
    _TEXT_COLOR = "#5a6a72"
    _CIRCLE_R = 14

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        bg_color: str = "#ffffff",
    ) -> None:
        super().__init__(parent)
        self._BG_COLOR = bg_color
        self.setFixedWidth(36)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        r = float(self._CIRCLE_R)
        line_c = QColor(self._LINE_COLOR)
        pen = QPen(line_c, 2.5)
        p.setPen(pen)
        p.drawLine(int(cx), 0, int(cx), int(cy - r))
        p.drawLine(int(cx), int(cy + r), int(cx), h)
        p.setBrush(QBrush(QColor(self._BG_COLOR)))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor(self._TEXT_COLOR)))
        font = p.font()
        font.setPointSizeF(7.5)
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            Qt.AlignmentFlag.AlignCenter,
            "OR",
        )
        p.end()


def _build_hotseat_on_your_turn_tooltip_content(
    *,
    initial_sharing: bool = False,
) -> QWidget:
    """Help-icon tooltip: initial-sharing text (rounds 1–2) or Question | OR | Search."""
    host = QWidget()
    host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    root = QVBoxLayout(host)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(8)

    if initial_sharing:
        hint = QLabel(
            "Initially share the space that is not the habitat according to your clue."
        )
        hint.setWordWrap(True)
        hint.setMinimumWidth(220)
        hint.setStyleSheet("color: #5a6a72; font-size: 9pt;")
        root.addWidget(hint)
        host.adjustSize()
        return host

    columns_host = QWidget()
    columns_row = QHBoxLayout(columns_host)
    columns_row.setContentsMargins(0, 0, 0, 0)
    columns_row.setSpacing(0)

    col_q = QWidget()
    q_lay = QVBoxLayout(col_q)
    q_lay.setContentsMargins(0, 0, 4, 0)
    q_lay.setSpacing(6)
    lbl_q_title = QLabel("Question:")
    q_lay.addWidget(lbl_q_title)
    lbl_q_hint = QLabel("Ask one other player if this space could be the habitat. If the answer is No, additionally share the space that is not the habitat according to your clue.")
    lbl_q_hint.setWordWrap(True)
    lbl_q_hint.setMinimumWidth(140)
    lbl_q_hint.setStyleSheet("color: #5a6a72; font-size: 9pt;")
    q_lay.addWidget(lbl_q_hint)

    or_div = _OrDivider(bg_color="#d8ecea")
    or_div.setMinimumHeight(72)

    col_s = QWidget()
    s_lay = QVBoxLayout(col_s)
    s_lay.setContentsMargins(4, 0, 0, 0)
    s_lay.setSpacing(6)
    lbl_s_title = QLabel("Search:")
    s_lay.addWidget(lbl_s_title)
    lbl_s_hint = QLabel("Select a space and check if it could be the habitat according to other players' clues. If any of the answers is No, additionally share the space that is not the habitat according to your clue.")
    lbl_s_hint.setWordWrap(True)
    lbl_s_hint.setMinimumWidth(140)
    lbl_s_hint.setStyleSheet("color: #5a6a72; font-size: 9pt;")
    s_lay.addWidget(lbl_s_hint)

    columns_row.addWidget(col_q, 1, Qt.AlignmentFlag.AlignTop)
    columns_row.addWidget(or_div, 0)
    columns_row.addWidget(col_s, 1, Qt.AlignmentFlag.AlignTop)
    root.addWidget(columns_host)
    host.adjustSize()
    return host


def _hotseat_additional_sharing_arrow_pixmap(width: int, height: int) -> QPixmap:
    """Blocky right arrow with rounded corners (shaft + head), matches Additional sharing row."""
    pix = QPixmap(width, height)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3A8BC1"))

    m = max(0.5, min(width, height) * 0.08)
    iw = width - 2.0 * m
    ih = height - 2.0 * m
    cy = height / 2.0

    shaft_w = iw * 0.48
    shaft_h = ih * 0.40
    tri_h = ih * 0.88
    rr = min(2.8, shaft_h * 0.24, iw * 0.09)

    x0 = m
    y_shaft_t = cy - shaft_h / 2.0
    shaft = QPainterPath()
    shaft.addRoundedRect(QRectF(x0, y_shaft_t, shaft_w, shaft_h), rr, rr)

    base_x = x0 + shaft_w - rr * 0.35
    tip_x = m + iw - 0.5
    y_top = cy - tri_h / 2.0
    y_bot = cy + tri_h / 2.0
    tip = QPointF(tip_x, cy)
    bt = QPointF(base_x, y_top)
    bb = QPointF(base_x, y_bot)
    tri_path = _hotseat_rounded_triangle_path(tip, bt, bb, min(rr, 2.4))

    combined = shaft.united(tri_path)
    p.drawPath(combined)
    p.end()
    return pix


def _hotseat_rounded_triangle_path(
    tip: QPointF, base_top: QPointF, base_bottom: QPointF, r: float
) -> QPainterPath:
    """CCW triangle tip → base_top → base_bottom with quadratic fillets at vertices."""
    pts = [tip, base_top, base_bottom]
    n = 3
    segs: list[tuple[QPointF, QPointF, QPointF]] = []
    for i in range(n):
        a = pts[(i - 1) % n]
        b = pts[i]
        c = pts[(i + 1) % n]
        abx = b.x() - a.x()
        aby = b.y() - a.y()
        bcx = c.x() - b.x()
        bcy = c.y() - b.y()
        la = math.hypot(abx, aby)
        lc = math.hypot(bcx, bcy)
        if la < 1e-6 or lc < 1e-6:
            continue
        v1 = QPointF(abx / la, aby / la)
        v2 = QPointF(bcx / lc, bcy / lc)
        cos_turn = max(-1.0, min(1.0, -v1.x() * v2.x() - v1.y() * v2.y()))
        ang = math.acos(cos_turn)
        if ang < 1e-4:
            continue
        tan_h = math.tan(ang / 2.0)
        if tan_h < 1e-6:
            continue
        d = min(r / tan_h, la * 0.48, lc * 0.48)
        p1 = QPointF(b.x() - v1.x() * d, b.y() - v1.y() * d)
        p2 = QPointF(b.x() + v2.x() * d, b.y() + v2.y() * d)
        segs.append((p1, b, p2))

    path = QPainterPath()
    if not segs:
        path.moveTo(tip)
        path.lineTo(base_top)
        path.lineTo(base_bottom)
        path.closeSubpath()
        return path

    path.moveTo(segs[0][0])
    for p1, b, p2 in segs:
        path.quadTo(b, p2)
    path.closeSubpath()
    return path


def _hotseat_arrow_right_label() -> QLabel:
    """Right-arrow for Additional sharing (custom rounded block arrow, not theme SP_ArrowRight)."""
    w, h = 24, 22
    lab = QLabel()
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setPixmap(_hotseat_additional_sharing_arrow_pixmap(w, h))
    lab.setFixedSize(w, h)
    return lab


class _HotseatMapChipStripWidget(QFrame):
    """Chip flow below the map: Show clue, options row, then action chip / sharing."""

    def __init__(self, sidebar: "HotseatGameplaySidebar", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sidebar = sidebar
        self._initial_sharing_mode = False
        self.setObjectName("hotseatMapChipStrip")
        # No card frame: avoid QWidget[card] border from cards.qss; blend with map viewport.
        self.setStyleSheet(
            "#hotseatMapChipStrip { background: transparent; border: none; padding: 0px 0px 8px 0px; }"
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        clue_row = QHBoxLayout()
        clue_row.setContentsMargins(0, 0, 0, 0)
        clue_row.setSpacing(8)
        clue_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.btn_clue_toggle = QPushButton("Show clue")
        self.btn_clue_toggle.setProperty("secondary", True)
        self.btn_clue_toggle.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.btn_clue_toggle.clicked.connect(sidebar._on_clue_toggle)
        clue_row.addWidget(self.btn_clue_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_clue = QLabel("")
        self.lbl_clue.setWordWrap(False)
        self.lbl_clue.setVisible(False)
        self.lbl_clue.setStyleSheet("color: #5a6a72;")
        self.lbl_clue.setMinimumWidth(0)
        self.lbl_clue.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.lbl_clue.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        clue_row.addWidget(self.lbl_clue, 0, Qt.AlignmentFlag.AlignVCenter)
        clue_row.addStretch(1)
        _help_px = 20
        self.btn_on_your_turn_help = QLabel()
        self.btn_on_your_turn_help.setObjectName("hotseatOnYourTurnHelp")
        self.btn_on_your_turn_help.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _help_ic = QIcon(":/assets/icons/help_question_icon.svg")
        _pm_help = _help_ic.pixmap(QSize(_help_px, _help_px), QIcon.Mode.Normal, QIcon.State.Off)
        if _pm_help.isNull() and ICON_HELP.exists():
            _pm_help = QIcon(str(ICON_HELP)).pixmap(
                QSize(_help_px, _help_px), QIcon.Mode.Normal, QIcon.State.Off
            )
        if not _pm_help.isNull():
            self.btn_on_your_turn_help.setPixmap(_pm_help)
        self.btn_on_your_turn_help.setFixedSize(_help_px, _help_px)
        self.btn_on_your_turn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        on_your_turn_host = QWidget()
        on_your_turn_host.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum
        )
        on_your_turn_row = QHBoxLayout(on_your_turn_host)
        on_your_turn_row.setContentsMargins(0, 0, 0, 0)
        on_your_turn_row.setSpacing(6)
        on_your_turn_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        lbl_on_your_turn = QLabel("On your turn:")
        lbl_on_your_turn.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        on_your_turn_row.addWidget(
            lbl_on_your_turn, 0, Qt.AlignmentFlag.AlignVCenter
        )
        on_your_turn_row.addWidget(
            self.btn_on_your_turn_help, 0, Qt.AlignmentFlag.AlignVCenter
        )
        clue_row.addWidget(on_your_turn_host, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(clue_row)

        # Row 1: Select one option: Question  Search  (or Initial sharing title).
        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(12)
        options_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._lbl_select_option = QLabel("Select one option:")
        self._lbl_select_option.setContentsMargins(8, 0, 0, 0)
        self._lbl_title_initial = QLabel("Initial sharing:")
        self._lbl_title_initial.setContentsMargins(8, 0, 0, 0)
        self._radio_q = QRadioButton("Question")
        self._radio_s = QRadioButton("Search")
        self._radio_q.setCursor(Qt.CursorShape.PointingHandCursor)
        self._radio_s.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_group = QButtonGroup(self)
        self._action_group.setExclusive(True)
        self._action_group.addButton(self._radio_q, 0)
        self._action_group.addButton(self._radio_s, 1)
        self._radio_q.toggled.connect(self._on_action_radio_toggled)
        self._radio_s.toggled.connect(self._on_action_radio_toggled)
        options_row.addWidget(
            self._lbl_select_option, 0, Qt.AlignmentFlag.AlignVCenter
        )
        options_row.addWidget(
            self._lbl_title_initial, 0, Qt.AlignmentFlag.AlignVCenter
        )
        options_row.addWidget(self._radio_q, 0, Qt.AlignmentFlag.AlignVCenter)
        options_row.addWidget(self._radio_s, 0, Qt.AlignmentFlag.AlignVCenter)
        options_row.addStretch(1)
        root.addLayout(options_row)

        # Row 2: selected action chip, then arrow + additional sharing on demand.
        # Reserve chip height so showing/hiding the chip does not jump the strip.
        chip_px = _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        self._action_row_host = QWidget()
        self._action_row_host.setMinimumHeight(chip_px)
        self._action_row_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        action_row = QHBoxLayout(self._action_row_host)
        action_row.setContentsMargins(8, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        def _chip_slot(chip: QWidget) -> QWidget:
            host = QWidget()
            host.setFixedSize(chip_px, chip_px)
            slot_lay = QHBoxLayout(host)
            slot_lay.setContentsMargins(0, 0, 0, 0)
            slot_lay.setSpacing(0)
            slot_lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignCenter)
            return host

        self.lbl_question = _HotseatChipDragLabel(
            "question", _HOTSEAT_QUESTION_CHIP_HEX, self, hotseat_sidebar=sidebar
        )
        self.lbl_question.setFixedSize(chip_px, chip_px)
        self.lbl_question.setPixmap(get_player_question_chip_pixmap("", chip_px))
        self.lbl_share_q = _HotseatChipDragLabel(
            "square", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_share_q.setFixedSize(chip_px, chip_px)
        self.lbl_share_q.setPixmap(get_player_square_chip_pixmap("", chip_px))
        self.lbl_search = _HotseatChipDragLabel(
            "circle", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_search.setFixedSize(chip_px, chip_px)
        self.lbl_search.setPixmap(get_player_circle_chip_pixmap("", chip_px))
        self.lbl_share_s = _HotseatChipDragLabel(
            "square", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_share_s.setFixedSize(chip_px, chip_px)
        self.lbl_share_s.setPixmap(get_player_square_chip_pixmap("", chip_px))

        self._slot_question = _chip_slot(self.lbl_question)
        self._slot_search = _chip_slot(self.lbl_search)

        self._ar_q = _hotseat_arrow_right_label()
        self._ar_s = _hotseat_arrow_right_label()
        self._lbl_add_q = QLabel("Additional sharing:")
        self._lbl_add_s = QLabel("Additional sharing:")
        self._btn_undo_q = QToolButton()
        self._btn_undo_q.setObjectName("btnHotseatUndoAdditionalSharingQ")
        self._btn_undo_q.setIcon(QIcon(":/assets/icons/undo.svg"))
        self._btn_undo_q.setIconSize(QSize(20, 20))
        self._btn_undo_q.setAutoRaise(True)
        self._btn_undo_q.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_undo_q.clicked.connect(sidebar.undo_additional_sharing_clicked)
        self._btn_undo_s = QToolButton()
        self._btn_undo_s.setObjectName("btnHotseatUndoAdditionalSharingS")
        self._btn_undo_s.setIcon(QIcon(":/assets/icons/undo.svg"))
        self._btn_undo_s.setIconSize(QSize(20, 20))
        self._btn_undo_s.setAutoRaise(True)
        self._btn_undo_s.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_undo_s.clicked.connect(sidebar.undo_additional_sharing_clicked)
        al_vc = Qt.AlignmentFlag.AlignVCenter

        action_row.addWidget(self._slot_question, 0, al_vc)
        action_row.addWidget(self._slot_search, 0, al_vc)
        action_row.addWidget(self._ar_q, 0, al_vc)
        action_row.addWidget(self._ar_s, 0, al_vc)
        action_row.addWidget(self._lbl_add_q, 0, al_vc)
        action_row.addWidget(self._lbl_add_s, 0, al_vc)
        action_row.addWidget(self.lbl_share_q, 0, al_vc)
        action_row.addWidget(self.lbl_share_s, 0, al_vc)
        action_row.addWidget(self._btn_undo_q, 0, al_vc)
        action_row.addWidget(self._btn_undo_s, 0, al_vc)
        action_row.addStretch(1)
        root.addWidget(self._action_row_host)

        self._lbl_title_initial.hide()
        self.lbl_question.hide()
        self.lbl_search.hide()
        self.set_sharing_rows_visible(False, False)

    def _on_action_radio_toggled(self, checked: bool) -> None:
        if not checked:
            return
        sb = self._sidebar
        if sb is None:
            return
        sb.sync_hotseat_question_bank_visibility()
        sb.sync_hotseat_search_bank_visibility()
        sb.sync_hotseat_map_strip_sharing_rows()
        sb._schedule_map_chip_strip_layout_bump()
        sb.geometry_needs_update.emit()

    def selected_action(self) -> Literal["question", "search"] | None:
        if self._radio_q.isChecked():
            return "question"
        if self._radio_s.isChecked():
            return "search"
        return None

    def set_action_selection(self, use_search: bool | None) -> None:
        """Select Question (False), Search (True), or clear both (None)."""
        self._radio_q.blockSignals(True)
        self._radio_s.blockSignals(True)
        try:
            if use_search is None:
                self._action_group.setExclusive(False)
                self._radio_q.setChecked(False)
                self._radio_s.setChecked(False)
                self._action_group.setExclusive(True)
            elif use_search:
                self._radio_s.setChecked(True)
            else:
                self._radio_q.setChecked(True)
        finally:
            self._radio_q.blockSignals(False)
            self._radio_s.blockSignals(False)

    def set_action_radios_enabled(self, enabled: bool) -> None:
        self._radio_q.setEnabled(enabled)
        self._radio_s.setEnabled(enabled)
        cursor = (
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ArrowCursor
        )
        self._radio_q.setCursor(cursor)
        self._radio_s.setCursor(cursor)

    def set_initial_sharing_mode(self, enabled: bool) -> None:
        self._initial_sharing_mode = bool(enabled)

    def set_sharing_rows_visible(self, question_row: bool, search_row: bool) -> None:
        """Row 2: action chip from radio selection; arrow + additional sharing on demand."""
        if self._initial_sharing_mode:
            self._lbl_select_option.setVisible(False)
            self._lbl_title_initial.setVisible(True)
            self._radio_q.setVisible(False)
            self._radio_s.setVisible(False)
            self._slot_question.setVisible(False)
            self._slot_search.setVisible(False)
            self.lbl_question.setVisible(False)
            self.lbl_search.setVisible(False)
            self._ar_q.setVisible(False)
            self._lbl_add_q.setVisible(False)
            self.lbl_share_q.setVisible(True)
            # Undo button visibility is controlled by sidebar state sync.
            self._ar_s.setVisible(False)
            self._lbl_add_s.setVisible(False)
            self.lbl_share_s.setVisible(False)
            self._btn_undo_s.setVisible(False)
            self.adjustSize()
            self.updateGeometry()
            return
        self._lbl_select_option.setVisible(True)
        self._lbl_title_initial.setVisible(False)
        self._radio_q.setVisible(True)
        self._radio_s.setVisible(True)
        action = self.selected_action()
        show_q = action == "question"
        show_s = action == "search"
        self._slot_question.setVisible(show_q)
        self._slot_search.setVisible(show_s)
        self.lbl_question.setVisible(show_q)
        self.lbl_search.setVisible(show_s)
        self._ar_q.setVisible(question_row)
        self._lbl_add_q.setVisible(question_row)
        self.lbl_share_q.setVisible(question_row)
        self._btn_undo_q.setVisible(question_row)
        self._ar_s.setVisible(search_row)
        self._lbl_add_s.setVisible(search_row)
        self.lbl_share_s.setVisible(search_row)
        self._btn_undo_s.setVisible(search_row)
        self.adjustSize()
        self.updateGeometry()


class HotseatGameplaySidebar(QWidget):
    """Turn order + current player controls (Play Hotseat)."""

    geometry_needs_update = Signal()
    undo_additional_sharing_clicked = Signal()
    history_chip_focus_requested = Signal(str, str, int, int, int)


    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._names: list[str] = []
        self._color_names: list[str] = []
        self._n: int = 0
        self._turn_index: int = 0
        self._round_num: int = 1
        self._clue_visible: bool = False
        self._clues: list[str] = []
        self._lbl_round_value: QLabel | None = None
        self._turn_rows: list[tuple[QWidget, QLabel, QLabel, QLabel, QLabel]] = []
        self._lbl_clue: QLabel | None = None
        self._btn_clue_toggle: QPushButton | None = None
        self._question_icons_host: QWidget | None = None
        self._question_icons_layout: QHBoxLayout | None = None
        self._lbl_question_chip: _HotseatChipDragLabel | None = None
        self._lbl_search_chip: _HotseatChipDragLabel | None = None
        self._lbl_sharing_chip: _HotseatChipDragLabel | None = None
        self._hotseat_canvas: Any = None
        self._hotseat_question_used: bool = False
        self._hotseat_search_used: bool = False
        #: Map strip: show arrow + "Additional sharing" + square only after a square chip appears from that row's action.
        self._hotseat_map_strip_sharing_question_row: bool = False
        self._hotseat_map_strip_sharing_search_row: bool = False
        #: Additional sharing: one square from strip per turn; dimmed home while dragging it.
        self._hotseat_sharing_square_used: bool = False
        self._hotseat_sharing_square_carry: bool = False
        self._hotseat_question_carry: bool = False
        self._hotseat_search_carry: bool = False
        #: Set by ``HotseatBoardView.set_gameplay_sidebar(...)`` (bank chip drag uses this view).
        self.hotseat_board_view: Any = None
        self._map_chip_strip: _HotseatMapChipStripWidget | None = None
        self._turn_history_table: QTableWidget | None = None
        self._turn_history_pending: bool = False
        self._possible_clues_host: QWidget | None = None
        self._possible_clue_icon_labels: list[QLabel] = []
        self._possible_clues_header_row: QWidget | None = None
        self._lbl_apply_hint: QLabel | None = None
        self._cb_apply_hint: QCheckBox | None = None
        self._possible_clues_advanced_mode: bool = False
        self._hint_description: str | None = None
        self._hotseat_last_question_target_idx: int | None = None
        #: Round + turn-order flow — placed above the map by ``HotseatBoardPanel``.
        self._status_panel: QWidget | None = None
        self._turn_order_host: QWidget | None = None

        self.undo_additional_sharing_clicked.connect(self._on_undo_additional_sharing_clicked)
        self._setup_ui()
        win = self.window() if isinstance(self.window(), QWidget) else self
        self._app_tooltip = HoverTooltipManager(win, self)
        for _chip, _ic, _name, dot, _arrow in self._turn_rows:
            self._app_tooltip.add(dot, "Waiting", only_when_disabled=False)
        if self._map_chip_strip is not None:
            self._app_tooltip.add(self._map_chip_strip._btn_undo_q, TOOLTIP_UNDO, only_when_disabled=False)
            self._app_tooltip.add(self._map_chip_strip._btn_undo_s, TOOLTIP_UNDO, only_when_disabled=False)
            self._app_tooltip.add(
                self._map_chip_strip.btn_on_your_turn_help,
                self._on_your_turn_tooltip_content,
                only_when_disabled=False,
            )

    def _on_your_turn_tooltip_content(self) -> QWidget:
        return _build_hotseat_on_your_turn_tooltip_content(
            initial_sharing=self._is_initial_sharing_round()
        )

    @property
    def status_panel(self) -> QWidget | None:
        return self._status_panel

    def _on_undo_additional_sharing_clicked(self) -> None:
        v = getattr(self, "hotseat_board_view", None)
        fn = getattr(v, "undo_hotseat_additional_sharing_square", None) if v is not None else None
        if callable(fn):
            fn()

    def _is_initial_sharing_round(self) -> bool:
        return int(self._round_num) <= 2

    @property
    def map_chip_strip(self) -> _HotseatMapChipStripWidget | None:
        return self._map_chip_strip

    def _chip_home_px_for_label(self, lab: _HotseatChipDragLabel) -> int:
        """Sidebar bank and map strip both use ``_HOTSEAT_VIEW_SCALE`` (1.0 for game)."""
        ms = self._map_chip_strip
        if ms is not None and (
            lab is ms.lbl_question
            or lab is ms.lbl_search
            or lab is ms.lbl_share_q
            or lab is ms.lbl_share_s
        ):
            return _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        return _HOTSEAT_CHIP_HOME_PX

    def _question_chip_labels(self) -> list[_HotseatChipDragLabel]:
        out: list[_HotseatChipDragLabel] = []
        if self._lbl_question_chip is not None:
            out.append(self._lbl_question_chip)
        if self._map_chip_strip is not None:
            out.append(self._map_chip_strip.lbl_question)
        return out

    def _search_chip_labels(self) -> list[_HotseatChipDragLabel]:
        out: list[_HotseatChipDragLabel] = []
        if self._lbl_search_chip is not None:
            out.append(self._lbl_search_chip)
        if self._map_chip_strip is not None:
            out.append(self._map_chip_strip.lbl_search)
        return out

    def _sharing_chip_labels(self) -> list[_HotseatChipDragLabel]:
        out: list[_HotseatChipDragLabel] = []
        if self._lbl_sharing_chip is not None:
            out.append(self._lbl_sharing_chip)
        if self._map_chip_strip is not None:
            out.extend(
                (self._map_chip_strip.lbl_share_q, self._map_chip_strip.lbl_share_s)
            )
        return out

    def _setup_ui(self) -> None:
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        # Status card: Round + turn-order flow (above map).
        status_card = QWidget()
        status_card.setProperty("card", True)
        status_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        status_lay = QVBoxLayout(status_card)
        status_lay.setContentsMargins(10, 10, 10, 10)
        status_lay.setSpacing(6)

        round_row = QHBoxLayout()
        round_row.setContentsMargins(0, 0, 0, 0)
        round_row.setSpacing(6)
        round_row.addWidget(QLabel("Round:"))
        self._lbl_round_value = QLabel("1")
        self._lbl_round_value.setStyleSheet(
            f"color: {_STATUS_BLUE}; font-weight: bold;"
        )
        round_row.addWidget(self._lbl_round_value)
        round_row.addStretch(1)
        status_lay.addLayout(round_row)

        turn_order_host = QWidget()
        turn_order_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        turn_flow = _FlowLayout(turn_order_host, h_spacing=6, v_spacing=6)
        for i in range(5):
            chip = QWidget()
            chip.setSizePolicy(
                QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum
            )
            hl = QHBoxLayout(chip)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)
            hl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            dot = QLabel()
            dot.setFixedSize(_TURN_STATUS_DOT_PX, _TURN_STATUS_DOT_PX)
            dot.setScaledContents(True)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic = QLabel()
            ic.setFixedSize(18, 18)
            ic.setScaledContents(True)
            name = QLabel("")
            name.setWordWrap(False)
            name.setMinimumWidth(0)
            name.setSizePolicy(
                QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
            )
            hl.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(ic, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)
            arrow = _hotseat_arrow_right_label()
            turn_flow.addWidget(chip)
            turn_flow.addWidget(arrow)
            # (chip, meeple, name, status_dot, arrow_after)
            self._turn_rows.append((chip, ic, name, dot, arrow))
        status_lay.addWidget(turn_order_host)
        self._turn_order_host = turn_order_host

        self._status_panel = status_card
        status_card.hide()

        # Right sidebar: sharing / turn history.
        turn_card = QWidget(self)
        turn_card.setProperty("card", True)
        turn_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        turn_lay = QVBoxLayout(turn_card)
        turn_lay.setContentsMargins(10, 10, 10, 10)
        turn_lay.setSpacing(6)

        lbl_turn_history = QLabel("Turn history:")
        lbl_turn_history.setWordWrap(True)
        lbl_turn_history.setMinimumWidth(0)
        lbl_turn_history.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        turn_lay.addWidget(lbl_turn_history)

        hist = QTableWidget(0, 4, turn_card)
        hist.setObjectName("hotseatTurnHistoryTable")
        hist.setHorizontalHeaderLabels(
            ["Round", "Player", "Action", "Chips placed"]
        )
        hist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hist.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        hist.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hist.setWordWrap(True)
        hist.verticalHeader().setVisible(False)
        hist.setCornerButtonEnabled(False)
        hist.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr = hist.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hist.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        hist.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hist.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        # Keep sidebar width stable: table should adapt to available width,
        # not drive the parent size hint (which shrinks the map viewport).
        hist.setMinimumWidth(0)
        hist.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        hist.setMinimumHeight(120)
        turn_lay.addWidget(hist, 1)
        self._turn_history_table = hist

        header_row = QWidget(turn_card)
        header_row.setMinimumWidth(0)
        header_lay = QHBoxLayout(header_row)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setSpacing(8)

        lbl_possible_clues = QLabel("Possible clues:")
        lbl_possible_clues.setWordWrap(True)
        lbl_possible_clues.setMinimumWidth(0)
        lbl_possible_clues.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        header_lay.addWidget(lbl_possible_clues, 0, Qt.AlignmentFlag.AlignVCenter)
        header_lay.addStretch(1)

        lbl_apply_hint = QLabel("Apply hint:")
        lbl_apply_hint.setMinimumWidth(0)
        header_lay.addWidget(lbl_apply_hint, 0, Qt.AlignmentFlag.AlignVCenter)
        cb_apply_hint = QCheckBox()
        cb_apply_hint.setText("")
        cb_apply_hint.setChecked(False)
        cb_apply_hint.toggled.connect(self._on_apply_hint_toggled)
        header_lay.addWidget(cb_apply_hint, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl_apply_hint = lbl_apply_hint
        self._cb_apply_hint = cb_apply_hint
        self._possible_clues_header_row = header_row
        turn_lay.addWidget(header_row)
        self._set_apply_hint_controls(visible=False, enabled=False)

        clues_host = QWidget()
        clues_host.setObjectName("hotseatPossibleCluesHost")
        clues_host.setMinimumWidth(0)
        clues_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        clues_grid = QGridLayout(clues_host)
        clues_grid.setContentsMargins(0, 0, 0, 0)
        clues_grid.setHorizontalSpacing(4)
        clues_grid.setVerticalSpacing(4)
        self._possible_clues_host = clues_host
        turn_lay.addWidget(clues_host, 0)

        # Single child fills the sidebar when height is synced to the map column.
        root.addWidget(turn_card, 1)

        self._map_chip_strip = _HotseatMapChipStripWidget(self)
        self._map_chip_strip.hide()
        self._btn_clue_toggle = self._map_chip_strip.btn_clue_toggle
        self._lbl_clue = self._map_chip_strip.lbl_clue

        self._sync_clue_display()
        self._apply_style_polish()

    def _reset_question_mode_to_question(self) -> None:
        """Clear Question/Search radio selection for a new turn/session."""
        ms = self._map_chip_strip
        if ms is None:
            return
        ms.set_action_selection(None)
        ms.set_action_radios_enabled(True)

    def _selected_hotseat_action(self) -> Literal["question", "search"] | None:
        ms = self._map_chip_strip
        if ms is None or self._is_initial_sharing_round():
            return None
        return ms.selected_action()

    def sync_hotseat_action_radios(self) -> None:
        """Disable Question/Search radios after the chosen action chip is confirmed this turn."""
        ms = self._map_chip_strip
        if ms is None:
            return
        if self._is_initial_sharing_round():
            return
        locked = self._hotseat_question_used or self._hotseat_search_used
        ms.set_action_radios_enabled(not locked)

    def _apply_style_polish(self) -> None:
        widgets: list[QWidget] = [self]
        if self._status_panel is not None:
            widgets.append(self._status_panel)
        if self._map_chip_strip is not None:
            widgets.append(self._map_chip_strip)
        for host in widgets:
            for w in host.findChildren(QPushButton):
                if w.property("secondary"):
                    style = w.style()
                    if style is not None:
                        style.unpolish(w)
                        style.polish(w)

    def _sync_clue_display(self) -> None:
        """Show the active player's clue text from ``self._clues`` (maps.json books)."""
        if self._lbl_clue is None:
            return
        if (
            0 <= self._turn_index < self._n
            and self._turn_index < len(self._clues)
        ):
            self._lbl_clue.setText(self._clues[self._turn_index])
        else:
            self._lbl_clue.setText("")
        self._lbl_clue.setVisible(self._clue_visible)

    def _on_clue_toggle(self) -> None:
        self._clue_visible = not self._clue_visible
        if self._btn_clue_toggle is not None:
            self._btn_clue_toggle.setText("Hide clue" if self._clue_visible else "Show clue")
        if self._lbl_clue is not None:
            self._lbl_clue.setVisible(self._clue_visible)
        if self._map_chip_strip is not None:
            self._map_chip_strip.adjustSize()
            self._map_chip_strip.updateGeometry()
        self._schedule_map_chip_strip_layout_bump()
        self.geometry_needs_update.emit()

    def set_session(
        self,
        names: list[str],
        color_names: list[str],
        clues: list[str] | None = None,
        *,
        advanced_mode: bool = False,
        show_apply_hint: bool = False,
        hint_description: str | None = None,
    ) -> None:
        self._names = list(names)
        self._color_names = list(color_names)
        self._n = len(names)
        self._turn_index = 0
        self._round_num = 1
        raw = list(clues) if clues is not None else []
        self._clues = [
            raw[i] if i < len(raw) else "" for i in range(self._n)
        ]
        self._clue_visible = False
        if self._btn_clue_toggle is not None:
            self._btn_clue_toggle.setText("Show clue")
        self._hotseat_question_used = False
        self._hotseat_search_used = False
        self._hotseat_map_strip_sharing_question_row = False
        self._hotseat_map_strip_sharing_search_row = False
        self._hotseat_sharing_square_used = False
        self._hotseat_sharing_square_carry = False
        self._hotseat_question_carry = False
        self._hotseat_search_carry = False
        self._hotseat_last_question_target_idx = None
        self._possible_clues_advanced_mode = bool(advanced_mode)
        self._hint_description = hint_description
        self._reset_question_mode_to_question()
        self.clear_turn_history()
        self._sync_turn_history_player_column_width()
        # Predefined maps: show Apply hint; disable when map has no hint for this player count.
        self._set_apply_hint_controls(
            visible=show_apply_hint,
            enabled=bool(show_apply_hint and hint_description),
        )
        self.set_possible_clues(advanced_mode=advanced_mode)
        self._refresh_all()

    def _set_apply_hint_controls(self, *, visible: bool, enabled: bool) -> None:
        if self._lbl_apply_hint is not None:
            self._lbl_apply_hint.setVisible(visible)
            self._lbl_apply_hint.setEnabled(enabled)
        if self._cb_apply_hint is not None:
            self._cb_apply_hint.blockSignals(True)
            if not visible or not enabled:
                self._cb_apply_hint.setChecked(False)
            self._cb_apply_hint.setVisible(visible)
            self._cb_apply_hint.setEnabled(enabled)
            self._cb_apply_hint.blockSignals(False)

    def _set_apply_hint_visible(self, visible: bool) -> None:
        """Back-compat helper used when clearing the board."""
        self._set_apply_hint_controls(visible=visible, enabled=False)

    def apply_hint_enabled(self) -> bool:
        cb = self._cb_apply_hint
        return bool(
            cb is not None
            and cb.isVisible()
            and cb.isEnabled()
            and cb.isChecked()
        )

    def _on_apply_hint_toggled(self, _checked: bool = False) -> None:
        self.set_possible_clues(advanced_mode=self._possible_clues_advanced_mode)

    def clear_possible_clues(self) -> None:
        tip = getattr(self, "_app_tooltip", None)
        for lbl in self._possible_clue_icon_labels:
            if tip is not None:
                tip.remove_target(lbl)
        self._possible_clue_icon_labels = []
        host = self._possible_clues_host
        if host is None:
            return
        lay = host.layout()
        if not isinstance(lay, QGridLayout):
            return
        while lay.count():
            item = lay.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def set_possible_clues(self, *, advanced_mode: bool) -> None:
        """Show icons for condition labels; optionally filter by map hint."""
        self.clear_possible_clues()
        host = self._possible_clues_host
        if host is None:
            return
        lay = host.layout()
        if not isinstance(lay, QGridLayout):
            return
        self._possible_clues_advanced_mode = bool(advanced_mode)
        labels = all_condition_labels(advanced_mode=advanced_mode)
        if self.apply_hint_enabled():
            labels = filter_clue_labels_by_hint(labels, self._hint_description)
        icons = _load_hotseat_clue_icon_pixmaps()
        default_pix = _hotseat_default_clue_pixmap()
        tip = getattr(self, "_app_tooltip", None)
        cols = max(1, _POSSIBLE_CLUE_COLS)
        for i, label in enumerate(labels):
            slot = get_slot_for_clue_label(label)
            pix = icons.get(slot) if slot else None
            if pix is None or pix.isNull():
                pix = default_pix
            icon = QLabel(host)
            icon.setFixedSize(_POSSIBLE_CLUE_ICON_PX, _POSSIBLE_CLUE_ICON_PX)
            icon.setScaledContents(False)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if pix is not None and not pix.isNull():
                icon.setPixmap(pix)
            if tip is not None:
                tip.add(icon, label, only_when_disabled=False)
            lay.addWidget(icon, i // cols, i % cols, Qt.AlignmentFlag.AlignLeft)
            self._possible_clue_icon_labels.append(icon)
        host.adjustSize()
        host.updateGeometry()

    def set_turn_index(self, idx: int) -> None:
        self._turn_index = max(0, min(idx, max(0, self._n - 1)))
        self._clue_visible = False
        if self._btn_clue_toggle is not None:
            self._btn_clue_toggle.setText("Show clue")
        self._hotseat_question_used = False
        self._hotseat_search_used = False
        self._hotseat_map_strip_sharing_question_row = False
        self._hotseat_map_strip_sharing_search_row = False
        self._hotseat_sharing_square_used = False
        self._hotseat_sharing_square_carry = False
        self._hotseat_question_carry = False
        self._hotseat_search_carry = False
        self._hotseat_last_question_target_idx = None
        self._reset_question_mode_to_question()
        self._refresh_all()

    def set_round(self, n: int) -> None:
        self._round_num = max(1, int(n))
        if self._lbl_round_value is not None:
            self._lbl_round_value.setText(str(self._round_num))
        self.sync_hotseat_map_strip_sharing_rows()
        self.sync_hotseat_question_bank_visibility()
        self.sync_hotseat_search_bank_visibility()
        self.sync_hotseat_sharing_bank_visibility()
        self.geometry_needs_update.emit()

    def set_clue_text(self, text: str) -> None:
        """Override clue text for the current turn index (optional)."""
        if 0 <= self._turn_index < self._n:
            while len(self._clues) <= self._turn_index:
                self._clues.append("")
            self._clues[self._turn_index] = text
        self._sync_clue_display()

    def clue_text_for_player(self, player_index: int) -> str:
        """Book clue string for a player (same labels as the deduction rule list)."""
        if 0 <= player_index < len(self._clues):
            return (self._clues[player_index] or "").strip()
        return ""

    def set_question_or_search(self, use_search: bool) -> None:
        """Select Question or Search radio and show the matching strip chip."""
        ms = self._map_chip_strip
        if ms is not None and not self._is_initial_sharing_round():
            ms.set_action_selection(bool(use_search))
        self._refresh_chips()
        self.sync_hotseat_question_bank_visibility()
        self.sync_hotseat_search_bank_visibility()
        self.sync_hotseat_map_strip_sharing_rows()
        self.sync_hotseat_action_radios()
        self._schedule_map_chip_strip_layout_bump()
        self.geometry_needs_update.emit()

    def _player_cell_widget(
        self, player_index: int, *, include_name: bool
    ) -> QWidget:
        host = QWidget()
        lay = QHBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        icon = QLabel(host)
        icon.setFixedSize(16, 16)
        icon.setScaledContents(True)
        cname = (
            self._color_names[player_index]
            if 0 <= player_index < len(self._color_names)
            else ""
        )
        icon.setPixmap(get_player_meeple_pixmap(cname, 16))
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)
        if include_name:
            name = (
                self._names[player_index]
                if 0 <= player_index < len(self._names)
                else f"Player {player_index + 1}"
            )
            lbl = QLabel(name, host)
            lbl.setWordWrap(False)
            lay.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)
        return host

    def clear_turn_history(self) -> None:
        table = self._turn_history_table
        if table is None:
            return
        table.setRowCount(0)
        self._turn_history_pending = False
        self._sync_turn_history_player_column_width()

    def _sync_turn_history_player_column_width(self) -> None:
        table = self._turn_history_table
        if table is None:
            return
        fm = QFontMetrics(table.font())
        label_w = fm.horizontalAdvance("Player")
        names_w = 0
        for idx in range(self._n):
            nm = self._names[idx] if idx < len(self._names) else f"Player {idx + 1}"
            names_w = max(names_w, fm.horizontalAdvance(nm))
        # Meeple icon + cell paddings/layout spacing.
        icon_and_padding = 44
        target_w = max(label_w, names_w) + icon_and_padding
        table.setColumnWidth(1, max(110, target_w))

    def begin_turn_history_row(self, *, round_num: int, player_index: int) -> None:
        """Add a pending history row with Round + Player only (before the turn is played)."""
        table = self._turn_history_table
        if table is None:
            return
        if self._turn_history_pending:
            return
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(str(max(1, int(round_num)))))
        table.setCellWidget(
            row,
            1,
            self._player_cell_widget(player_index, include_name=True),
        )
        table.setItem(row, 2, QTableWidgetItem(""))
        table.setItem(row, 3, QTableWidgetItem(""))
        self._turn_history_pending = True
        table.resizeRowToContents(row)
        table.scrollToBottom()

    def append_turn_history_row(
        self,
        *,
        round_num: int,
        player_index: int,
        action: str,
        question_target_idx: int | None,
        chips_placed: list[HistoryChipRef],
    ) -> None:
        """Fill Action + Chips on the pending row (or insert a full row if none)."""
        table = self._turn_history_table
        if table is None:
            return
        if self._turn_history_pending and table.rowCount() > 0:
            row = table.rowCount() - 1
        else:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(max(1, int(round_num)))))
            table.setCellWidget(
                row,
                1,
                self._player_cell_widget(player_index, include_name=True),
            )
        if action == "Question" and question_target_idx is not None:
            action_host = QWidget(table)
            action_lay = QHBoxLayout(action_host)
            action_lay.setContentsMargins(0, 0, 0, 0)
            action_lay.setSpacing(4)
            action_lay.addWidget(QLabel("Question", action_host), 0, Qt.AlignmentFlag.AlignVCenter)
            action_lay.addWidget(
                self._player_cell_widget(question_target_idx, include_name=False),
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
            action_lay.addStretch(1)
            table.takeItem(row, 2)
            table.removeCellWidget(row, 2)
            table.setCellWidget(row, 2, action_host)
        else:
            table.removeCellWidget(row, 2)
            table.setItem(row, 2, QTableWidgetItem(action))
        chips_host = QWidget(table)
        chips_lay = QHBoxLayout(chips_host)
        chips_lay.setContentsMargins(0, 0, 0, 0)
        chips_lay.setSpacing(4)
        for shape_kind, color_hex, r, c, cell_idx in chips_placed:
            payload: HistoryChipRef = (shape_kind, color_hex, r, c, cell_idx)
            chip_icon = _HistoryChipIconLabel(payload, chips_host)
            chip_icon.setFixedSize(16, 16)
            chip_icon.setScaledContents(True)
            if shape_kind == "question":
                chip_icon.setPixmap(get_player_question_chip_pixmap("", 16))
            elif shape_kind == "square":
                chip_icon.setPixmap(
                    get_player_square_chip_pixmap(
                        _hotseat_color_name_from_hex(color_hex), 16
                    )
                )
            else:
                chip_icon.setPixmap(
                    get_player_circle_chip_pixmap(
                        _hotseat_color_name_from_hex(color_hex), 16
                    )
                )
            chip_icon.clicked.connect(self._on_history_chip_icon_clicked)
            tip = getattr(self, "_app_tooltip", None)
            if tip is not None:
                tip.add(chip_icon, "Show on map", only_when_disabled=False)
            chips_lay.addWidget(chip_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        chips_lay.addStretch(1)
        table.takeItem(row, 3)
        table.removeCellWidget(row, 3)
        table.setCellWidget(row, 3, chips_host)
        self._turn_history_pending = False
        table.resizeRowToContents(row)
        table.scrollToBottom()

    def _on_history_chip_icon_clicked(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 5:
            return
        shape_kind, color_hex, r, c, cell_idx = payload
        self.history_chip_focus_requested.emit(
            str(shape_kind),
            str(color_hex),
            int(r),
            int(c),
            int(cell_idx),
        )

    def _refresh_all(self) -> None:
        self._refresh_header_summary()
        self._refresh_turn_order()
        self._refresh_question_icons()
        self._refresh_chips()
        self._sync_clue_display()
        self.sync_hotseat_question_bank_visibility()
        self.sync_hotseat_search_bank_visibility()
        self.sync_hotseat_map_strip_sharing_rows()
        self.sync_hotseat_sharing_bank_visibility()
        self.sync_hotseat_action_radios()
        self.geometry_needs_update.emit()

    def sync_hotseat_map_strip_sharing_rows(self) -> None:
        """Show Additional sharing controls only when a square resulted from Question or Search on this turn."""
        ms = self._map_chip_strip
        if ms is None:
            return
        is_initial = self._is_initial_sharing_round()
        ms.set_initial_sharing_mode(is_initial)
        if is_initial:
            ms.set_sharing_rows_visible(True, False)
            return
        ms.set_sharing_rows_visible(
            self._hotseat_map_strip_sharing_question_row,
            self._hotseat_map_strip_sharing_search_row,
        )

    def _schedule_map_chip_strip_layout_bump(self) -> None:
        """Embedded strip under QGraphicsProxyWidget often needs a deferred relayout to show new children."""
        def bump() -> None:
            v = getattr(self, "hotseat_board_view", None)
            if v is not None:
                v.layout_map_chip_strip_proxy()
                vp = v.viewport()
                if vp is not None:
                    vp.update()
                sync = getattr(v, "sync_hotseat_map_strip_proxy_item_cursor", None)
                if callable(sync):
                    sync()

        bump()
        QTimer.singleShot(0, bump)

    def attach_hotseat_canvas(self, canvas: Any) -> None:
        """Wire chip callbacks so the question bank slot shows a shadow while a gray ? chip is on the map."""
        old = self._hotseat_canvas
        if old is not None:
            setattr(old, "_on_chip_assigned", None)
            setattr(old, "_on_chip_released", None)
        self._hotseat_canvas = canvas
        if canvas is not None:

            def _assigned(_chip: Any, _r: int, _c: int, _idx: int) -> None:
                self.sync_hotseat_question_bank_visibility()
                self.sync_hotseat_search_bank_visibility()
                self.sync_hotseat_sharing_bank_visibility()

            def _released(_chip: Any) -> None:
                self.sync_hotseat_question_bank_visibility()
                self.sync_hotseat_search_bank_visibility()
                self.sync_hotseat_sharing_bank_visibility()

            canvas._on_chip_assigned = _assigned
            canvas._on_chip_released = _released
        self.sync_hotseat_question_bank_visibility()
        self.sync_hotseat_sharing_bank_visibility()

    def may_drag_question_chip_from_bank(self) -> bool:
        """False while a gray ? chip is already on the map or the question was already used this turn."""
        if self._is_initial_sharing_round():
            return False
        if self._selected_hotseat_action() != "question":
            return False
        if self._hotseat_question_used:
            return False
        if self._hotseat_search_used:
            return False
        if self._hotseat_question_carry:
            return False
        c = self._hotseat_canvas
        if c is None:
            return True
        return not any(getattr(ch, "_question_mark", False) for ch in c.chip_slot)

    def sync_hotseat_question_bank_visibility(self) -> None:
        """Dimmed chip shadow while ? is on map, after question/search is used, or after Search was chosen this turn."""
        labs = self._question_chip_labels()
        if not labs:
            return
        ms = self._map_chip_strip
        is_initial = self._is_initial_sharing_round()
        show_strip_q = self._selected_hotseat_action() == "question"
        c = self._hotseat_canvas
        if c is None:
            show_shadow = (
                is_initial
                or
                self._hotseat_question_used
                or self._hotseat_search_used
                or self._hotseat_question_carry
            )
            for lab in labs:
                if ms is not None and lab is ms.lbl_question:
                    if is_initial or not show_strip_q:
                        lab.setVisible(False)
                        continue
                px = self._chip_home_px_for_label(lab)
                full = get_player_question_chip_pixmap("", px)
                if lab.graphicsEffect() is not None:
                    lab.setGraphicsEffect(None)
                lab.setFixedSize(px, px)
                lab.setVisible(True)
                if show_shadow:
                    dimmed = QPixmap(full.size())
                    dimmed.fill(Qt.GlobalColor.transparent)
                    p = QPainter(dimmed)
                    p.setOpacity(0.38)
                    p.drawPixmap(0, 0, full)
                    p.end()
                    lab.setPixmap(dimmed)
                    lab.set_shadow(True)
                else:
                    lab.setPixmap(full)
                    lab.set_shadow(False)
            self.sync_hotseat_action_radios()
            return
        on_map = any(
            getattr(ch, "_question_mark", False) for ch in c.chip_slot
        )
        show_shadow = (
            on_map
            or is_initial
            or self._hotseat_question_used
            or self._hotseat_search_used
            or self._hotseat_question_carry
        )
        for lab in labs:
            if ms is not None and lab is ms.lbl_question:
                if is_initial or not show_strip_q:
                    lab.setVisible(False)
                    continue
            px = self._chip_home_px_for_label(lab)
            full = get_player_question_chip_pixmap("", px)
            lab.setVisible(True)
            if lab.graphicsEffect() is not None:
                lab.setGraphicsEffect(None)
            lab.setFixedSize(px, px)
            if show_shadow:
                dimmed = QPixmap(full.size())
                dimmed.fill(Qt.GlobalColor.transparent)
                p = QPainter(dimmed)
                p.setOpacity(0.38)
                p.drawPixmap(0, 0, full)
                p.end()
                lab.setPixmap(dimmed)
                lab.set_shadow(True)
            else:
                lab.setPixmap(full)
                lab.set_shadow(False)
        self.sync_hotseat_action_radios()

    def may_drag_search_chip_from_bank(self) -> bool:
        """False when the search action was already used this turn or question was chosen instead."""
        if self._is_initial_sharing_round():
            return False
        if self._selected_hotseat_action() != "search":
            return False
        if self._hotseat_question_used:
            return False
        if self._hotseat_search_carry:
            return False
        return not self._hotseat_search_used

    def sync_hotseat_search_bank_visibility(self) -> None:
        """Dimmed strip while a Search circle is on the map, during bank carry, or after Search / Question use."""
        labs = self._search_chip_labels()
        if not labs:
            return
        ms = self._map_chip_strip
        is_initial = self._is_initial_sharing_round()
        show_strip_s = self._selected_hotseat_action() == "search"
        cur = self._turn_index
        cname = self._color_names[cur] if 0 <= cur < len(self._color_names) else ""
        show_shadow = (
            is_initial
            or
            self._hotseat_search_used
            or self._hotseat_question_used
            or self._hotseat_search_carry
        )
        for lab in labs:
            if ms is not None and lab is ms.lbl_search:
                if is_initial or not show_strip_s:
                    lab.setVisible(False)
                    continue
            lab.setVisible(True)
            px = self._chip_home_px_for_label(lab)
            full = get_player_circle_chip_pixmap(cname, px)
            lab.setFixedSize(px, px)
            if show_shadow:
                dimmed = QPixmap(full.size())
                dimmed.fill(Qt.GlobalColor.transparent)
                p = QPainter(dimmed)
                p.setOpacity(0.38)
                p.drawPixmap(0, 0, full)
                p.end()
                lab.setPixmap(dimmed)
                lab.set_shadow(True)
            else:
                lab.setPixmap(full)
                lab.set_shadow(False)
        self.sync_hotseat_action_radios()

    def may_drag_sharing_chip_from_bank(self) -> bool:
        """False after the additional sharing square was placed this turn (or while a bank carry is active)."""
        if self._hotseat_sharing_square_used:
            return False
        if self._hotseat_sharing_square_carry:
            return False
        return True

    def sync_hotseat_sharing_bank_visibility(self) -> None:
        """Dimmed home shadow after sharing square is placed or while dragging it from the strip."""
        labs = self._sharing_chip_labels()
        if not labs:
            return
        cur = self._turn_index
        cname = self._color_names[cur] if 0 <= cur < len(self._color_names) else ""
        show_shadow = (
            self._hotseat_sharing_square_used
            or self._hotseat_sharing_square_carry
        )
        ms = self._map_chip_strip
        if ms is not None:
            # Undo is only meaningful when a sharing square has been placed (i.e. the bank/home is shadowed).
            if self._is_initial_sharing_round():
                ms._btn_undo_q.setVisible(bool(self._hotseat_sharing_square_used))
                ms._btn_undo_s.setVisible(False)
            else:
                ms._btn_undo_q.setVisible(
                    bool(self._hotseat_map_strip_sharing_question_row)
                    and bool(self._hotseat_sharing_square_used)
                )
                ms._btn_undo_s.setVisible(
                    bool(self._hotseat_map_strip_sharing_search_row)
                    and bool(self._hotseat_sharing_square_used)
                )
        for lab in labs:
            px = self._chip_home_px_for_label(lab)
            full = get_player_square_chip_pixmap(cname, px)
            lab.setFixedSize(px, px)
            if show_shadow:
                dimmed = QPixmap(full.size())
                dimmed.fill(Qt.GlobalColor.transparent)
                p = QPainter(dimmed)
                p.setOpacity(0.38)
                p.drawPixmap(0, 0, full)
                p.end()
                lab.setPixmap(dimmed)
                lab.set_shadow(True)
            else:
                lab.setPixmap(full)
                lab.set_shadow(False)
                lab.setCursor(Qt.CursorShape.OpenHandCursor)

    def _refresh_header_summary(self) -> None:
        if self._lbl_round_value is not None:
            self._lbl_round_value.setText(str(self._round_num))

    def _update_status_dot_tooltip(self, dot: QLabel, text: str) -> None:
        tip = getattr(self, "_app_tooltip", None)
        if tip is None:
            return
        tip.remove_target(dot)
        tip.add(dot, text, only_when_disabled=False)

    def _refresh_turn_order(self) -> None:
        t = self._turn_index
        last_visible = self._n - 1
        for i in range(5):
            chip, ic, name, dot, arrow = self._turn_rows[i]
            if i >= self._n:
                chip.hide()
                arrow.hide()
                continue
            chip.show()
            arrow.setVisible(i < last_visible)
            cname = self._color_names[i] if i < len(self._color_names) else ""
            ic.setPixmap(get_player_meeple_pixmap(cname, 18))
            name.setText(self._names[i] if i < len(self._names) else f"Player {i + 1}")
            if i < t:
                st = _TurnStatus.DONE
                st_text = "Done"
            elif i == t:
                st = _TurnStatus.ACTIVE
                st_text = "Active"
            else:
                st = _TurnStatus.WAITING
                st_text = "Waiting"
            nf = name.font()
            nf.setBold(False)
            nf.setWeight(
                QFont.Weight.DemiBold if i == t else QFont.Weight.Normal
            )
            name.setFont(nf)
            dot.setPixmap(_status_dot_pixmap(st, _TURN_STATUS_DOT_PX))
            self._update_status_dot_tooltip(dot, st_text)
        host = getattr(self, "_turn_order_host", None)
        if host is not None:
            host.updateGeometry()
        self.geometry_needs_update.emit()

    def hotseat_chip_home_scene(
        self,
        view: "HotseatBoardView",
        kind: Literal["question", "search", "share"],
    ) -> QPointF:
        """Scene point at the center of the matching chip preview (map strip below the map)."""
        ms = self._map_chip_strip
        w: QWidget | None = None
        if kind == "question":
            w = self._lbl_question_chip
            if w is None and ms is not None:
                w = ms.lbl_question
        elif kind == "search":
            w = self._lbl_search_chip
            if w is None and ms is not None:
                w = ms.lbl_search
        else:
            w = self._lbl_sharing_chip
            if w is None and ms is not None:
                if self._hotseat_map_strip_sharing_question_row:
                    w = ms.lbl_share_q
                elif self._hotseat_map_strip_sharing_search_row:
                    w = ms.lbl_share_s
                else:
                    w = ms.lbl_share_q
        if w is None:
            return QPointF(0, 0)
        center_g = w.mapToGlobal(QPoint(w.width() // 2, w.height() // 2))
        vp_pt = view.viewport().mapFromGlobal(center_g)
        return view.mapToScene(vp_pt)

    def other_player_slots(self) -> list[tuple[int, str]]:
        """Turn index and color name for every player except the current one (question chip)."""
        out: list[tuple[int, str]] = []
        cur = self._turn_index
        for i in range(self._n):
            if i == cur:
                continue
            cn = self._color_names[i] if i < len(self._color_names) else ""
            out.append((i, cn))
        return out

    def other_player_slots_clockwise(self) -> list[tuple[int, str]]:
        """Players starting from next after current, wrapping around (for Search)."""
        out: list[tuple[int, str]] = []
        cur = self._turn_index
        for offset in range(1, self._n):
            i = (cur + offset) % self._n
            cn = self._color_names[i] if i < len(self._color_names) else ""
            out.append((i, cn))
        return out

    def _refresh_question_icons(self) -> None:
        lay = self._question_icons_layout
        host = self._question_icons_host
        if lay is None or host is None:
            return
        self._lbl_question_chip = None
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        lab = _HotseatChipDragLabel(
            "question", _HOTSEAT_QUESTION_CHIP_HEX, host, hotseat_sidebar=self
        )
        self._lbl_question_chip = lab
        lab.setPixmap(
            get_player_question_chip_pixmap("", _HOTSEAT_CHIP_HOME_PX)
        )
        lab.setFixedSize(_HOTSEAT_CHIP_HOME_PX, _HOTSEAT_CHIP_HOME_PX)
        lay.addWidget(lab)
        lay.addStretch(1)

    def _refresh_chips(self) -> None:
        cur = self._turn_index
        cname = self._color_names[cur] if 0 <= cur < len(self._color_names) else ""
        hx = get_player_color_hex(cname)
        for lab in self._search_chip_labels():
            px = self._chip_home_px_for_label(lab)
            circ = get_player_circle_chip_pixmap(cname, px)
            lab.set_hotseat_chip("circle", hx)
            lab.setFixedSize(px, px)
            lab.setPixmap(circ)
        for lab in self._sharing_chip_labels():
            px = self._chip_home_px_for_label(lab)
            sq = get_player_square_chip_pixmap(cname, px)
            lab.set_hotseat_chip("square", hx)
            lab.setFixedSize(px, px)
            lab.setPixmap(sq)


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
        #: Map-strip proxy item cursor; viewport mirror (Windows often ignores ``QGraphicsProxyWidget`` cursors).
        self._hotseat_strip_proxy_cursor_set: bool = False
        self._hotseat_strip_viewport_cursor_mirrored: bool = False
        #: ``setOverrideCursor(OpenHand)`` while over a movable strip chip (reliable on Windows).
        self._hotseat_strip_override_cursor_active: bool = False
        self._hotseat_dbg_strip_cursor_last_t: float = 0.0
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
        self._clear_hotseat_map_strip_cursor()
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
        self.unsetCursor()
        self._hotseat_strip_viewport_cursor_mirrored = False
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
        self.unsetCursor()
        self._hotseat_strip_viewport_cursor_mirrored = False
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
            and self._map_chip_strip_proxy is not None
        ):
            self.sync_hotseat_map_strip_proxy_item_cursor()
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

    def _hotseat_strip_restore_override_cursor_if_any(self) -> None:
        if not self._hotseat_strip_override_cursor_active:
            return
        app = QApplication.instance()
        if app is not None:
            app.restoreOverrideCursor()
        self._hotseat_strip_override_cursor_active = False

    def _hotseat_strip_ensure_override_open_hand(self) -> None:
        if self._hotseat_strip_override_cursor_active:
            return
        app = QApplication.instance()
        if app is not None:
            app.setOverrideCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._hotseat_strip_override_cursor_active = True

    def _clear_hotseat_map_strip_cursor(self) -> None:
        """Unset strip proxy cursor and any viewport mirror from ``sync_hotseat_map_strip_proxy_item_cursor``."""
        p = self._map_chip_strip_proxy
        if p is not None and self._hotseat_strip_proxy_cursor_set:
            p.unsetCursor()
            self._hotseat_strip_proxy_cursor_set = False
        if self._hotseat_strip_viewport_cursor_mirrored:
            self.viewport().unsetCursor()
            self.unsetCursor()
            self._hotseat_strip_viewport_cursor_mirrored = False
        self._hotseat_strip_restore_override_cursor_if_any()

    def _debug_hotseat_strip_cursor_row(
        self,
        *,
        where: str,
        carry: str | None = None,
        lf: QPoint | None = None,
        fw: int | None = None,
        fh: int | None = None,
        child: str | None = None,
        chip_shape: str | None = None,
        shadow: bool | None = None,
        action: str | None = None,
    ) -> None:
        if not _HOTSEAT_DEBUG_STRIP_CURSOR:
            return
        now = time.monotonic()
        if now - self._hotseat_dbg_strip_cursor_last_t < 0.15:
            return
        self._hotseat_dbg_strip_cursor_last_t = now
        parts = [
            f"where={where}",
            f"carry={carry!r}",
        ]
        if lf is not None and fw is not None and fh is not None:
            parts.append(f"lf=({lf.x()},{lf.y()}) size=({fw}x{fh})")
        elif fw is not None and fh is not None:
            parts.append(f"size=({fw}x{fh})")
        if child is not None:
            parts.append(f"childAt={child}")
        if chip_shape is not None:
            parts.append(f"chip_shape={chip_shape}")
        if shadow is not None:
            parts.append(f"shadow={shadow}")
        if action is not None:
            parts.append(f"action={action}")
        print("[hotseat strip cursor]", " ".join(parts), flush=True)

    def _hotseat_strip_chip_at_global(
        self, strip_root: QWidget, global_pos: QPoint
    ) -> _HotseatChipDragLabel | None:
        """Bank chip under the cursor: ``childAt`` when mapped local pos is in-strip, else ``widgetAt`` + ``isAncestorOf``."""
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
            self._debug_hotseat_strip_cursor_row(where="no_proxy")
            return
        if self._hotseat_bank_carry is not None:
            self._clear_hotseat_map_strip_cursor()
            self._debug_hotseat_strip_cursor_row(
                where="bank_carry_skip", carry=str(self._hotseat_bank_carry)
            )
            return
        w = p.widget()
        if w is None:
            self._debug_hotseat_strip_cursor_row(where="no_strip_widget")
            return
        fw, fh = w.width(), w.height()
        if fw <= 0 or fh <= 0:
            self._clear_hotseat_map_strip_cursor()
            self._debug_hotseat_strip_cursor_row(
                where="strip_zero_size", fw=fw, fh=fh, action="unset_if_was_set"
            )
            return
        gw = QCursor.pos()
        chip = self._hotseat_strip_chip_at_global(w, gw)
        lf = w.mapFromGlobal(gw)
        top = QApplication.widgetAt(gw)
        top_name = type(top).__name__ if top is not None else "None"
        over_strip_geom = 0 <= lf.x() < fw and 0 <= lf.y() < fh
        over_strip_native = top is not None and w.isAncestorOf(top)
        over_strip = over_strip_geom or over_strip_native
        if chip is None:
            self._clear_hotseat_map_strip_cursor()
            self._debug_hotseat_strip_cursor_row(
                where="no_chip_on_strip" if over_strip else "not_over_strip",
                lf=lf,
                fw=fw,
                fh=fh,
                child=top_name,
                action="unset_if_was_set",
            )
            return
        sh = getattr(chip, "_shadow", False)
        child_name = type(chip).__name__
        if sh:
            self._hotseat_strip_restore_override_cursor_if_any()
            cur = QCursor(Qt.CursorShape.ArrowCursor)
            p.setCursor(cur)
            self.viewport().setCursor(cur)
            self.setCursor(cur)
            chip.setCursor(cur)
            self._hotseat_strip_proxy_cursor_set = True
            self._hotseat_strip_viewport_cursor_mirrored = True
            self._debug_hotseat_strip_cursor_row(
                where="chip_shadow",
                lf=lf,
                fw=fw,
                fh=fh,
                child=child_name,
                chip_shape=getattr(chip, "_shape", "?"),
                shadow=True,
                action="proxy_ArrowCursor",
            )
        else:
            cur = QCursor(Qt.CursorShape.OpenHandCursor)
            p.setCursor(cur)
            self.viewport().setCursor(cur)
            self.setCursor(cur)
            chip.setCursor(cur)
            self._hotseat_strip_proxy_cursor_set = True
            self._hotseat_strip_viewport_cursor_mirrored = True
            self._hotseat_strip_ensure_override_open_hand()
            self._debug_hotseat_strip_cursor_row(
                where="chip_ok",
                lf=lf,
                fw=fw,
                fh=fh,
                child=child_name,
                chip_shape=getattr(chip, "_shape", "?"),
                shadow=sh,
                action="override_OpenHandCursor",
            )

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
        # Find a placed additional-sharing square (movable) and send it home.
        for ch in list(canvas.chip_slot.keys()):
            if getattr(ch, "_hotseat_from_sharing_bank", False) and getattr(ch, "shape_kind", None) == "square":
                try:
                    canvas.release_chip(ch)
                    ch._apply_bank_home_after_release_off_hex()
                    canvas.notify_undo_checkpoint()
                except Exception:
                    pass
                break

    def lock_all_map_chips(self) -> None:
        """Freeze every placed map chip so no chip can be moved between turns."""
        bb = self._hotseat_board_builder
        if bb is None or bb.canvas is None:
            return
        for chip in list(bb.canvas.chip_slot.keys()):
            try:
                chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                chip.setCursor(Qt.CursorShape.ArrowCursor)
            except Exception:
                pass
        self._notify_end_turn_eligibility_changed()

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
        bb = self._hotseat_board_builder
        if bb is not None and bb.canvas is not None and chip in bb.canvas.chip_slot:
            bb.canvas.release_chip(chip)
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
        self.unsetCursor()
        self._hotseat_strip_viewport_cursor_mirrored = False

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
            chip.setCursor(Qt.CursorShape.ArrowCursor)
            self._remove_question_picker_overlay_only()
            if slot is not None:
                bb._relayout_hex_figures(slot[0], slot[1], slot[2])
            bb.canvas.notify_undo_checkpoint()
            sb._hotseat_question_used = True
            sb._hotseat_last_question_target_idx = answered_player_idx
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
            chip.setCursor(Qt.CursorShape.ArrowCursor)
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
                new_chip.setCursor(Qt.CursorShape.ArrowCursor)
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
            sb._hotseat_last_question_target_idx = None
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

    def _computer_iter_hex_cells(self) -> list[tuple[int, int, int, int, int]]:
        """All playable hex slots as (row, col, cell_idx, y, x)."""
        bb = self._hotseat_board_builder
        if bb is None or bb.canvas is None or bb.controller is None:
            return []
        out: list[tuple[int, int, int, int, int]] = []
        for (row, col), piece in bb.canvas.occupied.items():
            if piece is None:
                continue
            cells = getattr(piece, "cells", [])
            for cell_idx in range(len(cells)):
                coords = bb.controller.cell_big_coords(piece, cell_idx)
                if coords is None:
                    continue
                y, x = coords
                out.append((row, col, cell_idx, y, x))
        return out

    def _computer_build_conditions_grid(self) -> Any | None:
        bb = self._hotseat_board_builder
        if bb is None or bb.controller is None:
            return None
        try:
            return compute_all_conditions(
                bb.controller.build_current_map(),
                advanced_mode=self._hotseat_advanced_mode,
            )
        except Exception:
            return None

    def _computer_player_color_hex(self, player_index: int) -> str:
        sb = self._gameplay_sidebar
        if sb is None:
            return ""
        cname = sb._color_names[player_index] if 0 <= player_index < len(sb._color_names) else ""
        return get_player_color_hex(cname)

    def _computer_place_square_random(self) -> bool:
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or bb.controller is None or sc is None:
            return False
        if not sb.may_drag_sharing_chip_from_bank():
            return False
        cur = getattr(sb, "_turn_index", 0)
        hx = self._computer_player_color_hex(cur).lower()
        clue = sb.clue_text_for_player(cur)
        grid = self._computer_build_conditions_grid()
        matched = _hotseat_match_clue_to_grid(clue, grid) if grid is not None and clue else None
        candidates: list[tuple[int, int, int]] = []
        for row, col, cell_idx, y, x in self._computer_iter_hex_cells():
            if matched is not None and matched in grid.rules_true_at_hex(y, x):
                continue
            existing = bb.canvas.chip_occupied.get((row, col, cell_idx), [])
            n_square = sum(1 for c in existing if getattr(c, "shape_kind", None) == "square")
            colors_used = {(getattr(c, "fill_color", "") or "").lower() for c in existing}
            if len(existing) + 1 > 4:
                continue
            if n_square + 1 > 1:
                continue
            if hx in colors_used:
                continue
            candidates.append((row, col, cell_idx))
        if not candidates:
            return False
        row, col, cell_idx = random.choice(candidates)
        chip = ChipItem("square", hx)
        chip._hotseat_from_sharing_bank = True
        chip.set_canvas(bb.canvas)
        view = self

        def _home() -> QPointF:
            return sb.hotseat_chip_home_scene(view, "share")

        chip.set_hotseat_home_resolver(_home)
        chip.setZValue(5000)
        chip.setScale(MARKER_SCALE_CANVAS)
        sc.addItem(chip)
        bb.canvas.assign_chip(chip, row, col, cell_idx)
        bb.canvas.notify_undo_checkpoint()
        sb._hotseat_sharing_square_used = True
        sb.sync_hotseat_sharing_bank_visibility()
        self._notify_end_turn_eligibility_changed()
        return True

    def _computer_resolve_question_chip(
        self, chip: ChipItem, answered_player_idx: int
    ) -> bool:
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        if sb is None or bb is None or bb.canvas is None or bb.controller is None:
            return False
        hx = self._computer_player_color_hex(answered_player_idx)
        slot = bb.canvas.chip_slot.get(chip)
        if slot is None:
            return False
        r, c0, cell_idx = slot
        existing = [
            c for c in bb.canvas.chip_occupied.get((r, c0, cell_idx), []) if c is not chip
        ]
        if hx.lower() in {(getattr(c, "fill_color", "") or "").lower() for c in existing}:
            return False
        shape: Literal["circle", "square"] = "circle"
        clue = sb.clue_text_for_player(answered_player_idx)
        coords = bb.controller.cell_big_coords(
            bb.canvas.occupied.get((r, c0)), cell_idx
        ) if bb.canvas.occupied.get((r, c0)) is not None else None
        if clue and coords is not None:
            y, x = coords
            grid = self._computer_build_conditions_grid()
            if grid is not None:
                matched = _hotseat_match_clue_to_grid(clue, grid)
                if matched is not None:
                    shape = "circle" if matched in grid.rules_true_at_hex(y, x) else "square"
        if shape == "square":
            n_square = sum(1 for c in existing if getattr(c, "shape_kind", None) == "square")
            if n_square >= 1:
                return False
        chip.resolve_hotseat_question(hx, shape_kind=shape)
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        chip.setCursor(Qt.CursorShape.ArrowCursor)
        bb._relayout_hex_figures(r, c0, cell_idx)
        bb.canvas.notify_undo_checkpoint()
        sb._hotseat_question_used = True
        sb._hotseat_last_question_target_idx = answered_player_idx
        try:
            if chip.shape_kind == "circle":
                occ2 = bb.canvas.chip_occupied.get((r, c0, cell_idx), [])
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
        sb._hotseat_map_strip_sharing_question_row = bool(resolved_square)
        sb._hotseat_map_strip_sharing_search_row = False
        sb.sync_hotseat_question_bank_visibility()
        sb.sync_hotseat_search_bank_visibility()
        sb.sync_hotseat_map_strip_sharing_rows()
        sb.sync_hotseat_sharing_bank_visibility()
        sb._schedule_map_chip_strip_layout_bump()
        sb.geometry_needs_update.emit()
        self._notify_end_turn_eligibility_changed()
        return True

    def _computer_question_random(self) -> bool:
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or sc is None:
            return False
        sb.set_question_or_search(False)
        if not sb.may_drag_question_chip_from_bank():
            return False
        others = sb.other_player_slots()
        if not others:
            return False
        grid = self._computer_build_conditions_grid()
        matched_by_player: dict[int, str | None] = {}
        if grid is not None:
            for pl_idx, _ in others:
                matched_by_player[pl_idx] = _hotseat_match_clue_to_grid(
                    sb.clue_text_for_player(pl_idx), grid
                )
        candidates: list[tuple[int, int, int, list[int]]] = []
        for row, col, cell_idx, y, x in self._computer_iter_hex_cells():
            existing = bb.canvas.chip_occupied.get((row, col, cell_idx), [])
            if any(getattr(c, "shape_kind", None) == "square" for c in existing):
                continue
            if len(existing) + 1 > 4:
                continue
            colors_used = {(getattr(c, "fill_color", "") or "").lower() for c in existing}
            n_square = sum(1 for c in existing if getattr(c, "shape_kind", None) == "square")
            valid_players: list[int] = []
            for pl_idx, cname in others:
                hx = get_player_color_hex(cname).lower()
                if hx in colors_used:
                    continue
                resp_shape: Literal["circle", "square"] = "circle"
                matched = matched_by_player.get(pl_idx)
                if matched is not None and grid is not None:
                    resp_shape = "circle" if matched in grid.rules_true_at_hex(y, x) else "square"
                if resp_shape == "square" and n_square >= 1:
                    continue
                valid_players.append(pl_idx)
            if valid_players:
                candidates.append((row, col, cell_idx, valid_players))
        if not candidates:
            return False
        row, col, cell_idx, valid_players = random.choice(candidates)
        answered_player_idx = random.choice(valid_players)
        chip = ChipItem("circle", _HOTSEAT_QUESTION_CHIP_HEX, question_mark=True)
        chip.set_canvas(bb.canvas)
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        chip.setCursor(Qt.CursorShape.ArrowCursor)
        view = self

        def _home() -> QPointF:
            return sb.hotseat_chip_home_scene(view, "question")

        chip.set_hotseat_home_resolver(_home)
        chip.setZValue(5000)
        chip.setScale(MARKER_SCALE_CANVAS)
        sc.addItem(chip)
        bb.canvas.assign_chip(chip, row, col, cell_idx)
        return self._computer_resolve_question_chip(chip, answered_player_idx)

    def _computer_resolve_search_chip(self, chip: ChipItem) -> bool:
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or bb.controller is None or sc is None:
            return False
        slot = bb.canvas.chip_slot.get(chip)
        if slot is None:
            return False
        r, c0, cell_idx = slot
        piece = bb.canvas.occupied.get((r, c0))
        if piece is None:
            return False
        coords = bb.controller.cell_big_coords(piece, cell_idx)
        if coords is None:
            return False
        y, x = coords
        grid = self._computer_build_conditions_grid()
        if grid is None:
            return False
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        chip.setCursor(Qt.CursorShape.ArrowCursor)
        clockwise = sb.other_player_slots_clockwise()
        placed_square = False
        occ0 = bb.canvas.chip_occupied.get((r, c0, cell_idx), [])
        already_circle_colors = {
            (getattr(c, "fill_color", "") or "").lower()
            for c in occ0
            if getattr(c, "shape_kind", None) == "circle"
            and not getattr(c, "_question_mark", False)
        }
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
            new_chip.setCursor(Qt.CursorShape.ArrowCursor)
            view = self

            def _home() -> QPointF:
                return sb.hotseat_chip_home_scene(view, "search")

            new_chip.set_hotseat_home_resolver(_home)
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
        sb._hotseat_last_question_target_idx = None
        try:
            occ = bb.canvas.chip_occupied.get((r, c0, cell_idx), [])
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
        sb._hotseat_map_strip_sharing_search_row = bool(placed_square)
        sb._hotseat_map_strip_sharing_question_row = False
        sb.sync_hotseat_search_bank_visibility()
        sb.sync_hotseat_question_bank_visibility()
        sb.sync_hotseat_map_strip_sharing_rows()
        sb.sync_hotseat_sharing_bank_visibility()
        if placed_square:
            sb._schedule_map_chip_strip_layout_bump()
        sb.geometry_needs_update.emit()
        self._notify_end_turn_eligibility_changed()
        return True

    def _computer_search_random(self) -> bool:
        sb = self._gameplay_sidebar
        bb = self._hotseat_board_builder
        sc = self.scene()
        if sb is None or bb is None or bb.canvas is None or bb.controller is None or sc is None:
            return False
        sb.set_question_or_search(True)
        if not sb.may_drag_search_chip_from_bank():
            return False
        cur = getattr(sb, "_turn_index", 0)
        hx_cur = self._computer_player_color_hex(cur).lower()
        grid = self._computer_build_conditions_grid()
        clue_cur = sb.clue_text_for_player(cur)
        matched_cur = _hotseat_match_clue_to_grid(clue_cur, grid) if grid is not None and clue_cur else None
        existing_circle_candidates: list[ChipItem] = []
        new_candidates: list[tuple[int, int, int]] = []
        for row, col, cell_idx, y, x in self._computer_iter_hex_cells():
            existing = bb.canvas.chip_occupied.get((row, col, cell_idx), [])
            if any(getattr(c, "shape_kind", None) == "square" for c in existing):
                continue
            if matched_cur is not None and grid is not None and matched_cur not in grid.rules_true_at_hex(y, x):
                continue
            colors_used = {(getattr(c, "fill_color", "") or "").lower() for c in existing}
            if hx_cur in colors_used:
                same_circle = next(
                    (
                        c
                        for c in existing
                        if getattr(c, "shape_kind", None) == "circle"
                        and not getattr(c, "_question_mark", False)
                        and (getattr(c, "fill_color", "") or "").lower() == hx_cur
                    ),
                    None,
                )
                if same_circle is not None:
                    existing_circle_candidates.append(same_circle)
                continue
            n_square = sum(1 for c in existing if getattr(c, "shape_kind", None) == "square")
            if len(existing) + 1 > 4:
                continue
            if n_square > 1:
                continue
            new_candidates.append((row, col, cell_idx))
        if not existing_circle_candidates and not new_candidates:
            return False
        if existing_circle_candidates and new_candidates:
            use_existing = random.choice((True, False))
        else:
            use_existing = bool(existing_circle_candidates)
        if use_existing:
            chip = random.choice(existing_circle_candidates)
            return self._computer_resolve_search_chip(chip)
        row, col, cell_idx = random.choice(new_candidates)
        chip = ChipItem("circle", hx_cur)
        chip.set_canvas(bb.canvas)
        chip.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        chip.setCursor(Qt.CursorShape.ArrowCursor)
        view = self

        def _home() -> QPointF:
            return sb.hotseat_chip_home_scene(view, "search")

        chip.set_hotseat_home_resolver(_home)
        chip.setZValue(5000)
        chip.setScale(MARKER_SCALE_CANVAS)
        sc.addItem(chip)
        bb.canvas.assign_chip(chip, row, col, cell_idx)
        return self._computer_resolve_search_chip(chip)

    def run_hotseat_computer_turn(self) -> bool:
        """Play one full computer turn using the same rule constraints as manual turns."""
        sb = self._gameplay_sidebar
        if sb is None:
            return False
        if int(getattr(sb, "_round_num", 1)) <= 2:
            return self._computer_place_square_random()
        actions = [self._computer_question_random, self._computer_search_random]
        random.shuffle(actions)
        moved = False
        for fn in actions:
            if fn():
                moved = True
                break
        if not moved:
            return False
        if (
            sb._hotseat_map_strip_sharing_question_row
            or sb._hotseat_map_strip_sharing_search_row
        ) and not sb._hotseat_sharing_square_used:
            if not self._computer_place_square_random():
                return False
        return True

    def set_gameplay_sidebar(self, sidebar: HotseatGameplaySidebar) -> None:
        self._gameplay_sidebar = sidebar
        sidebar.hotseat_board_view = self

    def detach_map_chip_strip_proxy(self) -> None:
        self._clear_hotseat_map_strip_cursor()
        p = self._map_chip_strip_proxy
        self._map_chip_strip_proxy = None
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
        # Strip moved/resized without a mouse move (e.g. after question confirm): refresh proxy cursor.
        self.sync_hotseat_map_strip_proxy_item_cursor()

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
        result = super().viewportEvent(event)
        # QGraphicsView updates the viewport cursor from the top scene item *after* any
        # eventFilter; re-sync strip cursor so proxy + viewport mirror stay visible (Windows).
        if (
            event.type() in (QEvent.Type.MouseMove, QEvent.Type.HoverMove)
            and self._hotseat_bank_carry is None
            and self._map_chip_strip_proxy is not None
        ):
            self.sync_hotseat_map_strip_proxy_item_cursor()
        return result

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


class HotseatBoardPanel(QWidget):
    """Builds a BoardView for a single loaded map (no simulation / rules)."""

    session_ended = Signal()
    end_turn_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._turn_index: int = 0
        self._round_num: int = 1
        self._computer_flags: list[bool] = []
        self._computer_turn_running: bool = False
        self._win_dialog_shown: bool = False
        self._turn_start_chip_ids: set[int] = set()
        self._turn_placed_chip_ids: set[int] = set()
        self._history_pulse_chip: ChipItem | None = None
        self._history_pulse_timer: QTimer | None = None
        self._history_pulse_started: float = 0.0
        self._history_pulse_z_before: float | None = None
        self._history_pulse_dim: QGraphicsPathItem | None = None
        _win = self.window()
        self._figures_hover_tooltip = HoverTooltipManager(
            _win if isinstance(_win, QWidget) else self, self
        )
        self._map_data: dict[str, Any] | None = None
        self._habitat_hex: tuple[int, int] | None = None
        self._scene = QGraphicsScene(self)
        self._view = HotseatBoardView(self._scene)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._board_builder = BoardBuilder(self._scene, self._view)

        self._sidebar = HotseatGameplaySidebar(self)
        self._sidebar.setMinimumWidth(280)
        self._sidebar.hide()
        self._view.set_gameplay_sidebar(self._sidebar)

        self._sidebar.geometry_needs_update.connect(self._schedule_fit_hotseat_board)
        self._sidebar.history_chip_focus_requested.connect(
            self._on_history_chip_focus_requested
        )

        ms = self._sidebar.map_chip_strip
        if ms is not None:
            ms.hide()

        self._map_column = QWidget(self)
        self._map_column.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        map_col_lay = QVBoxLayout(self._map_column)
        map_col_lay.setContentsMargins(0, 0, 0, 0)
        map_col_lay.setSpacing(8)
        status = self._sidebar.status_panel
        if status is not None:
            map_col_lay.addWidget(status, 0)
        map_col_lay.addWidget(self._view, 0)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(8)
        # Top-align: map view height is capped by terrain fit; sidebar height is synced to match (see _constrain_view_to_terrain).
        main_row.addWidget(self._map_column, 3, Qt.AlignmentFlag.AlignTop)
        main_row.addWidget(self._sidebar, 1, Qt.AlignmentFlag.AlignTop)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 8, 0, 0)
        bottom_row.setSpacing(4)
        bottom_row.addStretch(1)
        self._btn_end_turn = QPushButton("End Turn")
        self._btn_end_turn.setObjectName("btnHotseatEndTurn")
        self._btn_end_turn.setProperty("primary", True)
        st_et = self._btn_end_turn.style()
        if st_et is not None:
            st_et.unpolish(self._btn_end_turn)
            st_et.polish(self._btn_end_turn)
        self._btn_end_turn.clicked.connect(self._on_end_turn_clicked)
        # Disabled QPushButton often never receives hover on Windows, so tooltips don't show.
        # Host keeps the tooltip; when disabled the button uses WA_TransparentForMouseEvents
        # so hover hits the host (see _apply_end_turn_tooltip_look).
        self._end_turn_tooltip_host = QWidget()
        self._end_turn_tooltip_host.setObjectName("hotseatEndTurnTooltipHost")
        # Match Solver Tool behavior: use HoverTooltipManager (custom rounded tooltip).
        self._figures_hover_tooltip.add(
            self._end_turn_tooltip_host,
            HOTSEAT_END_TURN_DISABLED_TOOLTIP,
            only_when_disabled=False,
            only_when=lambda: not self._end_turn_allowed(),
        )
        _et_lay = QHBoxLayout(self._end_turn_tooltip_host)
        _et_lay.setContentsMargins(0, 0, 0, 0)
        _et_lay.setSpacing(0)
        _et_lay.addWidget(self._btn_end_turn)
        self._btn_end_turn.setEnabled(False)
        self._apply_end_turn_tooltip_look(False)
        bottom_row.addWidget(self._end_turn_tooltip_host, 0, Qt.AlignmentFlag.AlignRight)
        self._btn_end_game = QPushButton("End Game")
        self._btn_end_game.setObjectName("btnHotseatEndGame")
        self._btn_end_game.setProperty("secondary", True)
        st = self._btn_end_game.style()
        if st is not None:
            st.unpolish(self._btn_end_game)
            st.polish(self._btn_end_game)
        self._btn_end_game.clicked.connect(self._on_end_game_clicked)
        bottom_row.addWidget(self._btn_end_game, 0, Qt.AlignmentFlag.AlignRight)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(main_row, 1)
        outer.addLayout(bottom_row, 0)
        self.setLayout(outer)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sidebar.geometry_needs_update.connect(self._sync_end_turn_button)

    def _on_end_turn_clicked(self) -> None:
        if not self._end_turn_allowed():
            return
        self._append_current_turn_history()
        self._view.lock_all_map_chips()
        # Advance turn locally (Play Hotseat controller doesn't currently subscribe to end_turn_clicked).
        n = getattr(self._sidebar, "_n", 0)
        if n > 0:
            next_idx = (self._turn_index + 1) % n
            if next_idx == 0:
                self._round_num = max(1, int(self._round_num) + 1)
                self.set_hotseat_round(self._round_num)
            self._turn_index = next_idx
            self.set_hotseat_turn_index(self._turn_index)
            self._snapshot_turn_start_chips()
            self._begin_current_turn()
        self.end_turn_clicked.emit()

    def _snapshot_turn_start_chips(self) -> None:
        bb = self._board_builder
        if bb is None or bb.canvas is None:
            self._turn_start_chip_ids = set()
            self._turn_placed_chip_ids = set()
            return
        self._turn_start_chip_ids = {id(chip) for chip in bb.canvas.chip_slot}
        self._turn_placed_chip_ids = set()

    def _note_chip_assigned_for_history(self, chip: Any) -> None:
        """Record chips placed this turn (ignored again if already present at turn start)."""
        cid = id(chip)
        if cid not in self._turn_start_chip_ids:
            self._turn_placed_chip_ids.add(cid)

    def _note_chip_released_for_history(self, chip: Any) -> None:
        """Drop undone / returned chips so they are not listed in turn history."""
        self._turn_placed_chip_ids.discard(id(chip))

    def _describe_chip_for_history(self, chip: Any) -> tuple[str, str]:
        shape = getattr(chip, "shape_kind", None)
        if getattr(chip, "_question_mark", False):
            shape_txt = "question"
        elif shape == "circle":
            shape_txt = "circle"
        elif shape == "square":
            shape_txt = "square"
        else:
            shape_txt = "circle"
        color_hex = getattr(chip, "fill_color", "") or ""
        return (shape_txt, color_hex)

    def _chips_added_this_turn(self) -> list[HistoryChipRef]:
        bb = self._board_builder
        if bb is None or bb.canvas is None:
            return []
        out: list[HistoryChipRef] = []
        for chip in list(bb.canvas.chip_slot.keys()):
            if id(chip) not in self._turn_placed_chip_ids:
                continue
            if chip.scene() is None:
                continue
            slot = bb.canvas.chip_slot.get(chip)
            if slot is None:
                continue
            shape_txt, color_hex = self._describe_chip_for_history(chip)
            out.append((shape_txt, color_hex, slot[0], slot[1], slot[2]))
        return out

    def _action_for_current_turn(self) -> tuple[str, int | None]:
        sb = self._sidebar
        if sb._is_initial_sharing_round():
            return ("Initial sharing", None)
        if sb._hotseat_search_used:
            return ("Search", None)
        if sb._hotseat_question_used:
            return ("Question", sb._hotseat_last_question_target_idx)
        return ("—", None)

    def _append_current_turn_history(self) -> None:
        n = getattr(self._sidebar, "_n", 0)
        if n <= 0:
            return
        action, asked_idx = self._action_for_current_turn()
        self._sidebar.append_turn_history_row(
            round_num=self._round_num,
            player_index=self._turn_index,
            action=action,
            question_target_idx=asked_idx,
            chips_placed=self._chips_added_this_turn(),
        )

    def _on_history_chip_focus_requested(
        self,
        shape_kind: str,
        color_hex: str,
        row: int,
        col: int,
        cell_idx: int,
    ) -> None:
        chip = self._find_history_chip(shape_kind, color_hex, row, col, cell_idx)
        if chip is None:
            return
        self._start_history_chip_pulse(chip)

    def _find_history_chip(
        self,
        shape_kind: str,
        color_hex: str,
        row: int,
        col: int,
        cell_idx: int,
    ) -> ChipItem | None:
        bb = self._board_builder
        if bb is None or bb.canvas is None:
            return None
        want_color = (color_hex or "").lower()
        for chip in bb.canvas.chip_occupied.get((row, col, cell_idx), []):
            if chip.scene() is None:
                continue
            is_q = bool(getattr(chip, "_question_mark", False))
            chip_shape = "question" if is_q else str(getattr(chip, "shape_kind", "") or "")
            if chip_shape != shape_kind:
                continue
            if (getattr(chip, "fill_color", "") or "").lower() != want_color:
                continue
            return chip
        return None

    def _start_history_chip_pulse(self, chip: ChipItem) -> None:
        self._clear_history_chip_pulse()
        sc = chip.scene()
        if sc is None:
            return
        self._history_pulse_chip = chip
        self._history_pulse_z_before = float(chip.zValue())
        # Dim only the map canvas (not the chip strip / other scene UI below it).
        map_rect = QRectF()
        bb = self._board_builder
        if bb is not None and getattr(bb, "canvas", None) is not None:
            cr = bb.canvas.rect
            if cr.isValid():
                map_rect = QRectF(cr)
        if not map_rect.isValid():
            fr = self._view.hotseat_canvas_fit_rect()
            if fr is not None and fr.isValid():
                map_rect = QRectF(fr)
        if not map_rect.isValid():
            map_rect = self._view.terrain_scene_rect_excluding_ui_proxies()
        if not map_rect.isValid():
            return
        path = QPainterPath()
        path.addRoundedRect(map_rect, float(CANVAS_RADIUS), float(CANVAS_RADIUS))
        dim = QGraphicsPathItem(path)
        dim.setBrush(QBrush(QColor(0, 0, 0, int(255 * _HISTORY_DIM_ALPHA))))
        dim.setPen(QPen(Qt.PenStyle.NoPen))
        dim.setZValue(_HISTORY_DIM_Z)
        dim.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        sc.addItem(dim)
        self._history_pulse_dim = dim
        chip.setZValue(max(self._history_pulse_z_before, _HISTORY_CHIP_FOCUS_Z))
        self._history_pulse_started = time.monotonic()
        chip.set_history_pulse(1.0)
        timer = QTimer(self)
        timer.setInterval(33)
        timer.timeout.connect(self._on_history_chip_pulse_tick)
        self._history_pulse_timer = timer
        timer.start()

    def _on_history_chip_pulse_tick(self) -> None:
        chip = self._history_pulse_chip
        if chip is None or chip.scene() is None:
            self._clear_history_chip_pulse()
            return
        elapsed_ms = (time.monotonic() - self._history_pulse_started) * 1000.0
        if elapsed_ms >= _HISTORY_CHIP_PULSE_MS:
            self._clear_history_chip_pulse()
            return
        t = elapsed_ms / float(_HISTORY_CHIP_PULSE_MS)
        envelope = max(0.0, 1.0 - t)
        # ~2 soft beats over 2 seconds, fading out.
        wave = 0.5 + 0.5 * math.sin(2.0 * math.pi * 1.0 * (elapsed_ms / 1000.0))
        alpha = envelope * (0.25 + 0.75 * wave)
        chip.set_history_pulse(alpha)
        dim = self._history_pulse_dim
        if dim is not None:
            try:
                dim.setBrush(
                    QBrush(QColor(0, 0, 0, int(255 * _HISTORY_DIM_ALPHA * envelope)))
                )
            except RuntimeError:
                pass

    def _clear_history_chip_pulse(self) -> None:
        timer = self._history_pulse_timer
        self._history_pulse_timer = None
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        dim = self._history_pulse_dim
        self._history_pulse_dim = None
        if dim is not None:
            try:
                sc = dim.scene()
                if sc is not None:
                    sc.removeItem(dim)
            except RuntimeError:
                pass
        chip = self._history_pulse_chip
        self._history_pulse_chip = None
        if chip is not None:
            try:
                chip.clear_history_pulse()
                if self._history_pulse_z_before is not None:
                    chip.setZValue(self._history_pulse_z_before)
            except RuntimeError:
                pass
        self._history_pulse_z_before = None

    def show_next_turn_dialog(self) -> None:
        """Enter current turn: modal for humans, auto-play for computer players."""
        self._begin_current_turn()

    def _is_computer_turn(self, idx: int | None = None) -> bool:
        player_idx = self._turn_index if idx is None else idx
        if player_idx < 0:
            return False
        if player_idx >= len(self._computer_flags):
            return False
        return bool(self._computer_flags[player_idx])

    def _begin_current_turn(self) -> None:
        if self._map_data is None:
            return
        self._ensure_pending_turn_history_row()
        if self._is_computer_turn():
            QTimer.singleShot(0, self._run_computer_turn)
            return
        self._show_next_turn_dialog(self._turn_index)

    def _ensure_pending_turn_history_row(self) -> None:
        n = getattr(self._sidebar, "_n", 0)
        if n <= 0:
            return
        self._sidebar.begin_turn_history_row(
            round_num=self._round_num,
            player_index=self._turn_index,
        )

    def _run_computer_turn(self) -> None:
        if self._computer_turn_running or self._map_data is None or self._win_dialog_shown:
            return
        if not self._is_computer_turn():
            return
        self._computer_turn_running = True
        try:
            acted = self._view.run_hotseat_computer_turn()
            self._sync_end_turn_button()
            if not acted or self._win_dialog_shown:
                return
            if self._end_turn_allowed():
                QTimer.singleShot(0, self._on_end_turn_clicked)
        finally:
            self._computer_turn_running = False

    def _on_hotseat_game_finished(self, *, winner_index: int) -> None:
        if self._win_dialog_shown:
            return
        self._win_dialog_shown = True
        if getattr(self._sidebar, "_turn_history_pending", False):
            self._append_current_turn_history()
        sb = self._sidebar
        names = getattr(sb, "_names", []) if sb is not None else []
        color_names = getattr(sb, "_color_names", []) if sb is not None else []
        n = int(getattr(sb, "_n", 0)) if sb is not None else 0

        dlg = QDialog(self.window())
        dlg.setWindowTitle("Game finished")
        dlg.setModal(True)
        dlg.setObjectName("dlgHotseatGameFinished")

        def _meeple(color_name: str, px: int = 18) -> QLabel:
            lab = QLabel()
            try:
                lab.setPixmap(get_player_meeple_pixmap(color_name, px))
            except Exception:
                lab.clear()
            lab.setFixedSize(px + 2, px + 2)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lab

        winner_host = QWidget(dlg)
        winner_host.setObjectName("hotseatGameFinishedWinnerRow")
        winner_row = QHBoxLayout(winner_host)
        winner_row.setContentsMargins(0, 0, 0, 0)
        winner_row.setSpacing(6)
        winner_row.addWidget(QLabel("Winner:"), 0)
        w_color = color_names[winner_index] if 0 <= winner_index < len(color_names) else ""
        winner_row.addWidget(_meeple(w_color), 0)
        w_name = names[winner_index] if 0 <= winner_index < len(names) else f"Player {winner_index + 1}"
        winner_row.addWidget(QLabel(w_name), 1)

        rounds_host = QWidget(dlg)
        rounds_host.setObjectName("hotseatGameFinishedRoundsRow")
        rounds_row = QHBoxLayout(rounds_host)
        rounds_row.setContentsMargins(0, 0, 0, 0)
        rounds_row.setSpacing(6)
        rounds_row.addWidget(QLabel("Rounds:"), 0)
        rounds_row.addWidget(QLabel(str(self._round_num)), 1)

        clues_title = QLabel("Clues:")
        clues_title.setObjectName("hotseatGameFinishedCluesTitle")
        #clues_title.setStyleSheet("font-weight: 600;")

        clues_host = QWidget(dlg)
        clues_host.setObjectName("hotseatGameFinishedCluesHost")
        clues_lay = QVBoxLayout(clues_host)
        clues_lay.setContentsMargins(0, 0, 0, 0)
        clues_lay.setSpacing(2)
        clues_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        for i in range(max(0, n)):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            c_name = color_names[i] if i < len(color_names) else ""
            row.addWidget(_meeple(c_name), 0)
            p_name = names[i] if i < len(names) else f"Player {i + 1}"
            row.addWidget(QLabel(p_name), 0)
            clue_txt = sb.clue_text_for_player(i) if sb is not None else ""
            clue_lab = QLabel(clue_txt)
            clue_lab.setWordWrap(True)
            row.addWidget(clue_lab, 1)
            clues_lay.addLayout(row)

        # No scroll area: keep clues sized tightly to content (no extra blank space at end).
        clues_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )

        ok_row_host = QWidget(dlg)
        ok_row_host.setObjectName("hotseatGameFinishedOkRow")
        ok_btn = QPushButton("Ok", ok_row_host)
        ok_btn.setObjectName("hotseatGameFinishedOkButton")
        ok_btn.setProperty("primary", True)
        st = ok_btn.style()
        if st is not None:
            st.unpolish(ok_btn)
            st.polish(ok_btn)
        ok_btn.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout(ok_row_host)
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch(1)
        btn_row.addWidget(ok_btn, 0)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)
        outer.addWidget(winner_host, 0)
        outer.addWidget(rounds_host, 0)
        outer.addWidget(clues_title, 0)
        outer.addWidget(clues_host, 0)
        outer.addWidget(ok_row_host, 0)

        dlg.setMinimumWidth(420)
        # Prevent vertical stretching when the dialog is taller than its content.
        # Fix heights to sizeHint so no block absorbs extra space.
        try:
            dlg.ensurePolished()
            for w in (winner_host, rounds_host, clues_title, clues_host, ok_row_host):
                w.adjustSize()
                h = int(w.sizeHint().height())
                if h > 0:
                    w.setFixedHeight(h)
        except Exception:
            pass
        # Keep the dialog compact: size to content but cap height to avoid a giant window
        # when clues are long/wrapped.
        try:
            screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
            max_h = int(screen.height() * 0.65) if screen is not None else 520
            # Compute a tight height explicitly from the fixed-height blocks + layout spacing/margins.
            m = outer.contentsMargins()
            spacing = int(outer.spacing())
            blocks = (winner_host, rounds_host, clues_title, clues_host, ok_row_host)
            bh = sum(int(w.height()) for w in blocks)
            tight_h = int(m.top() + m.bottom() + bh + spacing * (len(blocks) - 1))
            if tight_h > 0:
                dlg.setFixedHeight(min(tight_h, max_h))
        except Exception:
            pass
        dlg.exec()
        self.session_ended.emit()

    def _show_next_turn_dialog(self, player_index: int) -> None:
        class _ForceFixedWidth(QObject):
            def __init__(self, box: QMessageBox, w: int) -> None:
                super().__init__(box)
                self._box = box
                self._w = int(w)
                self._in_apply = False

            def _apply(self) -> None:
                if self._in_apply:
                    return
                self._in_apply = True
                try:
                    self._box.setMinimumWidth(self._w)
                    self._box.setMaximumWidth(self._w)
                    self._box.setFixedWidth(self._w)
                finally:
                    self._in_apply = False

            def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt override)
                if obj is self._box and event.type() in (
                    QEvent.Type.Show,
                    QEvent.Type.Resize,
                    QEvent.Type.LayoutRequest,
                    QEvent.Type.Polish,
                    QEvent.Type.PolishRequest,
                ):
                    # QMessageBox recomputes its size during show/exec on Windows; re-apply width.
                    self._apply()
                    QTimer.singleShot(0, self._apply)
                return False

        sb = self._sidebar
        cname = ""
        if sb is not None and 0 <= player_index < len(getattr(sb, "_color_names", [])):
            cname = sb._color_names[player_index]
        mb = QMessageBox(self.window())
        mb.setWindowTitle("Next turn")
        mb.setText(f"Player {player_index + 1} turn")
        try:
            mb.setIconPixmap(get_player_meeple_pixmap(cname, 48))
        except Exception:
            pass
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        ok_btn = mb.addButton("Ok", QMessageBox.ButtonRole.AcceptRole)
        mb.setDefaultButton(ok_btn)
        ok_btn.setProperty("primary", True)
        st = ok_btn.style()
        if st is not None:
            st.unpolish(ok_btn)
            st.polish(ok_btn)
        layout = mb.findChild(QGridLayout)
        if layout:
            layout.setHorizontalSpacing(0)
        mb.ensurePolished()
        mb.adjustSize()
        mb.setWindowModality(Qt.WindowModality.ApplicationModal)
        fw = _ForceFixedWidth(mb, 320)
        mb.installEventFilter(fw)
        fw._apply()
        mb.show()
        mb.raise_()
        mb.activateWindow()
        QTimer.singleShot(0, fw._apply)
        loop = QEventLoop()
        mb.finished.connect(loop.quit)
        loop.exec()

    def _apply_end_turn_tooltip_look(self, ok: bool) -> None:
        """Show disabled tooltip via parent host; pass mouse through the button when disabled."""
        host = getattr(self, "_end_turn_tooltip_host", None)
        btn = getattr(self, "_btn_end_turn", None)
        if host is None or btn is None:
            return
        if ok:
            btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            host.setToolTip("")
            btn.setToolTip("")
        else:
            btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            # Custom tooltip manager handles the display (matches Solver Tool behavior).
            host.setToolTip("")
            btn.setToolTip("")

    def _end_turn_allowed(self) -> bool:
        sb = self._sidebar
        if not sb.isVisible() or self._map_data is None:
            return False
        if int(getattr(sb, "_round_num", 1)) <= 2:
            if not sb._hotseat_sharing_square_used:
                return False
        else:
            if not (sb._hotseat_question_used or sb._hotseat_search_used):
                return False
            # Additional sharing: Question/Search produced a square — strip square must be placed too.
            if (
                sb._hotseat_map_strip_sharing_question_row
                or sb._hotseat_map_strip_sharing_search_row
            ) and not sb._hotseat_sharing_square_used:
                return False
        v = self._view
        if getattr(v, "_qpick_chip", None) is not None:
            return False
        if getattr(v, "_hotseat_bank_carry", None) is not None:
            return False
        if sb._hotseat_sharing_square_carry:
            return False
        if sb._hotseat_question_carry or sb._hotseat_search_carry:
            return False
        bb = self._board_builder
        if bb is None or bb.canvas is None:
            return True
        c = bb.canvas
        for ch in c.chip_slot:
            if getattr(ch, "_question_mark", False):
                return False
            if ch.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                # Allow movable additional-sharing squares; they can be repositioned or returned home.
                if getattr(ch, "shape_kind", None) == "square" and getattr(
                    ch, "_hotseat_from_sharing_bank", False
                ):
                    continue
                return False
        return True

    def _sync_end_turn_button(self) -> None:
        if not hasattr(self, "_btn_end_turn"):
            return
        ok = self._end_turn_allowed()
        self._btn_end_turn.setEnabled(ok)
        self._apply_end_turn_tooltip_look(ok)

    def _on_end_game_clicked(self) -> None:
        # Match Solve page Reset All modal (reset_nav_mixin._on_reset_clicked_wrapper).
        mb = QMessageBox(self.window())
        mb.setWindowTitle(END_HOTSEAT_CONFIRM_TITLE)
        mb.setText(END_HOTSEAT_CONFIRM_MSG)
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        st_y = yes_btn.style()
        if st_y is not None:
            st_y.unpolish(yes_btn)
            st_y.polish(yes_btn)
        layout = mb.findChild(QGridLayout)
        if layout:
            layout.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        self.session_ended.emit()

    def _schedule_fit_hotseat_board(self) -> None:
        """Sidebar geometry changed; re-apply terrain fit."""
        QTimer.singleShot(0, self._refit_terrain)

    def _hotseat_scene_br_excluding_ui_proxies(self) -> QRectF:
        """Terrain bounds only (UI proxies excluded)."""
        return self._view.terrain_scene_rect_excluding_ui_proxies()

    def load_map(
        self,
        map_data: dict[str, Any],
        player_names: list[str],
        player_color_names: list[str],
        *,
        computer_flags: list[bool] | None = None,
        clues: list[str] | None = None,
        habitat_hex: tuple[int, int] | None = None,
        show_apply_hint: bool = False,
    ) -> None:
        """Load terrain: pieces/markers locked; chips drag from the strip below the map onto hexes.

        ``clues`` / ``habitat_hex`` override maps.json books (used for custom maps).
        ``show_apply_hint`` is True for predefined maps (Custom Maps OFF).
        """
        self._map_data = map_data
        self._habitat_hex = habitat_hex

        self._view._clear_question_picker_state()
        self._view.detach_map_chip_strip_proxy()
        self._scene.clear()
        self._board_builder = BoardBuilder(self._scene, self._view)
        self._board_builder.build(tooltip_manager=self._figures_hover_tooltip)
        self._board_builder.load_from_map_data(map_data, freeze=True)
        advanced = bool(map_data.get("advancedMode", False))
        self._board_builder.apply_marker_visibility(advanced)
        self._view._hotseat_advanced_mode = advanced

        n = len(player_names)
        colors_hex = [get_player_color_hex(c) for c in player_color_names[:n]]
        while len(colors_hex) < n:
            colors_hex.append("#ffffff")
        self._board_builder.set_chip_player_rank_for_hotseat(colors_hex)
        self._board_builder.hide_structures_region()
        self._board_builder.set_marker_bank_home_shadow_enabled(False)
        self._view.set_hotseat_board_builder(self._board_builder)
        self._view._hotseat_game_finished_cb = self._on_hotseat_game_finished
        self._sidebar.attach_hotseat_canvas(self._board_builder.canvas)
        canvas = self._board_builder.canvas
        prev_assigned = getattr(canvas, "_on_chip_assigned", None)
        prev_released = getattr(canvas, "_on_chip_released", None)

        def _on_chip_assigned(chip: Any, row: int, col: int, cell_idx: int) -> None:
            if callable(prev_assigned):
                prev_assigned(chip, row, col, cell_idx)
            self._note_chip_assigned_for_history(chip)
            self._sync_end_turn_button()

        def _on_chip_released(chip: Any) -> None:
            if callable(prev_released):
                prev_released(chip)
            self._note_chip_released_for_history(chip)
            self._sync_end_turn_button()

        canvas._on_chip_assigned = _on_chip_assigned
        canvas._on_chip_released = _on_chip_released
        self._view._end_turn_eligibility_cb = self._sync_end_turn_button

        proxy_fz = getattr(self._board_builder, "_proxy_freeze", None)
        if proxy_fz is not None:
            proxy_fz.setVisible(False)
        for piece in self._board_builder.pieces:
            piece.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            piece.setCursor(Qt.CursorShape.ArrowCursor)
        for marker in self._board_builder.markers:
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            marker.setCursor(Qt.CursorShape.ArrowCursor)

        self._view.resetTransform()

        resolved_clues = list(clues) if clues is not None else get_clues_for_map(map_data, n)
        while len(resolved_clues) < n:
            resolved_clues.append("")
        hint_desc: str | None = None
        if show_apply_hint:
            hint_desc = get_hint_description(get_hint_id_for_map(map_data, n))
        self._sidebar.set_session(
            player_names,
            player_color_names,
            resolved_clues[:n],
            advanced_mode=advanced,
            show_apply_hint=show_apply_hint,
            hint_description=hint_desc,
        )
        self._turn_index = 0
        self._round_num = 1
        flags_raw = list(computer_flags) if computer_flags is not None else []
        self._computer_flags = [bool(flags_raw[i]) if i < len(flags_raw) else False for i in range(n)]
        self._computer_turn_running = False
        self._sidebar.show()
        sp = self._sidebar.status_panel
        if sp is not None:
            sp.show()
        # Defer QGraphicsProxyWidget + embedded strip until after the board page is visible.
        # Creating the native embed while the view is hidden/zero-sized often flashes on Windows.
        self._refit_terrain()
        QTimer.singleShot(0, self._attach_hotseat_map_chip_strip_proxy_deferred)
        self._snapshot_turn_start_chips()
        self._sync_end_turn_button()

    def _attach_hotseat_map_chip_strip_proxy_deferred(self) -> None:
        if self._map_data is None:
            return
        ms = self._sidebar.map_chip_strip
        if ms is not None:
            self._view.set_map_chip_strip_proxy_widget(ms)
        self._sidebar.sync_hotseat_map_strip_sharing_rows()
        self._sidebar.sync_hotseat_sharing_bank_visibility()
        self._refit_terrain()
        self._sync_end_turn_button()

    def set_hotseat_turn_index(self, idx: int) -> None:
        """Update which player is active in the turn-order / current-player panels."""
        self._sidebar.set_turn_index(idx)
        self._sync_end_turn_button()

    def set_hotseat_round(self, n: int) -> None:
        """Set displayed round number (1-based)."""
        self._sidebar.set_round(n)

    def set_hotseat_clue(self, text: str) -> None:
        """Set the clue text shown when the player taps Show."""
        self._sidebar.set_clue_text(text)

    def set_hotseat_question_or_search(self, use_search: bool) -> None:
        """Show either the Question row (other players' colors) or Search (circle chip)."""
        self._sidebar.set_question_or_search(use_search)

    def _reset_hotseat_view_constraints(self) -> None:
        """Allow the view to participate in layout again."""
        self._view._terrain_fit_rect = None
        self._view.setMinimumSize(0, 0)
        self._view.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        map_col = getattr(self, "_map_column", None)
        if map_col is not None:
            map_col.setMinimumWidth(0)
            map_col.setMaximumWidth(_QWIDGETSIZE_MAX)
        sp = self._sidebar.status_panel if hasattr(self, "_sidebar") else None
        if sp is not None:
            sp.setMinimumWidth(0)
            sp.setMaximumWidth(_QWIDGETSIZE_MAX)
            sp.setMinimumHeight(0)
            sp.setMaximumHeight(_QWIDGETSIZE_MAX)

    def _refit_terrain(self) -> None:
        """Fit canvas in the view; map chip strip is a scene proxy at fixed screen size."""
        if self._map_data is None:
            return
        fit_rect = self._view.hotseat_canvas_fit_rect()
        if fit_rect is None or not fit_rect.isValid():
            return
        self._constrain_view_to_terrain()
        self._view.set_terrain_fit_rect(fit_rect)
        self._view.sync_hotseat_map_strip_proxy_item_cursor()

    def _constrain_view_to_terrain(self) -> None:
        """At 1:1 scale, size the view so the viewport can show canvas + strip (capped by panel)."""
        if self._map_data is None:
            return
        fr = self._view.hotseat_canvas_fit_rect()
        if fr is None or not fr.isValid():
            return
        if self.width() < 2 and self.height() < 2:
            return
        self._view.layout_map_chip_strip_proxy()
        vp = self._view.viewport()
        chrome_w = max(0, self._view.width() - vp.width()) if vp else 0
        chrome_h = max(0, self._view.height() - vp.height()) if vp else 0
        sidebar_w = self._sidebar.sizeHint().width() if self._sidebar.isVisible() else 0
        spacing = 8
        if self.layout() is not None:
            # main_row spacing lives on the HBox inside outer; fall back to 8.
            main_item = self.layout().itemAt(0)
            if main_item is not None and main_item.layout() is not None:
                spacing = main_item.layout().spacing()
        map_col_spacing = 0
        status_h = 0
        sp = self._sidebar.status_panel
        map_col = getattr(self, "_map_column", None)
        if map_col is not None and map_col.layout() is not None:
            map_col_spacing = map_col.layout().spacing()
        avail_w = max(1, self.width() - sidebar_w - spacing - chrome_w)
        inset_w = 2 * _HOTSEAT_VIEW_MAP_INSET_PX
        desired_vp_w = max(2, int(math.ceil(fr.width())) + inset_w)
        view_w_est = min(desired_vp_w, avail_w) + chrome_w
        if sp is not None and sp.isVisible():
            if sp.hasHeightForWidth():
                status_h = max(1, int(sp.heightForWidth(view_w_est)))
            else:
                status_h = max(sp.sizeHint().height(), sp.height())
        avail_h = max(1, self.height() - chrome_h - status_h - map_col_spacing)
        strip_h = self._view.hotseat_map_strip_reserve_viewport_px()
        desired_vp_h = max(2, int(math.ceil(fr.height())) + strip_h)
        vp_w = min(desired_vp_w, avail_w)
        vp_h = min(desired_vp_h, avail_h)
        view_w = vp_w + chrome_w
        view_h = vp_h + chrome_h
        self._view.setMaximumSize(view_w, view_h)
        # Keep Round + turn-order card as wide as the map.
        if sp is not None:
            sp.setFixedWidth(view_w)
            if sp.hasHeightForWidth():
                sp.setMinimumHeight(0)
                sp.setMaximumHeight(max(1, int(sp.heightForWidth(view_w))))
        if map_col is not None:
            map_col.setFixedWidth(view_w)
        QTimer.singleShot(0, self._sync_sidebar_height_to_view)

    def _sync_sidebar_height_to_view(self) -> None:
        """Keep the gameplay sidebar the same height as the left map column (status + map)."""
        if self._map_data is None or not self._sidebar.isVisible():
            return
        map_col = getattr(self, "_map_column", None)
        h = map_col.height() if map_col is not None else self._view.height()
        if h < 2:
            h = self._view.height()
        if h < 2:
            return
        self._sidebar.setFixedHeight(h)
        # Deferred sidebar sizing shifts the view in the panel; cursor was synced before this ran.
        self._view.sync_hotseat_map_strip_proxy_item_cursor()
        QTimer.singleShot(0, self._view.sync_hotseat_map_strip_proxy_item_cursor)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._constrain_view_to_terrain()

    def clear_board(self) -> None:
        """Release scene contents (before hiding panel)."""
        self._clear_history_chip_pulse()
        self._map_data = None
        self._habitat_hex = None
        self._computer_flags = []
        self._computer_turn_running = False
        self._turn_start_chip_ids = set()
        self._turn_placed_chip_ids = set()
        self._view._end_turn_eligibility_cb = None
        self._view._hotseat_game_finished_cb = None
        self._win_dialog_shown = False
        self._btn_end_turn.setEnabled(False)
        self._apply_end_turn_tooltip_look(False)
        self._view.detach_map_chip_strip_proxy()
        ms = self._sidebar.map_chip_strip
        if ms is not None:
            ms.hide()
        self._view._hotseat_advanced_mode = False
        self._sidebar.clear_possible_clues()
        self._sidebar._hint_description = None
        self._sidebar._set_apply_hint_controls(visible=False, enabled=False)
        self._sidebar.attach_hotseat_canvas(None)
        self._view.set_hotseat_board_builder(None)
        self._sidebar.hide()
        sp = self._sidebar.status_panel
        if sp is not None:
            sp.hide()
            sp.setMinimumHeight(0)
            sp.setMaximumHeight(_QWIDGETSIZE_MAX)
        self._sidebar.setMinimumHeight(0)
        self._sidebar.setMaximumHeight(_QWIDGETSIZE_MAX)
        self._reset_hotseat_view_constraints()
        self._view.resetTransform()
        self._view._clear_question_picker_state()
        if self._scene is not None:
            self._scene.clear()
