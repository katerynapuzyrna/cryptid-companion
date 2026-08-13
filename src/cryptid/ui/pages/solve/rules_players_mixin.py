"""Solver page: Player count and advanced mode for rule dropdowns."""
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



class SolveRulesPlayersMixin:
    def on_players_changed(self, txt: str) -> None:
        # If the build settings are scrolled to the bottom, keep them pinned there
        # when enabling extra player rows (which increases the content height).
        vbar = self.buildScroll.verticalScrollBar()
        was_at_bottom = False
        if vbar is not None:
            # allow a tiny tolerance so "near bottom" is treated as bottom
            was_at_bottom = (vbar.maximum() - vbar.value()) <= 2

        self.rules.set_players_count(self.rules.parse_players(txt))

        if was_at_bottom and vbar is not None:
            # Defer until after layouts have updated so maximum() reflects new height.
            QTimer.singleShot(0, lambda vb=vbar: vb.setValue(vb.maximum()))

    def on_advanced_mode_toggled(self, enabled: bool) -> None:
        self.advanced_mode = bool(enabled)
        self._rule_labels = all_condition_labels(advanced_mode=self.advanced_mode)
        self.rules.set_rule_labels(self._rule_labels)
        self.board_builder.apply_marker_visibility(self.advanced_mode)
        if not self.advanced_mode:
            def _rewrite_solve_undo() -> None:
                u = getattr(self, "_board_undo", None)
                if u is not None:
                    u.rewrite_snapshots_strip_advanced_markers()

            _rewrite_solve_undo()
            QTimer.singleShot(0, _rewrite_solve_undo)


