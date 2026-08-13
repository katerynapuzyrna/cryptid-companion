"""Solver page: BoardBuilder, status list, help icon proxy, canvas callbacks."""
from PySide6.QtWidgets import (
    QGridLayout,
    QMessageBox,
    QWidget,
    QPushButton,
    QComboBox,
    QLabel,
    QCheckBox,
    QLineEdit,
    QGraphicsScene,
    QListWidget,
    QStackedWidget,
    QScrollArea,
    QButtonGroup,
    QHBoxLayout,
)
from PySide6.QtCore import QTimer, Qt, QRectF, QPointF
from PySide6.QtGui import QIcon
from typing import Optional

from board.board_view import BoardView
from board.board_builder import BoardBuilder
from board.canvas import PuzzleCanvas
from board.markers import MarkerItem
from logic.conditions import all_condition_labels, compute_all_conditions
from logic.map_builder import MapBuilder
from logic.clues import get_clues_for_map
from logic.map_loader import build_map_from_data, targets_to_highlighted_cells

from settings.config import ICON_HELP, ICON_STATUS_OK, ICON_STATUS_ERROR, ICON_STATUS_WARNING
from settings.strings import (
    TOOLTIP_SOLVE_BUILD,
    TOOLTIP_SOLVE_BUILD_DEDUCTION,
    TOOLTIP_SOLVE_SELECT,
    TOOLTIP_SOLVE_SELECT_DEDUCTION,
    TOOLTIP_HELP_BUILD,
    TOOLTIP_HELP_SIMULATION,
    TOOLTIP_ADVANCED_MODE,
    TOOLTIP_ADVANCED_MODE_SELECT,
    TOOLTIP_FREEZE_MAP,
    TOOLTIP_FREEZE_MAP_ENABLED,
    TOOLTIP_UNDO,
    TOAST_NO_INTERSECTION,
    TOAST_HEX_HIGHLIGHTED,
    TOAST_HEXES_HIGHLIGHTED,
    RESET_CONFIRM_TITLE,
    RESET_CONFIRM_MSG,
)
from ui.shared.rules_dropdowns_manager import RuleDropdownsManager
from ui.shared.map_cards_manager import MapCardsManager
from ui.shared.status_list_manager import StatusListManager
from ui.shared.widgets import (
    HoverTooltipManager,
    ComboBoxWithPopupAbove,
    add_clear_button_inside_combo,
    show_toast,
)
from ui.shared.board_undo import BoardUndoController


