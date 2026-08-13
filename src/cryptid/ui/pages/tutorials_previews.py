"""Small non-interactive previews for the Tutorials page."""
from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from board.factory import make_puzzle_pieces
from board.markers import MarkerItem
from board.pieces import Cell, HexPiece
from data.piece_defs import (
    COLOR_DESERT,
    COLOR_FOREST,
    COLOR_MOUNTAIN,
    COLOR_SWAMP,
    COLOR_WATER,
)
from logic.clue_grid import (
    CLUE_GRID_GROUP_SLOT_RANGES,
    get_clue_label_for_slot,
    split_group_slots_positive_negative,
)
from settings.config import CLUES_ICONS_DIR, ICON_CLUE
from ui.shared.widgets.player_colors import (
    PLAYER_COLORS,
    get_player_circle_chip_pixmap,
    get_player_square_chip_pixmap,
)

_TERRAIN_COLORS = {
    "water": COLOR_WATER,
    "mountain": COLOR_MOUNTAIN,
    "forest": COLOR_FOREST,
    "swamp": COLOR_SWAMP,
    "desert": COLOR_DESERT,
}

_STRUCTURE_COLORS = (
    ("#ffffff", "White"),
    ("#00aa00", "Green"),
    ("#0000ff", "Blue"),
    ("#000000", "Black"),
)


