"""Build/Select state snapshots and cross-page navigation."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QComboBox, QCheckBox, QLineEdit

from logic.conditions import all_condition_labels
from settings.strings import BTN_END_SIMULATION
from ui.shared.widgets import (
    get_selected_player_color,
    refresh_player_color_combos,
    sync_clear_button_visibility,
    sync_combo_placeholder_style,
)

from ui.pages.deduction.deduction_types import ModeState


class DeductionStateNavMixin:

    def _freeze_map_checkbox_state(self) -> tuple[bool, bool]:
        """Return (checked, enabled) for Freeze map, or (False, False) if missing."""
        cb = getattr(self.board_builder, "cbFreezeMap", None) if hasattr(self, "board_builder") and self.board_builder else None
        if cb is None:
            return (False, False)
        return (bool(cb.isChecked()), bool(cb.isEnabled()))

    def _save_build_state(self) -> None:
        """Save Build mode state (board + panel). Only when board shows Build data (not Select sim)."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        # If the user has never interacted with Build, keep using the fresh "home" layout
        # instead of persisting an effectively-empty snapshot.
        if not getattr(self, "_build_dirty", False):
            self._build_state = None
            return
        # Only persist Build state when the Build tab is actually active.
        # This prevents overwriting the Build snapshot with the Select-sim board layout.
        if getattr(self, "mapSourceStack", None) is not None:
            try:
                if self.mapSourceStack.currentIndex() != self._IDX_BUILD:
                    return
            except Exception:
                # If mapSourceStack is misconfigured, fail safe by not overwriting the saved state.
                return
        if getattr(self, "_in_solve_mode", False):
            return
        in_sim = self.btnSolve.text() == BTN_END_SIMULATION
        hl = True
        if self.board_builder.cbHighlightValidSpaces is not None:
            hl = self.board_builder.cbHighlightValidSpaces.isChecked()
        fz_checked, fz_enabled = self._freeze_map_checkbox_state()
        self._build_state = ModeState(
            map_data=self.board_builder.export_board_to_map_data(),
            players=self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip()) or 3,
            advanced=self.advanced_mode,
            rule=(self.rules.read_selected_rules(5)[0] or "").strip(),
            names=[(self.edtPlayer[i].text() or "").strip() if i < len(self.edtPlayer) and self.edtPlayer[i] else "" for i in range(5)],
            colors=[get_selected_player_color(self.cbColorP[i]) if i < len(self.cbColorP) and self.cbColorP[i] else "" for i in range(5)],
            in_simulation=in_sim,
            highlight_valid_spaces=hl,
            freeze_map_checked=fz_checked,
            freeze_map_enabled=fz_enabled,
        )

    def _save_build_state_for_navigation(self) -> None:
        """Always snapshot Create Map (build stack) for restoring after leaving the Deduction page."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        # Do not return early based on mapSourceStack or _in_solve_mode: those can desync from the
        # Create/Load radio while the board still shows Create Map data, leaving _build_state stale
        # and st.in_simulation False so cross-page restore skips _restore_simulation_session entirely.
        in_sim = self.btnSolve.text() == BTN_END_SIMULATION
        hl = True
        if self.board_builder.cbHighlightValidSpaces is not None:
            hl = self.board_builder.cbHighlightValidSpaces.isChecked()
        fz_checked, fz_enabled = self._freeze_map_checkbox_state()
        self._build_state = ModeState(
            map_data=self.board_builder.export_board_to_map_data(),
            players=self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip()) or 3,
            advanced=self.advanced_mode,
            rule=(self.rules.read_selected_rules(5)[0] or "").strip(),
            names=[(self.edtPlayer[i].text() or "").strip() if i < len(self.edtPlayer) and self.edtPlayer[i] else "" for i in range(5)],
            colors=[get_selected_player_color(self.cbColorP[i]) if i < len(self.cbColorP) and self.cbColorP[i] else "" for i in range(5)],
            in_simulation=in_sim,
            highlight_valid_spaces=hl,
            freeze_map_checked=fz_checked,
            freeze_map_enabled=fz_enabled,
        )
        self._build_dirty = True

    def on_navigate_away(self) -> None:
        """Snapshot Load Map / Create Map UI when switching to another app page."""
        self._nav_leave_load_map = bool(self.btnMapSelect.isChecked())
        if self.btnMapSelect.isChecked():
            st_sel = getattr(self, "_select_state", None)
            select_sim_active = (
                (getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None))
                or (
                    st_sel is not None
                    and getattr(st_sel, "in_simulation", False)
                    and getattr(st_sel, "map_data", None)
                )
                or self.btnSolve.text() == BTN_END_SIMULATION
            )
            if select_sim_active:
                sess = self._capture_simulation_session()
                if sess is not None:
                    self._select_sim_session = sess
            else:
                self._select_sim_session = None
            if not select_sim_active:
                self._save_select_state()
        else:
            # While End Simulation is shown, always try to capture; do not require _rule_combos (can be
            # cleared transiently). Only clear the snapshot when the user is clearly not in simulation.
            if (
                hasattr(self, "board_builder")
                and self.board_builder is not None
                and self.btnSolve.text() == BTN_END_SIMULATION
            ):
                sess = self._capture_simulation_session()
                if sess is not None:
                    self._build_sim_session = sess
            if self.btnSolve.text() != BTN_END_SIMULATION:
                self._build_sim_session = None
            self._save_build_state_for_navigation()
        self._navigation_state_saved = True

    def on_navigate_to(self) -> None:
        """Restore snapshot after returning to Deduction from another app page."""
        if not getattr(self, "_navigation_state_saved", False):
            return
        self._navigation_state_saved = False
        want_load_map = getattr(self, "_nav_leave_load_map", False)
        self.btnMapBuild.blockSignals(True)
        self.btnMapSelect.blockSignals(True)
        self.btnMapBuild.setChecked(not want_load_map)
        self.btnMapSelect.setChecked(want_load_map)
        self.btnMapBuild.blockSignals(False)
        self.btnMapSelect.blockSignals(False)

        if want_load_map:
            st_sel = getattr(self, "_select_state", None)
            returning_select_sim = (
                self._select_sim_session is not None
                and st_sel is not None
                and getattr(st_sel, "in_simulation", False)
            )
            if not returning_select_sim:
                self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_BROWSE)
                self.mapListCardsContainer.setVisible(True)
                mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
                if mc:
                    mc.setVisible(True)
            else:
                self.mapListCardsContainer.setVisible(False)
                mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
                if mc:
                    mc.setVisible(False)
            self._restore_select_state()
            if not returning_select_sim and not getattr(self, "_in_solve_mode", False):
                self._show_select_browse_filters()
        else:
            self.mapListCardsContainer.setVisible(False)
            mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
            if mc:
                mc.setVisible(False)
            self._restore_build_state()
        # Do not call _on_map_source_mode_changed(): SolvePageController would show the map list
        # whenever Select is checked and break Load Map simulation layout restored above.
        self._update_solve_and_reset_for_mode()

    def _apply_build_panel_from_state(self, st: ModeState) -> None:
        """Sync Create Map panel + markers from ModeState without loading map data."""
        if self.cbFreezeMap is not None:
            fz_en = bool(getattr(st, "freeze_map_enabled", False))
            fz_checked = (
                bool(getattr(st, "freeze_map_checked", False)) if fz_en else False
            )
            self.cbFreezeMap.blockSignals(True)
            self.cbFreezeMap.setChecked(fz_checked)
            self.cbFreezeMap.setEnabled(fz_en)
            self.cbFreezeMap.blockSignals(False)
            if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
                self.status_list_manager._apply_freeze_map_drag_state()
        self.advanced_mode = st.advanced
        self._rule_labels = all_condition_labels(advanced_mode=st.advanced)
        self.rules.set_rule_labels(self._rule_labels)
        self.rules.set_deduction_layout(st.players)
        self.cbBuildPlayers.blockSignals(True)
        idx = self.cbBuildPlayers.findText(str(st.players), Qt.MatchFixedString)
        self.cbBuildPlayers.setCurrentIndex(idx if idx != -1 else 0)
        self.cbBuildPlayers.blockSignals(False)
        self.cbBuildAdvancedMode.blockSignals(True)
        self.cbBuildAdvancedMode.setChecked(st.advanced)
        self.cbBuildAdvancedMode.blockSignals(False)
        if st.rule:
            self.rules.cbRuleP[0].blockSignals(True)
            idx_r = self.rules.cbRuleP[0].findText(st.rule)
            self.rules.cbRuleP[0].setCurrentIndex(idx_r if idx_r >= 0 else 0)
            self.rules.cbRuleP[0].blockSignals(False)
            sync_clear_button_visibility(self.rules.cbRuleP[0])
            sync_combo_placeholder_style(self.rules.cbRuleP[0])
        for i, edt in enumerate(self.edtPlayer):
            if edt is not None and i < len(st.names):
                edt.blockSignals(True)
                edt.setText(st.names[i] or "")
                edt.blockSignals(False)
        refresh_player_color_combos(self.cbColorP)
        for i, cb in enumerate(self.cbColorP):
            if cb is not None and i < len(st.colors) and st.colors[i]:
                cb.blockSignals(True)
                idx_c = cb.findText(st.colors[i])
                if idx_c >= 0:
                    cb.setCurrentIndex(idx_c)
                cb.blockSignals(False)
        refresh_player_color_combos(self.cbColorP)
        for cb in self.cbColorP:
            if cb is not None:
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)
        self.board_builder.apply_marker_visibility(st.advanced)
        if not st.advanced:
            def _rewrite_from_state() -> None:
                u = getattr(self, "_board_undo", None)
                if u is not None:
                    u.rewrite_snapshots_strip_advanced_markers()

            _rewrite_from_state()
            QTimer.singleShot(0, _rewrite_from_state)

    def _clear_simulation_ui_for_restore(self) -> None:
        """Clear simulation UI (chips, clue grid, status) without resetting board. Used when restoring Build after Select sim."""
        self._set_simulation_locked(False)
        self._in_solve_mode = False
        self._solve_mode_map_data = None
        canvas = getattr(self, "canvas", None) or (self.board_builder.canvas if hasattr(self, "board_builder") and self.board_builder else None)
        if canvas is not None:
            setattr(canvas, "_on_chip_assigned", None)
            setattr(canvas, "_on_chip_released", None)
            setattr(canvas, "_zero_targets_dim_full_map", False)
        for attr in ("_rule_combos", "_deactivated_combo_indices", "_impossible_per_player", "_initial_clues_per_player", "_all_conds", "_simulation_players"):
            if hasattr(self, attr):
                delattr(self, attr)
        if hasattr(self, "_hide_clue_icon"):
            self._hide_clue_icon()
        if hasattr(self, "_clues_table_section") and self._clues_table_section is not None:
            self._clues_table_section.setVisible(False)
        self.btnSolve.setText("Start Simulation")
        if hasattr(self, "board_builder") and self.board_builder is not None:
            if self.board_builder.controller and hasattr(self.board_builder.controller, "reset_state"):
                self.board_builder.controller.reset_state()
            self.board_builder.hide_chips()
        if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
            self.status_list_manager.reset_for_build()
            self.status_list_manager._apply_freeze_markers_drag_state(False)

    def _restore_build_state(self) -> None:
        """Restore Build mode: reparent view, swap to Build panel, load map. Build panel was never overwritten."""
        self._reparent_view_to(self._build_view_container)
        self._swap_to_build_panel()
        self.mapSourceStack.setCurrentIndex(self._IDX_BUILD)
        st = self._build_state
        # If user never edited Build, always show home state (tiles in rack, empty canvas).
        if not getattr(self, "_build_dirty", False):
            self._clear_simulation_ui_for_restore()
            self._reset_build_mode_state()
            return
        if st is None or not st.map_data:
            self._clear_simulation_ui_for_restore()
            self._reset_build_mode_state()
            return

        # Simulation was left running in memory: avoid hide_chips + map reload + session replay — that
        # reset chip positions and caused a visible delay. Re-sync panel + chrome only.
        live_build_sim = (
            self.btnSolve.text() == BTN_END_SIMULATION
            and bool(getattr(self, "_rule_combos", None))
            and getattr(self.board_builder, "_chips_mode", False)
        )
        if self._build_sim_session is not None or (st.in_simulation and live_build_sim):
            self._apply_build_panel_from_state(st)
            bb = self.board_builder
            if bb.canvas is not None:
                bb.canvas._show_highlights = st.highlight_valid_spaces
            if bb.cbHighlightValidSpaces is not None:
                bb.cbHighlightValidSpaces.blockSignals(True)
                bb.cbHighlightValidSpaces.setChecked(st.highlight_valid_spaces)
                bb.cbHighlightValidSpaces.blockSignals(False)
            if bb.highlight_overlay is not None:
                bb.highlight_overlay.setVisible(st.highlight_valid_spaces)
            self._reapply_build_simulation_chrome_after_restore()
            if hasattr(self, "_sync_hex_highlights_from_combos"):
                self._sync_hex_highlights_from_combos()
            if hasattr(self, "_update_status_and_structures"):
                self._update_status_and_structures()
            return

        self._clear_simulation_ui_for_restore()
        self.board_builder.load_from_map_data(st.map_data, freeze=False)
        self._apply_build_panel_from_state(st)
        # Restore build layout: freeze row, highlight toggle, proxy z-values
        bb = self.board_builder
        if bb._freeze_row is not None:
            bb._freeze_row.setVisible(True)
        if bb._highlight_row is not None:
            bb._highlight_row.setVisible(False)
        if hasattr(bb, "_proxy_freeze") and bb._proxy_freeze is not None:
            bb._proxy_freeze.setZValue(10002)
        if hasattr(bb, "_proxy_hl") and bb._proxy_hl is not None:
            bb._proxy_hl.setZValue(10001)
            if bb.canvas is not None:
                bb.canvas._show_highlights = st.highlight_valid_spaces
            if bb.cbHighlightValidSpaces is not None:
                bb.cbHighlightValidSpaces.blockSignals(True)
                bb.cbHighlightValidSpaces.setChecked(st.highlight_valid_spaces)
                bb.cbHighlightValidSpaces.blockSignals(False)
            if bb.highlight_overlay is not None:
                bb.highlight_overlay.setVisible(st.highlight_valid_spaces)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()
        if st.in_simulation and hasattr(self, "on_solve_clicked"):
            self.on_solve_clicked()

    def _save_select_state(self) -> None:
        """Save Select mode state."""
        # If we already have a Select-sim snapshot (in_simulation=True), never overwrite it here.
        # This keeps the simulation state stable while the user toggles between Build and Select.
        st = getattr(self, "_select_state", None)
        if st is not None and getattr(st, "in_simulation", False):
            return
        # Also, if we're currently in Select-sim simulation, rely on the snapshot created
        # when simulation started instead of replacing it with a non-simulation state.
        if getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None):
            return
        map_data = self.map_cards_manager.get_selected_map_data()
        card = self.map_cards_manager.get_card_for_map_data(map_data) if map_data else None
        self._select_state = ModeState(
            map_data=map_data,
            players=int((self.cbSelectPlayers.currentText() or "3").strip()) if self.cbSelectPlayers.currentText() in ("3", "4", "5") else 3,
            advanced=bool(self.cbSelectAdvancedMode.isChecked()),
            select_custom_maps=bool(
                getattr(self, "cbSelectCustomMaps", None) and self.cbSelectCustomMaps.isChecked()
            ),
            rule=card.get_selected_rule() if card else "",
            names=card.get_player_names() if card else [""] * 5,
            colors=card.get_player_colors() if card else [""] * 5,
            in_simulation=False,
            selected_map_data=map_data,
        )

    def _apply_saved_deduction_to_map_card(self, card: Any, st: ModeState) -> None:
        """Re-apply Load-map clue panel from ``_select_state`` (Create↔Load must not wipe fields)."""
        if not getattr(card, "_deduction_mode", False):
            return
        card.ensure_clues_built()
        if getattr(card, "_players", 3) != st.players:
            card.update_clues(st.players)
        combos = getattr(card, "_clue_combos", [])
        if st.rule and combos:
            cb0 = combos[0]
            cb0.blockSignals(True)
            idx_r = cb0.findText(st.rule)
            cb0.setCurrentIndex(idx_r if idx_r >= 0 else 0)
            cb0.blockSignals(False)
            sync_clear_button_visibility(cb0)
            sync_combo_placeholder_style(cb0)
        edt_list = getattr(card, "_edt_player", [])
        for i, edt in enumerate(edt_list):
            if edt is not None and i < len(st.names):
                edt.blockSignals(True)
                edt.setText(st.names[i] or "")
                edt.blockSignals(False)
        cb_colors = getattr(card, "_cb_color", [])
        refresh_player_color_combos(cb_colors)
        for i, cb in enumerate(cb_colors):
            if cb is not None and i < len(st.colors) and st.colors[i]:
                cb.blockSignals(True)
                idx_c = cb.findText(st.colors[i])
                if idx_c >= 0:
                    cb.setCurrentIndex(idx_c)
                cb.blockSignals(False)
        refresh_player_color_combos(cb_colors)
        for cb in cb_colors:
            if cb is not None:
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)
        if hasattr(card, "_update_player_rows_visibility"):
            card._update_player_rows_visibility()

    def _restore_select_state(self) -> None:
        """Restore Select mode state."""
        st = self._select_state
        if st is None:
            self.map_cards_manager.exit_solve_mode()
            self.map_cards_manager.clear_selection()
            self._in_solve_mode = False
            self._solve_mode_map_data = None
            self._show_select_browse_filters()
            return
        self._in_solve_mode = st.in_simulation
        self._solve_mode_map_data = st.selected_map_data
        if st.in_simulation and st.map_data:
            if (
                self._select_sim_session is not None
                and self.mapSourceStack.currentIndex() == self._IDX_SELECT_SIM
                and self.btnSolve.text() == BTN_END_SIMULATION
                and bool(getattr(self, "_rule_combos", None))
                and getattr(self.board_builder, "_chips_mode", False)
            ):
                self.map_cards_manager.enter_solve_mode(st.map_data)
                self.map_cards_manager.set_blur_for_all_cards(False)
                if hasattr(self, "_set_advanced_mode_visible"):
                    self._set_advanced_mode_visible(False)
                if hasattr(self, "_set_search_visible"):
                    self._set_search_visible(False)
                self._reparent_view_to(self._select_sim_view_container)
                self._swap_to_select_sim_panel()
                self.btnSolve.setText(BTN_END_SIMULATION)
                self.btnSolve.setEnabled(True)
                self._set_simulation_locked(True)
                if hasattr(self, "_sync_hex_highlights_from_combos"):
                    self._sync_hex_highlights_from_combos()
                if hasattr(self, "_show_clue_icon"):
                    self._show_clue_icon()
                if hasattr(self, "_update_clue_icon_color_states"):
                    self._update_clue_icon_color_states()
                if hasattr(self, "_update_status_and_structures"):
                    self._update_status_and_structures()
                return
            self.map_cards_manager.enter_solve_mode(st.map_data)
            self.map_cards_manager.set_blur_for_all_cards(False)
            if hasattr(self, "_set_advanced_mode_visible"):
                self._set_advanced_mode_visible(False)
            if hasattr(self, "_set_search_visible"):
                self._set_search_visible(False)
            self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_SIM)
            self.mapListCardsContainer.setVisible(False)
            mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
            if mc:
                mc.setVisible(False)
            self._reparent_view_to(self._select_sim_view_container)
            self.board_builder.load_from_map_data(st.map_data, freeze=True)
            if getattr(self, "_rules_select", None) is None:
                self._setup_select_sim_panel()
            self.advanced_mode = st.advanced
            self._rule_labels = all_condition_labels(advanced_mode=st.advanced)
            self._rules_select.set_rule_labels(self._rule_labels)
            self._rules_select.set_deduction_layout(st.players)
            self._select_sim_cb_players.blockSignals(True)
            idx = self._select_sim_cb_players.findText(str(st.players), Qt.MatchFixedString)
            self._select_sim_cb_players.setCurrentIndex(idx if idx != -1 else 0)
            self._select_sim_cb_players.blockSignals(False)
            self._select_sim_cb_advanced.blockSignals(True)
            self._select_sim_cb_advanced.setChecked(st.advanced)
            self._select_sim_cb_advanced.blockSignals(False)
            if st.rule:
                self._rules_select.cbRuleP[0].blockSignals(True)
                idx_r = self._rules_select.cbRuleP[0].findText(st.rule)
                self._rules_select.cbRuleP[0].setCurrentIndex(idx_r if idx_r >= 0 else 0)
                self._rules_select.cbRuleP[0].blockSignals(False)
                sync_clear_button_visibility(self._rules_select.cbRuleP[0])
                sync_combo_placeholder_style(self._rules_select.cbRuleP[0])
            for i, edt in enumerate(self._select_sim_edt_player):
                if edt is not None and i < len(st.names):
                    edt.blockSignals(True)
                    edt.setText(st.names[i] or "")
                    edt.blockSignals(False)
            refresh_player_color_combos(self._select_sim_cb_color)
            for i, cb in enumerate(self._select_sim_cb_color):
                if cb is not None and i < len(st.colors) and st.colors[i]:
                    cb.blockSignals(True)
                    idx_c = cb.findText(st.colors[i])
                    if idx_c >= 0:
                        cb.setCurrentIndex(idx_c)
                    cb.blockSignals(False)
            refresh_player_color_combos(self._select_sim_cb_color)
            for cb in self._select_sim_cb_color:
                if cb is not None:
                    sync_clear_button_visibility(cb)
                    sync_combo_placeholder_style(cb)
            self._swap_to_select_sim_panel()
            # Re-enter simulation UI: recompute combos, highlights, chips, and status panel
            # as if Start Simulation was just pressed for this map.
            self.board_builder.apply_marker_visibility(st.advanced)
            if hasattr(self, "_update_status_and_structures"):
                self._update_status_and_structures()
            self.btnSolve.setText(BTN_END_SIMULATION)
            self.btnSolve.setEnabled(True)
            self._set_simulation_locked(True)
            # Restore Select-sim session (chips, highlights, status) if we have one
            if self._select_sim_session is not None:
                self._restore_simulation_session(self._select_sim_session)
        else:
            self._reparent_view_to(self._build_view_container)
            self._swap_to_build_panel()
            self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_BROWSE)
            cb_cm = getattr(self, "cbSelectCustomMaps", None)
            if cb_cm is not None:
                cb_cm.blockSignals(True)
                cb_cm.setChecked(getattr(st, "select_custom_maps", False))
                cb_cm.blockSignals(False)
                self._apply_deduction_select_maps_source(getattr(st, "select_custom_maps", False))
            self.cbSelectPlayers.blockSignals(True)
            idx_sp = self.cbSelectPlayers.findText(str(st.players), Qt.MatchFixedString)
            self.cbSelectPlayers.setCurrentIndex(idx_sp if idx_sp != -1 else 0)
            self.cbSelectPlayers.blockSignals(False)
            self.cbSelectAdvancedMode.blockSignals(True)
            self.cbSelectAdvancedMode.setChecked(st.advanced)
            self.cbSelectAdvancedMode.blockSignals(False)
            # exit_solve_mode() used to clear_selection() -> clear_deduction_controls(); keep forms.
            self.map_cards_manager.exit_solve_mode(preserve_deduction_forms=True)
            if st.selected_map_data:
                for card, data in getattr(self.map_cards_manager, "_map_cards", []):
                    if data == st.selected_map_data:
                        card.set_selected(True)
                        self.map_cards_manager._selected_map_card = card
                        self._apply_saved_deduction_to_map_card(card, st)
                        break
            self.map_cards_manager.filter_map_cards()
            self._show_select_browse_filters()

