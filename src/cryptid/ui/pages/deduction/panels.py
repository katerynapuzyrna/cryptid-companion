"""Player name/color combobox wiring for Deduction build panel."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QComboBox, QLineEdit

from ui.shared.widgets import (
    refresh_player_color_combos,
    sync_clear_button_visibility,
    sync_combo_placeholder_style,
    get_selected_player_color,
    get_player_color_hex,
    get_colored_square_pixmap,
)


class DeductionPanelsMixin:

    def _on_color_combo_changed(self) -> None:
        """When any color selection changes, refresh all combos to hide taken colors."""
        # Only mark Build dirty if this change is on the Build panel (not Select-sim).
        if not (self.btnMapSelect.isChecked() and getattr(self, "_in_solve_mode", False)):
            self._build_dirty = True
        refresh_player_color_combos(self.cbColorP)
        self._apply_player_color_borders()

    def _on_player_name_changed(self, index: int) -> None:
        """Update valid clues header, board chip label, and status list when player name changes."""
        # Only mark Build dirty if this change is on the Build panel (not Select-sim).
        if not (self.btnMapSelect.isChecked() and getattr(self, "_in_solve_mode", False)):
            self._build_dirty = True
        placeholders = getattr(self, "_placeholders", ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"])
        edt = self.edtPlayer[index] if index < len(self.edtPlayer) else None
        name = (edt.text() or "").strip() or placeholders[index] if edt is not None else placeholders[index]
        if index >= 1:
            col_idx = index - 1
            if col_idx < len(getattr(self, "_valid_clues_headers", [])):
                hdr = self._valid_clues_headers[col_idx]
                if hdr is not None:
                    hdr.setText(f"{name} - Valid clues:")
        if hasattr(self, "board_builder") and self.board_builder is not None:
            self.board_builder.update_chip_label(index, name)
        if hasattr(self, "_update_status_and_structures"):
            self._update_status_and_structures()

    def _apply_player_color_borders(self) -> None:
        """Apply player-color brush-stroke icons to validCluesSection headers (players 2-5 only)."""
        players = self.rules.parse_players((self.cbBuildPlayers.currentText() or "").strip())
        players = players or 3
        default_color = "#95a5a6"
        for i in range(4):
            hex_color = default_color
            player_idx = i + 1
            if player_idx < players and player_idx < len(self.cbColorP) and self.cbColorP[player_idx] is not None:
                name = get_selected_player_color(self.cbColorP[player_idx])
                if name:
                    hex_color = get_player_color_hex(name)
            pix = get_colored_square_pixmap(hex_color)
            if i < len(getattr(self, "_valid_clues_icon_labels", [])):
                icon_lbl = self._valid_clues_icon_labels[i]
                if icon_lbl is not None:
                    icon_lbl.setPixmap(pix)

    def on_players_changed(self, txt: str) -> None:
        """Update clue dropdowns based on number of players selected."""
        vbar = self.buildScroll.verticalScrollBar()
        was_at_bottom = False
        if vbar is not None:
            was_at_bottom = (vbar.maximum() - vbar.value()) <= 2

        players = self.rules.parse_players((txt or "").strip())
        players = players or 3

        # Clear color combos and input fields for players whose rows are being hidden
        for i in range(players, 5):
            cb = self.cbColorP[i] if i < len(self.cbColorP) else None
            if cb is not None:
                cb.blockSignals(True)
                cb.setCurrentIndex(0)
                cb.blockSignals(False)
                sync_clear_button_visibility(cb)
                sync_combo_placeholder_style(cb)
            edt = self.edtPlayer[i] if i < len(self.edtPlayer) else None
            if edt is not None:
                edt.clear()

        self.rules.set_deduction_layout(players)
        refresh_player_color_combos(self.cbColorP)
        self._apply_player_color_borders()

        if was_at_bottom and vbar is not None:
            QTimer.singleShot(0, lambda vb=vbar: vb.setValue(vb.maximum()))

