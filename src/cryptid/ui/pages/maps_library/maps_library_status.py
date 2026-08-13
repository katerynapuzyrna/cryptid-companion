"""Status list for Maps Library create mode: header + tiles/structures rows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QCheckBox, QGraphicsItem
from PySide6.QtGui import QIcon, QFont

from board.canvas import PuzzleCanvas


class MapsLibraryStatusManager:
    """QListWidget with 'Status:' header plus two checklist rows (tiles, structures)."""

    def __init__(
        self,
        status_list: QListWidget,
        icon_ok: QIcon,
        icon_error: QIcon,
        cb_freeze_map: QCheckBox | None,
        canvas: PuzzleCanvas,
        pieces: list,
        markers: list,
    ):
        self._status_list = status_list
        self._icon_ok = icon_ok
        self._icon_error = icon_error
        self._cb_freeze_map = cb_freeze_map
        self._canvas = canvas
        self._pieces = pieces
        self._markers = markers
        self._header_text = "Status:"
        self._texts = [
            "All map tiles are placed",
            "All structures are placed",
        ]
        self.all_tiles_placed: bool = False
        self.all_struct: bool = False
        self._freeze_map_auto_checked = False
        if self._cb_freeze_map:
            self._cb_freeze_map.toggled.connect(self._apply_freeze_map_drag_state)

    def _expected_row_count(self) -> int:
        return 1 + len(self._texts)

    def _rebuild_list_items(self) -> None:
        """Header row + two status lines (all inside the QListWidget)."""
        self._status_list.clear()
        header = QListWidgetItem(self._header_text)
        header.setFlags(Qt.ItemFlag.ItemIsEnabled)
        header.setIcon(QIcon())
        hf = QFont(self._status_list.font())
        hf.setBold(False)
        hf.setWeight(QFont.Weight.DemiBold)  # font-weight: 600 (not full bold)
        header.setFont(hf)
        self._status_list.addItem(header)
        for txt in self._texts:
            self._status_list.addItem(txt)

    def update(self) -> None:
        if (
            not self._status_list
            or not self._canvas
            or not self._pieces
            or not self._markers
        ):
            return

        if self._status_list.count() != self._expected_row_count():
            self._rebuild_list_items()

        all_tiles = all(
            self._canvas.item_slot.get(p) is not None for p in self._pieces
        )
        visible_m = [m for m in self._markers if m.isVisible()]
        all_struct = all(
            self._canvas.marker_slot.get(m) is not None for m in visible_m
        )
        self.all_tiles_placed = all_tiles
        self.all_struct = all_struct

        for row, ok in enumerate([all_tiles, all_struct]):
            item = self._status_list.item(row + 1)
            if item is not None:
                item.setIcon(self._icon_ok if ok else self._icon_error)

        if self._cb_freeze_map:
            self._cb_freeze_map.blockSignals(True)
            self._cb_freeze_map.setEnabled(all_tiles)
            if not all_tiles:
                self._freeze_map_auto_checked = False
                self._cb_freeze_map.setChecked(False)
            elif not self._freeze_map_auto_checked:
                # Create Map: freeze as soon as all tiles are on the board (structures come after).
                self._freeze_map_auto_checked = True
                self._cb_freeze_map.setChecked(True)
            self._cb_freeze_map.blockSignals(False)
            self._apply_freeze_map_drag_state()

    def is_save_ready(self) -> bool:
        """Both status rows satisfied (tiles on board, structures placed)."""
        return self.all_tiles_placed and self.all_struct

    def _apply_freeze_map_drag_state(self) -> None:
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

    def reset_for_build(self) -> None:
        self._freeze_map_auto_checked = False
        self.all_tiles_placed = False
        self.all_struct = False
        self._rebuild_list_items()
        if self._cb_freeze_map:
            self._cb_freeze_map.blockSignals(True)
            self._cb_freeze_map.setChecked(False)
            self._cb_freeze_map.setEnabled(False)
            self._cb_freeze_map.blockSignals(False)
            self._apply_freeze_map_drag_state()
