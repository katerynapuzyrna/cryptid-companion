"""Manager for status list: validation state, icons, Solve button, freeze map."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtWidgets import QListWidget, QPushButton, QCheckBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from ui.shared.rules_dropdowns_manager import RuleDropdownsManager


class StatusListManager:
    """Coordinates status list: tiles/structures/rules validation, icons, Solve button, freeze map."""

    def __init__(
        self,
        status_list: QListWidget,
        icon_ok: QIcon,
        icon_error: QIcon,
        rules: "RuleDropdownsManager",
        cb_build_players: Any,  # QComboBox
        btn_solve: QPushButton,
        cb_freeze_map: QCheckBox | None,
        canvas: Any,  # PuzzleCanvas
        pieces: list,
        markers: list,
        chips: list | None = None,
        rule_check_count: int | None = None,
        icon_warning: QIcon | None = None,
        edt_player: list | None = None,
        cb_color: list | None = None,
        board_builder: Any = None,
        get_simulation_status: Callable[[], tuple[int, list[int]] | None] | None = None,
    ):
        self._status_list = status_list
        self._board_builder = board_builder
        self._get_simulation_status = get_simulation_status
        self._build_mode_item_texts = [
            "All map tiles are placed",
            "All structures are placed",
            "Your clue is selected",
            "Player's names are set",
            "Player's colors are selected",
        ]
        self._icon_ok = icon_ok
        self._icon_error = icon_error
        self._icon_warning = icon_warning
        self._rules = rules
        self._cb_build_players = cb_build_players
        self._btn_solve = btn_solve
        self._cb_freeze_map = cb_freeze_map
        self._canvas = canvas
        self._pieces = pieces
        self._markers = markers
        self._chips = chips or []
        self._rule_check_count = rule_check_count
        self._edt_player = edt_player or []
        self._cb_color = cb_color or []
        self._freeze_map_auto_checked = False
        self.all_tiles: bool = False
        self.all_struct: bool = False
        if self._cb_freeze_map:
            self._cb_freeze_map.toggled.connect(self._apply_freeze_map_drag_state)

    def update(self) -> None:
        """Recompute validation state, update status icons, Solve button, freeze checkbox."""
        if (
            not self._status_list
            or not self._canvas
            or not self._pieces
            or not self._markers
        ):
            return

        in_simulation = (
            self._board_builder is not None
            and getattr(self._board_builder, "_chips_mode", False)
            and self._get_simulation_status is not None
        )
        if in_simulation:
            self._update_simulation_mode()
            return

        if (
            self._rule_check_count is not None
            and self._status_list.count() != len(self._build_mode_item_texts)
        ):
            self._status_list.clear()
            for txt in self._build_mode_item_texts:
                self._status_list.addItem(txt)

        all_tiles = all(
            self._canvas.item_slot.get(p) is not None for p in self._pieces
        )
        visible_m = [m for m in self._markers if m.isVisible()]
        all_struct = all(
            self._canvas.marker_slot.get(m) is not None for m in visible_m
        )
        self.all_tiles = all_tiles
        self.all_struct = all_struct
        if self._rule_check_count is not None:
            rule_players = self._rule_check_count
        else:
            rule_players = None
        players = self._rules.parse_players(
            (self._cb_build_players.currentText() or "").strip()
        )
        players = players if players in (3, 4, 5) else 3
        check_players = rule_players if rule_players is not None else players
        sel = (
            self._rules.read_selected_rules(check_players)
            if players in (3, 4, 5) or rule_players is not None
            else []
        )
        all_rules = (
            (players in (3, 4, 5) or rule_players is not None)
            and len(sel) == check_players
            and all(bool(s) for s in sel)
        )

        all_names = True
        all_colors = True
        if (
            self._rule_check_count is not None
            and len(self._edt_player) >= players
            and len(self._cb_color) >= players
        ):
            for i in range(players):
                edt = self._edt_player[i] if i < len(self._edt_player) else None
                cb = self._cb_color[i] if i < len(self._cb_color) else None
                if edt is not None and (edt.text() or "").strip() == "":
                    all_names = False
                if cb is not None and (cb.currentIndex() or 0) <= 0:
                    all_colors = False

        validations = [all_tiles, all_struct, all_rules]
        if self._rule_check_count is not None and self._edt_player and self._cb_color:
            validations.extend([all_names, all_colors])

        for row, ok in enumerate(validations):
            if row < self._status_list.count():
                use_warning = (
                    row >= 3
                    and self._rule_check_count is not None
                    and self._icon_warning is not None
                )
                if use_warning:
                    self._status_list.item(row).setIcon(
                        self._icon_ok if ok else self._icon_warning
                    )
                else:
                    self._status_list.item(row).setIcon(
                        self._icon_ok if ok else self._icon_error
                    )

        if self._rule_check_count is not None and self._edt_player and self._cb_color:
            self._btn_solve.setEnabled(all_tiles and all_struct and all_rules)
        else:
            self._btn_solve.setEnabled(all_tiles and all_struct and all_rules)

        if self._cb_freeze_map:
            self._cb_freeze_map.blockSignals(True)
            self._cb_freeze_map.setEnabled(all_tiles)
            placed = sum(
                1
                for m in visible_m
                if self._canvas.marker_slot.get(m) is not None
            )
            if not all_tiles:
                self._freeze_map_auto_checked = False
                self._cb_freeze_map.setChecked(False)
            elif (
                placed >= 1
                and not self._freeze_map_auto_checked
            ):
                self._freeze_map_auto_checked = True
                self._cb_freeze_map.setChecked(True)
            self._cb_freeze_map.blockSignals(False)
            self._apply_freeze_map_drag_state()

    def _update_simulation_mode(self) -> None:
        """Update status list for simulation: Valid hexes, Player N valid clues, per-row icons."""
        data = self._get_simulation_status() if self._get_simulation_status else None
        if data is None:
            return
        if len(data) == 3:
            valid_hex_count, valid_clues_per_player, player_display_names = data
        else:
            valid_hex_count, valid_clues_per_player = data
            player_display_names = [f"Player {p + 1}" for p in range(len(valid_clues_per_player))]
        items = [f"Valid hexes - {valid_hex_count}"]
        for p in range(1, len(valid_clues_per_player)):
            c = valid_clues_per_player[p]
            name = player_display_names[p] if p < len(player_display_names) else f"Player {p + 1}"
            items.append(f"{name} valid clues - {c}")
        if self._status_list.count() != len(items):
            self._status_list.clear()
            for txt in items:
                self._status_list.addItem(txt)
        else:
            for row, txt in enumerate(items):
                self._status_list.item(row).setText(txt)
        counts = [valid_hex_count] + valid_clues_per_player[1:]
        for row, c in enumerate(counts):
            if row >= self._status_list.count():
                break
            if c == 0:
                icon = self._icon_error
            elif c == 1:
                icon = self._icon_ok
            else:
                icon = self._icon_warning if self._icon_warning else self._icon_ok
            self._status_list.item(row).setIcon(icon)
        self._status_list.doItemsLayout()

    def _apply_freeze_map_drag_state(self) -> None:
        """Enable/disable piece dragging based on freeze checkbox (Solver Tool)."""
        if not self._cb_freeze_map or not self._pieces:
            return
        frozen = self._cb_freeze_map.isChecked()
        for p in self._pieces:
            p.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                not frozen,
            )
            p.setCursor(
                Qt.CursorShape.ArrowCursor
                if frozen
                else Qt.CursorShape.OpenHandCursor
            )

    def _apply_freeze_markers_drag_state(self, frozen: bool) -> None:
        """Enable/disable marker and chip dragging (Deduction mode)."""
        grab = Qt.CursorShape.OpenHandCursor
        arrow = Qt.CursorShape.ArrowCursor
        for m in self._markers:
            m.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not frozen)
            m.setCursor(arrow if frozen else grab)
        for c in self._chips:
            c.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not frozen)
            c.setCursor(arrow if frozen else grab)

    def reset_for_build(self) -> None:
        """Reset freeze map state, restore build-mode status items, apply drag state (called when page does full reset)."""
        self._freeze_map_auto_checked = False
        if self._rule_check_count is not None:
            self._status_list.clear()
            for txt in self._build_mode_item_texts:
                self._status_list.addItem(txt)
        if self._cb_freeze_map:
            self._cb_freeze_map.blockSignals(True)
            self._cb_freeze_map.setChecked(False)
            self._cb_freeze_map.setEnabled(False)
            self._cb_freeze_map.blockSignals(False)
            self._apply_freeze_map_drag_state()
