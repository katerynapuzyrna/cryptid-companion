"""Play Hotseat page: player and map settings panels."""
from __future__ import annotations

import json
import random

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

from logic.conditions import all_condition_labels, compute_all_conditions
from logic.map_loader import build_map_from_data
from logic.rule_combinations import find_first_rule_combination_with_exactly_one_intersection
from settings.config import (
    CUSTOM_MAPS_JSON,
    HOTSEAT_TEST_DAN_BROKE_EVERYTHING,
    ICON_HELP,
    MAPS_JSON,
)
from settings.strings import (
    HOTSEAT_INCORRECT_MAP_NAME_MSG,
    HOTSEAT_INCORRECT_MAP_NAME_TITLE,
    RESET_CONFIRM_MSG,
    RESET_CONFIRM_TITLE,
)
from ui.shared.widgets import (
    add_clear_button_inside_combo,
    refresh_player_color_combos,
    setup_player_color_combo,
)
from ui.shared.widgets.player_colors import PLAYER_COLORS, get_selected_player_color

_HOTSEAT_CUSTOM_FLAG = "_hotseat_custom"

# TEMP testing: hardcoded 3-player clues for custom map "Dan broke everything".
_HOTSEAT_TEST_MAP_NAME = "Dan broke everything"
_HOTSEAT_TEST_CLUES = [
    "Within three spaces of a green structure",
    "Within three spaces of a blue structure",
    "On forest or mountain",
]


