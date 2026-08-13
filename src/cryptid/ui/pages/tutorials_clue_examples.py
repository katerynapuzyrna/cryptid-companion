"""Interactive clue examples preview for the Tutorials page."""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from logic.clue_grid import CLUE_GRID_LABELS
from logic.conditions import compute_all_conditions
from logic.map_loader import build_map_from_data, targets_to_highlighted_cells
from settings.config import MAPS_JSON
from ui.pages.tutorials_previews import _PreviewView
from ui.shared.map_card.scene import build_map_preview_scene
from ui.shared.widgets import ComboBoxWithPopupAbove, add_clear_button_inside_combo, sync_clear_button_visibility

_TUTORIAL_EXAMPLE_MAP_NAME = "Blackwater Expanse"
_CLUE_PLACEHOLDER = "<Select clue>"


def _load_map_by_name(name: str) -> dict[str, Any]:
    with open(MAPS_JSON, encoding="utf-8") as f:
        for entry in json.load(f).get("maps") or []:
            if entry.get("name") == name:
                return entry
    raise RuntimeError(f"Map not found in maps.json: {name!r}")


class ScaledMapPreviewWidget(QWidget):
    """Non-interactive map preview scaled to fit a max side length."""

    def __init__(
        self,
        map_data: dict[str, Any],
        *,
        max_side: float = 360,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scene, canvas, overlay = build_map_preview_scene(map_data)
        self._canvas = canvas
        self._highlight_overlay = overlay

        self._view = _PreviewView(self)
        self._view.setScene(scene)
        fit_rect = QRectF(canvas.rect)
        scene.setSceneRect(fit_rect)

        width = max(40, int(fit_rect.width()))
        height = max(40, int(fit_rect.height()))
        scale = min(1.0, max_side / max(width, height))
        width = max(40, int(width * scale))
        height = max(40, int(height * scale))
        self._view.setFixedSize(width, height)
        self._view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._view.set_fit_rect(fit_rect)
        layout.addWidget(self._view, 0, Qt.AlignmentFlag.AlignLeft)

    @property
    def map_width(self) -> int:
        return self._view.width()

    def apply_highlights(self, highlighted_cells: set[tuple[int, int, int]]) -> None:
        self._canvas._zero_targets_dim_full_map = len(highlighted_cells) == 0
        for piece in list(self._canvas.item_slot.keys()):
            piece.highlighted.clear()
        for row, col, cell_idx in highlighted_cells:
            piece = self._canvas.occupied.get((row, col))
            if piece is not None:
                piece.highlighted.add(cell_idx)
        for piece in self._canvas.item_slot:
            piece.update()
        for marker in self._canvas.marker_slot:
            marker.update()
        if self._highlight_overlay:
            self._highlight_overlay.update_highlights()

    def clear_highlights(self) -> None:
        self._canvas._zero_targets_dim_full_map = False
        for piece in self._canvas.item_slot:
            piece.highlighted.clear()
            piece.update()
        for marker in self._canvas.marker_slot:
            marker.update()
        if self._highlight_overlay:
            self._highlight_overlay.update_highlights()


class CluesExamplesWidget(QWidget):
    """Dropdown of all clues plus a map preview with valid-hex highlighting."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self._map_data = _load_map_by_name(_TUTORIAL_EXAMPLE_MAP_NAME)
        self._advanced_mode = bool(self._map_data.get("advancedMode", False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        self._preview = ScaledMapPreviewWidget(self._map_data, max_side=360, parent=self)
        map_width = self._preview.map_width

        self._combo = ComboBoxWithPopupAbove(self)
        self._combo.setObjectName("tutorialClueCombo")
        self._combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._combo.addItem(_CLUE_PLACEHOLDER)
        self._combo.addItems(CLUE_GRID_LABELS)
        add_clear_button_inside_combo(self._combo)
        sync_clear_button_visibility(self._combo)
        self._combo.setMinimumWidth(0)
        self._combo.setMaximumWidth(map_width)
        self._combo.setFixedWidth(map_width)
        self._combo.currentIndexChanged.connect(self._on_clue_changed)
        layout.addWidget(self._combo, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignLeft)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_combo_width()

    def _sync_combo_width(self) -> None:
        map_width = self._preview.map_width
        self._combo.setMinimumWidth(0)
        self._combo.setMaximumWidth(map_width)
        self._combo.setFixedWidth(map_width)

    def _on_clue_changed(self, index: int) -> None:
        label = (self._combo.currentText() or "").strip()
        if index <= 0 or not label or label == _CLUE_PLACEHOLDER:
            self._preview.clear_highlights()
            return

        current_map = build_map_from_data(self._map_data)
        all_conds = compute_all_conditions(current_map, advanced_mode=self._advanced_mode)
        try:
            targets = all_conds.intersection_hexes([label])
        except KeyError:
            self._preview.clear_highlights()
            return

        highlighted_cells = targets_to_highlighted_cells(targets, self._map_data)
        self._preview.apply_highlights(highlighted_cells)


def make_clues_examples_widget(parent: QWidget | None = None) -> QWidget:
    frame = QFrame(parent)
    frame.setObjectName("tutorialCluesExamplesHost")
    frame.setFrameShape(QFrame.Shape.NoFrame)
    frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(CluesExamplesWidget(frame))
    return frame
