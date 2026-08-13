"""Solver page: Build-tab Solve: intersection highlights on the live board."""
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
from ui.shell.breadcrumb_manager import touch_breadcrumbs



class SolveBuildSolveMixin:
    def on_solve_clicked(self) -> None:
        players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip())
        if players not in (3, 4, 5):
            print("Select number of players (3/4/5) first.")
            return
        sel = self.rules.read_selected_rules(players)
        if any(not r for r in sel):
            print("Select a rule for each player.")
            return
        self._clear_all_highlights()
        current_map = self.controller.build_current_map()
        all_conds = compute_all_conditions(current_map, advanced_mode=self.advanced_mode)
        try:
            targets = all_conds.intersection_hexes(sel)
        except KeyError as e:
            print(f"Unknown rule selected: {e}")
            return
        if not targets:
            self.canvas._zero_targets_dim_full_map = True
            for piece in self.pieces:
                if self.canvas.item_slot.get(piece) is not None:
                    piece.update()
            for m in self.markers:
                m.update()
            if self.highlight_overlay:
                self.highlight_overlay.update_highlights()
            show_toast(self.pages_stack, TOAST_NO_INTERSECTION)
            self._build_tab_solve_active = True
            touch_breadcrumbs(self)
            return
        self.canvas._zero_targets_dim_full_map = False
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is None:
                continue
            for i in range(len(piece.cells)):
                coords = self.controller.cell_big_coords(piece, i)
                if coords is not None and coords in targets:
                    piece.highlighted.add(i)
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is not None:
                piece.update()
        for m in self.markers:
            m.update()
        if self.highlight_overlay:
            self.highlight_overlay.update_highlights()
        count = len(targets)
        msg = TOAST_HEX_HIGHLIGHTED if count == 1 else TOAST_HEXES_HIGHLIGHTED.format(count=count)
        show_toast(self.pages_stack, msg)
        self._build_tab_solve_active = True
        touch_breadcrumbs(self)

