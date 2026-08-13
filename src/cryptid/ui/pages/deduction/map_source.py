"""Map source toggle, board setup hook, optional Atlantis preload."""
from __future__ import annotations

import json

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from settings.config import CUSTOM_MAPS_JSON, DATA_DIR, MAPS_JSON, PRELOAD_ATLANTIS_IN_DEDUCTION


class DeductionMapSourceMixin:

    def _wire_deduction_custom_maps_toggle(self) -> None:
        from PySide6.QtWidgets import QCheckBox

        cb = self._page.findChild(QCheckBox, "cbSelectCustomMaps")
        if cb is None:
            return
        self.cbSelectCustomMaps = cb
        cb.toggled.connect(self._on_deduction_select_custom_maps_toggled)

    def _on_deduction_select_custom_maps_toggled(self, use_custom: bool) -> None:
        self._apply_deduction_select_maps_source(use_custom)

    def _apply_deduction_select_maps_source(self, use_custom: bool) -> None:
        path = CUSTOM_MAPS_JSON if use_custom else MAPS_JSON
        bm = self.map_cards_manager
        cur = getattr(bm, "_maps_json_path", None)
        effective = cur if cur is not None else MAPS_JSON
        if effective.resolve() == path.resolve():
            bm.filter_map_cards()
            return
        bm.set_maps_json_path(path)

    def _on_map_source_toggled(self, _: bool) -> None:
        """Save current mode and restore the other so Build and Select stay independent."""
        if self.btnMapSelect.isChecked():
            # Leaving Build -> Select: if a Build simulation is active, snapshot it
            if hasattr(self, "board_builder") and self.board_builder is not None and getattr(self.board_builder, "_chips_mode", False):
                sess = self._capture_simulation_session()
                if sess is not None:
                    self._build_sim_session = sess
            # Always snapshot Create map when switching to Load (not only when _build_dirty).
            # _save_build_state() skips if !dirty and clears _build_state, so returning to Create reset the page.
            self._save_build_state_for_navigation()
            self.mapSourceStack.setCurrentIndex(self._IDX_SELECT_BROWSE)
            self.mapListCardsContainer.setVisible(True)
            mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
            if mc:
                mc.setVisible(True)
            self._restore_select_state()
            # Browse list (not an active Load-map sim): keep Advanced + Search visible.
            if not getattr(self, "_in_solve_mode", False):
                self._show_select_browse_filters()
        else:
            # Leaving Select -> Build: if a Select simulation is active, snapshot it
            if getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None):
                sess = self._capture_simulation_session()
                if sess is not None:
                    self._select_sim_session = sess
            self._save_select_state()
            self.mapListCardsContainer.setVisible(False)
            mc = self.selectContent.findChild(QWidget, "selectControls") if self.selectContent else None
            if mc:
                mc.setVisible(False)
            self._restore_build_state()
        self._on_map_source_mode_changed()

    def _build_board_content(self) -> None:
        super()._build_board_content()
        self._setup_select_sim_panel()
        if PRELOAD_ATLANTIS_IN_DEDUCTION and hasattr(self, "board_builder") and self.board_builder is not None:
            QTimer.singleShot(100, self._do_preload_atlantis)

    def _do_preload_atlantis(self) -> None:
        """Load Atlantis map (deferred so view is laid out)."""
        if not hasattr(self, "board_builder") or self.board_builder is None:
            return
        atlantis = self._get_atlantis_map_data()
        if atlantis is not None:
            self.board_builder.load_from_map_data(atlantis, freeze=False)
            if hasattr(self, "_update_status_and_structures"):
                self._update_status_and_structures()
            u = getattr(self, "_board_undo", None)
            if u is not None:
                u.reset()

    def _get_atlantis_map_data(self) -> dict | None:
        """Load Atlantis map from maps.json. Returns None if not found."""
        try:
            with open(DATA_DIR / "maps.json", encoding="utf-8") as f:
                maps = json.load(f).get("maps") or []
            for m in maps:
                if (m.get("name") or "").strip() == "Atlantis":
                    return m
        except Exception:
            pass

