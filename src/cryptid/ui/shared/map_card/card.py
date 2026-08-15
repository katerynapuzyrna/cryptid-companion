"""Map card frame: name, thumbnail/full preview, clue UI."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QColor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QStackedWidget,
    QSizePolicy,
    QToolButton,
    QSpacerItem,
)

from logic.clues import get_clues_for_map
from logic.conditions import all_condition_labels
from settings.config import ASSETS_DIR
from ui.shared.widgets import (
    ComboBoxWithPopupAbove,
    setup_player_color_combo,
    refresh_player_color_combos,
    add_clear_button_inside_combo,
    sync_clear_button_visibility,
    get_selected_player_color,
)

from .blur import _create_blurred_text_pixmap
from .scene import _get_preview_canvas_size
from .thumbnail_cache import (
    render_map_thumbnail_png,
    thumbnail_path_for_map_id,
)
from .views import MapCanvasPreviewWidget

# Tracks in-flight renders (predefined + custom maps share map_thumbnails_v* / {id}.png).
_THUMB_GENERATION_IN_PROGRESS: set[Any] = set()


def invalidate_map_thumbnail_on_disk(map_id: int) -> None:
    """Remove cached PNG so cards re-render from map JSON after geometry/content changes."""
    _THUMB_GENERATION_IN_PROGRESS.discard(map_id)
    path = thumbnail_path_for_map_id(map_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


# Approx width of the trailing delete column (balances name row for optical center).
_CUSTOM_MAP_NAME_ROW_BALANCE_W = 56


class MapCard(QFrame):
    """One map card: name label + map preview + player clues (right of map)."""

    clicked = Signal(dict)
    custom_edit_clicked = Signal(dict)
    custom_delete_clicked = Signal(dict)
    custom_rename_map_name_clicked = Signal(dict)

    def __init__(
        self,
        map_data: dict[str, Any],
        players: int = 3,
        deduction_mode: bool = False,
        on_rule_changed: Any = None,
        browse_only: bool = False,
        custom_map_actions: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.map_data = map_data
        self._players = players
        self._deduction_mode = deduction_mode
        self._browse_only = browse_only
        self._on_rule_changed = on_rule_changed
        self._btn_custom_edit: QToolButton | None = None
        self._btn_custom_delete: QToolButton | None = None
        self._btn_custom_map_name_pen: QToolButton | None = None
        self.setObjectName("mapCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, self.sizePolicy().verticalPolicy())
        self.setProperty("selected", False)
        self.setProperty("interactive", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        name = map_data.get("name") or f"Map {map_data.get('id', '?')}"
        lbl = QLabel(name)
        lbl.setObjectName("mapCardName")
        lbl.setWordWrap(False)
        if custom_map_actions:
            name_row = QWidget()
            name_row.setObjectName("mapCardNameRow")
            nl = QHBoxLayout(name_row)
            nl.setContentsMargins(0, 0, 0, 0)
            nl.setSpacing(6)
            # Fixed slot on the left ≈ tool column on the right so the name centers on the card.
            nl.addItem(
                QSpacerItem(
                    _CUSTOM_MAP_NAME_ROW_BALANCE_W,
                    1,
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Minimum,
                )
            )
            name_and_pen = QWidget()
            name_and_pen.setObjectName("mapCardNameAndPen")
            npl = QHBoxLayout(name_and_pen)
            npl.setContentsMargins(0, 0, 0, 0)
            npl.setSpacing(4)
            lbl.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            lbl.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
            )
            npl.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
            self._btn_custom_map_name_pen = QToolButton()
            self._btn_custom_map_name_pen.setObjectName("mapCardNamePen")
            self._btn_custom_map_name_pen.setIcon(
                QIcon(str(ASSETS_DIR / "icons" / "Edit pen icon.svg"))
            )
            self._btn_custom_map_name_pen.setIconSize(QSize(20, 20))
            self._btn_custom_map_name_pen.setAutoRaise(True)
            self._btn_custom_map_name_pen.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_custom_map_name_pen.clicked.connect(
                lambda: self.custom_rename_map_name_clicked.emit(dict(self.map_data))
            )
            npl.addWidget(self._btn_custom_map_name_pen, 0, Qt.AlignmentFlag.AlignVCenter)
            nl.addStretch(1)
            nl.addWidget(
                name_and_pen,
                0,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            )
            nl.addStretch(1)
            self._btn_custom_edit = QToolButton()
            self._btn_custom_edit.setObjectName("mapCardCustomEdit")
            self._btn_custom_edit.setIcon(QIcon(":/assets/icons/edit-button-svgrepo-com.svg"))
            self._btn_custom_edit.setIconSize(QSize(20, 20))
            self._btn_custom_edit.setAutoRaise(True)
            self._btn_custom_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_custom_edit.clicked.connect(
                lambda: self.custom_edit_clicked.emit(dict(self.map_data))
            )
            nl.addWidget(self._btn_custom_edit, 0, Qt.AlignmentFlag.AlignVCenter)
            self._btn_custom_delete = QToolButton()
            self._btn_custom_delete.setObjectName("mapCardCustomDelete")
            self._btn_custom_delete.setIcon(QIcon(":/assets/icons/delete-button-svgrepo-com.svg"))
            self._btn_custom_delete.setIconSize(QSize(20, 20))
            self._btn_custom_delete.setAutoRaise(True)
            self._btn_custom_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_custom_delete.clicked.connect(
                lambda: self.custom_delete_clicked.emit(dict(self.map_data))
            )
            nl.addWidget(self._btn_custom_delete, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(name_row)
        else:
            layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(12)
        self._full_preview: MapCanvasPreviewWidget | None = None
        self._preview_stack = QStackedWidget()

        self._thumb_w, self._thumb_h = _get_preview_canvas_size()
        self._thumb_label = QLabel()
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._thumb_label.setFixedSize(self._thumb_w, self._thumb_h)
        placeholder = QPixmap(self._thumb_w, self._thumb_h)
        placeholder.fill(QColor("#dfe6eb"))
        self._thumb_label.setPixmap(placeholder)

        thumb_widget = QWidget()
        thumb_layout = QVBoxLayout(thumb_widget)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_layout.setSpacing(0)
        thumb_layout.addWidget(self._thumb_label)
        self._preview_stack.addWidget(thumb_widget)

        row_layout.addWidget(self._preview_stack, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._clues_built: bool = False
        self._blur_placeholder = "••••••••••••••••"
        clues_column = QWidget()
        clues_column_layout = QVBoxLayout(clues_column)
        clues_column_layout.setContentsMargins(0, 0, 0, 0)
        clues_column_layout.setSpacing(4)
        self._clues_container = QWidget()
        self._clues_container.setVisible(False)
        self._clues_inner_container: QWidget | None = None
        clues_column_layout.addWidget(
            self._clues_container,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        self._clues_column_layout = clues_column_layout
        self._blur_row = QWidget()
        blur_row = self._blur_row
        blur_row_layout = QHBoxLayout(blur_row)
        blur_row_layout.setContentsMargins(0, 0, 0, 0)
        blur_row_layout.addStretch()
        blur_lbl = QLabel("Blur clues:")
        blur_lbl.setObjectName("mapCardBlurLabel")
        blur_row_layout.addWidget(blur_lbl, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._cb_blur_clues = QCheckBox()
        self._cb_blur_clues.setObjectName("mapCardBlurToggle")
        self._cb_blur_clues.setChecked(True)
        self._cb_blur_clues.toggled.connect(self._on_blur_toggled)
        blur_row_layout.addWidget(self._cb_blur_clues, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        clues_column_layout.addWidget(blur_row, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(clues_column, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(row, 0, Qt.AlignmentFlag.AlignHCenter)
        self._clues_column = clues_column
        self._clues_column.setVisible(False)
        self._blur_row.setVisible(False)

        self._clue_texts: list[str] = []
        self._clue_combos = []
        self._clue_stacks = []
        self._clue_rows = []
        self._edt_player = []
        self._cb_color = []

        self._thumb_loaded: bool = False
        self._load_thumbnail_from_disk()
        if browse_only:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_selection_style()

    def ensure_full_preview(self) -> None:
        """Create and show the full QGraphicsScene preview lazily."""
        if self._full_preview is None:
            self._full_preview = MapCanvasPreviewWidget(self.map_data, self)
            self._preview_stack.addWidget(self._full_preview)
        self._preview_stack.setCurrentWidget(self._full_preview)

    def _thumb_path(self):
        map_id = self.map_data.get("id")
        if map_id is None:
            return None
        return thumbnail_path_for_map_id(map_id)

    def _set_thumbnail_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        if pixmap.width() == self._thumb_w and pixmap.height() == self._thumb_h:
            self._thumb_label.setPixmap(pixmap)
            return
        scaled = pixmap.scaled(
            self._thumb_w,
            self._thumb_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb_label.setPixmap(scaled)

    def _load_thumbnail_from_disk(self) -> None:
        """Fast path for startup: load pre-generated thumbnails if present."""
        path = self._thumb_path()
        if path is None or not path.exists():
            return
        pix = QPixmap(str(path))
        if not pix.isNull():
            self._set_thumbnail_pixmap(pix)
            self._thumb_loaded = True

    def render_and_cache_thumbnail(self) -> bool:
        """Render thumbnail pixmap for this map and save it for future runs."""
        if self._thumb_loaded:
            return True
        path = self._thumb_path()
        if path is None:
            return False
        map_id = self.map_data.get("id")
        if map_id in _THUMB_GENERATION_IN_PROGRESS:
            return False
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self._set_thumbnail_pixmap(pix)
                self._thumb_loaded = True
                return True

        _THUMB_GENERATION_IN_PROGRESS.add(map_id)
        try:
            if not render_map_thumbnail_png(self.map_data, path):
                return False
            pix = QPixmap(str(path))
            if pix.isNull():
                return False
            self._set_thumbnail_pixmap(pix)
            self._thumb_loaded = True
            return True
        finally:
            _THUMB_GENERATION_IN_PROGRESS.discard(map_id)

    def ensure_clues_built(self) -> None:
        """Build the clue UI once; keep it hidden/shown based on selection."""
        if self._clues_built:
            return

        inner = self._build_clues_container()
        self._clues_inner_container = inner
        layout = self._clues_container.layout()
        if layout is None:
            layout = QVBoxLayout(self._clues_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
        layout.addWidget(inner)

        root = self.window()
        if root is not None:
            for cb in getattr(self, "_clue_combos", []):
                if isinstance(cb, ComboBoxWithPopupAbove):
                    cb.set_root_window(root)
            for cb in getattr(self, "_cb_color", []):
                if isinstance(cb, ComboBoxWithPopupAbove):
                    cb.set_root_window(root)

        cb_changed = getattr(self, "_on_rule_changed", None)
        if self._deduction_mode and cb_changed and self._clue_combos:
            self._clue_combos[0].currentIndexChanged.connect(lambda *_: cb_changed())

        self._clues_built = True

    def _build_clues_container(self) -> QWidget:
        """Build container with 'Player's clues:' or deduction layout: Your clue + Player's settings."""
        container = QWidget()
        container.setObjectName("mapCardCluesContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(4)
        self._clue_combos: list[QComboBox] = []
        self._clue_stacks: list[QStackedWidget] = []
        self._clue_rows: list[QWidget] = []
        self._edt_player: list[QLineEdit] = []
        self._cb_color: list[QComboBox] = []
        ordinals = ("1st", "2nd", "3rd", "4th", "5th")
        if self._deduction_mode:
            your_row = QWidget()
            your_row_layout = QHBoxLayout(your_row)
            your_row_layout.setContentsMargins(0, 0, 0, 0)
            your_row_layout.setSpacing(8)
            your_lbl = QLabel("Your clue:")
            your_lbl.setObjectName("mapCardCluesTitle")
            your_row_layout.addWidget(your_lbl)
            cb = ComboBoxWithPopupAbove(your_row)
            cb.setObjectName("mapCardClueCombo")
            cb.setEnabled(True)
            cb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            add_clear_button_inside_combo(cb)
            your_row_layout.addWidget(cb, 1)
            layout.addWidget(your_row)
            self._clue_combos.append(cb)
            self._clue_stacks.append(None)
            self._clue_rows.append(None)
            settings_lbl = QLabel("Player's settings:")
            settings_lbl.setObjectName("mapCardCluesTitle")
            settings_lbl.setContentsMargins(0, 8, 0, 0)
            layout.addWidget(settings_lbl)
            for i in range(5):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                top_margin = 10 if i == 0 else 4
                row_layout.setContentsMargins(0, top_margin, 0, 4)
                row_layout.setSpacing(4)
                ord_lbl = QLabel(f"{ordinals[i]}:")
                ord_lbl.setObjectName("mapCardClueOrdinal")
                row_layout.addWidget(ord_lbl)
                edt = QLineEdit()
                edt.setObjectName("mapCardPlayerName")
                edt.setPlaceholderText("Player 1 (you)" if i == 0 else f"Player {i + 1}")
                edt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                row_layout.addWidget(edt)
                cb_color = ComboBoxWithPopupAbove(row)
                cb_color.setObjectName("mapCardColorCombo")
                setup_player_color_combo(cb_color)
                add_clear_button_inside_combo(cb_color)
                cb_color.currentIndexChanged.connect(self._on_color_combo_changed)
                row_layout.addWidget(cb_color)
                layout.addWidget(row)
                self._edt_player.append(edt)
                self._cb_color.append(cb_color)
                self._clue_rows.append(row)
            refresh_player_color_combos(self._cb_color)
            self._update_player_rows_visibility()
        else:
            lbl = QLabel("Player's clues:")
            lbl.setObjectName("mapCardCluesTitle")
            layout.addWidget(lbl)
            for i in range(5):
                row = QWidget()
                row_layout = QHBoxLayout(row)
                top_margin = 10 if i == 0 else 4
                row_layout.setContentsMargins(0, top_margin, 4, 4)
                row_layout.setSpacing(4)
                ord_lbl = QLabel(f"{ordinals[i]}:")
                ord_lbl.setObjectName("mapCardClueOrdinal")
                row_layout.addWidget(ord_lbl)
                stack = QStackedWidget()
                stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                cb = ComboBoxWithPopupAbove(row)
                cb.setObjectName("mapCardClueCombo")
                cb.setEnabled(False)
                cb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                stack.addWidget(cb)
                blur_frame = QFrame()
                blur_frame.setObjectName("mapCardClueBlurOverlay")
                blur_layout = QHBoxLayout(blur_frame)
                blur_layout.setContentsMargins(4, 4, 4, 4)
                blur_lbl = QLabel()
                blur_lbl.setObjectName("mapCardClueBlurLabel")
                blur_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                blur_pixmap = _create_blurred_text_pixmap(
                    self._blur_placeholder,
                    cb.font(),
                    QColor("#98a4ac"),
                    342,
                    22,
                )
                blur_lbl.setPixmap(blur_pixmap)
                blur_lbl.setScaledContents(False)
                blur_layout.addWidget(blur_lbl)
                stack.addWidget(blur_frame)
                self._clue_combos.append(cb)
                self._clue_stacks.append(stack)
                row_layout.addWidget(stack, 1)
                layout.addWidget(row)
                self._clue_rows.append(row)
        self._update_clue_dropdowns()
        return container

    def _update_player_rows_visibility(self) -> None:
        """Show 4th and 5th player rows only when applicable (deduction mode)."""
        if not self._deduction_mode or len(self._clue_rows) < 6:
            return
        for i in range(5):
            row = self._clue_rows[i + 1]
            if row is not None:
                row.setVisible(i < self._players)

    def _on_blur_toggled(self, checked: bool) -> None:
        """When blur ON: show blurred placeholder overlay. When OFF: show combo with clue."""
        if self._deduction_mode:
            return
        for i, stack in enumerate(self._clue_stacks):
            if i < len(self._clue_texts):
                cb = self._clue_combos[i]
                if cb.count() > 0:
                    cb.blockSignals(True)
                    cb.setItemText(0, self._blur_placeholder if checked else self._clue_texts[i])
                    cb.blockSignals(False)
                stack.setCurrentIndex(1 if checked else 0)

    def _update_clue_dropdowns(self) -> None:
        """Populate clue dropdowns from map data and player count, or from all_condition_labels in deduction mode."""
        if self._deduction_mode:
            advanced = bool(self.map_data.get("advancedMode", False))
            rule_labels = all_condition_labels(advanced_mode=advanced)
            self._clue_texts = [""]
            cb = self._clue_combos[0]
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("")
            cb.addItems(rule_labels)
            cb.setCurrentIndex(0)
            cb.setEnabled(True)
            cb.blockSignals(False)
            sync_clear_button_visibility(cb)
            self._update_player_rows_visibility()
            return
        clues = get_clues_for_map(self.map_data, self._players)
        self._clue_texts = list(clues)
        blur_on = getattr(self, "_cb_blur_clues", None)
        blur_on = blur_on.isChecked() if blur_on else True
        for i, cb in enumerate(self._clue_combos):
            visible = i < self._players
            if i < len(self._clue_rows):
                self._clue_rows[i].setVisible(visible)
            cb.blockSignals(True)
            cb.clear()
            if visible and i < len(clues):
                display = self._blur_placeholder if blur_on else clues[i]
                cb.addItem(display)
                cb.setCurrentIndex(0)
                self._clue_stacks[i].setCurrentIndex(1 if blur_on else 0)
            cb.setEnabled(False)
            cb.blockSignals(False)

    def _on_color_combo_changed(self) -> None:
        """When any color selection changes on the card, refresh all combos to hide taken colors."""
        refresh_player_color_combos(self._cb_color)

    def update_clues(self, players: int) -> None:
        """Refresh clue dropdowns when player count changes."""
        if players == self._players:
            return
        old_players = self._players
        self._players = players
        if not self._clues_built or not bool(self.property("selected")):
            return
        if self._deduction_mode:
            if players < old_players:
                for i in range(players, len(self._edt_player)):
                    edt = self._edt_player[i]
                    if edt is not None:
                        edt.clear()
                for i in range(players, len(self._cb_color)):
                    cb = self._cb_color[i]
                    if cb is not None:
                        cb.blockSignals(True)
                        cb.setCurrentIndex(0)
                        cb.blockSignals(False)
                        sync_clear_button_visibility(cb)
                refresh_player_color_combos(self._cb_color)
            self._update_player_rows_visibility()
            return
        self._update_clue_dropdowns()

    def get_selected_rule(self) -> str:
        """Return the selected rule text (for deduction mode). Empty if none selected."""
        if not self._deduction_mode or not self._clue_combos:
            return ""
        txt = (self._clue_combos[0].currentText() or "").strip()
        return txt if self._clue_combos[0].currentIndex() != 0 else ""

    def get_player_names(self) -> list[str]:
        """Return player names from the card (deduction mode). Empty list if not deduction."""
        if not self._deduction_mode or not getattr(self, "_edt_player", []):
            return []
        return [(edt.text() or "").strip() for edt in self._edt_player[: self._players]]

    def get_player_colors(self) -> list[str]:
        """Return selected player color names from the card (deduction mode). Empty list if not deduction."""
        if not self._deduction_mode or not getattr(self, "_cb_color", []):
            return []
        return [get_selected_player_color(cb) for cb in self._cb_color[: self._players]]

    def set_selected(self, selected: bool, *, keep_clues_visible: bool = False) -> None:
        """Set the selection state of the card (border/background in QSS)."""
        if self.property("selected") != selected:
            self.setProperty("selected", selected)
            self._update_selection_style()
        # Maps Library browse tab never shows the clues column; ignore selection chrome that
        # would expand it (avoids a second “panel” inside the card).
        if getattr(self, "_browse_only", False):
            self._clues_column.setVisible(False)
            self._clues_container.setVisible(False)
            self._blur_row.setVisible(False)
            return
        if selected:
            just_built = not self._clues_built
            self.ensure_clues_built()
            self._clues_column.setVisible(True)
            self._clues_container.setVisible(True)
            self._blur_row.setVisible((not self._deduction_mode) and True)
            if not just_built:
                if self._deduction_mode:
                    self._update_player_rows_visibility()
                else:
                    self._update_clue_dropdowns()
        else:
            if keep_clues_visible:
                return
            self._clues_column.setVisible(False)
            self._clues_container.setVisible(False)
            self._blur_row.setVisible(False)
            if not self._deduction_mode and hasattr(self, "_cb_blur_clues") and self._cb_blur_clues is not None:
                self._cb_blur_clues.blockSignals(True)
                self._cb_blur_clues.setChecked(True)
                self._cb_blur_clues.blockSignals(False)
                self._on_blur_toggled(True)

    def _update_selection_style(self) -> None:
        """Update the visual style based on selection state."""
        self.style().unpolish(self)
        self.style().polish(self)

    def apply_highlights(self, highlighted_cells: set[tuple[int, int, int]]) -> None:
        """Set highlighted hexes on the map preview. Each tuple is (slot_row, slot_col, cell_idx)."""
        self.ensure_full_preview()
        if self._full_preview is not None:
            self._full_preview.apply_highlights(highlighted_cells)

    def clear_preview_highlights(self) -> None:
        """Clear highlights from the map preview."""
        if self._full_preview is not None:
            self._full_preview.clear_highlights()
            self._preview_stack.setCurrentIndex(0)

    def clear_deduction_controls(self) -> None:
        """Clear Your clue dropdown, player name lineedits, and color dropdowns (deduction mode only)."""
        if not self._deduction_mode:
            return
        if self._clue_combos:
            cb = self._clue_combos[0]
            cb.blockSignals(True)
            cb.setCurrentIndex(0)
            cb.blockSignals(False)
            sync_clear_button_visibility(cb)
        for edt in getattr(self, "_edt_player", []):
            if edt is not None:
                edt.clear()
        for cb in getattr(self, "_cb_color", []):
            if cb is not None:
                cb.blockSignals(True)
                cb.setCurrentIndex(0)
                cb.blockSignals(False)
                sync_clear_button_visibility(cb)
        refresh_player_color_combos(getattr(self, "_cb_color", []))

    def set_interactive(self, interactive: bool) -> None:
        """When False: clicks, hover styles, and pointing-hand cursor are disabled."""
        if self.property("interactive") != interactive:
            self.setProperty("interactive", interactive)
            self.setCursor(Qt.CursorShape.ArrowCursor if not interactive else Qt.CursorShape.PointingHandCursor)
            self._update_selection_style()

    def mousePressEvent(self, event):
        """Emit clicked signal when the card is clicked (not when clicking blur toggle or form controls)."""
        if getattr(self, "_browse_only", False):
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton and self.property("interactive") is not False:
            target = self.childAt(event.pos())
            if target is None:
                self.clicked.emit(self.map_data)
            elif (
                not self._is_blur_toggle_or_child(target)
                and not self._is_form_control_or_child(target)
                and not self._is_custom_map_action_or_child(target)
            ):
                self.clicked.emit(self.map_data)
        super().mousePressEvent(event)

    def _is_blur_toggle_or_child(self, w: QWidget) -> bool:
        """Return True if widget is the blur toggle row or its descendant."""
        while w and w is not self:
            if w == self._blur_row:
                return True
            w = w.parentWidget()
        return False

    def _is_form_control_or_child(self, w: QWidget) -> bool:
        """Deduction mode: True only for real inputs (combo, line edit), not labels/panel chrome."""
        if not self._deduction_mode:
            return False
        while w and w is not self:
            if isinstance(w, (QComboBox, QLineEdit)):
                return True
            w = w.parentWidget()
        return False

    def _is_custom_map_action_or_child(self, w: QWidget) -> bool:
        while w and w is not self:
            if (
                w is self._btn_custom_map_name_pen
                or w is self._btn_custom_edit
                or w is self._btn_custom_delete
            ):
                return True
            w = w.parentWidget()
        return False

    def wheelEvent(self, event):
        """Block wheel events to prevent map movement when hovering over map card."""
        event.ignore()

    def sizeHint(self):
        return self.minimumSizeHint()
