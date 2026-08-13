"""Breadcrumb segment lists for each main page (used by BreadcrumbManager)."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ui.pages.maps_library.page_maps_library import MapsLibraryPageController
    from ui.pages.page_deduction import DeductionPageController
    from ui.pages.page_solve import SolvePageController


def segments_maps_library(ctrl: Any) -> list[str]:
    c: MapsLibraryPageController = ctrl
    base = ["Home", "Maps Library"]
    if c.mapsLibStack is None or c.mapsLibStack.currentIndex() == 0:
        return base + ["Create Map"]
    if c.mapsLibBrowseStack is not None and c.mapsLibBrowseStack.currentIndex() == 1:
        name = (c._editing_custom_map_name or "").strip() or "Map"
        return base + ["Custom Maps", name, "edit"]
    if c.btnMapsLibPredefined is not None and c.btnMapsLibPredefined.isChecked():
        return base + ["Predefined Maps"]
    return base + ["Custom Maps"]


def segments_solve_tool(ctrl: Any) -> list[str]:
    c: SolvePageController = ctrl
    base = ["Home", "Solver Tool"]
    if c.btnMapBuild.isChecked():
        segs = base + ["Create Map"]
        if getattr(c, "_build_tab_solve_active", False):
            segs.append("solve")
        return segs
    segs = base + ["Load Map"]
    md = c.map_cards_manager.get_selected_map_data() or getattr(c, "_solve_mode_map_data", None)
    if md:
        name = (md.get("name") or f"Map {md.get('id', '?')}").strip()
        segs.append(name)
    if getattr(c, "_in_solve_mode", False):
        segs.append("solve")
    return segs


def segments_deduction_mode(ctrl: Any) -> list[str]:
    c: DeductionPageController = ctrl
    base = ["Home", "Deduction Mode"]
    if c.btnMapBuild.isChecked():
        segs = base + ["Create Map"]
        bb = getattr(c, "board_builder", None)
        if bb is not None and getattr(bb, "_chips_mode", False):
            segs.append("simulation")
        return segs
    segs = base + ["Load Map"]
    md = c.map_cards_manager.get_selected_map_data() or getattr(c, "_solve_mode_map_data", None)
    if md:
        name = (md.get("name") or f"Map {md.get('id', '?')}").strip()
        segs.append(name)
    if getattr(c, "_in_solve_mode", False):
        segs.append("simulation")
    return segs


def segments_static(_second: str) -> Callable[[], list[str]]:
    def _fn() -> list[str]:
        return ["Home", _second]

    return _fn


def segments_play_hotseat(ctrl: Any) -> list[str]:
    """Breadcrumb trail: setup vs game from hotseat stack index."""
    base = ["Home", "Play Hotseat"]
    stack = getattr(ctrl, "_stack", None)
    if stack is None or stack.currentIndex() <= 0:
        return base + ["setup"]
    return base + ["game"]
