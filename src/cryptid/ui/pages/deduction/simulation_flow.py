"""Start/end simulation, solve flow, map-source mode UI updates."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget, QComboBox

from logic.conditions import all_condition_labels, compute_all_conditions
from logic.rule_combinations import (
    find_rule_combinations_with_exactly_one_intersection,
    distinct_valid_clues_per_player,
)
from settings.config import ICON_HELP
from settings.strings import (
    TOAST_HEX_HIGHLIGHTED,
    TOAST_HEXES_HIGHLIGHTED,
    BTN_END_SIMULATION,
    BTN_RESET_ALL,
    BTN_RESET_CHIPS,
    END_SIMULATION_CONFIRM_MSG,
)
from ui.shared.widgets import (
    assign_colors_to_empty_combos,
    get_selected_player_color,
    get_player_color_hex,
    refresh_player_color_combos,
    show_toast,
    sync_clear_button_visibility,
    sync_combo_placeholder_style,
)

from ui.pages.deduction.deduction_types import ModeState


class DeductionSimulationFlowMixin:
    def _get_simulation_status(self) -> tuple[int, list[int], list[str]] | None:
        """Return (valid_hex_count, valid_clues_per_player, player_display_names) for status list, or None if not in simulation."""
        combos = getattr(self, "_rule_combos", [])
        deactivated = getattr(self, "_deactivated_combo_indices", set())
        clues = getattr(self, "_clues_per_player", [])
        players = getattr(self, "_simulation_players", None)
        if players is None or players not in (3, 4, 5):
            players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip()) or 3
        if not combos or not clues:
            # Still return simulation data (0 valid hexes, 0 clues per player) so status panel switches to simulation mode
            valid_clues_per_player = [0] * players
            placeholders = getattr(self, "_placeholders", ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"])
            player_display_names = []
            for i in range(players):
                edt = self.edtPlayer[i] if i < len(self.edtPlayer) else None
                name = (edt.text() or "").strip() if edt is not None else ""
                player_display_names.append(name or (placeholders[i] if i < len(placeholders) else f"Player {i + 1}"))
            return (0, valid_clues_per_player, player_display_names)
        all_targets = {
            target_hex for i, (_, target_hex) in enumerate(combos) if i not in deactivated
        }
        valid_hex_count = len(all_targets)
        valid_clues_per_player = [len(c) for c in clues]
        placeholders = getattr(self, "_placeholders", ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"])
        player_display_names = []
        for i in range(len(valid_clues_per_player)):
            edt = self.edtPlayer[i] if i < len(self.edtPlayer) else None
            name = (edt.text() or "").strip() if edt is not None else ""
            player_display_names.append(name or (placeholders[i] if i < len(placeholders) else f"Player {i + 1}"))
        return (valid_hex_count, valid_clues_per_player, player_display_names)

    def _set_simulation_locked(self, locked: bool) -> None:
        """Disable (locked=True) or enable (locked=False) controls after Start Simulation."""
        self.cbBuildAdvancedMode.setEnabled(not locked)
        self.cbBuildPlayers.setEnabled(not locked)
        self.rules.cbRuleP[0].setEnabled(not locked)
        sync_clear_button_visibility(self.rules.cbRuleP[0])
        for cb in self.cbColorP:
            if cb is not None:
                cb.setEnabled(not locked)
                sync_clear_button_visibility(cb)

    def _reapply_build_simulation_chrome_after_restore(self) -> None:
        """After _restore_simulation_session on Create Map: match on_solve_clicked tail (callbacks, rows, lock)."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        bb = self.board_builder
        if not getattr(bb, "_chips_mode", False):
            bb.show_chips()
        if self.canvas is not None:
            self.canvas._on_chip_assigned = self._on_chip_placed
            self.canvas._on_chip_released = self._on_chip_released
        self._show_clue_icon()
        self._update_clue_icon_color_states()
        self.btnSolve.setEnabled(True)
        self.btnSolve.setText(BTN_END_SIMULATION)
        self._set_simulation_locked(True)
        if bb._freeze_row is not None:
            bb._freeze_row.setVisible(False)
        if bb._highlight_row is not None:
            bb._highlight_row.setVisible(True)
        if hasattr(bb, "_proxy_freeze") and bb._proxy_freeze is not None:
            bb._proxy_freeze.setZValue(10000)
        if hasattr(bb, "_proxy_hl") and bb._proxy_hl is not None:
            bb._proxy_hl.setZValue(10002)
        if hasattr(self, "cbFreezeMap") and self.cbFreezeMap is not None:
            self.cbFreezeMap.blockSignals(True)
            self.cbFreezeMap.setChecked(True)
            self.cbFreezeMap.setEnabled(True)
            self.cbFreezeMap.blockSignals(False)
            if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
                self.status_list_manager._apply_freeze_map_drag_state()
                self.status_list_manager._apply_freeze_markers_drag_state(True)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()
        self._update_solve_and_reset_for_mode()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def _on_solve_or_confirm_clicked(self) -> None:
        """When End Simulation: confirm then reset. Otherwise: run Start Simulation or select-mode handler."""
        if self.btnSolve.text() == BTN_END_SIMULATION:
            mb = QMessageBox(self.window)
            mb.setWindowTitle("End Simulation")
            mb.setText(END_SIMULATION_CONFIRM_MSG)
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
            yes_btn.style().unpolish(yes_btn)
            yes_btn.style().polish(yes_btn)
            mb.exec()
            if mb.clickedButton() == yes_btn:
                if getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None):
                    self._reset_select_mode_simulation()
                else:
                    self._reset_build_mode_state()
                self._update_solve_and_reset_for_mode()
                from ui.shell.breadcrumb_manager import touch_breadcrumbs

                touch_breadcrumbs(self)
            return
        if self.btnMapSelect.isChecked():
            map_data = self._solve_mode_map_data or self.map_cards_manager.get_selected_map_data()
            if map_data is None:
                return
            self._on_solve_select_mode_clicked(map_data)
            return
        super()._on_solve_or_confirm_clicked()

    def on_solve_clicked(self) -> None:
        """Run pre-computation: find rule combinations with exactly 1 intersection, highlight targets on map."""
        if not hasattr(self, "controller") or self.controller is None:
            return
        self.buildScroll.setGraphicsEffect(None)
        self.btnSolve.setEnabled(False)
        self._calculating_simulation = True
        players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip())
        if players not in (3, 4, 5):
            self._calculating_simulation = False
            self.btnSolve.setEnabled(True)
            return
        assign_colors_to_empty_combos(self.cbColorP, players)
        first_player_rule = (self.rules.read_selected_rules(players)[0] or "").strip()
        current_map = self.controller.build_current_map()
        rule_labels = all_condition_labels(advanced_mode=self.advanced_mode)
        start_time = time.perf_counter()
        overlay_used = False

        def _yield_cb() -> None:
            nonlocal overlay_used
            elapsed = time.perf_counter() - start_time
            if not overlay_used and elapsed >= 0.1:
                self._show_calculating_overlay()
                overlay_used = True
            QApplication.processEvents()

        combos_with_hexes = find_rule_combinations_with_exactly_one_intersection(
            current_map,
            players,
            rule_labels,
            self.advanced_mode,
            fixed_first_rule=first_player_rule if first_player_rule else None,
            yield_callback=_yield_cb,
        )
        self._rule_combos = combos_with_hexes
        self._deactivated_combo_indices: set = set()
        self._impossible_per_player: list[set[str]] = [set() for _ in range(players)]
        self._all_conds = compute_all_conditions(current_map, self.advanced_mode)
        self._simulation_players = players
        self._clues_per_player = distinct_valid_clues_per_player(
            combos_with_hexes, players, self._deactivated_combo_indices
        )
        self._initial_clues_per_player = [s.copy() for s in self._clues_per_player]
        self._first_player_rule = first_player_rule
        all_targets = {
            target_hex
            for i, (_, target_hex) in enumerate(combos_with_hexes)
            if i not in self._deactivated_combo_indices
        }
        self._clear_all_highlights()
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is None:
                continue
            for i in range(len(piece.cells)):
                coords = self.controller.cell_big_coords(piece, i)
                if coords is not None and coords in all_targets:
                    piece.highlighted.add(i)
        self.canvas._zero_targets_dim_full_map = len(all_targets) == 0
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is not None:
                piece.update()
        for m in self.markers:
            m.update()
        if self.highlight_overlay:
            self.highlight_overlay.update_highlights()
        self._calculating_simulation = False
        if overlay_used:
            self._hide_calculating_overlay()
        # Populate and show clues table (Yes/No per clue per player) - HIDDEN
        # clues_per_player = distinct_valid_clues_per_player(combos_with_hexes, players)
        # placeholders = getattr(self, "_placeholders", ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"])
        # tbl = self._clues_table
        # tbl.setRowCount(len(rule_labels))
        # tbl.setColumnCount(1 + players)
        # tbl.setHorizontalHeaderItem(0, QTableWidgetItem("Clue"))
        # default_color = "#95a5a6"
        # for p in range(players):
        #     hex_color = default_color
        #     if p < len(self.cbColorP) and self.cbColorP[p] is not None:
        #         name = get_selected_player_color(self.cbColorP[p])
        #         if name:
        #             hex_color = get_player_color_hex(name)
        #     pix = get_colored_square_pixmap(hex_color)
        #     hdr = QTableWidgetItem(QIcon(pix), placeholders[p] if p < len(placeholders) else f"Player {p + 1}")
        #     tbl.setHorizontalHeaderItem(1 + p, hdr)
        # for row, clue in enumerate(rule_labels):
        #     tbl.setItem(row, 0, QTableWidgetItem(clue))
        #     for p in range(players):
        #         valid = clue in clues_per_player[p] if p < len(clues_per_player) else False
        #         tbl.setItem(row, 1 + p, QTableWidgetItem("Yes" if valid else "No"))
        # hdr = tbl.horizontalHeader()
        # hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        # for p in range(players):
        #     hdr.setSectionResizeMode(1 + p, QHeaderView.ResizeMode.Stretch)
        # tbl.resizeRowsToContents()
        # QApplication.processEvents()
        # h = tbl.horizontalHeader().height() + sum(tbl.rowHeight(r) for r in range(tbl.rowCount())) + 2 * tbl.frameWidth()
        # tbl.setMinimumHeight(h)
        # self._apply_player_color_borders()
        # self._clues_table_section.setVisible(True)
        # self._clues_table_section.updateGeometry()
        if hasattr(self, "board_builder") and self.board_builder is not None:
            colors_hex = [
                get_player_color_hex(get_selected_player_color(self.cbColorP[i]))
                for i in range(players)
                if i < len(self.cbColorP) and self.cbColorP[i] is not None
            ]
            player_names = [
                (self.edtPlayer[i].text() or "").strip()
                for i in range(players)
                if i < len(self.edtPlayer) and self.edtPlayer[i] is not None
            ]
            self.board_builder.show_structures_region()
            self.board_builder.add_player_chips(players, colors_hex, player_names)
            self.board_builder.show_chips()
            self.canvas._on_chip_assigned = self._on_chip_placed
            self.canvas._on_chip_released = self._on_chip_released
        self._show_clue_icon()
        count = len(all_targets)
        msg = TOAST_HEX_HIGHLIGHTED if count == 1 else TOAST_HEXES_HIGHLIGHTED.format(count=count)
        show_toast(self.pages_stack, msg)
        self.btnSolve.setEnabled(True)
        self.btnSolve.setText(BTN_END_SIMULATION)
        self._set_simulation_locked(True)
        if hasattr(self, "board_builder") and self.board_builder is not None:
            if self.board_builder._freeze_row is not None:
                self.board_builder._freeze_row.setVisible(False)
            if self.board_builder._highlight_row is not None:
                self.board_builder._highlight_row.setVisible(True)
            # Lower freeze proxy, raise highlight proxy so highlight row receives clicks
            if hasattr(self.board_builder, "_proxy_freeze") and self.board_builder._proxy_freeze is not None:
                self.board_builder._proxy_freeze.setZValue(10000)
            if hasattr(self.board_builder, "_proxy_hl") and self.board_builder._proxy_hl is not None:
                self.board_builder._proxy_hl.setZValue(10002)
        if hasattr(self, "cbFreezeMap") and self.cbFreezeMap is not None:
            self.cbFreezeMap.blockSignals(True)
            self.cbFreezeMap.setChecked(True)
            self.cbFreezeMap.setEnabled(True)
            self.cbFreezeMap.blockSignals(False)
            if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
                self.status_list_manager._apply_freeze_map_drag_state()
                self.status_list_manager._apply_freeze_markers_drag_state(True)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

        # Capture session snapshot for the current mode (Build vs Select)
        sess = self._capture_simulation_session()
        if sess is not None:
            if self.btnMapSelect.isChecked():
                self._select_sim_session = sess
            else:
                self._build_sim_session = sess
        self._update_solve_and_reset_for_mode()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)
        u = getattr(self, "_board_undo", None)
        if u is not None:
            u.reset()
        if hasattr(self, "_update_board_undo_tracking"):
            self._update_board_undo_tracking()

    def _reset_select_mode_simulation(self) -> None:
        """Reset when ending simulation that started from Select mode: restore select browse view."""
        self._reparent_view_to(self._build_view_container)
        self._swap_to_build_panel()
        self._reset_build_mode_state()
        self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_BROWSE)
        self.mapListCardsContainer.setVisible(True)
        mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
        if mc:
            mc.setVisible(True)
        self.map_cards_manager.exit_solve_mode()
        self.map_cards_manager.clear_selection()
        self.map_cards_manager.clear_all_cards_deduction_controls()
        self._in_solve_mode = False
        self._solve_mode_map_data = None
        # _update_solve_and_reset_for_mode() uses _select_state.in_simulation; if we leave it True,
        # it would switch back to Select-sim and hide the map cards list.
        self._select_sim_session = None
        if self.edtSelectSearch:
            self.edtSelectSearch.clear()
        self.cbSelectAdvancedMode.blockSignals(True)
        self.cbSelectAdvancedMode.setChecked(False)
        self.cbSelectAdvancedMode.blockSignals(False)
        self.cbSelectAdvancedMode.setEnabled(True)
        cb_cm = getattr(self, "cbSelectCustomMaps", None)
        if cb_cm is not None:
            cb_cm.blockSignals(True)
            cb_cm.setChecked(False)
            cb_cm.blockSignals(False)
            self._apply_deduction_select_maps_source(False)
        self.map_cards_manager.filter_map_cards()
        idx = self.cbSelectPlayers.findText("3", Qt.MatchFixedString)
        self.cbSelectPlayers.setCurrentIndex(idx) if idx != -1 else self.cbSelectPlayers.setCurrentText("3")
        self.cbSelectPlayers.setEnabled(True)
        self._show_select_browse_filters()
        self.map_cards_manager.set_blur_for_all_cards(True)
        row = self.btnReset.parentWidget()
        if row:
            row.setVisible(True)
        self.btnSolve.setEnabled(False)
        players = (
            int((self.cbSelectPlayers.currentText() or "3").strip())
            if self.cbSelectPlayers.currentText() in ("3", "4", "5")
            else 3
        )
        self._select_state = ModeState(
            map_data=None,
            players=players,
            advanced=False,
            select_custom_maps=False,
            rule="",
            names=[""] * 5,
            colors=[""] * 5,
            in_simulation=False,
            selected_map_data=None,
        )
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def _on_solve_select_mode_clicked(self, map_data: dict) -> None:
        """Start Simulation: switch to Select-sim layout (board + Select panel), load map, run. Build panel untouched."""
        card = self.map_cards_manager.get_card_for_map_data(map_data)
        if card is None:
            return
        if getattr(self, "_rules_select", None) is None:
            self._setup_select_sim_panel()
        if self._rules_select is None:
            return
        self._save_build_state()
        # 1. Switch to Select-sim layout (index 2)
        self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_SIM)
        self.mapListCardsContainer.setVisible(False)
        mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
        if mc:
            mc.setVisible(False)
        # 2. Reparent board view to Select-sim layout
        self._reparent_view_to(self._select_sim_view_container)
        # Ensure wheel events on the reparented BoardView are handled by our
        # Select-sim wheel forwarder (so they don't bubble up to mainScroll).
        forwarder = getattr(self, "_select_sim_wheel_forwarder", None)
        if forwarder is not None and hasattr(self, "view") and self.view is not None:
            self.view.installEventFilter(forwarder)
            try:
                vp = self.view.viewport()
                if vp is not None:
                    vp.installEventFilter(forwarder)
            except Exception:
                pass
        # 3. Load map into board
        self.board_builder.load_from_map_data(map_data, freeze=True)
        # 4. Sync Select-sim panel (NOT Build) from selected card
        players = int((self.cbSelectPlayers.currentText() or "3").strip()) if self.cbSelectPlayers.currentText() in ("3", "4", "5") else 3
        advanced = bool(map_data.get("advancedMode", False))
        self.advanced_mode = advanced
        self._rule_labels = all_condition_labels(advanced_mode=advanced)
        self._rules_select.set_rule_labels(self._rule_labels)
        self._rules_select.set_deduction_layout(players)
        self._select_sim_cb_players.blockSignals(True)
        idx = self._select_sim_cb_players.findText(str(players), Qt.MatchFixedString)
        self._select_sim_cb_players.setCurrentIndex(idx if idx != -1 else 0)
        self._select_sim_cb_players.blockSignals(False)
        self._select_sim_cb_advanced.blockSignals(True)
        self._select_sim_cb_advanced.setChecked(advanced)
        self._select_sim_cb_advanced.blockSignals(False)
        rule_txt = card.get_selected_rule()
        if rule_txt:
            self._rules_select.cbRuleP[0].blockSignals(True)
            idx_rule = self._rules_select.cbRuleP[0].findText(rule_txt)
            self._rules_select.cbRuleP[0].setCurrentIndex(idx_rule if idx_rule >= 0 else 0)
            self._rules_select.cbRuleP[0].blockSignals(False)
            sync_clear_button_visibility(self._rules_select.cbRuleP[0])
            sync_combo_placeholder_style(self._rules_select.cbRuleP[0])
        names = card.get_player_names()
        for i, edt in enumerate(self._select_sim_edt_player):
            if edt is not None and i < players:
                nm = (names[i] if i < len(names) else "") or ""
                edt.blockSignals(True)
                edt.setText(nm)
                edt.blockSignals(False)
        colors = card.get_player_colors()
        refresh_player_color_combos(self._select_sim_cb_color)
        for i, cb in enumerate(self._select_sim_cb_color):
            if cb is not None and i < players and i < len(colors) and colors[i]:
                cb.blockSignals(True)
                idx_color = cb.findText(colors[i])
                if idx_color >= 0:
                    cb.setCurrentIndex(idx_color)
                cb.blockSignals(False)
        refresh_player_color_combos(self._select_sim_cb_color)
        for cb in self._select_sim_cb_color:
            if cb is not None:
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)
        # 5. Swap to Select-sim panel so simulation reads from it
        self._swap_to_select_sim_panel()
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()
        self.board_builder.apply_marker_visibility(advanced)
        self._in_solve_mode = True
        self._solve_mode_map_data = map_data
        state_names = [(names[i] if i < len(names) else "") for i in range(5)]
        state_colors = [(colors[i] if i < len(colors) else "") for i in range(5)]
        # Persist Select-sim state so that toggling Build↔Select returns to simulation, not the map list.
        self._select_state = ModeState(
            map_data=map_data,
            players=players,
            advanced=advanced,
            select_custom_maps=bool(
                getattr(self, "cbSelectCustomMaps", None) and self.cbSelectCustomMaps.isChecked()
            ),
            rule=rule_txt or "",
            names=state_names,
            colors=state_colors,
            in_simulation=True,
            selected_map_data=map_data,
        )
        self.on_solve_clicked()
        # Avoid focus/selection on player 1 name line edit (defer so it runs after layout settles)
        edt0 = self._select_sim_edt_player[0] if self._select_sim_edt_player else None
        if edt0 is not None:
            QTimer.singleShot(0, edt0.clearFocus)

    def _on_map_source_mode_changed(self) -> None:
        """Override: tab-specific button labels, enabled state, tooltips. Reset/Solve row always visible."""
        super()._on_map_source_mode_changed()
        self._update_solve_and_reset_for_mode()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

    def _update_solve_and_reset_for_mode(self) -> None:
        """Set btnSolve text, enabled state, and Reset row visibility per current tab."""
        row = self.btnReset.parentWidget()
        if row:
            row.setVisible(True)
        is_select = self.btnMapSelect.isChecked()
        combos_ok = bool(getattr(self, "_rule_combos", None))
        build_in_sim = (
            not is_select
            and hasattr(self, "board_builder")
            and self.board_builder is not None
            and (
                getattr(self.board_builder, "_chips_mode", False)
                or (combos_ok and self.btnSolve.text() == BTN_END_SIMULATION)
            )
        )
        # For Select tab, treat "in simulation" based on the saved select state,
        # so switching Build↔Select restores the correct layout even if runtime flags were reset.
        st = getattr(self, "_select_state", None)
        select_in_sim = bool(
            is_select
            and st is not None
            and getattr(st, "in_simulation", False)
            and getattr(st, "map_data", None)
        )
        if is_select:
            if select_in_sim:
                # Ensure we are on the Select-sim layout, not the map cards list
                self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_SIM)
                self.mapListCardsContainer.setVisible(False)
                mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
                if mc:
                    mc.setVisible(False)
                self.btnSolve.setText(BTN_END_SIMULATION)
                self.btnSolve.setEnabled(True)
                self.btnSolve.setProperty("primary", True)
                self.btnSolve.style().unpolish(self.btnSolve)
                self.btnSolve.style().polish(self.btnSolve)
            else:
                # Browse mode: show map cards list
                self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_BROWSE)
                self.mapListCardsContainer.setVisible(True)
                mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
                if mc:
                    mc.setVisible(True)
                self.btnSolve.setText("Start Simulation")
                self.btnSolve.setProperty("primary", True)
                self.btnSolve.style().unpolish(self.btnSolve)
                self.btnSolve.style().polish(self.btnSolve)
                self.map_cards_manager._update_solve_for_select_mode()
        else:
            if build_in_sim:
                self.btnSolve.setText(BTN_END_SIMULATION)
                self.btnSolve.setEnabled(True)
                self.btnSolve.setProperty("primary", True)
                self.btnSolve.style().unpolish(self.btnSolve)
                self.btnSolve.style().polish(self.btnSolve)
            else:
                self.btnSolve.setText("Start Simulation")
                self.btnSolve.setProperty("primary", True)
                self.btnSolve.style().unpolish(self.btnSolve)
                self.btnSolve.style().polish(self.btnSolve)
                if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
                    self._update_status_and_structures()

        reset_chips_mode = (
            build_in_sim
            or select_in_sim
            or (
                is_select
                and getattr(self, "_in_solve_mode", False)
                and getattr(self, "_solve_mode_map_data", None)
            )
        )
        self.btnReset.setText(BTN_RESET_CHIPS if reset_chips_mode else BTN_RESET_ALL)

        # Block switching Create Map / Load Map while the other mode has an active simulation.
        in_sim = self.btnSolve.text() == BTN_END_SIMULATION
        sim_on_create_map = in_sim and self.btnMapBuild.isChecked()
        sim_on_load_map = in_sim and self.btnMapSelect.isChecked()
        if sim_on_create_map:
            self.btnMapSelect.setEnabled(False)
            self.btnMapBuild.setEnabled(True)
        elif sim_on_load_map:
            self.btnMapBuild.setEnabled(False)
            self.btnMapSelect.setEnabled(True)
        else:
            self.btnMapBuild.setEnabled(True)
            self.btnMapSelect.setEnabled(True)

