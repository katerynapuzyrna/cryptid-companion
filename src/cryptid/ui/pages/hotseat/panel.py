"""Hotseat board panel: scene + view + sidebar + end game."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtWidgets import QGraphicsScene

from board.board_builder import BoardBuilder
from settings.config import ICON_HELP
from settings.strings import (
    END_HOTSEAT_CONFIRM_MSG,
    END_HOTSEAT_CONFIRM_TITLE,
    HOTSEAT_END_TURN_DISABLED_TOOLTIP,
)
from logic.clues import get_clues_for_map
from ui.shared.widgets.player_colors import get_player_color_hex

from ui.shared.widgets import HoverTooltipManager

from .board_view import HotseatBoardView
from .constants import _HOTSEAT_VIEW_MAP_INSET_PX, _QWIDGETSIZE_MAX
from .sidebar import HotseatGameplaySidebar


class HotseatBoardPanel(QWidget):
    """Builds a BoardView for a single loaded map (no simulation / rules)."""

    session_ended = Signal()
    end_turn_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_tooltip = HoverTooltipManager(self.window(), self)
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

        ms = self._sidebar.map_chip_strip
        if ms is not None:
            ms.hide()

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(8)
        # Top-align: map view height is capped by terrain fit; sidebar height is synced to match (see _constrain_view_to_terrain).
        main_row.addWidget(self._view, 3, Qt.AlignmentFlag.AlignTop)
        main_row.addWidget(self._sidebar, 1, Qt.AlignmentFlag.AlignTop)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 8, 0, 0)
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
        # so hover hits the host (see _sync_end_turn_button).
        self._end_turn_tooltip_host = QWidget()
        self._end_turn_tooltip_host.setObjectName("hotseatEndTurnTooltipHost")
        self._app_tooltip.add(
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
        self.end_turn_clicked.emit()

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
        clues: list[str] | None = None,
        habitat_hex: tuple[int, int] | None = None,
    ) -> None:
        """Load terrain: pieces/markers locked; chips drag from the strip below the map onto hexes.

        ``clues`` / ``habitat_hex`` override maps.json books (used for custom maps).
        """
        self._map_data = map_data
        self._habitat_hex = habitat_hex

        self._view._clear_question_picker_state()
        self._view.detach_map_chip_strip_proxy()
        self._scene.clear()
        self._board_builder = BoardBuilder(self._scene, self._view)
        self._board_builder.build()
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
        self._sidebar.attach_hotseat_canvas(self._board_builder.canvas)
        canvas = self._board_builder.canvas
        prev_assigned = getattr(canvas, "_on_chip_assigned", None)
        prev_released = getattr(canvas, "_on_chip_released", None)

        def _on_chip_assigned(chip: Any, row: int, col: int, cell_idx: int) -> None:
            if callable(prev_assigned):
                prev_assigned(chip, row, col, cell_idx)
            self._sync_end_turn_button()

        def _on_chip_released(chip: Any) -> None:
            if callable(prev_released):
                prev_released(chip)
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
        self._sidebar.set_session(player_names, player_color_names, resolved_clues[:n])
        self._sidebar.show()
        # Defer QGraphicsProxyWidget + embedded strip until after the board page is visible.
        # Creating the native embed while the view is hidden/zero-sized often flashes on Windows.
        self._refit_terrain()
        QTimer.singleShot(0, self._attach_hotseat_map_chip_strip_proxy_deferred)
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

    def _refit_terrain(self) -> None:
        """Fit canvas in the view; map chip strip is a scene proxy at fixed screen size."""
        if self._map_data is None:
            return
        fit_rect = self._view.hotseat_canvas_fit_rect()
        if fit_rect is None or not fit_rect.isValid():
            return
        self._constrain_view_to_terrain()
        self._view.set_terrain_fit_rect(fit_rect)
        self._view.sync_hotseat_embedded_proxy_cursors()

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
        spacing = self.layout().spacing() if self.layout() else 8
        avail_w = max(1, self.width() - sidebar_w - spacing - chrome_w)
        avail_h = max(1, self.height() - chrome_h)
        strip_h = self._view.hotseat_map_strip_reserve_viewport_px()
        inset_w = 2 * _HOTSEAT_VIEW_MAP_INSET_PX
        desired_vp_w = max(2, int(math.ceil(fr.width())) + inset_w)
        desired_vp_h = max(2, int(math.ceil(fr.height())) + strip_h)
        vp_w = min(desired_vp_w, avail_w)
        vp_h = min(desired_vp_h, avail_h)
        self._view.setMaximumSize(vp_w + chrome_w, vp_h + chrome_h)
        QTimer.singleShot(0, self._sync_sidebar_height_to_view)

    def _sync_sidebar_height_to_view(self) -> None:
        """Keep the gameplay sidebar the same height as the board view (map + strip), not the full window."""
        if self._map_data is None or not self._sidebar.isVisible():
            return
        h = self._view.height()
        if h < 2:
            return
        self._sidebar.setFixedHeight(h)
        self._view.sync_hotseat_embedded_proxy_cursors()
        QTimer.singleShot(0, self._view.sync_hotseat_embedded_proxy_cursors)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._constrain_view_to_terrain()

    def clear_board(self) -> None:
        """Release scene contents (before hiding panel)."""
        self._map_data = None
        self._habitat_hex = None
        self._view.detach_map_chip_strip_proxy()
        ms = self._sidebar.map_chip_strip
        if ms is not None:
            ms.hide()
        self._view._hotseat_advanced_mode = False
        self._sidebar.attach_hotseat_canvas(None)
        self._view.set_hotseat_board_builder(None)
        self._sidebar.hide()
        self._sidebar.setMinimumHeight(0)
        self._sidebar.setMaximumHeight(_QWIDGETSIZE_MAX)
        self._reset_hotseat_view_constraints()
        self._view.resetTransform()
        self._view._clear_question_picker_state()
        if self._scene is not None:
            self._scene.clear()
