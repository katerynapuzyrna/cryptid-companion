"""Bank chip labels and map chip strip (drag-to-map)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QWidget

from ui.shared.widgets.player_colors import (
    get_player_circle_chip_pixmap,
    get_player_question_chip_pixmap,
    get_player_square_chip_pixmap,
)

from .constants import (
    _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX,
    _HOTSEAT_QUESTION_CHIP_HEX,
)

if TYPE_CHECKING:
    from .sidebar import HotseatGameplaySidebar


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
        sb = self._hotseat_sidebar_ancestor()
        if _hotseat_chip_drag_label_movable(self, sb):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _hotseat_sidebar_ancestor(self) -> HotseatGameplaySidebar | None:
        if self._hotseat_sidebar_ref is not None:
            return self._hotseat_sidebar_ref
        from .sidebar import HotseatGameplaySidebar as _HS

        w: QWidget | None = self.parentWidget()
        while w is not None:
            if isinstance(w, _HS):
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


class _HotseatMapChipStripWidget(QFrame):
    """Chip flow below the map: Question/Search -> Additional sharing (inside QGraphicsView)."""

    def __init__(self, sidebar: HotseatGameplaySidebar, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hotseatMapChipStrip")
        # No card frame: avoid QWidget[card] border from cards.qss; blend with map viewport.
        self.setStyleSheet(
            "#hotseatMapChipStrip { background: transparent; border: none; padding: 8px 6px 8px 6px; }"
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )

        def _title(text: str) -> QLabel:
            t = QLabel(text)
            t.setStyleSheet("font-weight: 600;")
            return t

        # Single grid so Question row and Search row share column widths: both circles
        # (neutral ? chip + colored Search chip) align on one vertical line below the map.
        grid = QGridLayout(self)
        grid.setContentsMargins(10, 0, 10, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.lbl_question = _HotseatChipDragLabel(
            "question", _HOTSEAT_QUESTION_CHIP_HEX, self, hotseat_sidebar=sidebar
        )
        self.lbl_question.setFixedSize(
            _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX, _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        )
        self.lbl_question.setPixmap(
            get_player_question_chip_pixmap("", _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX)
        )
        self.lbl_share_q = _HotseatChipDragLabel(
            "square", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_share_q.setFixedSize(
            _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX, _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        )
        self.lbl_share_q.setPixmap(
            get_player_square_chip_pixmap("", _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX)
        )
        self.lbl_search = _HotseatChipDragLabel(
            "circle", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_search.setFixedSize(
            _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX, _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        )
        self.lbl_search.setPixmap(
            get_player_circle_chip_pixmap("", _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX)
        )
        self.lbl_share_s = _HotseatChipDragLabel(
            "square", "#808080", self, hotseat_sidebar=sidebar
        )
        self.lbl_share_s.setFixedSize(
            _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX, _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX
        )
        self.lbl_share_s.setPixmap(
            get_player_square_chip_pixmap("", _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX)
        )

        from .divider_arrows import _hotseat_arrow_right_label

        self._ar_q = _hotseat_arrow_right_label()
        self._ar_s = _hotseat_arrow_right_label()
        self._lbl_add_q = QLabel("Additional sharing:")
        self._lbl_add_s = QLabel("Additional sharing:")
        al_vc = Qt.AlignmentFlag.AlignVCenter
        al_tl = Qt.AlignmentFlag.AlignLeft | al_vc

        grid.addWidget(_title("Question:"), 0, 0, al_tl)
        grid.addWidget(self.lbl_question, 0, 1, al_vc)
        grid.addWidget(self._ar_q, 0, 2, al_vc)
        grid.addWidget(self._lbl_add_q, 0, 3, al_tl)
        grid.addWidget(self.lbl_share_q, 0, 4, al_vc)

        grid.addWidget(_title("Search:"), 1, 0, al_tl)
        grid.addWidget(self.lbl_search, 1, 1, al_vc)
        grid.addWidget(self._ar_s, 1, 2, al_vc)
        grid.addWidget(self._lbl_add_s, 1, 3, al_tl)
        grid.addWidget(self.lbl_share_s, 1, 4, al_vc)
        grid.setColumnStretch(5, 1)
        self.set_sharing_rows_visible(False, False)

    def set_sharing_rows_visible(self, question_row: bool, search_row: bool) -> None:
        """Arrow + label + square chip for a row; hidden until a square results on-map from that action."""
        self._ar_q.setVisible(question_row)
        self._lbl_add_q.setVisible(question_row)
        self.lbl_share_q.setVisible(question_row)
        self._ar_s.setVisible(search_row)
        self._lbl_add_s.setVisible(search_row)
        self.lbl_share_s.setVisible(search_row)
        self.adjustSize()
        self.updateGeometry()


def _hotseat_chip_drag_label_movable(
    chip: _HotseatChipDragLabel, sb: Any
) -> bool:
    """Whether the bank chip behaves as draggable (matches ``mousePressEvent`` gating)."""
    if getattr(chip, "_shadow", False):
        return False
    if sb is None:
        return False
    shape = chip._shape
    if shape == "question":
        return sb.may_drag_question_chip_from_bank()
    if shape == "circle":
        return sb.may_drag_search_chip_from_bank()
    if shape == "square":
        return sb.may_drag_sharing_chip_from_bank()
    return False
