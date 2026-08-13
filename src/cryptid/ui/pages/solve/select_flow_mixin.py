"""Solver page: Load-map UI: search, solve mode, select-mode solve and confirm."""
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



class SolveSelectFlowMixin:
    def _on_select_players_changed(self, _: str) -> None:
        """When in solve mode, clear highlights and blur clues so user must click Solve again."""
        if self._in_solve_mode and self._solve_mode_map_data:
            card = self.map_cards_manager.get_card_for_map_data(self._solve_mode_map_data)
            if card:
                card.clear_preview_highlights()
            self.map_cards_manager.set_blur_for_all_cards(True)

    def _set_search_visible(self, visible: bool) -> None:
        """Show or hide search label and field."""
        lbl = self.selectContent.findChild(QLabel, "lblSelectSearch") if self.selectContent else None
        if lbl:
            lbl.setVisible(visible)
        if self.edtSelectSearch:
            self.edtSelectSearch.setVisible(visible)

    def _set_advanced_mode_visible(self, visible: bool) -> None:
        """Show or hide Advanced mode label and toggle."""
        lbl = self.selectContent.findChild(QLabel, "lblSelectAdvancedMode") if self.selectContent else None
        if lbl:
            lbl.setVisible(visible)
        self.cbSelectAdvancedMode.setVisible(visible)

    def _show_select_browse_filters(self) -> None:
        """Ensure Advanced mode + Search are visible on the Load Map browse bar."""
        self._set_advanced_mode_visible(True)
        self._set_search_visible(True)

    def _enter_solve_mode(self, map_data: dict) -> None:
        """Enter solve mode: show only card, blur off. Players combo stays enabled."""
        self._in_solve_mode = True
        self._solve_mode_map_data = map_data
        self.map_cards_manager.enter_solve_mode(map_data)
        self.map_cards_manager.set_blur_for_all_cards(False)
        self._set_advanced_mode_visible(False)
        self._set_search_visible(False)
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def _exit_solve_mode(self) -> None:
        """Exit solve mode: restore cards, controls, blur on."""
        self._in_solve_mode = False
        self._solve_mode_map_data = None
        self.board_builder.reset_board()
        u = getattr(self, "_board_undo", None)
        if u is not None:
            u.reset()
        self.map_cards_manager.exit_solve_mode()
        self.map_cards_manager.set_blur_for_all_cards(True)
        self.cbSelectPlayers.setEnabled(True)
        self.cbSelectAdvancedMode.blockSignals(True)
        self.cbSelectAdvancedMode.setChecked(False)
        self.cbSelectAdvancedMode.blockSignals(False)
        self._show_select_browse_filters()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)
        if hasattr(self, "_update_board_undo_tracking"):
            self._update_board_undo_tracking()

    def _on_solve_select_mode_clicked(self, map_data: dict) -> None:
        """Run solve for predefined map: highlight intersection on map card, toast. No board load."""
        players = int((self.cbSelectPlayers.currentText() or "3").strip()) if self.cbSelectPlayers.currentText() in ("3", "4", "5") else 3
        advanced = bool(map_data.get("advancedMode", False))
        sel = get_clues_for_map(map_data, players)
        if any(not r for r in sel):
            return
        current_map = build_map_from_data(map_data)
        all_conds = compute_all_conditions(current_map, advanced_mode=advanced)
        try:
            targets = all_conds.intersection_hexes(sel)
        except KeyError:
            return
        if not targets:
            card = self.map_cards_manager.get_card_for_map_data(map_data)
            if card:
                card.apply_highlights(set())
            show_toast(self.pages_stack, TOAST_NO_INTERSECTION)
            return
        highlighted_cells = targets_to_highlighted_cells(targets, map_data)
        card = self.map_cards_manager.get_card_for_map_data(map_data)
        if card:
            card.apply_highlights(highlighted_cells)
        count = len(targets)
        msg = TOAST_HEX_HIGHLIGHTED if count == 1 else TOAST_HEXES_HIGHLIGHTED.format(count=count)
        show_toast(self.pages_stack, msg)

    def _on_solve_or_confirm_clicked(self) -> None:
        if self.btnMapSelect.isChecked():
            map_data = self._solve_mode_map_data or self.map_cards_manager.get_selected_map_data()
            if map_data is None:
                return
            self._enter_solve_mode(map_data)
            self._on_solve_select_mode_clicked(map_data)
        else:
            self.on_solve_clicked()


