"""Hotseat gameplay sidebar: turn order, clues, bank chips."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Literal

from PySide6.QtCore import QPoint, QPointF, QTimer, Signal, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.shared.widgets.player_colors import (
    get_player_circle_chip_pixmap,
    get_player_color_hex,
    get_player_meeple_pixmap,
    get_player_question_chip_pixmap,
    get_player_square_chip_pixmap,
)

from .chip_widgets import _HotseatChipDragLabel, _HotseatMapChipStripWidget
from .constants import (
    _HOTSEAT_CHIP_HOME_PX,
    _HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX,
    _HOTSEAT_QUESTION_CHIP_HEX,
    _STATUS_BLUE,
    _TURN_STATUS_DOT_PX,
    _TURN_STATUS_LABEL_PAD,
)
from .divider_arrows import _OrDivider
from .turn_status import _TurnStatus, _status_dot_pixmap

if TYPE_CHECKING:
    from .board_view import HotseatBoardView


class HotseatGameplaySidebar(QWidget):
    """Turn order + current player controls (Play Hotseat)."""

    geometry_needs_update = Signal()


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
        self._ic_summary_current: QLabel | None = None
        self._lbl_summary_current_name: QLabel | None = None
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
        #: Question / Search bank drag: dimmed strip like sharing square (no solid chip at home until placed).
        self._hotseat_question_carry: bool = False
        self._hotseat_search_carry: bool = False
        #: Set by ``HotseatBoardView.set_gameplay_sidebar(...)`` (bank chip drag uses this view).
        self.hotseat_board_view: Any = None
        self._map_chip_strip: _HotseatMapChipStripWidget | None = None
        self._setup_ui()

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

        turn_card = QWidget(self)
        turn_card.setProperty("card", True)
        turn_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        turn_lay = QVBoxLayout(turn_card)
        turn_lay.setContentsMargins(10, 10, 10, 10)
        turn_lay.setSpacing(6)

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
        turn_lay.addLayout(round_row)

        cur_summary = QWidget()
        cur_summary.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        cur_sum_lay = QHBoxLayout(cur_summary)
        cur_sum_lay.setContentsMargins(0, 0, 0, 0)
        cur_sum_lay.setSpacing(6)
        cur_sum_lay.addWidget(QLabel("Current player:"))
        self._ic_summary_current = QLabel()
        self._ic_summary_current.setFixedSize(18, 18)
        self._ic_summary_current.setScaledContents(True)
        self._lbl_summary_current_name = QLabel("")
        self._lbl_summary_current_name.setWordWrap(True)
        self._lbl_summary_current_name.setMinimumWidth(0)
        self._lbl_summary_current_name.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        cur_sum_lay.addWidget(self._ic_summary_current, 0, Qt.AlignmentFlag.AlignTop)
        cur_sum_lay.addWidget(self._lbl_summary_current_name, 1)
        turn_lay.addWidget(cur_summary)

        clue_row = QHBoxLayout()
        clue_row.setContentsMargins(0, 0, 0, 0)
        clue_row.setSpacing(8)
        clue_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._btn_clue_toggle = QPushButton("Show clue")
        self._btn_clue_toggle.setProperty("secondary", True)
        self._btn_clue_toggle.clicked.connect(self._on_clue_toggle)
        self._btn_clue_toggle.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        clue_row.addWidget(self._btn_clue_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        self._lbl_clue = QLabel("")
        self._lbl_clue.setWordWrap(False)
        self._lbl_clue.setVisible(False)
        self._lbl_clue.setStyleSheet("color: #5a6a72;")
        self._lbl_clue.setMinimumWidth(0)
        self._lbl_clue.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._lbl_clue.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        clue_row.addWidget(self._lbl_clue, 1, Qt.AlignmentFlag.AlignVCenter)
        turn_lay.addLayout(clue_row)

        spacer_summary = QWidget()
        spacer_summary.setFixedHeight(8)
        turn_lay.addWidget(spacer_summary)

        title = QLabel("Turn order:")
        turn_lay.addWidget(title)

        for _ in range(5):
            row = QWidget()
            row.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
            )
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            hl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            ic = QLabel()
            ic.setFixedSize(18, 18)
            ic.setScaledContents(True)
            name = QLabel("")
            name.setWordWrap(True)
            name.setMinimumWidth(0)
            name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            dot = QLabel()
            dot.setFixedSize(_TURN_STATUS_DOT_PX, _TURN_STATUS_DOT_PX)
            dot.setScaledContents(True)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status = QLabel("")
            status.setWordWrap(False)
            status.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            fm = QFontMetrics(status.font())
            _status_w = max(
                int(math.ceil(fm.boundingRect(s).width()))
                for s in ("Waiting", "Active", "Done")
            )
            status.setFixedWidth(_status_w + _TURN_STATUS_LABEL_PAD)
            # Fixed-width column so every row’s dot shares the same vertical line.
            dot_col = QWidget()
            dot_col.setFixedWidth(_TURN_STATUS_DOT_PX + 2)
            dot_col.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum
            )
            dcl = QHBoxLayout(dot_col)
            dcl.setContentsMargins(0, 0, 0, 0)
            dcl.setSpacing(0)
            dcl.addWidget(dot, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            dcl.addStretch(1)
            status_strip = QWidget()
            status_strip.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum
            )
            ssl = QHBoxLayout(status_strip)
            ssl.setContentsMargins(0, 0, 0, 0)
            ssl.setSpacing(4)
            ssl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            ssl.addWidget(dot_col, 0, Qt.AlignmentFlag.AlignVCenter)
            ssl.addWidget(status, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(ic, 0, Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(name, 1, Qt.AlignmentFlag.AlignVCenter)
            hl.addWidget(status_strip, 0, Qt.AlignmentFlag.AlignVCenter)
            turn_lay.addWidget(row)
            self._turn_rows.append((row, ic, name, dot, status))

        spacer_oyt = QWidget()
        spacer_oyt.setFixedHeight(8)
        turn_lay.addWidget(spacer_oyt)

        lbl_on_your_turn = QLabel("On your turn:")
        lbl_on_your_turn.setWordWrap(True)
        lbl_on_your_turn.setMinimumWidth(0)
        lbl_on_your_turn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        turn_lay.addWidget(lbl_on_your_turn)

        # Two-column layout: Question | OR | Search
        columns_host = QWidget()
        columns_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        columns_row = QHBoxLayout(columns_host)
        columns_row.setContentsMargins(0, 0, 0, 0)
        columns_row.setSpacing(0)

        col_q = QWidget()
        col_q.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        q_lay = QVBoxLayout(col_q)
        q_lay.setContentsMargins(0, 0, 4, 0)
        q_lay.setSpacing(6)
        lbl_q_title = QLabel("Question:")
        lbl_q_title.setStyleSheet("font-weight: 600;")
        q_lay.addWidget(lbl_q_title)
        lbl_q_hint = QLabel(
            "Ask one other player if this space could be the habitat. If the answer is No, additionally share the space that is not the habitat according to your clue."
        )
        lbl_q_hint.setWordWrap(True)
        lbl_q_hint.setMinimumWidth(0)
        lbl_q_hint.setStyleSheet("color: #5a6a72; font-size: 9pt;")
        lbl_q_hint.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        q_lay.addWidget(lbl_q_hint)

        or_div = _OrDivider()

        col_s = QWidget()
        col_s.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        s_lay = QVBoxLayout(col_s)
        s_lay.setContentsMargins(4, 0, 0, 0)
        s_lay.setSpacing(6)
        lbl_s_title = QLabel("Search:")
        lbl_s_title.setStyleSheet("font-weight: 600;")
        s_lay.addWidget(lbl_s_title)
        lbl_s_hint = QLabel(
            "Select a space and check if it could be the habitat. If the answer is No, additionally share the space that is not the habitat according to your clue."
        )
        lbl_s_hint.setWordWrap(True)
        lbl_s_hint.setMinimumWidth(0)
        lbl_s_hint.setStyleSheet("color: #5a6a72; font-size: 9pt;")
        lbl_s_hint.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        s_lay.addWidget(lbl_s_hint)

        columns_row.addWidget(col_q, 1, Qt.AlignmentFlag.AlignTop)
        columns_row.addWidget(or_div, 0)
        columns_row.addWidget(col_s, 1, Qt.AlignmentFlag.AlignTop)
        turn_lay.addWidget(columns_host)

        #share_row = QHBoxLayout()
        #share_row.setSpacing(6)
        #share_row.addWidget(QLabel("Sharing in return:"))
        #share_row.addStretch(1)
        #turn_lay.addLayout(share_row)
        # Extra card height goes below this block so “On your turn” stays compact under Turn order.
        turn_lay.addStretch(1)

        # Single child fills the sidebar when height is synced to the map column.
        root.addWidget(turn_card, 1)

        self._sync_clue_display()
        self._apply_style_polish()

        self._map_chip_strip = _HotseatMapChipStripWidget(self)
        self._map_chip_strip.hide()

    def _reset_question_mode_to_question(self) -> None:
        """No-op: both columns are always visible."""

    def _apply_style_polish(self) -> None:
        for w in self.findChildren(QPushButton):
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
        self.geometry_needs_update.emit()

    def set_session(
        self,
        names: list[str],
        color_names: list[str],
        clues: list[str] | None = None,
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
        self._reset_question_mode_to_question()
        self._refresh_all()

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
        self._refresh_all()

    def set_round(self, n: int) -> None:
        self._round_num = max(1, int(n))
        if self._lbl_round_value is not None:
            self._lbl_round_value.setText(str(self._round_num))
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
        """No-op: both columns are always visible."""
        self._refresh_chips()

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
        self.geometry_needs_update.emit()

    def sync_hotseat_map_strip_sharing_rows(self) -> None:
        """Show Additional sharing controls only when a square resulted from Question or Search on this turn."""
        ms = self._map_chip_strip
        if ms is None:
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
                sync = getattr(v, "sync_hotseat_embedded_proxy_cursors", None)
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
        c = self._hotseat_canvas
        if c is None:
            show_shadow = (
                self._hotseat_question_used
                or self._hotseat_search_used
                or self._hotseat_question_carry
            )
            for lab in labs:
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
            return
        on_map = any(
            getattr(ch, "_question_mark", False) for ch in c.chip_slot
        )
        show_shadow = (
            on_map
            or self._hotseat_question_used
            or self._hotseat_search_used
            or self._hotseat_question_carry
        )
        for lab in labs:
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

    def may_drag_search_chip_from_bank(self) -> bool:
        """False when the search action was already used this turn or question was chosen instead."""
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
        cur = self._turn_index
        cname = self._color_names[cur] if 0 <= cur < len(self._color_names) else ""
        show_shadow = (
            self._hotseat_search_used
            or self._hotseat_question_used
            or self._hotseat_search_carry
        )
        for lab in labs:
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
        ic = self._ic_summary_current
        name = self._lbl_summary_current_name
        if ic is None or name is None:
            return
        if 0 <= self._turn_index < self._n:
            cname = (
                self._color_names[self._turn_index]
                if self._turn_index < len(self._color_names)
                else ""
            )
            ic.setPixmap(get_player_meeple_pixmap(cname, 18))
            name.setText(
                self._names[self._turn_index]
                if self._turn_index < len(self._names)
                else f"Player {self._turn_index + 1}"
            )
        else:
            ic.clear()
            name.setText("—")

    def _refresh_turn_order(self) -> None:
        t = self._turn_index
        for i in range(5):
            row_w, ic, name, dot, status = self._turn_rows[i]
            if i >= self._n:
                row_w.hide()
                continue
            row_w.show()
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
            status.setText(st_text)

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

