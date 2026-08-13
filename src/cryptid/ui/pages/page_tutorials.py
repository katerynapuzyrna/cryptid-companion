"""Tutorials page: overview / components / setup / play cards."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from settings.strings import (
    HOW_TO_PLAY_HTML,
    TUTORIAL_CLUES_EXAMPLES_TITLE,
    TUTORIAL_CLUES_BODY,
    TUTORIAL_CLUES_TITLE,
    TUTORIAL_COMPONENTS_TITLE,
    TUTORIAL_MAP_BODY,
    TUTORIAL_MAP_TITLE,
    TUTORIAL_OVERVIEW_BODY,
    TUTORIAL_OVERVIEW_TITLE,
    TUTORIAL_PIECES_BODY,
    TUTORIAL_PIECES_TITLE,
    TUTORIAL_PLAY_GOAL_BODY,
    TUTORIAL_PLAY_PIECES_BODY,
    TUTORIAL_PLAY_QUESTION_BODY,
    TUTORIAL_PLAY_RULES_BODY,
    TUTORIAL_PLAY_SEARCH_BODY,
    TUTORIAL_PLAY_SECTION_GOAL,
    TUTORIAL_PLAY_SECTION_PIECES,
    TUTORIAL_PLAY_SECTION_QUESTION,
    TUTORIAL_PLAY_SECTION_RULES,
    TUTORIAL_PLAY_SECTION_SEARCH,
    TUTORIAL_PLAY_SECTION_TURN,
    TUTORIAL_PLAY_TITLE,
    TUTORIAL_PLAY_TURN_INTRO,
    TUTORIAL_SETUP_BODY,
    TUTORIAL_SETUP_TITLE,
    TUTORIAL_STRUCTURES_BODY,
    TUTORIAL_STRUCTURES_TITLE,
    TUTORIAL_TERRAIN_TITLE,
    TUTORIAL_TERRAIN_BODY,
    TUTORIAL_TERRITORY_BODY,
    TUTORIAL_TERRITORY_TITLE,
)
from ui.shared.widgets import HoverTooltipManager
from ui.pages.tutorials_clue_examples import make_clues_examples_widget
from ui.pages.tutorials_previews import (
    make_map_tile_widget,
    make_playing_pieces_preview,
    make_possible_clues_grouped,
    make_structures_preview,
    make_terrain_types_row,
    make_territory_types_row,
)


def _body_label(text: str, *, compact: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("tutorialCardBody")
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    if compact:
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    else:
        lbl.setMinimumWidth(0)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    return lbl


def _section_heading(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("tutorialSectionTitle")
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return lbl


def _nested_section(title: str, body: str) -> QWidget:
    wrap = QWidget()
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(wrap)
    lay.setContentsMargins(12, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(_section_heading(title))
    lay.addWidget(_body_label(body, compact=True))
    return wrap


def _make_card(title: str, *, inner: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("tutorialInnerCard" if inner else "tutorialCard")
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    frame.setFrameShape(QFrame.Shape.NoFrame)
    if inner:
        # Hug content; grid/column layout aligns cards top-left without stretching.
        frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
    else:
        frame.setMinimumWidth(0)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)
    title_lbl = QLabel(title)
    title_lbl.setObjectName("tutorialInnerCardTitle" if inner else "tutorialCardTitle")
    title_lbl.setWordWrap(True)
    if inner:
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    else:
        title_lbl.setMinimumWidth(0)
    lay.addWidget(title_lbl)
    return frame, lay


# Structures / Animal territory column width relative to map/terrain column.
_COMPONENTS_STRUCTURES_COL_WIDTH_FACTOR = 0.9


def _prepare_paired_inner_card(frame: QFrame, lay: QVBoxLayout) -> None:
    """Expand to share row/column size; keep content top-aligned inside the card."""
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay.addStretch(1)


class TutorialsPageController:
    """Build the Tutorials card layout; keep legacy HTML hidden for later reuse."""

    def __init__(self, page: QWidget):
        self._page = page
        self._tooltip = HoverTooltipManager(page, page)

    def setup(self) -> None:
        tb = self._page.findChild(QTextBrowser, "textHowToPlay")
        if tb is not None:
            tb.setHtml(HOW_TO_PLAY_HTML)
            tb.hide()

        host = self._page.findChild(QWidget, "tutorialsCards")
        if host is None:
            raise RuntimeError("tutorialsCards not found on Tutorials page")
        layout = host.layout()
        if layout is None:
            raise RuntimeError("tutorialsCards has no layout")

        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        layout.addWidget(self._build_overview_card())
        layout.addWidget(self._build_components_card())
        layout.addWidget(self._build_simple_card(TUTORIAL_SETUP_TITLE, TUTORIAL_SETUP_BODY))
        layout.addWidget(self._build_play_card())

    def _build_simple_card(self, title: str, body: str) -> QFrame:
        card, lay = _make_card(title)
        lay.addWidget(_body_label(body))
        return card

    def _build_play_card(self) -> QFrame:
        card, lay = _make_card(TUTORIAL_PLAY_TITLE)
        lay.setSpacing(8)

        lay.addWidget(_section_heading(TUTORIAL_PLAY_SECTION_GOAL))
        lay.addWidget(_body_label(TUTORIAL_PLAY_GOAL_BODY, compact=True))

        lay.addWidget(_section_heading(TUTORIAL_PLAY_SECTION_TURN))
        lay.addWidget(_body_label(TUTORIAL_PLAY_TURN_INTRO, compact=True))
        lay.addWidget(_nested_section(TUTORIAL_PLAY_SECTION_QUESTION, TUTORIAL_PLAY_QUESTION_BODY))
        lay.addWidget(_nested_section(TUTORIAL_PLAY_SECTION_SEARCH, TUTORIAL_PLAY_SEARCH_BODY))

        lay.addWidget(_section_heading(TUTORIAL_PLAY_SECTION_PIECES))
        lay.addWidget(_body_label(TUTORIAL_PLAY_PIECES_BODY, compact=True))

        lay.addWidget(_section_heading(TUTORIAL_PLAY_SECTION_RULES))
        lay.addWidget(_body_label(TUTORIAL_PLAY_RULES_BODY, compact=True))

        return card

    def _build_overview_card(self) -> QFrame:
        return self._build_simple_card(TUTORIAL_OVERVIEW_TITLE, TUTORIAL_OVERVIEW_BODY)

    def _build_components_card(self) -> QFrame:
        card, lay = _make_card(TUTORIAL_COMPONENTS_TITLE)

        map_card, map_lay = _make_card(TUTORIAL_MAP_TITLE, inner=True)
        map_lay.addWidget(_body_label(TUTORIAL_MAP_BODY, compact=True))
        map_lay.addWidget(
            make_map_tile_widget(matrix_id="A", max_side=200),
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        _prepare_paired_inner_card(map_card, map_lay)

        terrain_card, terrain_lay = _make_card(TUTORIAL_TERRAIN_TITLE, inner=True)
        terrain_lay.addWidget(_body_label(TUTORIAL_TERRAIN_BODY, compact=True))
        terrain_lay.addWidget(make_terrain_types_row(terrain_card, vertical=False))
        _prepare_paired_inner_card(terrain_card, terrain_lay)

        struct_card, struct_lay = _make_card(TUTORIAL_STRUCTURES_TITLE, inner=True)
        struct_lay.addWidget(_body_label(TUTORIAL_STRUCTURES_BODY, compact=True))
        struct_lay.addWidget(make_structures_preview(struct_card))
        _prepare_paired_inner_card(struct_card, struct_lay)

        terr_card, terr_lay = _make_card(TUTORIAL_TERRITORY_TITLE, inner=True)
        terr_lay.addWidget(_body_label(TUTORIAL_TERRITORY_BODY, compact=True))
        terr_lay.addWidget(make_territory_types_row(terr_card))
        _prepare_paired_inner_card(terr_card, terr_lay)

        pieces_card, pieces_lay = _make_card(TUTORIAL_PIECES_TITLE, inner=True)
        pieces_lay.addWidget(_body_label(TUTORIAL_PIECES_BODY, compact=True))
        pieces_lay.addWidget(make_playing_pieces_preview(pieces_card))
        pieces_card.setMinimumWidth(300)
        _prepare_paired_inner_card(pieces_card, pieces_lay)

        # Grid: equal width per column; row 0 / row 1 heights matched across columns.
        #   map        | structures      | playing pieces (spans both rows)
        #   terrain    | animal territory|
        grid_host = QWidget(card)
        grid_host.setMinimumWidth(0)
        grid_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.addWidget(map_card, 0, 0)
        grid.addWidget(struct_card, 0, 1)
        grid.addWidget(pieces_card, 0, 2, 2, 1)
        grid.addWidget(terrain_card, 1, 0)
        grid.addWidget(terr_card, 1, 1)
        col0_hint = max(map_card.sizeHint().width(), terrain_card.sizeHint().width())
        if col0_hint > 0:
            grid.setColumnMinimumWidth(
                1,
                max(1, int(col0_hint * _COMPONENTS_STRUCTURES_COL_WIDTH_FACTOR)),
            )
        grid.setColumnStretch(0, 10)
        grid.setColumnStretch(1, 9)
        grid.setColumnStretch(2, 20)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 0)
        lay.addWidget(grid_host)

        clues_row_host = QWidget(card)
        clues_row_host.setMinimumWidth(0)
        clues_row_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        clues_row = QHBoxLayout(clues_row_host)
        clues_row.setContentsMargins(0, 0, 0, 0)
        clues_row.setSpacing(12)
        clues_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        examples_card, examples_lay = _make_card(TUTORIAL_CLUES_EXAMPLES_TITLE, inner=True)
        examples_lay.addWidget(make_clues_examples_widget(parent=examples_card))
        clues_row.addWidget(examples_card, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        clues_card, clues_lay = _make_card(TUTORIAL_CLUES_TITLE, inner=True)
        clues_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        clues_lay.addWidget(_body_label(TUTORIAL_CLUES_BODY, compact=True))
        clues_lay.addWidget(
            make_possible_clues_grouped(parent=clues_card, tooltip_manager=self._tooltip)
        )
        _prepare_paired_inner_card(clues_card, clues_lay)
        clues_row.addWidget(clues_card, 1)

        lay.addWidget(clues_row_host)

        return card