class SolveBoardMixin:
    def _build_board_content(self) -> None:
        self.board_builder = BoardBuilder(self.scene, self.view)
        self.board_builder.build(
            add_tooltip=lambda w, t, **kw: self._app_tooltip.add(w, t, **kw),
            tooltip_freeze_map=TOOLTIP_FREEZE_MAP,
            tooltip_manager=self._app_tooltip,
        )
        self.canvas = self.board_builder.canvas
        self.pieces = self.board_builder.pieces
        self.markers = self.board_builder.markers
        self.controller = self.board_builder.controller
        self.highlight_overlay = self.board_builder.highlight_overlay
        self.cbFreezeMap = self.board_builder.cbFreezeMap
        self._app_tooltip.add(
            self.cbFreezeMap,
            TOOLTIP_FREEZE_MAP_ENABLED,
            only_when_disabled=False,
            only_when=lambda: self.cbFreezeMap.isEnabled(),
        )

        deduction = getattr(self, "_deduction_mode", False)
        chips = getattr(self.board_builder, "chips", []) if hasattr(self, "board_builder") and self.board_builder else []
        self.status_list_manager = StatusListManager(
            self.statusList,
            self._icon_status_ok,
            self._icon_status_error,
            self.rules,
            self.cbBuildPlayers,
            self.btnSolve,
            self.cbFreezeMap,
            self.canvas,
            self.pieces,
            self.markers,
            chips=chips,
            rule_check_count=1 if deduction else None,
            icon_warning=self._icon_status_warning if deduction else None,
            edt_player=getattr(self, "edtPlayer", None),
            cb_color=getattr(self, "cbColorP", None),
            board_builder=self.board_builder if deduction else None,
            get_simulation_status=getattr(self, "_get_simulation_status", None),
        )

        def _on_marker_assigned() -> None:
            self._update_status_and_structures()

        self.canvas._on_marker_assigned = lambda: QTimer.singleShot(0, _on_marker_assigned)

        def _on_marker_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot:
                self.board_builder.clear_highlights()
            QTimer.singleShot(0, self._update_status_and_structures)

        self.canvas._on_marker_reassigned = _on_marker_reassigned

        def _on_piece_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot:
                self.board_builder.clear_highlights()
            QTimer.singleShot(0, self._update_status_and_structures)

        self.canvas._on_piece_reassigned = _on_piece_reassigned

        # Help icon in scene at z=100: visible above pieces (0), but overlayed by dragged piece (15000)
        self._help_icon_proxy = self.scene.addWidget(self._help_icon_wrapper)
        self._help_icon_proxy.setZValue(100)
        self._update_help_icon_pos()
        self.view._on_resize = lambda: QTimer.singleShot(0, self._update_help_icon_pos)

        self._connect_auto_clear_signals()
        self.board_builder.apply_marker_visibility(self.advanced_mode)
        self._update_status_and_structures()

        self._board_undo = BoardUndoController(
            self.board_builder,
            [self.board_builder.btnUndoFreeze, self.board_builder.btnUndoHighlight],
            self._app_tooltip,
            TOOLTIP_UNDO,
            after_undo=self._after_board_undo,
        )
        self._update_board_undo_tracking()

    def _undo_tracking_for_board(self) -> bool:
        return self.btnMapBuild.isChecked()

    def _update_board_undo_tracking(self) -> None:
        u = getattr(self, "_board_undo", None)
        if u is None:
            return
        u.set_tracking(self._undo_tracking_for_board())

    def _after_board_undo(self) -> None:
        """After undo: simulation recomputes highlights from chips (includes status update)."""
        bb = getattr(self, "board_builder", None)
        if (
            bb is not None
            and getattr(bb, "_chips_mode", False)
            and hasattr(self, "_recompute_all_players_from_chips")
        ):
            self._recompute_all_players_from_chips()
        else:
            self._update_status_and_structures()

    def _update_status_and_structures(self) -> None:
        """Update status list and toggle Structures region (build mode only)."""
        if not hasattr(self, "status_list_manager") or self.status_list_manager is None:
            return
        self.status_list_manager.update()
        self._update_build_overlay_save_visible()
        bb = getattr(self, "board_builder", None)
        if bb is None:
            return
        # Structures region visibility only in build mode; chips mode keeps region visible
        if getattr(bb, "_chips_mode", False):
            return
        all_struct = getattr(self.status_list_manager, "all_struct", False)
        if all_struct and hasattr(bb, "hide_structures_background_only"):
            bb.hide_structures_background_only()
        elif not all_struct and hasattr(bb, "show_structures_region"):
            bb.show_structures_region()

    def _update_build_overlay_save_visible(self) -> None:
        w = getattr(self, "_build_save_icon", None)
        if w is None:
            return
        bb = getattr(self, "board_builder", None)
        in_sim = bb is not None and getattr(bb, "_chips_mode", False)
        deduction = getattr(self, "_deduction_mode", False)
        slm = getattr(self, "status_list_manager", None)
        tiles_ok = bool(slm is not None and getattr(slm, "all_tiles", False))
        struct_ok = bool(slm is not None and getattr(slm, "all_struct", False))
        # Deduction: keep save visible during simulation if tiles/structures were satisfied before sim.
        w.setVisible(
            bool(
                self.btnMapBuild.isChecked()
                and tiles_ok
                and struct_ok
                and (not in_sim or deduction)
            )
        )

    def _update_help_icon_pos(self) -> None:
        self._update_build_overlay_save_visible()
        if hasattr(self, "_help_icon_proxy") and self._help_icon_proxy and self.scene:
            # Top-right of the *visible* viewport in scene coords — not sceneRect().right(),
            # or the icon sits off-screen when the window is narrower than the board.
            vp = self.view.viewport().rect()
            vr = self.view.mapToScene(vp).boundingRect()
            if not vr.isValid() or vr.width() < 1.0 or vr.height() < 1.0:
                r = self.scene.sceneRect()
            else:
                r = vr
            w = self._help_icon_wrapper.width()
            self._help_icon_proxy.setPos(r.right() - w - 8, r.top() + 8)
            self._help_icon_proxy.setZValue(100)
