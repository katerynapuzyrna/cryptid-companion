"""Solver Tool page: thin coordinator; behavior lives in ui.pages.solve mixins."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ui.pages.solve.setup_mixin import SolveSetupMixin
from ui.pages.solve.map_source_mixin import SolveMapSourceMixin
from ui.pages.solve.rules_players_mixin import SolveRulesPlayersMixin
from ui.pages.solve.board_mixin import SolveBoardMixin
from ui.pages.solve.highlights_mixin import SolveHighlightsMixin
from ui.pages.solve.reset_nav_mixin import SolveResetNavMixin
from ui.pages.solve.select_flow_mixin import SolveSelectFlowMixin
from ui.pages.solve.build_solve_mixin import SolveBuildSolveMixin


class SolvePageController(
    SolveBuildSolveMixin,
    SolveSelectFlowMixin,
    SolveResetNavMixin,
    SolveHighlightsMixin,
    SolveBoardMixin,
    SolveRulesPlayersMixin,
    SolveMapSourceMixin,
    SolveSetupMixin,
):
    """Solver Tool page: board building, map selection, rules, solve/reset."""

    def __init__(self, page: QWidget, window: QWidget):
        self.window = window
        self._page = page
        self._find = lambda name, cls: page.findChild(cls, name) or self._raise(name)

    def _raise(self, name: str):
        raise RuntimeError(f"Widget '{name}' not found in page_solve (check objectName).")
