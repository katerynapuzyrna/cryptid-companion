"""Solver page: Auto-clear highlights when rules or pieces change."""
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



class SolveHighlightsMixin:
    def _connect_auto_clear_signals(self) -> None:
        if getattr(self, "_auto_clear_wired", False):
            return
        self._auto_clear_wired = True

        def defer(*args) -> None:
            QTimer.singleShot(0, self._update_status_and_structures)

        def on_clear(*args) -> None:
            self._auto_clear_highlights()

        def on_status(*args) -> None:
            self._update_status_and_structures()

        self.cbBuildAdvancedMode.toggled.connect(on_clear)
        self.cbBuildPlayers.currentTextChanged.connect(on_clear)
        for cb in self.cbRuleP:
            cb.currentIndexChanged.connect(on_clear)
            cb.currentTextChanged.connect(on_clear)
        self.cbBuildAdvancedMode.toggled.connect(on_status)
        self.cbBuildPlayers.currentTextChanged.connect(on_status)
        for cb in self.cbRuleP:
            cb.currentIndexChanged.connect(on_status)
            cb.currentTextChanged.connect(on_status)
        for edt in getattr(self, "edtPlayer", []):
            if edt is not None:
                edt.textChanged.connect(on_status)
        for cb in getattr(self, "cbColorP", []):
            if cb is not None:
                cb.currentIndexChanged.connect(on_status)

        # Auto-clear highlights when any puzzle piece is rotated (e.g. 0° ↔ 180°).
        # Markers and chips do not trigger auto-clear here; their slot changes are
        # handled via BoardBuilder/canvas callbacks.
        for item in self.pieces:
            if hasattr(item, "rotationChanged"):
                item.rotationChanged.connect(on_clear)
                item.rotationChanged.connect(defer)

    def _auto_clear_highlights(self) -> None:
        if getattr(self, "_suppress_auto_clear", False):
            return
        self._clear_all_highlights()

    def _clear_all_highlights(self) -> None:
        if hasattr(self, "board_builder"):
            self.board_builder.clear_highlights()
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas._zero_targets_dim_full_map = False
        if getattr(self, "btnMapBuild", None) is not None and self.btnMapBuild.isChecked():
            if getattr(self, "_build_tab_solve_active", False):
                self._build_tab_solve_active = False
                from ui.shell.breadcrumb_manager import touch_breadcrumbs

                touch_breadcrumbs(self)