class _PreviewView(QGraphicsView):
    """Fixed-size non-interactive graphics preview."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setInteractive(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: transparent; border: none;")
        self._fit_rect: QRectF | None = None

    def set_fit_rect(self, rect: QRectF) -> None:
        self._fit_rect = QRectF(rect)
        self._refit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refit()

    def _refit(self) -> None:
        if self._fit_rect is not None and not self._fit_rect.isEmpty():
            self.fitInView(self._fit_rect, Qt.AspectRatioMode.KeepAspectRatio)


def _render_scene_item(item, *, pad: float = 10.0, max_side: float | None = None) -> QWidget:
    """Put a graphics item in a fitted non-interactive view."""
    item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
    scene = QGraphicsScene()
    scene.addItem(item)
    br = item.mapRectToScene(item.boundingRect()).adjusted(-pad, -pad, pad, pad)
    scene.setSceneRect(br)

    view = _PreviewView()
    view.setScene(scene)
    w = max(40, int(br.width()))
    h = max(40, int(br.height()))
    if max_side is not None:
        scale = min(1.0, max_side / max(w, h))
        w = max(40, int(w * scale))
        h = max(40, int(h * scale))
    view.setFixedSize(w, h)
    view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    view.set_fit_rect(br)
    return view


def make_terrain_hex_widget(terrain_key: str, *, size: float = 56) -> QWidget:
    color = _TERRAIN_COLORS[terrain_key]
    piece = HexPiece([Cell(0, 0, color)], "", "A")
    piece.show_corner_mark = False
    return _render_scene_item(piece, pad=6, max_side=size)


def make_territory_hex_widget(kind: str, *, size: float = 56) -> QWidget:
    """kind: 'bear' (black dashed) or 'cougar' (red dashed). Outline only, no terrain fill."""
    dotted = "black" if kind == "bear" else "red"
    piece = HexPiece([Cell(0, 0, COLOR_FOREST, inner_dotted=dotted)], "", "A")
    piece.show_corner_mark = False
    piece.show_terrain_fill = False
    return _render_scene_item(piece, pad=6, max_side=size)


def make_map_tile_widget(*, matrix_id: str = "A", max_side: float = 220) -> QWidget:
    """Preview a full puzzle tile (default: piece A / number 1)."""
    pieces = make_puzzle_pieces()
    piece = next((p for p in pieces if p.matrix_id == matrix_id), None)
    if piece is None:
        piece = pieces[0]
    return _render_scene_item(piece, pad=12, max_side=max_side)


def make_structure_marker_widget(shape: str, color: str, *, size: float = 44) -> QWidget:
    m = MarkerItem(shape_kind=shape, color=color)  # type: ignore[arg-type]
    m.setScale(1.8)
    m.setFlag(m.GraphicsItemFlag.ItemIsMovable, False)
    m.setPos(QPointF(0, 0))
    return _render_scene_item(m, pad=8, max_side=size)


def make_labeled_preview_row(
    items: list[tuple[QWidget, str]],
    *,
    parent: QWidget | None = None,
) -> QWidget:
    """Horizontal row of preview + caption pairs."""
    host = QWidget(parent)
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 4, 0, 0)
    row.setSpacing(16)
    for preview, caption in items:
        cell = QWidget(host)
        cell_l = QVBoxLayout(cell)
        cell_l.setContentsMargins(0, 0, 0, 0)
        cell_l.setSpacing(6)
        cell_l.addWidget(preview, 0, Qt.AlignmentFlag.AlignHCenter)
        cap = QLabel(caption)
        cap.setObjectName("tutorialCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cap.setWordWrap(True)
        cell_l.addWidget(cap)
        row.addWidget(cell, 0, Qt.AlignmentFlag.AlignTop)
    return host


def make_terrain_types_row(parent: QWidget | None = None, *, vertical: bool = False) -> QWidget:
    from settings.strings import TUTORIAL_TERRAIN_LABELS

    items = [
        (make_terrain_hex_widget(key), label) for key, label in TUTORIAL_TERRAIN_LABELS
    ]
    if not vertical:
        return make_labeled_preview_row(items, parent=parent)

    host = QWidget(parent)
    col = QVBoxLayout(host)
    col.setContentsMargins(0, 4, 0, 0)
    col.setSpacing(8)
    for preview, caption in items:
        cell = QWidget(host)
        cell_l = QHBoxLayout(cell)
        cell_l.setContentsMargins(0, 0, 0, 0)
        cell_l.setSpacing(10)
        cell_l.addWidget(preview, 0, Qt.AlignmentFlag.AlignVCenter)
        cap = QLabel(caption)
        cap.setObjectName("tutorialCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        cell_l.addWidget(cap, 1)
        col.addWidget(cell)
    return host


def make_territory_types_row(parent: QWidget | None = None) -> QWidget:
    from settings.strings import TUTORIAL_TERRITORY_LABELS

    items = [
        (make_territory_hex_widget(key), label) for key, label in TUTORIAL_TERRITORY_LABELS
    ]
    return make_labeled_preview_row(items, parent=parent)


def make_structures_preview(parent: QWidget | None = None) -> QWidget:
    from settings.strings import (
        TUTORIAL_STRUCTURES_GROUP_SHACKS,
        TUTORIAL_STRUCTURES_GROUP_STONES,
    )

    host = QWidget(parent)
    host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.setSpacing(12)

    for shape, group_title in (
        ("octagon", TUTORIAL_STRUCTURES_GROUP_STONES),
        ("triangle", TUTORIAL_STRUCTURES_GROUP_SHACKS),
    ):
        group = QWidget(host)
        group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        group_l = QVBoxLayout(group)
        group_l.setContentsMargins(0, 0, 0, 0)
        group_l.setSpacing(6)

        icons_host = QWidget(group)
        icons_host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        icons = QHBoxLayout(icons_host)
        icons.setContentsMargins(0, 0, 0, 0)
        icons.setSpacing(3)
        for color, _name in _STRUCTURE_COLORS:
            icons.addWidget(
                make_structure_marker_widget(shape, color, size=36),
                0,
                Qt.AlignmentFlag.AlignLeft,
            )
        group_l.addWidget(icons_host, 0, Qt.AlignmentFlag.AlignLeft)

        group_lbl = QLabel(group_title)
        group_lbl.setObjectName("tutorialCaption")
        group_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        group_lbl.setWordWrap(True)
        group_l.addWidget(group_lbl)

        lay.addWidget(group, 0, Qt.AlignmentFlag.AlignLeft)
    return host


def make_playing_pieces_preview(parent: QWidget | None = None) -> QWidget:
    from settings.strings import TUTORIAL_PIECES_CUBE_CAPTION, TUTORIAL_PIECES_DISC_CAPTION

    chip_size = 24
    colors = [name for name, _hex in PLAYER_COLORS]

    def _chip_row(kind: str, caption: str) -> QWidget:
        cell = QWidget(parent)
        cell.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        chips_host = QWidget(cell)
        chips_host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        chips = QHBoxLayout(chips_host)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        for c in colors:
            lbl = QLabel()
            lbl.setObjectName("tutorialPreviewIcon")
            lbl.setFixedSize(chip_size, chip_size)
            if kind == "cube":
                pm = get_player_square_chip_pixmap(c, chip_size)
            else:
                pm = get_player_circle_chip_pixmap(c, chip_size)
            lbl.setPixmap(pm)
            chips.addWidget(lbl, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(chips_host, 0, Qt.AlignmentFlag.AlignLeft)

        cap = QLabel(caption)
        cap.setObjectName("tutorialCaption")
        cap.setWordWrap(False)
        lay.addWidget(cap)
        return cell

    host = QWidget(parent)
    host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    col = QVBoxLayout(host)
    col.setContentsMargins(0, 4, 0, 0)
    col.setSpacing(12)
    col.addWidget(_chip_row("cube", TUTORIAL_PIECES_CUBE_CAPTION), 0, Qt.AlignmentFlag.AlignLeft)
    col.addWidget(_chip_row("disc", TUTORIAL_PIECES_DISC_CAPTION), 0, Qt.AlignmentFlag.AlignLeft)
    return host


def _load_clue_icons(size: int = 36) -> dict[int, QPixmap]:
    result: dict[int, QPixmap] = {}
    if not CLUES_ICONS_DIR.is_dir():
        return result
    for f in CLUES_ICONS_DIR.iterdir():
        if f.suffix.lower() not in (".svg", ".png") or "_" not in f.stem:
            continue
        try:
            n = int(f.stem.split("_", 1)[0])
        except ValueError:
            continue
        pix = QPixmap(str(f))
        if pix.isNull():
            continue
        result[n] = pix.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return result


def _make_clue_icons_row(
    slots: Sequence[int],
    *,
    parent: QWidget,
    icons: dict[int, QPixmap],
    default: QPixmap,
    icon_size: int,
    tooltip_manager=None,
    columns: int,
) -> QWidget:
    from PySide6.QtWidgets import QGridLayout

    host = QWidget(parent)
    host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)

    for idx, slot in enumerate(slots):
        row, col = divmod(idx, columns)
        label = get_clue_label_for_slot(slot)
        icon_lbl = QLabel(host)
        icon_lbl.setObjectName("tutorialPreviewIcon")
        icon_lbl.setFixedSize(icon_size, icon_size)
        icon_lbl.setScaledContents(False)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = icons.get(slot)
        if pm is None or pm.isNull():
            pm = default
        if pm is not None and not pm.isNull():
            icon_lbl.setPixmap(pm)
        if tooltip_manager is not None:
            tooltip_manager.add(icon_lbl, label, only_when_disabled=False)
        else:
            icon_lbl.setToolTip(label)
        grid.addWidget(icon_lbl, row, col, Qt.AlignmentFlag.AlignLeft)

    return host


def make_possible_clues_grid(
    *,
    parent: QWidget | None = None,
    tooltip_manager=None,
    columns: int = 12,
    icon_size: int = 32,
) -> QWidget:
    """All 48 clue icons in a grid; label text shown on hover only."""
    icons = _load_clue_icons(icon_size)
    default = QPixmap()
    if ICON_CLUE.exists():
        default = QIcon(str(ICON_CLUE)).pixmap(icon_size, icon_size)

    host = QWidget(parent)
    host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    row_host = _make_clue_icons_row(
        list(range(1, 49)),
        parent=host,
        icons=icons,
        default=default,
        icon_size=icon_size,
        tooltip_manager=tooltip_manager,
        columns=columns,
    )
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.addWidget(row_host)
    return host


def _make_clue_side_column(
    title: str,
    slots: Sequence[int],
    *,
    parent: QWidget,
    icons: dict[int, QPixmap],
    default: QPixmap,
    icon_size: int,
    tooltip_manager=None,
    columns: int,
) -> QWidget:
    column = QWidget(parent)
    column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lay = QVBoxLayout(column)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)

    title_lbl = QLabel(title)
    title_lbl.setObjectName("tutorialCaption")
    title_lbl.setWordWrap(True)
    lay.addWidget(title_lbl)

    lay.addWidget(
        _make_clue_icons_row(
            slots,
            parent=column,
            icons=icons,
            default=default,
            icon_size=icon_size,
            tooltip_manager=tooltip_manager,
            columns=columns,
        ),
        0,
        Qt.AlignmentFlag.AlignLeft,
    )
    return column


def make_possible_clues_grouped(
    *,
    parent: QWidget | None = None,
    tooltip_manager=None,
    icon_size: int = 32,
) -> QWidget:
    """All 48 clue icons grouped by clue category, positive and negative side by side."""
    from settings.strings import (
        TUTORIAL_CLUES_GROUP_ONE_SPACE,
        TUTORIAL_CLUES_GROUP_ONE_SPACE_NOT,
        TUTORIAL_CLUES_GROUP_TERRAIN_PAIR,
        TUTORIAL_CLUES_GROUP_TERRAIN_PAIR_NOT,
        TUTORIAL_CLUES_GROUP_THREE_SPACES,
        TUTORIAL_CLUES_GROUP_THREE_SPACES_NOT,
        TUTORIAL_CLUES_GROUP_TWO_SPACES,
        TUTORIAL_CLUES_GROUP_TWO_SPACES_NOT,
    )

    group_titles = {
        "terrain_pair": (
            TUTORIAL_CLUES_GROUP_TERRAIN_PAIR,
            TUTORIAL_CLUES_GROUP_TERRAIN_PAIR_NOT,
        ),
        "one_space": (
            TUTORIAL_CLUES_GROUP_ONE_SPACE,
            TUTORIAL_CLUES_GROUP_ONE_SPACE_NOT,
        ),
        "two_spaces": (
            TUTORIAL_CLUES_GROUP_TWO_SPACES,
            TUTORIAL_CLUES_GROUP_TWO_SPACES_NOT,
        ),
        "three_spaces": (
            TUTORIAL_CLUES_GROUP_THREE_SPACES,
            TUTORIAL_CLUES_GROUP_THREE_SPACES_NOT,
        ),
    }
    group_half_columns = {
        "terrain_pair": 5,
        "one_space": 6,
        "two_spaces": 4,
        "three_spaces": 4,
    }

    host = QWidget(parent)
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    col = QVBoxLayout(host)
    col.setContentsMargins(0, 4, 0, 0)
    col.setSpacing(14)

    icons = _load_clue_icons(icon_size)
    default = QPixmap()
    if ICON_CLUE.exists():
        default = QIcon(str(ICON_CLUE)).pixmap(icon_size, icon_size)

    for group_key, slots in CLUE_GRID_GROUP_SLOT_RANGES:
        positive_slots, negative_slots = split_group_slots_positive_negative(slots)
        pos_title, neg_title = group_titles[group_key]
        half_columns = group_half_columns[group_key]

        group = QWidget(host)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        group_l = QHBoxLayout(group)
        group_l.setContentsMargins(0, 0, 0, 0)
        group_l.setSpacing(16)
        group_l.addWidget(
            _make_clue_side_column(
                pos_title,
                positive_slots,
                parent=group,
                icons=icons,
                default=default,
                icon_size=icon_size,
                tooltip_manager=tooltip_manager,
                columns=half_columns,
            ),
            1,
        )
        group_l.addWidget(
            _make_clue_side_column(
                neg_title,
                negative_slots,
                parent=group,
                icons=icons,
                default=default,
                icon_size=icon_size,
                tooltip_manager=tooltip_manager,
                columns=half_columns,
            ),
            1,
        )
        col.addWidget(group)

    return host
