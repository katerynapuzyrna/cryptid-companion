from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from ui.shared.widgets import sync_clear_button_visibility, sync_combo_placeholder_style


@dataclass
class RuleDropdownsManager:
    lblRulesTitle: QLabel
    ruleRows: List[QWidget | None]      # optional row containers
    lblRuleP: List[QLabel]              # labels per player
    cbRuleP: List[QComboBox]            # comboboxes per player
    rule_labels: List[str]              # all_condition_labels()

    # model: index 0 = empty, index 1+ = rules
    RULE_IDX_EMPTY: int = 0
    _CLUE_PLACEHOLDER: str = "<Select clue>"

    # keep previous players count to decide when to reset newly-enabled fields
    _players_count: int = 0

    def _set_clue_placeholder(self, cb: QComboBox, enabled: bool) -> None:
        """Set empty item text to placeholder for enabled combos, empty string for disabled."""
        cb.setItemText(self.RULE_IDX_EMPTY, self._CLUE_PLACEHOLDER if enabled else "")

    def setup_once(self) -> None:
        """Populate each combobox ONCE. All rows hidden until set_players_count is called."""
        self.lblRulesTitle.setVisible(True)

        for cb in self.cbRuleP:
            cb.blockSignals(True)
            cb.clear()

            cb.addItem("")  # index 0 = empty
            cb.addItems(self.rule_labels)  # index 1+ = rules

            cb.setCurrentIndex(self.RULE_IDX_EMPTY)
            cb.setEnabled(False)

            cb.blockSignals(False)
            sync_clear_button_visibility(cb)
            sync_combo_placeholder_style(cb)

        # hide all rows until set_players_count shows the first N
        for i in range(5):
            self._set_row_visible(i, False)

        # initial state: no players selected yet
        self._players_count = 0

    def set_players_count(self, players: int) -> None:
        """
        Enable first N, disable the rest (hide rows).

        Preserve selections for fields that stay enabled.
        Newly enabled fields MUST be reset to empty.
        """
        players = players if players in (3, 4, 5) else 0
        prev = self._players_count

        for i in range(5):
            will_be_enabled = i < players
            was_enabled = i < prev

            # reset only if this field becomes enabled now (newly enabled)
            reset_if_enabling = will_be_enabled and (not was_enabled)

            self.set_rule_enabled(i, enabled=will_be_enabled, reset_if_enabling=reset_if_enabling)

        self._players_count = players

    def clear_rules(self, players: int) -> None:
        """
        Force-clear rules for the first N players:
          - enabled combos (0..N-1) -> empty
          - disabled combos (N..4)  -> empty, row hidden
        This is intended for the Reset button.
        """
        players = players if players in (3, 4, 5) else 0

        for i in range(5):
            cb = self.cbRuleP[i]
            cb.blockSignals(True)

            if i < players:
                self._set_row_visible(i, True)
                cb.setEnabled(True)
                cb.setCurrentIndex(self.RULE_IDX_EMPTY)
            else:
                cb.setEnabled(False)
                cb.setCurrentIndex(self.RULE_IDX_EMPTY)
                self._set_row_visible(i, False)

            cb.blockSignals(False)
            self._set_clue_placeholder(cb, i < players)
            sync_clear_button_visibility(cb)
            sync_combo_placeholder_style(cb)

        # keep internal state consistent with what user sees
        self._players_count = players

    def _set_row_visible(self, i: int, visible: bool) -> None:
        """Show or hide the row for player i."""
        row = self.ruleRows[i] if i < len(self.ruleRows) else None
        if row is not None:
            row.setVisible(visible)
        else:
            self.lblRuleP[i].setVisible(visible)
            self.cbRuleP[i].setVisible(visible)

    def set_rule_enabled(self, i: int, enabled: bool, reset_if_enabling: bool = True) -> None:
        cb = self.cbRuleP[i]
        cb.blockSignals(True)

        cb.setEnabled(enabled)
        if enabled:
            self._set_row_visible(i, True)
            if reset_if_enabling:
                cb.setCurrentIndex(self.RULE_IDX_EMPTY)
        else:
            cb.setCurrentIndex(self.RULE_IDX_EMPTY)
            self._set_row_visible(i, False)

        cb.blockSignals(False)
        self._set_clue_placeholder(cb, enabled)
        sync_clear_button_visibility(cb)
        sync_combo_placeholder_style(cb)

    def set_deduction_layout(self, players: int = 3) -> None:
        """Show N rows (1 column) per players; enable only 1st, disable the rest (visible but greyed).
        Preserves the 1st rule selection when changing player count."""
        players = players if players in (3, 4, 5) else 3
        for i in range(5):
            visible = i < players
            self._set_row_visible(i, visible)
            cb = self.cbRuleP[i]
            cb.blockSignals(True)
            cb.setEnabled(visible and i == 0)
            # Preserve 1st rule when changing players; clear disabled combos only
            if i != 0 or not visible:
                cb.setCurrentIndex(self.RULE_IDX_EMPTY)
            cb.blockSignals(False)
            self._set_clue_placeholder(cb, visible and i == 0)
            sync_clear_button_visibility(cb)
            sync_combo_placeholder_style(cb)
        self._players_count = players

    def parse_players(self, txt: str) -> int:
        t = (txt or "").strip()
        return int(t) if t in ("3", "4", "5") else 0

    def read_selected_rules(self, players: int) -> List[str]:
        """
        Read ONLY enabled combos (first N).
        Returns list of length N with selected labels or "" if not selected.
        """
        selected: List[str] = []
        for i in range(players):
            cb = self.cbRuleP[i]
            txt = (cb.currentText() or "").strip()
            if cb.currentIndex() == self.RULE_IDX_EMPTY or not txt:
                selected.append("")
            else:
                selected.append(txt)
        return selected

    def reset_for_players_3(self) -> None:
        """Convenience: enable 3 with empty, disable 4-5."""
        self.set_players_count(3)

    def clear_first_rule(self) -> None:
        """Clear the 1st player's rule combo (for deduction mode reset)."""
        if not self.cbRuleP:
            return
        cb = self.cbRuleP[0]
        cb.blockSignals(True)
        cb.setCurrentIndex(self.RULE_IDX_EMPTY)
        cb.blockSignals(False)
        self._set_clue_placeholder(cb, cb.isEnabled())
        sync_clear_button_visibility(cb)
        sync_combo_placeholder_style(cb)

    def set_rule_labels(self, rule_labels: List[str]) -> None:
        """
        Replace rule list in all comboboxes.
        Preserves empty row (index 0). Tries to keep current selection if it still exists;
        otherwise resets to empty for enabled combos.

        IMPORTANT:
        This intentionally does NOT "remember" invalid/removed rules (e.g. Not/black),
        so they won't come back when labels are re-expanded again.
        """
        self.rule_labels = rule_labels

        for cb in self.cbRuleP:
            enabled = cb.isEnabled()
            prev_txt = (cb.currentText() or "").strip()

            cb.blockSignals(True)

            cb.clear()
            cb.addItem("")  # index 0 = empty (placeholder set below)
            cb.addItems(self.rule_labels)  # index 1+ = rules

            self._set_clue_placeholder(cb, enabled)

            if not enabled:
                cb.setCurrentIndex(self.RULE_IDX_EMPTY)
            else:
                if prev_txt and prev_txt in self.rule_labels:
                    cb.setCurrentText(prev_txt)
                else:
                    cb.setCurrentIndex(self.RULE_IDX_EMPTY)

            cb.blockSignals(False)
            sync_clear_button_visibility(cb)
            sync_combo_placeholder_style(cb)