class PlayHotseatPageController:
    """Wires hotseat settings: player count, names, colors, map toggles."""

    def __init__(self, page: QWidget, window: QWidget):
        self._page = page
        self._window = window
        self.cbHotseatNumPlayers: QComboBox | None = None
        self.edtHotseatPlayer: list[QLineEdit | None] = []
        self.cbHotseatColor: list[QComboBox | None] = []
        self.cbHotseatComputer: list[QCheckBox | None] = []
        self._player_rows: list[QWidget | None] = []
        self.cbHotseatAdvancedMode: QCheckBox | None = None
        self.cbHotseatIncludeCustomMaps: QCheckBox | None = None
        self.rbHotseatRandomMap: QRadioButton | None = None
        self.rbHotseatSpecificMap: QRadioButton | None = None
        self.edtHotseatSpecificMapName: QLineEdit | None = None
        self._panel_random_map_options: QWidget | None = None
        self._panel_specific_map_options: QWidget | None = None
        self._map_mode_group: QButtonGroup | None = None
        self.btnHotseatStartGame: QPushButton | None = None
        self._stack: QStackedWidget | None = None
        self._board_panel = None
        self._setup_page: QWidget | None = None

    def setup(self) -> None:
        self.cbHotseatNumPlayers = self._page.findChild(QComboBox, "cbHotseatNumPlayers")
        self.edtHotseatPlayer = [
            self._page.findChild(QLineEdit, f"edtHotseatPlayer{i}") for i in range(1, 6)
        ]
        self.cbHotseatColor = [
            self._page.findChild(QComboBox, f"cbColorP{i}") for i in range(1, 6)
        ]
        self._player_rows = [
            self._page.findChild(QWidget, f"rowHotseatPlayer{i}") for i in range(1, 6)
        ]
        self.cbHotseatAdvancedMode = self._page.findChild(QCheckBox, "cbHotseatAdvancedMode")
        self.cbHotseatIncludeCustomMaps = self._page.findChild(QCheckBox, "cbHotseatIncludeCustomMaps")
        self.rbHotseatRandomMap = self._page.findChild(QRadioButton, "rbHotseatRandomMap")
        self.rbHotseatSpecificMap = self._page.findChild(QRadioButton, "rbHotseatSpecificMap")
        self.edtHotseatSpecificMapName = self._page.findChild(QLineEdit, "edtHotseatSpecificMapName")
        self._panel_random_map_options = self._page.findChild(QWidget, "panelHotseatRandomMapOptions")
        self._panel_specific_map_options = self._page.findChild(QWidget, "panelHotseatSpecificMapOptions")
        self._install_computer_toggles()
        self._install_map_mode_radios()

        btn_reset = self._page.findChild(QPushButton, "btnHotseatResetAll")
        self.btnHotseatStartGame = self._page.findChild(QPushButton, "btnHotseatStartGame")
        if btn_reset is not None:
            btn_reset.clicked.connect(self._on_reset_all_clicked)
        if self.btnHotseatStartGame is not None:
            self.btnHotseatStartGame.setProperty("primary", True)
            self.btnHotseatStartGame.style().unpolish(self.btnHotseatStartGame)
            self.btnHotseatStartGame.style().polish(self.btnHotseatStartGame)
            self.btnHotseatStartGame.clicked.connect(self._on_start_game)

        _placeholders = ["Player 1", "Player 2", "Player 3", "Player 4", "Player 5"]
        for i, edt in enumerate(self.edtHotseatPlayer):
            if edt is not None and i < len(_placeholders):
                edt.setPlaceholderText(_placeholders[i])
        if self.edtHotseatSpecificMapName is not None:
            self.edtHotseatSpecificMapName.setPlaceholderText("Enter map name")
            self.edtHotseatSpecificMapName.textChanged.connect(self._on_specific_map_name_changed)

        for cb in self.cbHotseatColor:
            if cb is not None:
                setup_player_color_combo(cb)
                add_clear_button_inside_combo(cb)
                cb.currentIndexChanged.connect(self._on_color_combo_changed)

        if self.cbHotseatNumPlayers is not None:
            self.cbHotseatNumPlayers.currentTextChanged.connect(self._on_num_players_changed)

        if self.cbHotseatAdvancedMode is not None:
            self.cbHotseatAdvancedMode.toggled.connect(self._on_advanced_mode_changed)

        refresh_player_color_combos([c for c in self.cbHotseatColor if c is not None])
        self._apply_player_rows_visibility()
        self._apply_map_mode_visibility()
        self._sync_custom_maps_toggle_enabled()
        self._sync_start_game_enabled()

        row = self._page.findChild(QWidget, "hotseatPanelsRow")
        if row is not None:
            lay = row.layout()
            if isinstance(lay, QGridLayout):
                lay.setColumnStretch(0, 1)
                lay.setColumnStretch(1, 0)
                lay.setRowStretch(0, 1)

        self._install_setup_board_stack()

    def _install_map_mode_radios(self) -> None:
        if self.rbHotseatRandomMap is None or self.rbHotseatSpecificMap is None:
            return
        for rb in (self.rbHotseatRandomMap, self.rbHotseatSpecificMap):
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._map_mode_group = QButtonGroup(self._page)
        self._map_mode_group.setExclusive(True)
        self._map_mode_group.addButton(self.rbHotseatRandomMap, 0)
        self._map_mode_group.addButton(self.rbHotseatSpecificMap, 1)
        self.rbHotseatRandomMap.toggled.connect(self._on_map_mode_changed)
        self.rbHotseatSpecificMap.toggled.connect(self._on_map_mode_changed)

    def _is_specific_map_mode(self) -> bool:
        return bool(self.rbHotseatSpecificMap is not None and self.rbHotseatSpecificMap.isChecked())

    def _on_map_mode_changed(self, _checked: bool = False) -> None:
        self._apply_map_mode_visibility()
        if not self._is_specific_map_mode():
            self._sync_custom_maps_toggle_enabled()
        self._sync_start_game_enabled()

    def _on_specific_map_name_changed(self, _text: str = "") -> None:
        self._sync_start_game_enabled()

    def _specific_map_name_entered(self) -> bool:
        if self.edtHotseatSpecificMapName is None:
            return False
        return bool((self.edtHotseatSpecificMapName.text() or "").strip())

    def _sync_start_game_enabled(self) -> None:
        btn = self.btnHotseatStartGame
        if btn is None:
            return
        if self._is_specific_map_mode():
            btn.setEnabled(self._specific_map_name_entered())
        else:
            btn.setEnabled(True)

    def _show_incorrect_map_name_dialog(self) -> None:
        mb = QMessageBox(self._window)
        mb.setWindowTitle(HOTSEAT_INCORRECT_MAP_NAME_TITLE)
        mb.setText(HOTSEAT_INCORRECT_MAP_NAME_MSG)
        mb.setIcon(QMessageBox.Icon.Warning)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        ok_btn = mb.addButton("Ok", QMessageBox.ButtonRole.AcceptRole)
        mb.setDefaultButton(ok_btn)
        ok_btn.setProperty("primary", True)
        st = ok_btn.style()
        if st is not None:
            st.unpolish(ok_btn)
            st.polish(ok_btn)
        layout = mb.findChild(QGridLayout)
        if layout is not None:
            layout.setHorizontalSpacing(0)
        mb.exec()

    def _on_advanced_mode_changed(self, _checked: bool = False) -> None:
        self._sync_custom_maps_toggle_enabled()

    def _apply_map_mode_visibility(self) -> None:
        specific = self._is_specific_map_mode()
        if self._panel_random_map_options is not None:
            self._panel_random_map_options.setVisible(not specific)
        if self._panel_specific_map_options is not None:
            self._panel_specific_map_options.setVisible(specific)

    def _advanced_mode_checked(self) -> bool:
        return bool(
            self.cbHotseatAdvancedMode is not None and self.cbHotseatAdvancedMode.isChecked()
        )

    def _has_playable_custom_maps_for_advanced(self, advanced: bool) -> bool:
        return bool(
            self._filter_playable_maps(self._load_custom_maps_json_pool(), advanced=advanced)
        )

    def _sync_custom_maps_toggle_enabled(self) -> None:
        """Disable + uncheck Custom Maps when none match the current Advanced Mode."""
        cb = self.cbHotseatIncludeCustomMaps
        if cb is None:
            return
        has_custom = self._has_playable_custom_maps_for_advanced(self._advanced_mode_checked())
        cb.setEnabled(has_custom)
        lbl = self._page.findChild(QLabel, "lblHotseatIncludeCustomMaps")
        if lbl is not None:
            lbl.setEnabled(has_custom)
        if not has_custom:
            cb.setChecked(False)

    def _install_computer_toggles(self) -> None:
        self.cbHotseatComputer = []
        for i, row in enumerate(self._player_rows, start=1):
            if row is None:
                self.cbHotseatComputer.append(None)
                continue
            cb_name = f"cbHotseatComputer{i}"
            lbl_name = f"lblHotseatComputer{i}"
            existing = row.findChild(QCheckBox, cb_name)
            if existing is not None:
                self.cbHotseatComputer.append(existing)
                continue
            lay = row.layout()
            if not isinstance(lay, QHBoxLayout):
                self.cbHotseatComputer.append(None)
                continue
            lbl = QLabel("Computer player:")
            lbl.setObjectName(lbl_name)
            cb = QCheckBox()
            cb.setObjectName(cb_name)
            lay.addWidget(lbl)
            lay.addWidget(cb)
            self.cbHotseatComputer.append(cb)

    def _install_setup_board_stack(self) -> None:
        """Replace the middle section (panels + spacer + buttons) with setup | board stack."""
        main_lay = self._page.layout()
        if main_lay is None:
            return
        item3 = main_lay.takeAt(3)
        item2 = main_lay.takeAt(2)
        item1 = main_lay.takeAt(1)
        row_btn = item3.widget() if item3 is not None else None
        hotseat_row = item1.widget() if item1 is not None else None
        if row_btn is None or hotseat_row is None:
            return

        setup_page = QWidget(self._page)
        setup_lay = QVBoxLayout(setup_page)
        setup_lay.setContentsMargins(0, 0, 0, 0)
        setup_lay.setSpacing(6)
        setup_lay.addWidget(hotseat_row, 1)
        if item2 is not None and item2.spacerItem() is not None:
            setup_lay.addItem(item2)
        else:
            setup_lay.addStretch(0)
        setup_lay.addWidget(row_btn, 0)
        self._setup_page = setup_page

        self._stack = QStackedWidget(self._page)
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._stack.addWidget(setup_page)

        def _stack_changed(_i: int) -> None:
            fn = getattr(self, "_breadcrumb_refresh", None)
            if callable(fn):
                fn()

        self._stack.currentChanged.connect(_stack_changed)
        main_lay.insertWidget(1, self._stack, 1)

    def _ensure_board_panel(self) -> None:
        """Create the gameplay board on first Start Game (defers heavy hotseat_board import)."""
        if self._board_panel is not None or self._stack is None:
            return
        from ui.pages.hotseat_board import HotseatBoardPanel

        self._board_panel = HotseatBoardPanel(self._page)
        self._board_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._stack.addWidget(self._board_panel)
        self._board_panel.session_ended.connect(self._on_hotseat_session_ended)

    def _on_hotseat_session_ended(self) -> None:
        """User confirmed End Game: clear board, reset setup to defaults, show setup."""
        if self._board_panel is not None:
            self._board_panel.clear_board()
        self._on_reset_all()
        if self._stack is not None:
            self._stack.setCurrentIndex(0)
        fn = getattr(self, "_breadcrumb_refresh", None)
        if callable(fn):
            fn()

    def _player_count(self) -> int:
        if self.cbHotseatNumPlayers is None:
            return 3
        t = (self.cbHotseatNumPlayers.currentText() or "").strip()
        if t in ("3", "4", "5"):
            return int(t)
        return 3

    def _clear_player_slots_from(self, start_index: int) -> None:
        """Clear name and color for player indices [start_index, 5) (0-based)."""
        for i in range(start_index, 5):
            if i < len(self.edtHotseatPlayer):
                edt = self.edtHotseatPlayer[i]
                if edt is not None:
                    edt.clear()
            if i < len(self.cbHotseatColor):
                cb = self.cbHotseatColor[i]
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setCurrentIndex(0)
                    cb.blockSignals(False)
            if i < len(self.cbHotseatComputer):
                cb_comp = self.cbHotseatComputer[i]
                if cb_comp is not None:
                    cb_comp.setChecked(False)

    def _on_num_players_changed(self, _text: str) -> None:
        n = self._player_count()
        self._clear_player_slots_from(n)
        refresh_player_color_combos([c for c in self.cbHotseatColor if c is not None])
        self._apply_player_rows_visibility()

    def _on_color_combo_changed(self, _index: int) -> None:
        refresh_player_color_combos([c for c in self.cbHotseatColor if c is not None])

    def _apply_player_rows_visibility(self) -> None:
        n = self._player_count()
        for i, row in enumerate(self._player_rows):
            if row is not None:
                row.setVisible(i < n)
        pl = self._page.findChild(QWidget, "playersSettings")
        if pl is not None:
            pl.updateGeometry()

    def _on_reset_all_clicked(self) -> None:
        mb = QMessageBox(self._window)
        mb.setWindowTitle(RESET_CONFIRM_TITLE)
        mb.setText(RESET_CONFIRM_MSG)
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        no_btn = mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        st = yes_btn.style()
        if st is not None:
            st.unpolish(yes_btn)
            st.polish(yes_btn)
        layout = mb.findChild(QGridLayout)
        if layout is not None:
            layout.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        self._on_reset_all()

    def _on_reset_all(self) -> None:
        if self.cbHotseatNumPlayers is not None:
            self.cbHotseatNumPlayers.setCurrentIndex(0)
        for edt in self.edtHotseatPlayer:
            if edt is not None:
                edt.clear()
        if self.rbHotseatRandomMap is not None:
            self.rbHotseatRandomMap.setChecked(True)
        for cb in (self.cbHotseatAdvancedMode, self.cbHotseatIncludeCustomMaps):
            if cb is not None:
                cb.setChecked(False)
        if self.edtHotseatSpecificMapName is not None:
            self.edtHotseatSpecificMapName.clear()
        for cb in self.cbHotseatColor:
            if cb is not None:
                cb.blockSignals(True)
                cb.setCurrentIndex(0)
                cb.blockSignals(False)
        for cb in self.cbHotseatComputer:
            if cb is not None:
                cb.setChecked(False)
        refresh_player_color_combos([c for c in self.cbHotseatColor if c is not None])
        self._apply_player_rows_visibility()
        self._apply_map_mode_visibility()
        self._sync_custom_maps_toggle_enabled()
        self._sync_start_game_enabled()

    def _resolve_computer_flags(self, n: int) -> list[bool]:
        out: list[bool] = []
        for i in range(n):
            cb = self.cbHotseatComputer[i] if i < len(self.cbHotseatComputer) else None
            out.append(bool(cb.isChecked()) if cb is not None else False)
        return out

    def _resolve_player_names(self, n: int) -> list[str]:
        placeholders = ["Player 1", "Player 2", "Player 3", "Player 4", "Player 5"]
        out: list[str] = []
        for i in range(n):
            edt = self.edtHotseatPlayer[i] if i < len(self.edtHotseatPlayer) else None
            t = (edt.text() or "").strip() if edt is not None else ""
            out.append(t if t else placeholders[i])
        return out

    def _resolve_player_colors(self, n: int) -> list[str]:
        """Use chosen colors; for empty slots assign distinct random colors from PLAYER_COLORS."""
        names = [c[0] for c in PLAYER_COLORS]
        chosen: list[str] = []
        for i in range(n):
            cb = self.cbHotseatColor[i] if i < len(self.cbHotseatColor) else None
            c = get_selected_player_color(cb) if cb is not None else ""
            chosen.append(c)
        used = {c for c in chosen if c}
        pool = [x for x in names if x not in used]
        random.shuffle(pool)
        pi = 0
        out: list[str] = []
        for i in range(n):
            if chosen[i]:
                out.append(chosen[i])
            else:
                if pi < len(pool):
                    out.append(pool[pi])
                    pi += 1
                else:
                    out.append(names[i % len(names)])
        return out

    def _load_maps_json_pool(self) -> list[dict]:
        try:
            with open(MAPS_JSON, encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get("maps") or [])
        except OSError:
            return []

    def _load_custom_maps_json_pool(self) -> list[dict]:
        try:
            with open(CUSTOM_MAPS_JSON, encoding="utf-8") as f:
                data = json.load(f)
            maps = list(data.get("maps") or [])
        except OSError:
            return []
        return [m for m in maps if not self._is_soft_deleted_custom_map(m)]

    @staticmethod
    def _is_soft_deleted_custom_map(map_data: dict) -> bool:
        """Maps Library hides soft-deleted entries; hotseat must ignore them too."""
        try:
            return int(map_data.get("soft_deleted", 0) or 0) != 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _filter_playable_maps(maps_list: list[dict], *, advanced: bool) -> list[dict]:
        pool = [m for m in maps_list if bool(m.get("advancedMode", False)) == advanced]
        return [
            m
            for m in pool
            if m.get("id") is not None and str(m.get("id", "")).strip() != ""
        ]

    def on_navigate_to(self) -> None:
        """Refresh Custom Maps enablement when returning to Play Hotseat."""
        self._sync_custom_maps_toggle_enabled()

    @staticmethod
    def _clues_and_habitat_for_custom_map(
        map_data: dict,
        players: int,
        *,
        advanced: bool,
    ) -> tuple[list[str], tuple[int, int]] | None:
        """First valid clue set + habitat hex for a custom map, or None if none exist."""
        hardcoded = PlayHotseatPageController._hardcoded_test_clues_and_habitat(
            map_data, players, advanced=advanced
        )
        if hardcoded is not None:
            return hardcoded
        try:
            current_map = build_map_from_data(map_data)
        except Exception:
            return None
        found = find_first_rule_combination_with_exactly_one_intersection(
            current_map,
            players,
            all_condition_labels(advanced_mode=advanced),
            advanced_mode=advanced,
        )
        if found is None:
            return None
        rules, target_hex = found
        y, x = int(target_hex[0]), int(target_hex[1])
        return (list(rules), (y, x))

    @staticmethod
    def _hardcoded_test_clues_and_habitat(
        map_data: dict,
        players: int,
        *,
        advanced: bool,
    ) -> tuple[list[str], tuple[int, int]] | None:
        """TEMP: fixed clues for 'Dan broke everything' (3 players)."""
        if not HOTSEAT_TEST_DAN_BROKE_EVERYTHING:
            return None
        if players != len(_HOTSEAT_TEST_CLUES):
            return None
        if str(map_data.get("name") or "").strip().lower() != _HOTSEAT_TEST_MAP_NAME.lower():
            return None
        try:
            current_map = build_map_from_data(map_data)
            grid = compute_all_conditions(current_map, advanced_mode=advanced)
            hexes = grid.intersection_hexes(_HOTSEAT_TEST_CLUES)
        except Exception:
            return None
        if len(hexes) != 1:
            return None
        target_hex = next(iter(hexes))
        return (list(_HOTSEAT_TEST_CLUES), (int(target_hex[0]), int(target_hex[1])))

    def _find_map_by_name(self, name: str) -> tuple[dict, bool] | None:
        """Return (map_data, is_custom) for an exact case-insensitive name match."""
        needle = name.strip().lower()
        if not needle:
            return None
        for m in self._load_maps_json_pool():
            if str(m.get("name") or "").strip().lower() == needle:
                if m.get("id") is None or str(m.get("id", "")).strip() == "":
                    continue
                return (dict(m), False)
        for m in self._load_custom_maps_json_pool():
            if str(m.get("name") or "").strip().lower() == needle:
                if m.get("id") is None or str(m.get("id", "")).strip() == "":
                    continue
                tagged = dict(m)
                tagged[_HOTSEAT_CUSTOM_FLAG] = True
                return (tagged, True)
        return None

    def _on_start_game(self) -> None:
        if self._stack is None:
            return
        self._ensure_board_panel()
        if self._board_panel is None:
            return

        n = self._player_count()
        names = self._resolve_player_names(n)
        colors = self._resolve_player_colors(n)
        computer_flags = self._resolve_computer_flags(n)

        chosen: dict | None = None
        clues_override: list[str] | None = None
        habitat_hex: tuple[int, int] | None = None
        show_apply_hint = False

        if self._is_specific_map_mode():
            map_name = (
                (self.edtHotseatSpecificMapName.text() or "").strip()
                if self.edtHotseatSpecificMapName is not None
                else ""
            )
            if not map_name:
                return
            found = self._find_map_by_name(map_name)
            if found is None:
                self._show_incorrect_map_name_dialog()
                return
            chosen, is_custom = found
            show_apply_hint = not is_custom
            advanced = bool(chosen.get("advancedMode", False))
            if is_custom:
                resolved = self._clues_and_habitat_for_custom_map(
                    chosen, n, advanced=advanced
                )
                if resolved is None:
                    QMessageBox.warning(
                        self._window,
                        "Play Hotseat",
                        "This custom map has no valid clue combination for the "
                        "current player count.",
                    )
                    return
                clues_override, habitat_hex = resolved
        else:
            advanced = (
                bool(self.cbHotseatAdvancedMode.isChecked())
                if self.cbHotseatAdvancedMode is not None
                else False
            )
            use_custom_only = (
                bool(self.cbHotseatIncludeCustomMaps.isChecked())
                if self.cbHotseatIncludeCustomMaps is not None
                else False
            )
            show_apply_hint = not use_custom_only
            if use_custom_only:
                pool = []
                for m in self._filter_playable_maps(
                    self._load_custom_maps_json_pool(), advanced=advanced
                ):
                    tagged = dict(m)
                    tagged[_HOTSEAT_CUSTOM_FLAG] = True
                    pool.append(tagged)
                source = "custom_maps.json"
            else:
                pool = self._filter_playable_maps(
                    self._load_maps_json_pool(), advanced=advanced
                )
                source = "maps.json"
            if not pool:
                QMessageBox.warning(
                    self._window,
                    "Play Hotseat",
                    f"No playable maps in {source} for the current Advanced mode "
                    "(each map needs a non-empty id).",
                )
                return

            random.shuffle(pool)
            for candidate in pool:
                if candidate.get(_HOTSEAT_CUSTOM_FLAG):
                    resolved = self._clues_and_habitat_for_custom_map(
                        candidate, n, advanced=advanced
                    )
                    if resolved is None:
                        continue
                    clues_override, habitat_hex = resolved
                    chosen = candidate
                    break
                chosen = candidate
                break
            if chosen is None:
                QMessageBox.warning(
                    self._window,
                    "Play Hotseat",
                    "No playable custom map has a valid clue combination for this "
                    "player count and Advanced mode setting.",
                )
                return

        # Load while setup is still visible; suppress intermediate paints on the board panel.
        board = self._board_panel
        board.setUpdatesEnabled(False)
        try:
            board.load_map(
                chosen,
                names,
                colors,
                computer_flags=computer_flags,
                clues=clues_override,
                habitat_hex=habitat_hex,
                show_apply_hint=show_apply_hint,
            )
            self._stack.setCurrentIndex(1)
        finally:
            board.setUpdatesEnabled(True)
        # Let the board render (map + turn panel) before showing the modal.
        QTimer.singleShot(0, board.show_next_turn_dialog)
