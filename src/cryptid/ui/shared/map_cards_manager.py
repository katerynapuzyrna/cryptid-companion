"""Manager for map selection cards: load, filter by advanced mode, selection."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QCheckBox, QComboBox, QPushButton, QLineEdit, QLabel, QScrollArea
from PySide6.QtCore import Qt, QTimer, QObject, QEvent, Signal

from settings.config import CUSTOM_MAPS_JSON, DATA_DIR, MAPS_JSON
from settings.strings import (
    TOOLTIP_MAPS_LIB_DELETE_CUSTOM,
    TOOLTIP_MAPS_LIB_EDIT_CUSTOM,
    TOOLTIP_MAPS_LIB_EDIT_MAP_NAME,
)
from ui.shared.map_card import MapCard, _get_preview_canvas_size
from ui.shared.widgets import HoverTooltipManager

# Horizontal footprint for column math: preview canvas width + fixed chrome (see MapCard layout).
_MAP_CARD_WIDTH_BEYOND_PREVIEW = 20

# Extra floor for switching to 3 columns (in addition to fitting 3× reference card width).
# Set to 0 to use only the intrinsic width rule. Default > 0 keeps 2 columns on a typical
# default window even when intrinsic math would allow 3.
_MIN_VIEWPORT_WIDTH_FOR_THREE_COLUMNS = 1260


def _custom_map_soft_deleted_value(data: dict) -> int:
    """0 = visible in Maps Library Custom tab; non-zero = hidden."""
    v = data.get("soft_deleted", 0)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _parse_players(cb: QComboBox) -> int:
    t = (cb.currentText() or "").strip()
    return int(t) if t in ("3", "4", "5") else 3


class MapCardsManager(QObject):
    """Coordinates map cards: loading, filtering by advanced mode, selection."""

    custom_map_edit_requested = Signal(dict)
    custom_map_delete_requested = Signal(dict)
    custom_map_rename_map_name_requested = Signal(dict)
    map_selection_changed = Signal()

    def __init__(
        self,
        container: QWidget,
        cb_select_advanced_mode: QCheckBox,
        cb_select_players: QComboBox,
        btn_solve: QPushButton,
        btn_map_select: QPushButton,
        edt_search: QLineEdit | None = None,
        lbl_no_cards: QLabel | None = None,
        deduction_mode: bool = False,
        browse_only: bool = False,
        maps_json_path: Path | None = None,
        hover_tooltip: HoverTooltipManager | None = None,
    ):
        super().__init__(container)
        self._container = container
        self._hover_tooltip = hover_tooltip
        self._cb_select_advanced_mode = cb_select_advanced_mode
        self._cb_select_players = cb_select_players
        self._deduction_mode = deduction_mode
        self._browse_only = browse_only
        self._maps_json_path = maps_json_path
        self._edt_search = edt_search
        self._lbl_no_cards = lbl_no_cards
        self._btn_solve = btn_solve
        self._btn_map_select = btn_map_select
        self._map_cards: list[tuple[MapCard, dict]] = []
        self._selected_map_card: Optional[MapCard] = None
        # Display order for visible cards (permuted by last-in-row select/deselect swaps).
        self._visible_card_order: list[MapCard] = []
        # True if current selection was last-in-row (all-span-1) when the user selected it.
        self._selected_was_last_in_row_at_select: bool = False
        # Last grid column count while no card was selected (for sticky 3-col after select).
        self._last_unselected_columns: int = 2
        self._scroll_area: QScrollArea | None = None
        self._scroll_viewport: QWidget | None = None
        self._container.installEventFilter(self)
        # Container resize alone can miss QScrollArea viewport width updates; observe both.
        p: QWidget | None = self._container.parentWidget()
        while p is not None:
            if isinstance(p, QScrollArea):
                self._scroll_area = p
                self._scroll_viewport = p.viewport()
                p.installEventFilter(self)
                self._scroll_viewport.installEventFilter(self)
                break
            p = p.parentWidget()

    def _is_custom_maps_json_source(self) -> bool:
        return (
            self._maps_json_path is not None
            and self._maps_json_path.resolve() == CUSTOM_MAPS_JSON.resolve()
        )

    def _scroll_map_list_to_top(self) -> None:
        """Scroll the map list to the top (after filter/relayout when content height changes)."""
        if self._scroll_area is None:
            return
        sa = self._scroll_area

        def _go() -> None:
            sa.verticalScrollBar().setValue(0)

        # Defer so Qt can finish updating scroll range from the new layout.
        QTimer.singleShot(0, _go)
        QTimer.singleShot(30, _go)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Reflow cards when the list container or scroll viewport width changes."""
        if event.type() == QEvent.Type.Resize:
            if watched is self._container:
                self._relayout_cards()
            elif self._scroll_area is not None and (
                watched is self._scroll_area or watched is self._scroll_viewport
            ):
                self._relayout_cards()
        return super().eventFilter(watched, event)

    def _grid_layout(self) -> QGridLayout:
        """Return cards layout as QGridLayout (create if missing)."""
        layout = self._container.layout()
        if layout is None:
            layout = QGridLayout(self._container)
        if not isinstance(layout, QGridLayout):
            raise TypeError("map cards container layout must be QGridLayout")
        return layout

    def _reference_card_width(self) -> int:
        """Static width for 2-vs-3 column math: map preview width + fixed padding.

        Does not use per-card sizeHint (clues inflate that). Preview size matches MapCard thumbnails.
        """
        map_w, _ = _get_preview_canvas_size()
        return int(map_w) + _MAP_CARD_WIDTH_BEYOND_PREVIEW

    @staticmethod
    def _grid_horizontal_spacing(layout: QGridLayout) -> int:
        s = layout.horizontalSpacing()
        if s < 0:
            s = layout.spacing()
        return max(0, s)

    def _available_width_for_columns(self) -> int:
        """Scroll viewport width when inside QScrollArea; else container width."""
        p: QWidget | None = self._container
        while p is not None:
            if isinstance(p, QScrollArea):
                return max(0, p.viewport().width())
            p = p.parentWidget()
        return max(0, self._container.width())

    def _raw_column_count_for_width(self) -> int:
        """2 vs 3 columns from viewport only (no selection / sticky). For last-in-row sim."""
        layout = self._grid_layout()
        spacing = self._grid_horizontal_spacing(layout)
        card_w = self._reference_card_width()
        available = self._available_width_for_columns()
        intrinsic_three = card_w * 3 + spacing * 2
        threshold_for_3 = max(intrinsic_three, _MIN_VIEWPORT_WIDTH_FOR_THREE_COLUMNS)
        return 3 if available >= threshold_for_3 else 2

    @staticmethod
    def _last_in_row_indices_all_span_one(order: list[MapCard], columns: int) -> set[int]:
        """Indices of cards that complete a row if every card uses span 1."""
        col = 0
        last: set[int] = set()
        for i in range(len(order)):
            span = 1
            if col + span > columns:
                col = 0
            col += span
            if col >= columns:
                last.add(i)
                col = 0
        return last

    def _rebuild_visible_card_order_from_maps(self) -> None:
        """Natural order: maps.json order, visible cards only."""
        self._visible_card_order = [c for c, _ in self._map_cards if c.isVisible()]

    def _sync_visible_order_if_needed(self) -> None:
        visible = [c for c, _ in self._map_cards if c.isVisible()]
        vis_set = set(visible)
        ordered_vis = [c for c in self._visible_card_order if c in vis_set]
        if len(ordered_vis) != len(visible) or set(ordered_vis) != vis_set:
            self._visible_card_order = visible

    def _maybe_swap_with_prev_if_last_in_row_on_select(self, card: MapCard) -> bool:
        """If `card` is last in an all-span-1 row, swap with previous. Returns True if it was last."""
        if card not in self._visible_card_order:
            return False
        columns = self._raw_column_count_for_width()
        o = self._visible_card_order
        idx = o.index(card)
        last_i = self._last_in_row_indices_all_span_one(o, columns)
        was_last = idx in last_i
        if was_last and idx > 0:
            o[idx - 1], o[idx] = o[idx], o[idx - 1]
        return was_last

    def _maybe_swap_with_next_if_was_last_at_select(self, card: MapCard) -> None:
        """If this card was last-in-row when selected, swap with next. Call before deselecting."""
        if not self._selected_was_last_in_row_at_select:
            return
        if card not in self._visible_card_order:
            return
        o = self._visible_card_order
        idx = o.index(card)
        if idx < len(o) - 1:
            o[idx], o[idx + 1] = o[idx + 1], o[idx]

    def _column_count_for_width(self) -> int:
        """2 columns when narrow; 3 when the scroll viewport fits three reference cards.

        Reference width = preview canvas width + _MAP_CARD_WIDTH_BEYOND_PREVIEW (20px).
        _MIN_VIEWPORT_WIDTH_FOR_THREE_COLUMNS can still raise the threshold when > 0.
        """
        raw = self._raw_column_count_for_width()

        selected = (
            self._selected_map_card is not None
            and bool(self._selected_map_card.property("selected"))
        )
        if not selected:
            self._last_unselected_columns = raw
            return raw

        # Selection / vertical scrollbar can shave a few px; tolerate that without dropping to 2.
        layout = self._grid_layout()
        spacing = self._grid_horizontal_spacing(layout)
        card_w = self._reference_card_width()
        available = self._available_width_for_columns()
        intrinsic_three = card_w * 3 + spacing * 2
        threshold_for_3 = max(intrinsic_three, _MIN_VIEWPORT_WIDTH_FOR_THREE_COLUMNS)
        scrollbar_slack = 40
        avail_relaxed = available + scrollbar_slack
        if self._last_unselected_columns == 3:
            hold_slack = 120  # px: stay at 3 unless viewport shrinks this much further
            if avail_relaxed >= threshold_for_3 - hold_slack:
                return 3
        return raw

    def _relayout_cards(self) -> None:
        """
        Rebuild grid:
        - default 2 cards per row; 3 per row when width allows
        - selected card spans 2 columns (when grid has ≥2 cols) so the clues panel has
          width without stretching every column; remaining slots fill with span-1 cards
        """
        layout = self._grid_layout()

        # Detach all managed card widgets from grid positions (keep widgets alive).
        for card, _ in self._map_cards:
            layout.removeWidget(card)

        self._sync_visible_order_if_needed()
        visible_cards = [c for c in self._visible_card_order if c.isVisible()]
        visible_set = frozenset(visible_cards)

        # Detached widgets keep their last geometry until re-added; send filtered/hidden cards
        # to the back and hide so they cannot paint on top of the active grid.
        for card, _ in self._map_cards:
            if card not in visible_set:
                card.hide()
                card.lower()

        if not visible_cards:
            return

        columns = self._column_count_for_width()

        # Normalize stretches for the active column count.
        for c in range(6):
            layout.setColumnStretch(c, 1 if c < columns else 0)

        row = 0
        col = 0
        for card in visible_cards:
            selected_here = (
                card is self._selected_map_card and bool(card.property("selected"))
            )
            if selected_here and columns >= 2:
                span = min(2, columns)
            else:
                span = 1
            if col + span > columns:
                row += 1
                col = 0
            layout.addWidget(card, row, col, 1, span, Qt.AlignmentFlag.AlignTop)
            col += span
            if col >= columns:
                row += 1
                col = 0

        for card in visible_cards:
            card.show()
            card.raise_()

    def load_maps(self) -> list:
        """Load maps from maps.json (or ``maps_json_path`` when set). Returns list of map dicts."""
        path = self._maps_json_path or MAPS_JSON
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("maps") or []
        except Exception:
            return []

    def set_maps_json_path(self, path: Path) -> None:
        """Point at another JSON file (same schema as maps.json) and rebuild cards."""
        self._maps_json_path = path
        self.setup()

    def setup(self) -> None:
        """Create cards from loaded maps, add to layout, connect signals, apply filter."""
        # Invalidate any in-flight thumbnail timer from a previous setup() (e.g. after saving
        # a custom map we call setup() again; without this, thumbnails never queue for new cards).
        self._maps_epoch = getattr(self, "_maps_epoch", 0) + 1
        epoch = self._maps_epoch

        if self._hover_tooltip is not None:
            for card, _ in list(self._map_cards):
                ed = getattr(card, "_btn_custom_edit", None)
                dd = getattr(card, "_btn_custom_delete", None)
                pen = getattr(card, "_btn_custom_map_name_pen", None)
                if ed is not None:
                    self._hover_tooltip.remove_target(ed)
                if dd is not None:
                    self._hover_tooltip.remove_target(dd)
                if pen is not None:
                    self._hover_tooltip.remove_target(pen)

        maps_data = self.load_maps()
        layout = self._container.layout()
        if layout is None:
            layout = QGridLayout(self._container)
        else:
            # Clear existing layout (widget already has one from .ui)
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w is not None:
                    # deleteLater() is deferred; without hide + reparent, stale cards can
                    # still paint as siblings of the container until the event loop runs.
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
            # Paranoia: cards removed from the layout (e.g. relayout/filter edge cases) are no
            # longer in layout.count() but can still be direct children and paint at (0,0).
            for ch in list(self._container.children()):
                if isinstance(ch, MapCard):
                    ch.hide()
                    ch.setParent(None)
                    ch.deleteLater()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._map_cards.clear()
        self._selected_map_card = None
        self._visible_card_order.clear()
        self._selected_was_last_in_row_at_select = False
        self._last_unselected_columns = 2
        players = _parse_players(self._cb_select_players)

        show_custom_actions = self._browse_only and self._is_custom_maps_json_source()
        for i, map_item in enumerate(maps_data):
            card = MapCard(
                map_item,
                players=players,
                deduction_mode=self._deduction_mode,
                on_rule_changed=self._update_solve_for_select_mode,
                browse_only=self._browse_only,
                custom_map_actions=show_custom_actions,
            )
            if isinstance(layout, QGridLayout):
                layout.addWidget(card, i, 0, 1, 1, Qt.AlignmentFlag.AlignTop)
            else:
                layout.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
            self._map_cards.append((card, map_item))
            if not self._browse_only:
                card.clicked.connect(self._on_card_clicked)
            if show_custom_actions:
                card.custom_edit_clicked.connect(self.custom_map_edit_requested.emit)
                card.custom_delete_clicked.connect(self.custom_map_delete_requested.emit)
                card.custom_rename_map_name_clicked.connect(
                    self.custom_map_rename_map_name_requested.emit
                )
                if self._hover_tooltip is not None:
                    if card._btn_custom_map_name_pen is not None:
                        self._hover_tooltip.add(
                            card._btn_custom_map_name_pen,
                            TOOLTIP_MAPS_LIB_EDIT_MAP_NAME,
                            only_when_disabled=False,
                        )
                    if card._btn_custom_edit is not None:
                        self._hover_tooltip.add(
                            card._btn_custom_edit,
                            TOOLTIP_MAPS_LIB_EDIT_CUSTOM,
                            only_when_disabled=False,
                        )
                    if card._btn_custom_delete is not None:
                        self._hover_tooltip.add(
                            card._btn_custom_delete,
                            TOOLTIP_MAPS_LIB_DELETE_CUSTOM,
                            only_when_disabled=False,
                        )

        if not getattr(self, "_map_cards_signals_wired", False):
            self._cb_select_advanced_mode.toggled.connect(self._on_advanced_mode_toggled)
            self._cb_select_players.currentTextChanged.connect(self._on_players_changed)
            if self._edt_search:
                self._edt_search.textChanged.connect(self._on_search_changed)
            self._map_cards_signals_wired = True
        self.filter_map_cards()
        self._start_thumbnail_generation(epoch)

    def _start_thumbnail_generation(self, epoch: int) -> None:
        """Render missing thumbnails gradually so the UI window appears quickly."""
        self._thumb_queue = [
            card for card, _ in self._map_cards
            if not getattr(card, "_thumb_loaded", False)
        ]
        self._thumb_attempts: dict[int, int] = {}

        def tick() -> None:
            if epoch != getattr(self, "_maps_epoch", 0):
                return
            if not self._thumb_queue:
                return
            card = self._thumb_queue.pop(0)
            map_id = card.map_data.get("id")
            try:
                card.render_and_cache_thumbnail()
            except Exception:
                # Thumbnails are best-effort; never break the UI.
                pass

            if not getattr(card, "_thumb_loaded", False):
                # If thumbnail generation was blocked by another page/card, retry later.
                if map_id is not None:
                    self._thumb_attempts[map_id] = self._thumb_attempts.get(map_id, 0) + 1
                    if self._thumb_attempts[map_id] < 10:
                        self._thumb_queue.append(card)
            QTimer.singleShot(10, tick)

        QTimer.singleShot(0, tick)

    def filter_map_cards(self) -> None:
        """Show/hide cards based on advanced mode and search (3+ chars)."""
        advanced = self._cb_select_advanced_mode.isChecked()
        search = (self._edt_search.text() or "").strip().lower() if self._edt_search else ""
        use_search = len(search) >= 3

        is_custom_file = self._is_custom_maps_json_source()

        visible_count = 0
        for card, data in self._map_cards:
            am = bool(data.get("advancedMode", False))
            adv_match = (advanced and am) or (not advanced and not am)
            name = (data.get("name") or "").lower()
            search_match = not use_search or search in name
            custom_ok = (not is_custom_file) or (_custom_map_soft_deleted_value(data) == 0)
            visible = adv_match and search_match and custom_ok
            card.setVisible(visible)
            if visible:
                visible_count += 1

        if self._lbl_no_cards is not None:
            self._lbl_no_cards.setVisible(visible_count == 0)

        self._rebuild_visible_card_order_from_maps()
        self._selected_was_last_in_row_at_select = False
        self._relayout_cards()
        self._update_solve_for_select_mode()
        self._scroll_map_list_to_top()

    def _update_solve_for_select_mode(self) -> None:
        """Enable Solve only if in select mode, a map is selected, and it is visible (not filtered).
        In deduction mode, also require that the selected card has a rule selected."""
        if self._browse_only:
            return
        if not self._btn_map_select.isChecked():
            return
        if self._selected_map_card is None:
            self._btn_solve.setEnabled(False)
            return
        if self._deduction_mode:
            rule_ok = bool(self._selected_map_card.get_selected_rule())
            self._btn_solve.setEnabled(self._selected_map_card.isVisible() and rule_ok)
        else:
            self._btn_solve.setEnabled(self._selected_map_card.isVisible())

    def _on_advanced_mode_toggled(self, _: bool) -> None:
        self.filter_map_cards()

    def _on_search_changed(self, _: str) -> None:
        self.filter_map_cards()

    def _on_players_changed(self, _: str) -> None:
        """Refresh clue dropdowns / player rows on all cards when player count changes."""
        players = _parse_players(self._cb_select_players)
        for card, _ in self._map_cards:
            card.update_clues(players)
        self._relayout_cards()

    def _on_card_clicked(self, map_data: dict) -> None:
        """Handle map card click: update selection, enable Solve in select mode."""
        clicked_card: Optional[MapCard] = None
        for card, data in self._map_cards:
            if data == map_data:
                clicked_card = card
                break
        if clicked_card is None:
            return

        # Toggle behavior:
        # - click selected card -> deselect
        # - click other card -> select clicked, deselect previous
        # Last-in-row: on select swap with previous; on deselect swap with next only if last-at-select.
        if self._selected_map_card is clicked_card:
            self._deselect_current_card()
            self._relayout_cards()
            self._update_solve_for_select_mode()
            self.map_selection_changed.emit()
            return
        else:
            if self._selected_map_card is not None:
                old = self._selected_map_card
                self._maybe_swap_with_next_if_was_last_at_select(old)
                self._selected_was_last_in_row_at_select = False
                old.set_selected(False)
            was_last = self._maybe_swap_with_prev_if_last_in_row_on_select(clicked_card)
            clicked_card.set_selected(True)
            self._selected_map_card = clicked_card
            self._selected_was_last_in_row_at_select = was_last

        self._relayout_cards()
        self._update_solve_for_select_mode()
        self.map_selection_changed.emit()

    def _deselect_current_card(self, *, clear_deduction: bool = True) -> None:
        """Clear manager selection; optionally clear deduction clue fields (default True)."""
        if self._selected_map_card is None:
            return
        card = self._selected_map_card
        self._maybe_swap_with_next_if_was_last_at_select(card)
        self._selected_was_last_in_row_at_select = False
        if clear_deduction:
            card.clear_deduction_controls()
        card.set_selected(False)
        self._selected_map_card = None

    def get_selected_map_data(self) -> Optional[dict]:
        """Return selected map data dict, or None."""
        if self._selected_map_card is None:
            return None
        for card, data in self._map_cards:
            if card is self._selected_map_card:
                return data
        return None

    def get_card_for_map_data(self, map_data: dict) -> Optional["MapCard"]:
        """Return the MapCard for the given map data, or None."""
        for card, data in self._map_cards:
            if data == map_data:
                return card
        return None

    def clear_selection(self, *, clear_deduction: bool = True) -> None:
        """Clear selected card."""
        if self._selected_map_card:
            self._deselect_current_card(clear_deduction=clear_deduction)
            self._relayout_cards()
            self.map_selection_changed.emit()

    def enter_solve_mode(self, map_data: dict) -> None:
        """Show only the card for map_data: deselected look, clues stay visible, non-interactive."""
        map_id = map_data.get("id")
        for card, data in self._map_cards:
            visible = data.get("id") == map_id
            card.setVisible(visible)
            if visible:
                card.set_selected(False, keep_clues_visible=True)
                card.set_interactive(False)
            else:
                card.set_selected(False)
                card.set_interactive(False)
        self._selected_map_card = None
        self._rebuild_visible_card_order_from_maps()
        self._selected_was_last_in_row_at_select = False
        self._relayout_cards()
        self.map_selection_changed.emit()

    def exit_solve_mode(self, *, preserve_deduction_forms: bool = False) -> None:
        """Show all cards per filter, make interactive, clear selection.

        When ``preserve_deduction_forms`` is True (deduction Load map after Create tab),
        keep clue combo / names / colors on the card so returning to Load restores the panel.
        """
        self.clear_selection(clear_deduction=not preserve_deduction_forms)
        for card, _ in self._map_cards:
            # Solve mode uses set_selected(False, keep_clues_visible=True) with no manager selection;
            # clear_selection() then does nothing for that card — force full deselect to hide clues.
            card.set_selected(False)
            card.set_interactive(True)
            card.clear_preview_highlights()
        self.filter_map_cards()

    def clear_all_cards_deduction_controls(self) -> None:
        """Clear Your clue, player names, and color dropdowns on all deduction-mode cards."""
        for card, _ in self._map_cards:
            if getattr(card, "_deduction_mode", False):
                card.clear_deduction_controls()

    def set_blur_for_all_cards(self, checked: bool) -> None:
        """Set blur clues on/off for all cards (no-op for deduction mode cards)."""
        for card, _ in self._map_cards:
            if getattr(card, "_deduction_mode", False):
                continue
            cb = getattr(card, "_cb_blur_clues", None)
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(checked)
                cb.blockSignals(False)
            if hasattr(card, "_on_blur_toggled"):
                card._on_blur_toggled(checked)
