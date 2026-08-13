"""Solver page: Map source segment: stack index and Solve button visibility."""
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



class SolveMapSourceMixin:

    def _on_map_source_toggled(self, _: bool) -> None:
        if self.btnMapSelect.isChecked():
            self.mapSourceStack.setCurrentIndex(1)
        else:
            self.mapSourceStack.setCurrentIndex(0)
        self._on_map_source_mode_changed()

    def _on_map_source_mode_changed(self) -> None:
        is_select = self.btnMapSelect.isChecked()
        if is_select:
            self._build_tab_solve_active = False
            self.mapListCardsContainer.setVisible(True)
            mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
            if mc:
                mc.setVisible(True)
            if self._in_solve_mode and self._solve_mode_map_data:
                self.map_cards_manager.enter_solve_mode(self._solve_mode_map_data)
            else:
                self.map_cards_manager.filter_map_cards()
        else:
            self.btnSolve.setText("Solve")
            self.btnSolve.setProperty("primary", True)
            self.btnSolve.style().unpolish(self.btnSolve)
            self.btnSolve.style().polish(self.btnSolve)
            if hasattr(self, "status_list_manager"):
                self._update_status_and_structures()
            self.mapListCardsContainer.setVisible(False)
            row = self.btnReset.parentWidget()
            if row:
                row.setVisible(True)
        if is_select and self.map_cards_manager.get_selected_map_data() is None:
            self.btnSolve.setEnabled(False)
        self._update_build_overlay_save_visible()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)
        if hasattr(self, "_update_board_undo_tracking"):
            self._update_board_undo_tracking()

    def _set_players_combo_to_3(self) -> None:
        self.cbBuildPlayers.blockSignals(True)
        idx = self.cbBuildPlayers.findText("3", Qt.MatchFixedString)
        self.cbBuildPlayers.setCurrentIndex(idx) if idx != -1 else self.cbBuildPlayers.setCurrentText("3")
        self.cbBuildPlayers.blockSignals(False)


