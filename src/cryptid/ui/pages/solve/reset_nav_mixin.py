"""Solver page: Reset confirmations, select-mode reset, navigation hooks, build reset."""
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



class SolveResetNavMixin:
    def _on_reset_clicked_wrapper(self) -> None:
        mb = QMessageBox(self.window)
        mb.setWindowTitle(RESET_CONFIRM_TITLE)
        mb.setText(RESET_CONFIRM_MSG)
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        no_btn = mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        yes_btn.style().unpolish(yes_btn)
        yes_btn.style().polish(yes_btn)
        layout = mb.findChild(QGridLayout)
        if layout:
            layout.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        if self.btnMapSelect.isChecked():
            self._on_reset_select_mode()
        else:
            self.on_reset_clicked()

    def _reset_select_mode_state(self) -> None:
        """Reset select mode state (for when switching to build or leaving page)."""
        if self._in_solve_mode:
            self._exit_solve_mode()
        self.map_cards_manager.clear_selection()
        # Deduction Load map: wipe clue forms on every card (e.g. after switching maps without deselecting).
        self.map_cards_manager.clear_all_cards_deduction_controls()
        if self.edtSelectSearch:
            self.edtSelectSearch.clear()
        self.cbSelectAdvancedMode.blockSignals(True)
        self.cbSelectAdvancedMode.setChecked(False)
        self.cbSelectAdvancedMode.blockSignals(False)
        self.cbSelectAdvancedMode.setEnabled(True)
        self.map_cards_manager.filter_map_cards()
        idx = self.cbSelectPlayers.findText("3", Qt.MatchFixedString)
        self.cbSelectPlayers.setCurrentIndex(idx) if idx != -1 else self.cbSelectPlayers.setCurrentText("3")
        self.cbSelectPlayers.setEnabled(True)
        self._show_select_browse_filters()
        self.map_cards_manager.set_blur_for_all_cards(True)
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def _on_reset_select_mode(self) -> None:
        self._reset_select_mode_state()
        self.mapListCardsContainer.setVisible(True)
        mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
        if mc:
            mc.setVisible(True)
        row = self.btnReset.parentWidget()
        if row:
            row.setVisible(True)
        self.btnSolve.setEnabled(False)

    def on_navigate_away(self) -> None:
        """Preserve state when leaving Solve page (no reset)."""

    def on_navigate_to(self) -> None:
        """Restore preserved state when returning (no forced build mode)."""

    def _reset_build_mode_state(self) -> None:
        """Reset build mode state (for when switching to select or leaving page)."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas._zero_targets_dim_full_map = False
        self.board_builder.reset_board()
        self.cbBuildPlayers.blockSignals(True)
        self._set_players_combo_to_3()
        self.cbBuildPlayers.blockSignals(False)
        self.rules.set_players_count(3)
        self.cbBuildAdvancedMode.blockSignals(True)
        self.cbBuildAdvancedMode.setChecked(False)
        self.cbBuildAdvancedMode.blockSignals(False)
        self.advanced_mode = False
        self._rule_labels = all_condition_labels(advanced_mode=False)
        self.rules.set_rule_labels(self._rule_labels)
        self.rules.clear_rules(players=3)
        self.board_builder.apply_marker_visibility(False)
        if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
            self.status_list_manager.reset_for_build()
            self._update_status_and_structures()
        self._build_tab_solve_active = False
        u = getattr(self, "_board_undo", None)
        if u is not None:
            u.reset()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def on_reset_clicked(self) -> None:
        self._reset_build_mode_state()


