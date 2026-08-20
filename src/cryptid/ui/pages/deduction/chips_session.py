"""Chips on board, session capture/restore, reset flows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox, QGridLayout

from logic.conditions import all_condition_labels
from logic.rule_combinations import distinct_valid_clues_per_player
from settings.config import ICON_HELP
from settings.strings import (
    BTN_END_SIMULATION,
    BTN_RESET_CHIPS,
    RESET_CHIPS_CONFIRM_MSG,
)

from ui.shared.widgets import (
    get_selected_player_color,
    refresh_player_color_combos,
    sync_clear_button_visibility,
    sync_combo_placeholder_style,
)

from ui.pages.deduction.deduction_types import SimulationSession


class DeductionChipsSessionMixin:

    def _sync_hex_highlights_from_combos(self) -> None:
        """Apply piece hex highlights from _rule_combos and _deactivated_combo_indices."""
        combos = getattr(self, "_rule_combos", [])
        deactivated = getattr(self, "_deactivated_combo_indices", set())
        all_targets = {
            target_hex
            for i, (_, target_hex) in enumerate(combos)
            if i not in deactivated
        }
        # Update in place (do not clear-all first): avoids a full flash empty → redraw on undo.
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is None:
                if piece.highlighted:
                    piece.highlighted.clear()
                continue
            new_hl: set[int] = set()
            for idx in range(len(piece.cells)):
                co = self.controller.cell_big_coords(piece, idx)
                if co is not None and co in all_targets:
                    new_hl.add(idx)
            if piece.highlighted != new_hl:
                piece.highlighted.clear()
                piece.highlighted.update(new_hl)
        self.canvas._zero_targets_dim_full_map = len(all_targets) == 0
        for piece in self.pieces:
            if self.canvas.item_slot.get(piece) is not None:
                piece.update()
        for m in self.markers:
            m.update()
        if self.highlight_overlay:
            self.highlight_overlay.update_highlights()

    def _on_chip_placed(self, chip_item, row: int, col: int, cell_idx: int) -> None:
        """When a chip is placed or moved to a hex: trigger full recompute for that player."""
        # Only mark Build dirty if this is Build-tab simulation (chips in Select-sim are not Build edits).
        if self.btnMapBuild.isChecked():
            self._build_dirty = True
        bb = getattr(self, "board_builder", None)
        if bb is None:
            return
        color = (getattr(chip_item, "fill_color", "") or "").lower()
        player_idx = getattr(bb, "_chip_player_rank", {}).get(color, -1)
        players = getattr(self, "_simulation_players", 0)
        if player_idx < 0 or player_idx >= players:
            return
        if getattr(chip_item, "shape_kind", None) not in ("circle", "square"):
            return
        self._recompute_from_chips(player_idx)

    def _on_chip_released(self, chip_item) -> None:
        """When a chip is removed from the board (moved outside map): trigger recompute for that player."""
        if self.btnMapBuild.isChecked():
            self._build_dirty = True
        bb = getattr(self, "board_builder", None)
        if bb is None:
            return
        color = (getattr(chip_item, "fill_color", "") or "").lower()
        player_idx = getattr(bb, "_chip_player_rank", {}).get(color, -1)
        players = getattr(self, "_simulation_players", 0)
        if player_idx < 0 or player_idx >= players:
            return
        self._recompute_from_chips(player_idx)

    def _impossible_union_for_player_chips(self, player_idx: int) -> set[str]:
        """Union of impossible clue labels for this player from circle/square chips on the board."""
        all_conds = getattr(self, "_all_conds", None)
        bb = getattr(self, "board_builder", None)
        if all_conds is None or bb is None or self.canvas is None:
            return set()
        chip_rank = getattr(bb, "_chip_player_rank", {})
        hexes_with_chips: list[tuple[int, int, str]] = []
        for chip, slot in list(self.canvas.chip_slot.items()):
            pidx = chip_rank.get((getattr(chip, "fill_color", "") or "").lower(), -1)
            if pidx != player_idx:
                continue
            shape = getattr(chip, "shape_kind", None)
            if shape not in ("circle", "square"):
                continue
            row, col, cell_idx = slot
            piece = self.canvas.occupied.get((row, col)) if self.canvas else None
            if piece is None:
                continue
            coords = self.controller.cell_big_coords(piece, cell_idx)
            if coords is None:
                continue
            y, x = coords
            hexes_with_chips.append((y, x, shape))

        impossible_union: set[str] = set()
        for y, x, shape in hexes_with_chips:
            rules_true = all_conds.rules_true_at_hex(y, x)
            if shape == "circle":
                impossible_union.update(r for r in all_conds.labels if r not in rules_true)
            else:
                impossible_union.update(r for r in all_conds.labels if r in rules_true)
        return impossible_union

    def _recompute_from_chips(self, player_idx: int) -> None:
        """
        Recompute valid conditions and deactivation from all chips on the board.
        Called when any chip of this player is placed, moved, or removed.
        """
        combos = getattr(self, "_rule_combos", [])
        all_conds = getattr(self, "_all_conds", None)
        players = getattr(self, "_simulation_players", 0)
        initial = getattr(self, "_initial_clues_per_player", None)
        bb = getattr(self, "board_builder", None)
        if not combos or all_conds is None or initial is None or bb is None:
            return

        impossible_union = self._impossible_union_for_player_chips(player_idx)
        while len(self._impossible_per_player) <= player_idx:
            self._impossible_per_player.append(set())
        self._impossible_per_player[player_idx] = impossible_union

        # Build valid clue sets for all players from current impossible unions
        impossible_per = getattr(self, "_impossible_per_player", [])
        valid_per_player: list[set[str]] = []
        for p in range(players):
            imp = impossible_per[p] if p < len(impossible_per) else set()
            base = initial[p] if p < len(initial) else set()
            valid_per_player.append(base - imp)

        deactivated: set[int] = set()
        for i, (combo, _) in enumerate(combos):
            for p in range(min(players, len(combo))):
                if p < len(valid_per_player) and combo[p] not in valid_per_player[p]:
                    deactivated.add(i)
                    break

        self._deactivated_combo_indices = deactivated

        # Step 6: recompute _clues_per_player from active combos
        self._clues_per_player = distinct_valid_clues_per_player(
            combos, players, deactivated
        )

        # Step 7: update clue icon color states (valid=colored, invalid=transparent)
        self._update_clue_icon_color_states()

        # Step 8: recalculate highlights
        self._sync_hex_highlights_from_combos()
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

    def _recompute_all_players_from_chips(self) -> None:
        """Refresh impossible sets, combo deactivation, and highlights from all chips (e.g. after board undo)."""
        combos = getattr(self, "_rule_combos", [])
        players = getattr(self, "_simulation_players", 0)
        initial = getattr(self, "_initial_clues_per_player", None)
        bb = getattr(self, "board_builder", None)
        if not combos or initial is None or bb is None:
            return
        while len(self._impossible_per_player) < players:
            self._impossible_per_player.append(set())
        for p in range(players):
            self._impossible_per_player[p] = self._impossible_union_for_player_chips(p)
        impossible_per = getattr(self, "_impossible_per_player", [])
        valid_per_player: list[set[str]] = []
        for p in range(players):
            imp = impossible_per[p] if p < len(impossible_per) else set()
            base = initial[p] if p < len(initial) else set()
            valid_per_player.append(base - imp)

        deactivated: set[int] = set()
        for i, (combo, _) in enumerate(combos):
            for p in range(min(players, len(combo))):
                if p < len(valid_per_player) and combo[p] not in valid_per_player[p]:
                    deactivated.add(i)
                    break

        self._deactivated_combo_indices = deactivated
        self._clues_per_player = distinct_valid_clues_per_player(
            combos, players, deactivated
        )
        self._update_clue_icon_color_states()
        self._sync_hex_highlights_from_combos()
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

    def _capture_simulation_session(self) -> SimulationSession | None:
        """Snapshot the current simulation (map, solver fields, chips, highlights) into a session."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return None
        if not hasattr(self, "canvas") or self.canvas is None:
            return None
        combos = list(getattr(self, "_rule_combos", None) or [])
        snapshot_sim = (
            self.btnSolve.text() == BTN_END_SIMULATION
            or getattr(self.board_builder, "_chips_mode", False)
        )
        if not combos and not snapshot_sim:
            return None

        players = getattr(self, "_simulation_players", None)
        if players is None or players not in (3, 4, 5):
            players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip()) or 3

        map_data = self.board_builder.export_board_to_map_data()
        names = [
            (self.edtPlayer[i].text() or "").strip()
            if i < len(self.edtPlayer) and self.edtPlayer[i] is not None
            else ""
            for i in range(5)
        ]
        colors = [
            get_selected_player_color(self.cbColorP[i])
            if i < len(self.cbColorP) and self.cbColorP[i] is not None
            else ""
            for i in range(5)
        ]
        first_rule = (getattr(self, "_first_player_rule", None) or "").strip() or (
            (self.rules.read_selected_rules(players)[0] or "").strip()
        )
        highlight_valid = bool(
            getattr(self.board_builder, "cbHighlightValidSpaces", None)
            and self.board_builder.cbHighlightValidSpaces.isChecked()
        )

        # Snapshot chip positions
        chip_slots: list[tuple[int, int, int, str, str]] = []
        chip_occ = getattr(self.canvas, "chip_occupied", {})
        for (row, col, cell_idx), chips in chip_occ.items():
            for chip in chips:
                shape = getattr(chip, "shape_kind", "")
                color = (getattr(chip, "fill_color", "") or "").lower()
                chip_slots.append((row, col, cell_idx, shape, color))

        return SimulationSession(
            map_data=map_data,
            players=players,
            advanced=self.advanced_mode,
            rule=first_rule,
            names=names,
            colors=colors,
            rule_combos=combos,
            deactivated=set(getattr(self, "_deactivated_combo_indices", set())),
            impossible_per_player=[s.copy() for s in getattr(self, "_impossible_per_player", [])],
            all_conds=getattr(self, "_all_conds", None),
            clues_per_player=[s.copy() for s in getattr(self, "_clues_per_player", [])],
            initial_clues_per_player=[s.copy() for s in getattr(self, "_initial_clues_per_player", [])],
            simulation_players=players,
            first_player_rule=first_rule,
            highlight_valid_spaces=highlight_valid,
            chip_slots=chip_slots,
        )

    def _restore_simulation_session(self, sess: SimulationSession) -> None:
        """Restore a previously captured simulation session onto the current board/panel."""
        if not hasattr(self, "board_builder") or self.board_builder is None or getattr(self, "canvas", None) is None:
            return

        # Solver fields
        self._rule_combos = list(sess.rule_combos)
        self._deactivated_combo_indices = set(sess.deactivated)
        self._impossible_per_player = [s.copy() for s in sess.impossible_per_player]
        self._all_conds = sess.all_conds
        self._clues_per_player = [s.copy() for s in sess.clues_per_player]
        self._initial_clues_per_player = [s.copy() for s in sess.initial_clues_per_player]
        self._simulation_players = sess.simulation_players
        self._first_player_rule = sess.first_player_rule
        self.advanced_mode = sess.advanced

        # Map + rules into whichever panel is active (Build or Select)
        self.board_builder.load_from_map_data(sess.map_data, freeze=True)
        self._rule_labels = all_condition_labels(advanced_mode=sess.advanced)
        self.rules.set_rule_labels(self._rule_labels)
        self.rules.set_deduction_layout(sess.players)

        self.cbBuildPlayers.blockSignals(True)
        idx = self.cbBuildPlayers.findText(str(sess.players), Qt.MatchFixedString)
        self.cbBuildPlayers.setCurrentIndex(idx if idx != -1 else 0)
        self.cbBuildPlayers.blockSignals(False)

        self.cbBuildAdvancedMode.blockSignals(True)
        self.cbBuildAdvancedMode.setChecked(sess.advanced)
        self.cbBuildAdvancedMode.blockSignals(False)

        for i, edt in enumerate(self.edtPlayer):
            if edt is not None and i < len(sess.names):
                edt.blockSignals(True)
                edt.setText(sess.names[i] or "")
                edt.blockSignals(False)

        refresh_player_color_combos(self.cbColorP)
        for i, cb in enumerate(self.cbColorP):
            if cb is not None and i < len(sess.colors) and sess.colors[i]:
                cb.blockSignals(True)
                idx_c = cb.findText(sess.colors[i])
                if idx_c >= 0:
                    cb.setCurrentIndex(idx_c)
                cb.blockSignals(False)
        refresh_player_color_combos(self.cbColorP)
        for cb in self.cbColorP:
            if cb is not None:
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)

        # Restore chips from chip_slots
        from board.markers import _grab_cursor, MARKER_Z_BANK, MARKER_SCALE_HOME  # type: ignore[attr-defined]

        # Clear any existing chip placements without destroying the chip bank
        if hasattr(self.board_builder, "chips") and self.board_builder.chips:
            for chip in self.board_builder.chips:
                if self.canvas:
                    self.canvas.release_chip(chip)
                chip.setZValue(MARKER_Z_BANK)
                chip.setScale(MARKER_SCALE_HOME)
                chip.setPos(chip._home_pos)
                chip.setCursor(_grab_cursor())

        # Build a reusable pool of chips by (shape, color)
        pool: dict[tuple[str, str], list] = {}
        for chip in getattr(self.board_builder, "chips", []):
            key = (getattr(chip, "shape_kind", ""), (getattr(chip, "fill_color", "") or "").lower())
            pool.setdefault(key, []).append(chip)

        for row, col, cell_idx, shape, color in sess.chip_slots:
            key = (shape, color)
            lst = pool.get(key)
            if not lst:
                continue
            chip = lst.pop()
            pos = self.canvas.snap_pos_for_item_to_slot(chip, row, col)
            chip.setPos(pos)
            self.canvas.assign_chip(chip, row, col, cell_idx)

        self.board_builder.show_chips()

        # Restore highlight_valid_spaces flag and overlay visibility
        if getattr(self.board_builder, "cbHighlightValidSpaces", None) is not None:
            self.board_builder.cbHighlightValidSpaces.blockSignals(True)
            self.board_builder.cbHighlightValidSpaces.setChecked(sess.highlight_valid_spaces)
            self.board_builder.cbHighlightValidSpaces.blockSignals(False)
        if getattr(self.board_builder, "highlight_overlay", None) is not None:
            self.board_builder.highlight_overlay.setVisible(sess.highlight_valid_spaces)

        if hasattr(self, "_sync_hex_highlights_from_combos"):
            self._sync_hex_highlights_from_combos()
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

    def _on_reset_clicked_wrapper(self) -> None:
        """Override: tab-specific reset. Select+sim: chips to home + recalc; Select browse: reset select; Build+sim: chips reset; Build: full reset."""
        if self.btnMapSelect.isChecked():
            if getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None):
                mb = QMessageBox(self.window)
                mb.setWindowTitle(BTN_RESET_CHIPS)
                mb.setText(RESET_CHIPS_CONFIRM_MSG)
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
                    self._reset_chips_and_highlights()
                    self._update_solve_and_reset_for_mode()
            else:
                super()._on_reset_clicked_wrapper()
                self._update_solve_and_reset_for_mode()
            return
        if self.btnSolve.text() == BTN_END_SIMULATION:
            mb = QMessageBox(self.window)
            mb.setWindowTitle(BTN_RESET_CHIPS)
            mb.setText(RESET_CHIPS_CONFIRM_MSG)
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
            layout = mb.findChild(QGridLayout)
            if layout:
                layout.setHorizontalSpacing(0)
            mb.exec()
            if mb.clickedButton() == yes_btn:
                self._reset_chips_and_highlights()
                self._update_solve_and_reset_for_mode()
            return
        super()._on_reset_clicked_wrapper()
        self._update_solve_and_reset_for_mode()

    def _reset_chips_and_highlights(self) -> None:
        """Reset all chips to home and restore highlights/clue icons to start-of-simulation state."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        self.board_builder.return_chips_to_home()
        players = getattr(self, "_simulation_players", 0)
        self._deactivated_combo_indices = set()
        self._impossible_per_player = [set() for _ in range(players)]
        self._clues_per_player = [s.copy() for s in self._initial_clues_per_player]
        self._update_clue_icon_color_states()
        self._sync_hex_highlights_from_combos()
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

    def _reset_build_mode_state(self) -> None:
        """Reset build mode: use deduction layout (1 enabled, rest disabled) instead of 3 players."""
        self._build_sim_session = None
        self._set_simulation_locked(False)
        if hasattr(self, "canvas") and self.canvas is not None:
            setattr(self.canvas, "_on_chip_assigned", None)
            setattr(self.canvas, "_on_chip_released", None)
            setattr(self.canvas, "_zero_targets_dim_full_map", False)
        for attr in ("_rule_combos", "_deactivated_combo_indices", "_impossible_per_player", "_initial_clues_per_player", "_all_conds", "_simulation_players"):
            if hasattr(self, attr):
                delattr(self, attr)
        self._hide_clue_icon()
        if hasattr(self, "_clues_table_section") and self._clues_table_section is not None:
            self._clues_table_section.setVisible(False)
        self.btnSolve.setText("Start Simulation")
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        self.board_builder.reset_board()
        self.cbBuildPlayers.blockSignals(True)
        self._set_players_combo_to_3()
        self.cbBuildPlayers.blockSignals(False)
        self.cbBuildAdvancedMode.blockSignals(True)
        self.cbBuildAdvancedMode.setChecked(False)
        self.cbBuildAdvancedMode.blockSignals(False)
        self.advanced_mode = False
        self._rule_labels = all_condition_labels(advanced_mode=False)
        self.rules.set_rule_labels(self._rule_labels)
        players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip())
        self.rules.set_deduction_layout(players or 3)
        self._apply_player_color_borders()
        self.rules.clear_first_rule()
        for cb in getattr(self, "cbColorP", []):
            if cb is not None:
                cb.blockSignals(True)
                cb.setCurrentIndex(0)
                cb.blockSignals(False)
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)
        refresh_player_color_combos(getattr(self, "cbColorP", []))
        for edt in getattr(self, "edtPlayer", []):
            if edt is not None:
                edt.clear()
        self.board_builder.apply_marker_visibility(False)
        if self.board_builder._freeze_row is not None:
            self.board_builder._freeze_row.setVisible(True)
        if self.board_builder._highlight_row is not None:
            self.board_builder._highlight_row.setVisible(False)
        # Raise freeze proxy so freeze row receives clicks in build mode
        if hasattr(self.board_builder, "_proxy_freeze") and self.board_builder._proxy_freeze is not None:
            self.board_builder._proxy_freeze.setZValue(10002)
        if hasattr(self.board_builder, "_proxy_hl") and self.board_builder._proxy_hl is not None:
            self.board_builder._proxy_hl.setZValue(10001)
            if self.board_builder.canvas is not None:
                self.board_builder.canvas._show_highlights = True
            if self.board_builder.cbHighlightValidSpaces is not None:
                self.board_builder.cbHighlightValidSpaces.blockSignals(True)
                self.board_builder.cbHighlightValidSpaces.setChecked(True)
                self.board_builder.cbHighlightValidSpaces.blockSignals(False)
            if self.board_builder.highlight_overlay is not None:
                self.board_builder.highlight_overlay.setVisible(True)
        if hasattr(self, "status_list_manager") and self.status_list_manager is not None:
            self.status_list_manager.reset_for_build()
            self.status_list_manager._apply_freeze_markers_drag_state(False)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()
        u = getattr(self, "_board_undo", None)
        if u is not None:
            u.reset()
        if hasattr(self, "_update_board_undo_tracking"):
            self._update_board_undo_tracking()
        from ui.shell.breadcrumb_manager import touch_breadcrumbs

        touch_breadcrumbs(self)

