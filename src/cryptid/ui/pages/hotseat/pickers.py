"""Circular Question / Search target picker widgets (embedded in QGraphicsProxyWidget)."""
from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QSizePolicy,
    QToolButton,
)

from ui.shared.widgets.player_colors import get_player_meeple_pixmap

from .constants import (
    _HOTSEAT_QPICK_ACTION_ICON_PX,
    _HOTSEAT_QPICK_MEEPLE_BTN_PX,
    _HOTSEAT_QPICK_MEEPLE_ICON_PX,
    _HOTSEAT_QPICK_RING_RADIUS,
)


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
