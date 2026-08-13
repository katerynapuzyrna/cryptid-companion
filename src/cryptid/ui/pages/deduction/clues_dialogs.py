"""Clue icon grid, calculating overlay, clues table (Deduction build UI)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QWheelEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHeaderView,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
)

from logic.clue_grid import get_clue_label_for_slot
from settings.config import ICON_CLUE, CLUES_ICONS_DIR, ICON_HELP
from settings.strings import CALCULATING
from ui.shared.widgets import (
    get_selected_player_color,
    DotsLoadingWidget,
)
from ui.shared.widgets.player_colors import get_player_meeple_pixmap


class DeductionCluesDialogsMixin:

    def _load_clue_icons_by_number(self) -> dict[int, QPixmap]:
        """Load icons from CLUES_ICONS_DIR. Filename number = which slot (1..48) to replace."""
        result: dict[int, QPixmap] = {}
        if not CLUES_ICONS_DIR.is_dir():
            return result
        for f in CLUES_ICONS_DIR.iterdir():
            if f.suffix.lower() not in (".svg", ".png"):
                continue
            stem = f.stem
            if "_" in stem:
                try:
                    n = int(stem.split("_", 1)[0])
                except ValueError:
                    continue
            else:
                continue
            pix = QPixmap(str(f))
            if not pix.isNull():
                result[n] = pix.scaled(
                    48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
        return result

    def _ensure_clue_icon(self) -> None:
        """Create clue icon grid (4 cols × 12 rows, 48 icons) and proxy once, hidden by default.
        Each cell: clue icon + player meeple icons (1st to last) to the right. Each proxy gets its own tooltip."""
        if getattr(self, "_clue_icon_proxies", None):
            return
        if not hasattr(self, "scene") or self.scene is None:
            return
        clues_by_num = self._load_clue_icons_by_number()
        default_pix = QPixmap()
        if ICON_CLUE.exists():
            default_pix = QPixmap(str(ICON_CLUE))
        if not default_pix.isNull():
            default_pix = default_pix.scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        players = self.rules.parse_players((getattr(self, "cbBuildPlayers", None) and self.cbBuildPlayers.currentText() or "").strip()) or 3
        # Exactly one meeple icon per player (e.g. 4 players => 4 icons, no more)
        color_names: list[str] = []
        cb_list = getattr(self, "cbColorP", [])
        for i in range(players):
            if i < len(cb_list) and cb_list[i] is not None:
                color_names.append(get_selected_player_color(cb_list[i]) or "")
            else:
                color_names.append("")
        color_names = color_names[:players]
        player_icon_size = 16
        cell_spacing = 4
        cell_width = 48 + cell_spacing + players * (player_icon_size + cell_spacing) + 4
        cell_height = 48
        h_spacing = 0
        v_spacing = 2
        proxies: list = []
        color_labels_per_cell: list[list] = []
        advanced_flags: list[bool] = []
        for i in range(48):
            slot_num = i + 1
            pix = clues_by_num.get(slot_num, default_pix)
            cell = QWidget()
            cell.setObjectName("clueIconCell")
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 4, 0)
            cell_layout.setSpacing(cell_spacing)
            icon_lbl = QLabel()
            icon_lbl.setObjectName("clueIcon")
            icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            icon_lbl.setFixedSize(48, 48)
            if not pix.isNull():
                icon_lbl.setPixmap(pix)
            cell_layout.addWidget(icon_lbl)
            cell_color_labels: list = []
            for color_name in color_names:
                color_lbl = QLabel()
                color_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                color_lbl.setFixedSize(player_icon_size, player_icon_size)
                if color_name:
                    color_pix = get_player_meeple_pixmap(color_name, player_icon_size)
                    if not color_pix.isNull():
                        color_lbl.setPixmap(color_pix)
                cell_layout.addWidget(color_lbl)
                cell_color_labels.append(color_lbl)
            color_labels_per_cell.append(cell_color_labels)
            proxy = self.scene.addWidget(cell)
            # Use HoverTooltipManager for rounded corners; target icon_lbl only (not color icons)
            tip_text = get_clue_label_for_slot(slot_num)
            # Advanced-only icons: all negative ("Not ...") and any rule mentioning black structures.
            is_advanced_only = tip_text.startswith("Not ") or " black " in tip_text
            advanced_flags.append(is_advanced_only)
            self._app_tooltip.add(
                icon_lbl, tip_text,
                only_when_disabled=False,
                only_when=lambda: (
                    bool(getattr(self, "_clue_icon_proxies", None) and len(self._clue_icon_proxies) > 0 and self._clue_icon_proxies[0].isVisible())
                    and getattr(self, "pages_stack", None) is not None
                    and self.pages_stack.currentWidget() == self._page
                ),
            )
            proxy.setZValue(100)
            row, col = divmod(i, 4)
            proxy.setPos(col * (cell_width + h_spacing), row * (cell_height + v_spacing))
            proxy.setVisible(False)
            proxies.append(proxy)
        self._clue_icon_proxies = proxies
        self._clue_icon_color_labels = color_labels_per_cell
        self._clue_icon_player_colors = color_names
        self._clue_icon_player_size = player_icon_size
        self._clue_icon_advanced_only = advanced_flags
        self._clue_icon_base_pos = (cell_width, cell_height, h_spacing, v_spacing)

    def _update_clue_icon_color_states(self) -> None:
        """Valid clues: meeple. Invalid clues: transparent. Player 1: fixed rule only."""
        labels = getattr(self, "_clue_icon_color_labels", [])
        clues_per_player = getattr(self, "_clues_per_player", [])
        first_rule = (getattr(self, "_first_player_rule", None) or "").strip()
        color_names = getattr(self, "_clue_icon_player_colors", [])
        size = getattr(self, "_clue_icon_player_size", 16)
        empty_pix = QPixmap(size, size)
        empty_pix.fill(Qt.GlobalColor.transparent)
        for i, cell_labels in enumerate(labels):
            slot_num = i + 1
            clue_label = get_clue_label_for_slot(slot_num)
            for p, color_lbl in enumerate(cell_labels):
                if p == 0:
                    active = (clue_label == first_rule)
                    if active:
                        color_name = color_names[p] if p < len(color_names) else ""
                        if color_name:
                            pix = get_player_meeple_pixmap(color_name, size)
                            color_lbl.setPixmap(pix if not pix.isNull() else empty_pix)
                        else:
                            color_lbl.setPixmap(empty_pix)
                    else:
                        color_lbl.setPixmap(empty_pix)
                else:
                    valid = (
                        p < len(clues_per_player)
                        and clue_label in clues_per_player[p]
                    )
                    if valid:
                        color_name = color_names[p] if p < len(color_names) else ""
                        if color_name:
                            pix = get_player_meeple_pixmap(color_name, size)
                            color_lbl.setPixmap(pix if not pix.isNull() else empty_pix)
                        else:
                            color_lbl.setPixmap(empty_pix)
                    else:
                        color_lbl.setPixmap(empty_pix)

    def _show_clue_icon(self) -> None:
        """Position clue icon grid to the right of the canvas and show it."""
        self._ensure_clue_icon()
        self._update_clue_icon_color_states()
        proxies = getattr(self, "_clue_icon_proxies", [])
        if not proxies:
            return
        advanced_flags = getattr(self, "_clue_icon_advanced_only", [False] * len(proxies))
        base_x, base_y = 0.0, 0.0
        canvas = getattr(self, "board_builder", None).canvas if hasattr(self, "board_builder") and self.board_builder is not None else getattr(self, "canvas", None)
        if canvas is not None and hasattr(canvas, "rect"):
            rect = canvas.rect
            base_x = rect.right() + 8
            base_y = rect.top()
        cw, ch, hs, vs = getattr(self, "_clue_icon_base_pos", (132, 48, 0, 2))
        for i, proxy in enumerate(proxies):
            row, col = divmod(i, 4)
            proxy.setPos(base_x + col * (cw + hs), base_y + row * (ch + vs))
            is_advanced_only = advanced_flags[i] if i < len(advanced_flags) else False
            if not getattr(self, "advanced_mode", False) and is_advanced_only:
                proxy.setVisible(False)
            else:
                proxy.setVisible(True)

    def _hide_clue_icon(self) -> None:
        """Hide clue icon grid and invalidate cache so next Start Simulation rebuilds with current players/colors."""
        proxies = getattr(self, "_clue_icon_proxies", [])
        if proxies and hasattr(self, "scene") and self.scene is not None:
            for proxy in proxies:
                self.scene.removeItem(proxy)
                proxy.deleteLater()
        self._clue_icon_proxies = []
        self._clue_icon_color_labels = []
        self._clue_icon_player_colors = []
        self._clue_icon_advanced_only = []

    def _make_calculating_overlay(self) -> QFrame:
        """Create overlay with 'Calculating...' and indeterminate progress, stacked over the map source area."""
        target = getattr(self, "mapSourceStack", None) or self.buildScroll
        overlay = QFrame(target)
        overlay.setObjectName("calculatingOverlay")
        overlay.setStyleSheet(
            "QFrame#calculatingOverlay { background-color: rgba(249, 251, 252, 0.9); "
            "border-radius: 8px; }"
        )
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(CALCULATING)
        lbl.setStyleSheet("font-size: 14px; color: #182022;")
        layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)
        dots = DotsLoadingWidget()
        layout.addWidget(dots, 0, Qt.AlignmentFlag.AlignHCenter)
        overlay.setVisible(False)

        scroll = target

        def _update_geometry() -> None:
            overlay.setGeometry(scroll.rect())

        class _ResizeFilter(QObject):
            def __init__(self, target):
                super().__init__(target)
                self._target = target

            def eventFilter(self, obj, event):
                if obj is self._target and event.type() == QEvent.Type.Resize:
                    _update_geometry()
                return False

        def _on_show(event):
            _update_geometry()
            QFrame.showEvent(overlay, event)

        overlay.showEvent = _on_show
        scroll.installEventFilter(_ResizeFilter(scroll))
        return overlay

    def _make_valid_clues_section(self) -> QWidget:
        """Create section showing distinct valid clues per player, below buildSettings.
        Layout: 1 player's rules per column (horizontal). Each column uses QLabels with word wrap.
        Wheel events are blocked on the section so the parent scroll doesn't steal them."""
        section = QWidget()
        section.setObjectName("validCluesSection")
        section.setVisible(False)
        layout = QHBoxLayout(section)
        layout.setSpacing(8)
        placeholders = ["Player 2", "Player 3", "Player 4", "Player 5"]
        valid_clues_containers: list[QWidget] = []  # QWidget with VBoxLayout of QLabels
        valid_clues_cols: list[QWidget] = []
        valid_clues_headers: list[QLabel] = []
        valid_clues_icon_labels: list[QLabel] = []
        for i in range(4):
            col = QWidget()
            col.setObjectName("validCluesCol")
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(2)
            header_row = QWidget()
            header_layout = QHBoxLayout(header_row)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(6)
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(14, 14)
            icon_lbl.setScaledContents(True)
            header_layout.addWidget(icon_lbl)
            lbl = QLabel(f"{placeholders[i]} - Valid clues:")
            lbl.setObjectName("validCluesHeader")
            header_layout.addWidget(lbl)
            valid_clues_icon_labels.append(icon_lbl)
            valid_clues_headers.append(lbl)
            col_layout.addWidget(header_row)
            clues_container = QWidget()
            clues_container.setObjectName("validCluesBody")
            clues_layout = QVBoxLayout(clues_container)
            clues_layout.setContentsMargins(0, 0, 0, 0)
            clues_layout.setSpacing(0)
            col_layout.addWidget(clues_container)
            valid_clues_containers.append(clues_container)
            valid_clues_cols.append(col)
            layout.addWidget(col, 1, Qt.AlignmentFlag.AlignTop)
        # Forward wheel events from section to buildScroll by scrolling the scroll bar directly
        build_scroll = self.buildScroll

        class _WheelForwarder(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Wheel and isinstance(event, QWheelEvent):
                    vbar = build_scroll.verticalScrollBar()
                    if vbar is not None:
                        delta = event.angleDelta().y()
                        step = max(vbar.singleStep(), 1) * 3
                        vbar.setValue(vbar.value() - int(delta / 120) * step)
                    return True
                return False

        forwarder = _WheelForwarder(section)
        section.installEventFilter(forwarder)
        for c in section.findChildren(QWidget):
            c.installEventFilter(forwarder)
        build_content = self.buildScroll.widget()
        content_layout = build_content.layout() if build_content else None
        if content_layout is not None:
            content_layout.addWidget(section, 0, Qt.AlignmentFlag.AlignTop)
            content_layout.addStretch()  # absorb extra space so section doesn't stretch
        self._valid_clues_containers = valid_clues_containers
        self._valid_clues_cols = valid_clues_cols
        self._valid_clues_headers = valid_clues_headers
        self._valid_clues_icon_labels = valid_clues_icon_labels
        return section

    def _make_clues_table_section(self) -> QWidget:
        """Table: rows=all clues, cols=Clue | Player 1 | Player 2 | ..., cells=Yes/No."""
        section = QWidget()
        section.setObjectName("cluesTableSection")
        section.setVisible(False)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        self._clues_table = QTableWidget()
        self._clues_table.setObjectName("cluesTable")
        self._clues_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._clues_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._clues_table)
        build_content = self.buildScroll.widget()
        content_layout = build_content.layout() if build_content else None
        if content_layout is not None:
            content_layout.addWidget(section, 0, Qt.AlignmentFlag.AlignTop)
            content_layout.addStretch()
        return section

    def _show_calculating_overlay(self) -> None:
        """Show overlay over buildScroll and dim buildScroll."""
        self._calculating_overlay.setGeometry(self.buildScroll.rect())
        self._calculating_overlay.raise_()
        self._calculating_overlay.setVisible(True)
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(0.5)
        self.buildScroll.setGraphicsEffect(effect)
        QApplication.processEvents()

    def _hide_calculating_overlay(self) -> None:
        """Hide overlay and restore buildScroll opacity."""
        self._calculating_overlay.setVisible(False)

