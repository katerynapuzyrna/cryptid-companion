"""Deduction Mode page: thin coordinator; behavior lives in ui.pages.deduction mixins."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QComboBox, QLineEdit, QCheckBox

from ui.pages.page_solve import SolvePageController
from ui.pages.deduction.select_sim import DeductionSelectSimMixin
from ui.pages.deduction.state_nav import DeductionStateNavMixin
from ui.pages.deduction.map_source import DeductionMapSourceMixin
from ui.pages.deduction.clues_dialogs import DeductionCluesDialogsMixin
from ui.pages.deduction.panels import DeductionPanelsMixin
from ui.pages.deduction.simulation_flow import DeductionSimulationFlowMixin
from ui.pages.deduction.chips_session import DeductionChipsSessionMixin
from ui.shared.widgets import (
    setup_player_color_combo,
    add_clear_button_inside_combo,
    refresh_player_color_combos,
)
from settings.strings import (
    TOOLTIP_MAP_SOURCE_BLOCKED_BY_SIM,
    BTN_END_SIMULATION,
)


class DeductionPageController(
    DeductionChipsSessionMixin,
    DeductionSimulationFlowMixin,
    DeductionCluesDialogsMixin,
    DeductionPanelsMixin,
    DeductionMapSourceMixin,
    DeductionStateNavMixin,
    DeductionSelectSimMixin,
    SolvePageController,
):
    """Deduction Mode: only 1st player rule, Start Simulation instead of Solve."""

    def __init__(self, page: QWidget, window: QWidget):
        self._deduction_mode = True
        self._build_dirty: bool = False
        self._select_sim_view_container: QWidget | None = None
        self._build_view_container: QWidget | None = None
        self._select_sim_cb_players: QComboBox | None = None
        self._select_sim_cb_advanced: QCheckBox | None = None
        self._select_sim_cb_rule_p: list[QComboBox | None] = []
        self._select_sim_edt_player: list[QLineEdit | None] = []
        self._select_sim_cb_color: list[QComboBox | None] = []
        self._rules_select = None
        self._status_list_manager_select = None
        self._build_sim_session = None
        self._select_sim_session = None
        self.cbSelectCustomMaps: QCheckBox | None = None
        super().__init__(page, window)
        self._wire_deduction_custom_maps_toggle()
        self._raise = self._raise_deduction
        self._clue_icon_proxy = None

    def _raise_deduction(self, name: str):
        raise RuntimeError(f"Widget '{name}' not found in page_deduction (check objectName).")

    def _undo_tracking_for_board(self) -> bool:
        if self.btnMapBuild.isChecked():
            return True
        bb = getattr(self, "board_builder", None)
        return bool(
            getattr(self, "_in_solve_mode", False)
            and bb is not None
            and getattr(bb, "_chips_mode", False)
        )

    def setup(self) -> None:
        """Wire Deduction page: same as Solve but rules_count=1, deduction_mode for cards."""
        super().setup()
        self.cbColorP: list[QComboBox] = [
            self._page.findChild(QComboBox, f"cbColorP{i}") for i in range(1, 6)
        ]
        self.edtPlayer: list[QLineEdit] = [
            self._page.findChild(QLineEdit, f"edtPlayer{i}") for i in range(1, 6)
        ]
        _placeholders = ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"]
        for i, edt in enumerate(self.edtPlayer):
            if edt is not None and i < len(_placeholders):
                edt.setPlaceholderText(_placeholders[i])
        for cb in self.cbColorP:
            if cb is not None:
                setup_player_color_combo(cb)
                add_clear_button_inside_combo(cb)
                cb.currentIndexChanged.connect(self._on_color_combo_changed)
        refresh_player_color_combos(self.cbColorP)
        players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip())
        self.rules.set_deduction_layout(players or 3)
        self.btnSolve.setText("Start Simulation")
        self._calculating_overlay = self._make_calculating_overlay()
        self._calculating_simulation = False
        self._clues_table_section = self._make_clues_table_section()
        self._apply_player_color_borders()
        self._placeholders = ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"]
        for i, edt in enumerate(self.edtPlayer):
            if edt is not None:
                edt.textChanged.connect(lambda t, idx=i: self._on_player_name_changed(idx))
                self._on_player_name_changed(i)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()
        self._build_state = None
        self._select_state = None
        self._build_dirty = False
        self._save_build_state()
        self._navigation_state_saved = False

        if not getattr(self, "_deduction_map_source_tooltips_registered", False):
            self._deduction_map_source_tooltips_registered = True
            self._app_tooltip.add(
                self.btnMapSelect,
                TOOLTIP_MAP_SOURCE_BLOCKED_BY_SIM,
                only_when_disabled=True,
                only_when=lambda: (
                    self.btnSolve.text() == BTN_END_SIMULATION and self.btnMapBuild.isChecked()
                ),
            )
            self._app_tooltip.add(
                self.btnMapBuild,
                TOOLTIP_MAP_SOURCE_BLOCKED_BY_SIM,
                only_when_disabled=True,
                only_when=lambda: (
                    self.btnSolve.text() == BTN_END_SIMULATION and self.btnMapSelect.isChecked()
                ),
            )
