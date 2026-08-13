"""BoardBuilder: creates canvas, pieces, markers, controller, overlay, freeze row."""
from __future__ import annotations

from typing import Callable, Optional, Any

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QCheckBox,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
    QGraphicsPathItem,
    QToolButton,
)
from PySide6.QtGui import (
    QColor,
    QPainterPath,
    QBrush,
    QPen,
    QPixmap,
    QPainter,
    QMouseEvent,
    QIcon,
)
from PySide6.QtCore import QPoint, QRect, QRectF, QPointF, Qt, QEvent, QObject, QSize

from board.board_view import BoardView
from board.canvas import PuzzleCanvas
from board.factory import make_puzzle_pieces, add_markers
from board.pieces import build_piece_outer_path, build_piece_inner_path, HexPiece, find_hex_under_point
from board.highlight_overlay import HighlightOverlay
from board.markers import (
    ChipItem,
    MARKER_SCALE_CANVAS,
    MARKER_SCALE_HOME,
    MARKER_Z_BANK,
    MarkerItem,
    marker_scale_canvas_for_hex_figure_count,
)
from board.geometry import axial_to_pixel
from logic.map_builder import MapBuilder
from logic.coord_mapping import is_rotated_180, visual_row_col_for_cell_index
from logic.map_loader import (
    parse_tile_id,
    slot_for_tile_id,
    cell_index_for_visual_row_col,
    COLOR_NAME_TO_HEX,
)

from settings.config import SLOT_OVERLAP_X, SLOT_OVERLAP_Y, HEX_SIZE
from settings.theme import CANVAS_RADIUS


class BoardBuilder:
    """Builds the puzzle board: canvas, pieces, markers, controller, overlay, freeze row."""

    def __init__(self, scene: QGraphicsScene, view: BoardView):
        self.scene = scene
        self.view = view
        self.canvas: Optional[PuzzleCanvas] = None
        self.pieces: list = []
        self.markers: list = []
        self.controller: Optional[MapBuilder] = None
        self.highlight_overlay: Optional[HighlightOverlay] = None
        self.chips: list = []
        self._chip_labels: list = []
        # Mapping from chip color (hex string) to player index (1=Player 1, 2=Player 2, ...).
        # Used to keep figure ordering consistent on a hex (marker, circles by player order, then square).
        self._chip_player_rank: dict[str, int] = {}
        self.cbFreezeMap: Optional[QCheckBox] = None
        self.cbHighlightValidSpaces: Optional[QCheckBox] = None
        self._freeze_row: Optional[QWidget] = None
        self._highlight_row: Optional[QWidget] = None
        self._canvas_w: float = 0
        self._canvas_h: float = 0
        self._structures_bg: QGraphicsPathItem | None = None
        self._structures_row_proxy = None
        self._structures_labels_widget: QWidget | None = None
        self._chips_labels_widget: QWidget | None = None
        self._structures_stacked: QStackedWidget | None = None
        self._structures_top: float = 0
        self._structures_left: float = 0
        self._structures_height: float = 50
        self._chips_mode: bool = False  # True after Start Simulation until Reset/End Simulation

    def build(
        self,
        add_tooltip: Optional[Callable[[QWidget, str, bool], None]] = None,
        tooltip_freeze_map: str = "",
        tooltip_manager: Optional[Any] = None,
    ) -> None:
        """Create canvas, pieces, markers, controller, overlay, freeze row."""
        self._tooltip_manager = tooltip_manager
        self.scene.clear()
        pieces = make_puzzle_pieces()
        self.pieces = pieces

        outer = build_piece_outer_path(pieces[0].cells)
        inner = build_piece_inner_path(pieces[0].cells)
        br = outer.boundingRect()
        step_x = br.width() - SLOT_OVERLAP_X
        step_y = br.height() - SLOT_OVERLAP_Y
        pad = 20
        canvas_w = pad * 2 + (2 - 1) * step_x + br.width()
        canvas_h = pad * 2 + (3 - 1) * step_y + br.height()
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h

        canvas_rect = QRectF(9, 9, canvas_w, canvas_h)
        self.canvas = PuzzleCanvas(self.scene, canvas_rect, 2, 3, outer, inner)
        self.canvas._show_highlights = True

        for p in pieces:
            p.set_canvas(self.canvas)

        max_w = max(p.boundingRect().width() for p in pieces)
        max_h = max(p.boundingRect().height() for p in pieces)
        gap = 30
        pieces_x = 20 + canvas_w + gap
        self._pieces_x = pieces_x
        self._piece_max_w = max_w
        self._piece_max_h = max_h
        for i, p in enumerate(pieces):
            row, col = i // 2, i % 2
            tx = pieces_x + col * (max_w + 30)
            ty = 20 + row * (max_h + 30)
            p.setPos(QPointF(tx - p.boundingRect().left(), ty - p.boundingRect().top()))
            p.set_home_pos(p.pos())
            self.scene.addItem(p)

        freeze_row = QWidget()
        freeze_row.setObjectName("freezeMapRow")
        fl = QHBoxLayout(freeze_row)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addStretch()
        fl.addWidget(QLabel("Freeze map:"))
        self.cbFreezeMap = QCheckBox()
        self.cbFreezeMap.setObjectName("cbFreezeMap")
        self.cbFreezeMap.setChecked(False)
        self.cbFreezeMap.setEnabled(False)
        if add_tooltip and tooltip_freeze_map:
            add_tooltip(self.cbFreezeMap, tooltip_freeze_map, only_when_disabled=True)
        fl.addWidget(self.cbFreezeMap)
        self.btnUndoFreeze = QToolButton()
        self.btnUndoFreeze.setObjectName("boardUndoFreeze")
        self.btnUndoFreeze.setIcon(QIcon(":/assets/icons/undo.svg"))
        self.btnUndoFreeze.setIconSize(QSize(20, 20))
        self.btnUndoFreeze.setAutoRaise(True)
        self.btnUndoFreeze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnUndoFreeze.setEnabled(False)
        fl.addWidget(self.btnUndoFreeze)
        freeze_row.adjustSize()
        proxy_freeze = self.scene.addWidget(freeze_row)
        proxy_freeze.setPos(9 + canvas_w - freeze_row.width(), 9 + canvas_h + 8)
        proxy_freeze.setZValue(10002)  # Above overlay (10000) and highlight row; receives clicks in build mode
        self._freeze_row = freeze_row
        self._proxy_freeze = proxy_freeze
        self.canvas._is_map_frozen = lambda: (
            self.cbFreezeMap.isEnabled() and self.cbFreezeMap.isChecked()
        )

        structures_height = 100
        structures_top = 9 + canvas_h + freeze_row.height() + 16
        y_octagons = structures_top + 24
        y_triangles = structures_top + 76
        marker_start_x = 9 + 12 + 110 + 30
        self.markers = add_markers(self.scene, marker_start_x, y_octagons, y_triangles)
        for m in self.markers:
            m.set_canvas(self.canvas)

        self.controller = MapBuilder(
            self.scene, self.canvas, self.pieces, self.markers
        )
        self.highlight_overlay = HighlightOverlay(self.canvas, self.pieces)
        self.scene.addItem(self.highlight_overlay)

        highlight_row = QWidget()
        highlight_row.setObjectName("highlightValidSpacesRow")
        hl = QHBoxLayout(highlight_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch()
        hl.addWidget(QLabel("Highlight valid spaces:"))
        self.cbHighlightValidSpaces = QCheckBox()
        self.cbHighlightValidSpaces.setObjectName("cbHighlightValidSpaces")
        self.cbHighlightValidSpaces.setChecked(True)
        self.cbHighlightValidSpaces.setToolTip("")
        hl.addWidget(self.cbHighlightValidSpaces)
        self.btnUndoHighlight = QToolButton()
        self.btnUndoHighlight.setObjectName("boardUndoHighlight")
        self.btnUndoHighlight.setIcon(QIcon(":/assets/icons/undo.svg"))
        self.btnUndoHighlight.setIconSize(QSize(20, 20))
        self.btnUndoHighlight.setAutoRaise(True)
        self.btnUndoHighlight.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btnUndoHighlight.setEnabled(False)
        hl.addWidget(self.btnUndoHighlight)
        highlight_row.adjustSize()
        proxy_hl = self.scene.addWidget(highlight_row)
        proxy_hl.setPos(9 + canvas_w - highlight_row.width(), 9 + canvas_h + 8)
        proxy_hl.setZValue(10001)  # Below freeze (10002) in build; raised when simulation starts
        highlight_row.setVisible(False)
        self._highlight_row = highlight_row
        self._proxy_hl = proxy_hl

        # Structures area: background for structure markers, same style/width as canvas, below "Freeze map"
        structures_height = 100
        structures_top = 9 + canvas_h + freeze_row.height() + 16
        structures_rect = QRectF(canvas_rect.left(), structures_top, canvas_w, structures_height)
        structures_path = QPainterPath()
        structures_path.addRoundedRect(structures_rect, CANVAS_RADIUS, CANVAS_RADIUS)
        structures_bg = QGraphicsPathItem(structures_path)
        structures_bg.setPen(QPen(Qt.PenStyle.NoPen))
        structures_bg.setBrush(QBrush(QColor(0, 0, 0, 0)))
        structures_bg.setZValue(-90)
        self.scene.addItem(structures_bg)
        self._structures_bg = structures_bg

        # Labels inside structures region: QStackedWidget so only one pane visible, layout stays consistent
        self._structures_top = structures_top
        self._structures_left = structures_rect.left()
        self._structures_height = structures_height
        structures_row = QWidget()
        structures_row.setObjectName("structuresRow")
        structures_row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        structures_layout = QVBoxLayout(structures_row)
        structures_layout.setContentsMargins(12, 8, 0, 0)
        structures_layout.setSpacing(0)
        stacked = QStackedWidget()
        stacked.setObjectName("structuresStacked")

        # Page 0: Structures (Standing Stone, Abandoned Shack)
        structures_labels = QWidget()
        struct_layout = QVBoxLayout(structures_labels)
        struct_layout.setContentsMargins(0, 0, 0, 0)
        struct_layout.setSpacing(2)
        #struct_layout.addSpacing(3)
        lbl_standing = QLabel("Standing Stone:")
        lbl_standing.setObjectName("structuresLabelStanding")
        struct_layout.addWidget(lbl_standing)
        struct_layout.addSpacing(15)
        lbl_shack = QLabel("Abandoned Shack:")
        lbl_shack.setObjectName("structuresLabelShack")
        struct_layout.addWidget(lbl_shack)
        struct_layout.addSpacing(8)
        stacked.addWidget(structures_labels)
        self._structures_labels_widget = structures_labels

        # Page 1: Chips (Could be, No)
        chips_labels = QWidget()
        chips_layout = QVBoxLayout(chips_labels)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(2)
        #chips_layout.addSpacing(3)
        lbl_could_be = QLabel("Could be chips:")
        lbl_could_be.setObjectName("structuresLabelCouldBe")
        chips_layout.addWidget(lbl_could_be)
        chips_layout.addSpacing(15)
        lbl_no_chips = QLabel("No chips:")
        lbl_no_chips.setObjectName("structuresLabelNo")
        chips_layout.addWidget(lbl_no_chips)
        chips_layout.addSpacing(8)
        stacked.addWidget(chips_labels)
        stacked.setCurrentIndex(0)
        self._chips_labels_widget = chips_labels
        self._structures_stacked = stacked
        structures_layout.addWidget(stacked)
        structures_row.adjustSize()
        proxy_struct = self.scene.addWidget(structures_row)
        proxy_struct.setPos(structures_rect.left(), structures_top)
        proxy_struct.setZValue(1000)
        self._structures_row_proxy = proxy_struct

        def _on_highlight_toggled(checked: bool) -> None:
            self.canvas._show_highlights = checked
            if self.highlight_overlay is not None:
                self.highlight_overlay.setVisible(checked)
            for p in self.pieces:
                p.update()
            for m in self.markers:
                m.update()
        self.cbHighlightValidSpaces.toggled.connect(_on_highlight_toggled)

        visible = self.view.mapToScene(self.view.viewport().rect()).boundingRect()
        br = self.scene.itemsBoundingRect()
        if br.isValid():
            self.scene.setSceneRect(visible.united(br))
        else:
            self.scene.setSceneRect(visible)

        self.canvas._on_figures_changed = self._relayout_hex_figures

        # When a marker moves to a different hex (or back to the bank), auto-clear highlights.
        # Dropping a marker back onto the same hex leaves highlights intact.
        def _on_marker_reassigned(old_slot, new_slot):
            if old_slot != new_slot:
                self.clear_highlights()
        self.canvas._on_marker_reassigned = _on_marker_reassigned

        # When a piece moves to a different slot (or off the canvas), auto-clear highlights.
        # Dropping a piece back onto the same slot leaves highlights intact.
        def _on_piece_reassigned(old_slot, new_slot):
            if old_slot != new_slot:
                self.clear_highlights()
        self.canvas._on_piece_reassigned = _on_piece_reassigned

        self._figures_tooltip_frame: Optional[QFrame] = None
        _filter = self._figures_tooltip_filter()
        self.view.viewport().installEventFilter(_filter)

    def _figures_tooltip_filter(self) -> QObject:
        """Event filter: right press = show tooltip, right release = hide tooltip."""
        bb = self

        class Filter(QObject):
            def eventFilter(self, obj, event):
                if not isinstance(event, QMouseEvent):
                    return False
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
                    view_pos = event.position().toPoint() if hasattr(event.position(), 'toPoint') else event.pos()
                    scene_pos = bb.view.mapToScene(view_pos)
                    items = bb.scene.items(scene_pos)
                    piece, idx, _ = find_hex_under_point(scene_pos, items)
                    if piece is not None and idx is not None and bb.canvas is not None:
                        slot = bb.canvas.item_slot.get(piece)
                        if slot is not None:
                            row, col = slot
                            marker = bb.canvas.marker_occupied.get((row, col, idx))
                            chips = list(bb.canvas.chip_occupied.get((row, col, idx), []))

                            # Use the same ordering as on the board:
                            # marker (if any), then circle chips by player order, then square chip.
                            def _chip_sort_key(chip: ChipItem) -> tuple[int, int]:
                                shape_rank = 0 if getattr(chip, "shape_kind", None) == "circle" else 1
                                color = (getattr(chip, "fill_color", "") or "").lower()
                                player_rank = getattr(bb, "_chip_player_rank", {}).get(color, 999)
                                return (shape_rank, player_rank)

                            ordered_chips = sorted(chips, key=_chip_sort_key)
                            figures = ([marker] if marker else []) + ordered_chips
                            if len(figures) >= 2:
                                bb._show_figures_tooltip(figures, view_pos)
                                return True
                elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.RightButton:
                    mgr = getattr(bb, "_tooltip_manager", None)
                    if mgr is not None and hasattr(mgr, "hide_custom"):
                        mgr.hide_custom()
                        return True
                    if bb._figures_tooltip_frame is not None and bb._figures_tooltip_frame.isVisible():
                        bb._figures_tooltip_frame.close()
                        bb._figures_tooltip_frame = None
                        return True
                return False

        return Filter(bb.view)

    def _show_figures_tooltip(self, figures: list, view_pos) -> None:
        """Show popup with figures at initial (full) size. Hide on right-release."""
        layout = QHBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        cell_sz = 36
        for fig in figures:
            pix = self._figure_to_pixmap(fig, cell_sz)
            lbl = QLabel()
            lbl.setPixmap(pix)
            layout.addWidget(lbl)
        content = QWidget()
        content.setLayout(layout)
        content.adjustSize()
        mgr = getattr(self, "_tooltip_manager", None)
        if mgr is not None and hasattr(mgr, "show_custom_content"):
            mgr.show_custom_content(content, self.view.viewport(), view_pos)
            return
        if self._figures_tooltip_frame is not None:
            self._figures_tooltip_frame.close()
        # Match ``HoverTooltipManager.show_custom_content`` + ``tooltip.qss`` (#roundedTooltip).
        outer = QFrame()
        outer.setObjectName("tooltipWindow")
        outer.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        outer.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner = QFrame(outer)
        inner.setObjectName("roundedTooltip")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.addWidget(content)
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(inner)
        outer.adjustSize()
        pos_global = self.view.viewport().mapToGlobal(view_pos)
        x = pos_global.x() + 12
        y = pos_global.y() + 12
        tw, th = outer.width(), outer.height()
        win = self.view.window()
        win_geom = QRect(win.mapToGlobal(QPoint(0, 0)), win.size()) if win is not None else QRect()
        screen = QApplication.primaryScreen().geometry() if QApplication.primaryScreen() else win_geom
        if x + tw > screen.right():
            x = pos_global.x() - tw - 12
        if y + th > screen.bottom():
            y = pos_global.y() - th - 12
        if win_geom.isValid():
            x = max(win_geom.left(), min(x, win_geom.right() - tw))
            y = max(win_geom.top(), min(y, win_geom.bottom() - th))
        outer.move(int(x), int(y))
        outer.show()
        self._figures_tooltip_frame = outer

    def _figure_to_pixmap(self, fig: ChipItem | MarkerItem, size: int) -> QPixmap:
        """Render figure at full size to pixmap."""
        if isinstance(fig, ChipItem):
            item = ChipItem(
                shape_kind=fig.shape_kind,
                color=fig.fill_color,
                question_mark=getattr(fig, "_question_mark", False),
            )
        else:
            item = MarkerItem(shape_kind=fig.shape_kind, color=fig.fill_color)
        # Render at home-bank scale so figures in the tooltip match their size in the marker/chip bank.
        item.setScale(MARKER_SCALE_HOME)
        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, size, size)
        scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
        scene.addItem(item)
        item.setPos(size / 2, size / 2)
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        # Match BoardView quality: enable antialiasing (and smooth transforms for safety)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        scene.render(painter, QRectF(0, 0, size, size), scene.sceneRect())
        painter.end()
        return pix

    def _relayout_hex_figures(self, row: int, col: int, cell_idx: int) -> None:
        """Position and scale figures (markers + chips) on a hex. 2: 1 row; 3: 2+1; 4: 2x2; 5: 2+2+1."""
        piece = self.canvas.occupied.get((row, col))
        if piece is None or not isinstance(piece, HexPiece) or cell_idx >= len(piece.cells):
            return
        cell = piece.cells[cell_idx]
        center_local = axial_to_pixel(cell.q, cell.r, HEX_SIZE)
        snap_center = piece.mapToScene(center_local)

        marker = self.canvas.marker_occupied.get((row, col, cell_idx))
        chips = list(self.canvas.chip_occupied.get((row, col, cell_idx), []))

        # Order figures on a hex as:
        #   marker (if any),
        #   circle chips in player order (Player 2 .. Player 5),
        #   then the square chip (at most one).
        def _chip_sort_key(chip: ChipItem) -> tuple[int, int]:
            shape_rank = 0 if getattr(chip, "shape_kind", None) == "circle" else 1
            color = (getattr(chip, "fill_color", "") or "").lower()
            player_rank = self._chip_player_rank.get(color, 999)
            return (shape_rank, player_rank)

        ordered_chips = sorted(chips, key=_chip_sort_key)
        figures = ([marker] if marker else []) + ordered_chips
        count = len(figures)
        if count == 0:
            return
        scale = marker_scale_canvas_for_hex_figure_count(count)
        if count == 1:
            f = figures[0]
            if hasattr(f, "setScale"):
                f.setScale(scale)
            f.setPos(snap_center)
            f.setZValue(5000)
            piece.stackBefore(f)
            return

        if count == 2:
            dx2 = 9.0
            offsets = [QPointF(-dx2, 0), QPointF(dx2, 0)]
        elif count == 3:
            dx3, dy3 = 7.0, 7.0
            offsets = [QPointF(-dx3, -dy3), QPointF(dx3, -dy3), QPointF(0, dy3)]
        elif count == 4:
            d4 = 7.0
            offsets = [
                QPointF(-d4, -d4), QPointF(d4, -d4),
                QPointF(-d4, d4), QPointF(d4, d4),
            ]
        else:
            dx5, dy5 = 7.0, 12.0
            offsets = [
                QPointF(-dx5, -dy5), QPointF(dx5, -dy5),
                QPointF(-dx5, 0), QPointF(dx5, 0),
                QPointF(0, dy5),
            ]
        for i, f in enumerate(figures):
            if i < len(offsets):
                pos = snap_center + offsets[i]
            else:
                pos = snap_center
            if hasattr(f, "setScale"):
                f.setScale(scale)
            f.setPos(pos)
            f.setZValue(5000)
            piece.stackBefore(f)

        # Ensure highlight overlay stays in sync when figures move on a highlighted hex
        if self.highlight_overlay is not None and getattr(self.canvas, "_show_highlights", True):
            self.highlight_overlay.update_highlights()

    def hide_structures_background_only(self) -> None:
        """Hide only the structures panel backdrop; labels / QStackedWidget row stay visible."""
        if self._structures_bg is not None:
            self._structures_bg.setVisible(False)

    def hide_structures_region(self) -> None:
        """Hide the structures background and the full label row (e.g. Play Hotseat)."""
        if self._structures_bg is not None:
            self._structures_bg.setVisible(False)
        if self._structures_row_proxy is not None:
            self._structures_row_proxy.setVisible(False)

    def show_structures_region(self) -> None:
        """Show the structures background and label row."""
        if self._structures_bg is not None:
            self._structures_bg.setVisible(True)
        if self._structures_row_proxy is not None:
            self._structures_row_proxy.setVisible(True)

    def set_chip_player_rank_for_hotseat(self, colors_hex: list[str]) -> None:
        """Order chips on hexes by player; used when chips come from sidebar drag (no bank)."""
        self._chip_player_rank = {}
        for i, h in enumerate(colors_hex):
            key = (h or "").lower()
            if key:
                self._chip_player_rank[key] = i

    def add_player_chips(
        self,
        players: int,
        colors_hex: list[str],
        player_names: Optional[list[str]] = None,
        *,
        first_player_has_chips: bool = False,
    ) -> None:
        """Create player chips (10 circles + 12 squares per player).
        Circles left, squares right. Chips hidden initially.

        By default Player 1 (index 0) has no chips (Deduction rules). Set
        ``first_player_has_chips=True`` for modes such as Play Hotseat where every
        player needs a chip color in the bank.
        """
        start_i = 0 if first_player_has_chips else 1
        self._chip_player_rank = {}
        for i in range(start_i, min(players, len(colors_hex))):
            color = (colors_hex[i] or "").lower()
            if color:
                self._chip_player_rank[color] = i

        for c in self.chips:
            if self.canvas:
                self.canvas.release_chip(c)
            self.scene.removeItem(c)
            c.deleteLater()
        self.chips.clear()
        for proxy in self._chip_labels:
            self.scene.removeItem(proxy)
            proxy.deleteLater()
        self._chip_labels.clear()

        chip_step_x = 0
        stack_gap = 45
        # Place chips in 2 rows: circle stacks (Could be), square stacks (No)
        chip_start_x =  9 + 12 + 110 + 30
        y_circles = self._structures_top + 24
        y_squares = self._structures_top + 76

        if self._structures_stacked is not None:
            self._structures_stacked.setCurrentIndex(1)

        for i in range(start_i, min(players, len(colors_hex))):
            hex_color = colors_hex[i] if i < len(colors_hex) else "#ffffff"
            # Row 1: circle stacks (Could be); Row 2: square stacks (No)
            col = i - start_i
            x_circles = chip_start_x + col * stack_gap
            x_squares = chip_start_x + col * stack_gap

            for j in range(10):
                chip = ChipItem(shape_kind="circle", color=hex_color)
                chip.set_canvas(self.canvas)
                pos = QPointF(x_circles + j * chip_step_x, y_circles)
                chip.setPos(pos)
                chip.set_home_pos(pos)
                chip.setZValue(MARKER_Z_BANK + j)
                chip.setVisible(False)
                self.scene.addItem(chip)
                self.chips.append(chip)
            for j in range(12):
                chip = ChipItem(shape_kind="square", color=hex_color)
                chip.set_canvas(self.canvas)
                pos = QPointF(x_squares + j * chip_step_x, y_squares)
                chip.setPos(pos)
                chip.set_home_pos(pos)
                chip.setZValue(MARKER_Z_BANK + j)
                chip.setVisible(False)
                self.scene.addItem(chip)
                self.chips.append(chip)

    def update_chip_label(self, index: int, text: str) -> None:
        """Update the player name label for chip row at index, if it exists.
        Index 0 (Player 1) has no chips, so skip."""
        if index <= 0 or index >= len(self._chip_labels) + 1:
            return
        proxy = self._chip_labels[index - 1]
        row = proxy.widget() if proxy else None
        if row is None:
            return
        lbl = row.findChild(QLabel, "chipPlayerLabel")
        if lbl is not None:
            lbl.setText(text or "")

    def set_marker_bank_home_shadow_enabled(self, enabled: bool) -> None:
        """Dimmed bank copies for structure markers: build mode only (not hotseat / simulation)."""
        if self.canvas is None:
            return
        cur = getattr(self.canvas, "_marker_bank_home_shadow_enabled", True)
        if cur == enabled:
            return
        for m in self.markers:
            m.prepareGeometryChange()
        self.canvas._marker_bank_home_shadow_enabled = enabled
        for m in self.markers:
            setattr(m, "_prev_bank_shadow_include", None)
            m.update()

    def show_chips(self) -> None:
        """Show player chips (after Start Simulation). Switches to Yes/No Chips mode."""
        self._chips_mode = True
        self.set_marker_bank_home_shadow_enabled(False)
        if self._structures_stacked is not None:
            self._structures_stacked.setCurrentIndex(1)
            self._structures_stacked.updateGeometry()
        if self._structures_row_proxy is not None:
            w = self._structures_row_proxy.widget()
            if w is not None:
                w.adjustSize()
        for proxy in self._chip_labels:
            proxy.setVisible(True)
        for c in self.chips:
            c.setVisible(True)

    def return_chips_to_home(self) -> None:
        """Return all chips to home position (keep visible, stay in chips mode)."""
        from board.markers import _grab_cursor
        for c in self.chips:
            if self.canvas:
                self.canvas.release_chip(c)
            c.setZValue(MARKER_Z_BANK)
            c.setScale(MARKER_SCALE_HOME)
            c.setPos(c._home_pos)
            c.setCursor(_grab_cursor())
            c.setVisible(True)

    def hide_chips(self) -> None:
        """Hide player chips and return to Structures mode."""
        self._chips_mode = False
        self.set_marker_bank_home_shadow_enabled(True)
        if self._structures_stacked is not None:
            self._structures_stacked.setCurrentIndex(0)
            self._structures_stacked.updateGeometry()
        if self._structures_row_proxy is not None:
            w = self._structures_row_proxy.widget()
            if w is not None:
                w.adjustSize()
        for proxy in self._chip_labels:
            proxy.setVisible(False)
        from board.markers import _grab_cursor
        for c in self.chips:
            if self.canvas:
                self.canvas.release_chip(c)
            c.setZValue(MARKER_Z_BANK)
            c.setScale(MARKER_SCALE_HOME)
            c.setPos(c._home_pos)
            c.setCursor(_grab_cursor())
            c.setVisible(False)

    def apply_marker_visibility(self, advanced_mode: bool) -> None:
        """Show/hide advanced markers based on advanced mode."""
        for m in self.markers:
            if not getattr(m, "advanced_only", False):
                continue
            if not advanced_mode:
                if self.canvas:
                    self.canvas.release_marker(m)
                m.setZValue(MARKER_Z_BANK)
                m.setScale(MARKER_SCALE_HOME)
                m.setPos(m._home_pos)
                m.setVisible(False)
            else:
                # Keep markers already on the canvas in place (e.g. black structures from map data)
                if self.canvas and m in self.canvas.marker_slot:
                    m.setVisible(True)
                else:
                    m.setZValue(MARKER_Z_BANK)
                    m.setScale(MARKER_SCALE_HOME)
                    m.setPos(m._home_pos)
                    m.setVisible(True)

    def clear_highlights(self) -> None:
        """Clear all piece highlights and update overlay."""
        for p in self.pieces:
            p.clear_highlight()
            p.update()
        for m in self.markers:
            m.update()
        if self.highlight_overlay:
            self.highlight_overlay.update_highlights()

    def reset_board(self) -> None:
        """Reset pieces, markers, and chips to initial state."""
        self.scene.clearSelection()
        if self.controller and hasattr(self.controller, "reset_state"):
            self.controller.reset_state()
        self.clear_highlights()
        self.hide_chips()
        for p in self.pieces:
            if self.canvas:
                self.canvas.release_item(p)
            p.setRotation(0)
            p.setPos(p._home_pos)
        for m in self.markers:
            if self.canvas:
                self.canvas.release_marker(m)
            m.setZValue(MARKER_Z_BANK)
            m.setScale(MARKER_SCALE_HOME)
            m.setPos(m._home_pos)

    def load_from_map_data(self, map_data: dict[str, Any], freeze: bool = True) -> None:
        """Load predefined map: place pieces and markers from map_data, optionally freeze."""
        self.clear_highlights()
        for p in self.pieces:
            if self.canvas:
                self.canvas.release_item(p)
            p.setRotation(0)
            p.setPos(p._home_pos)
        for m in self.markers:
            if self.canvas:
                self.canvas.release_marker(m)
            m.setZValue(MARKER_Z_BANK)
            m.setScale(MARKER_SCALE_HOME)
            m.setPos(m._home_pos)

        grid3x2 = map_data.get("grid3x2") or []
        default_grid = [["1", "2"], ["3", "4"], ["5", "6"]]
        for r in range(3):
            row_data = grid3x2[r] if r < len(grid3x2) else default_grid[r]
            for c in range(2):
                tile_id = (row_data[c] if c < len(row_data) else default_grid[r][c]).strip()
                if not tile_id:
                    continue
                piece_idx, rotated = parse_tile_id(tile_id)
                piece = self.pieces[piece_idx]
                piece.setRotation(180 if rotated else 0)
                pos = self.canvas.snap_pos_for_item_to_slot(piece, r, c)
                piece.setPos(pos)
                self.canvas.assign_item(piece, r, c)

        for struct in map_data.get("structures") or []:
            tile_id = struct.get("tileId") or ""
            slot = slot_for_tile_id(grid3x2, tile_id)
            if slot is None:
                continue
            row, col = slot
            piece = self.canvas.occupied.get((row, col))
            if piece is None:
                continue
            slot_tile_id = (grid3x2[row][col] if row < len(grid3x2) and col < len(grid3x2[row]) else "").strip().lower()
            piece_rotated_180 = slot_tile_id.endswith("t")
            for pl in struct.get("placements") or []:
                if not isinstance(pl, dict):
                    continue
                visual_row = pl.get("q", 0)
                visual_col = pl.get("r", 0)
                color = (pl.get("color") or "white").strip().lower()
                shape = (pl.get("shape") or "octagon").strip().lower()
                if shape not in ("circle", "triangle", "octagon"):
                    shape = "octagon"
                if shape == "circle":
                    shape = "octagon"
                cell_idx = cell_index_for_visual_row_col(
                    visual_row, visual_col, piece_rotated_180=piece_rotated_180
                )
                if cell_idx is None:
                    continue
                if not self.canvas.is_marker_cell_free(row, col, cell_idx):
                    continue
                hex_color = COLOR_NAME_TO_HEX.get(color, "#ffffff")
                marker = self._find_marker(shape, hex_color)
                if marker is None:
                    continue
                cell = piece.cells[cell_idx]
                center_local = axial_to_pixel(cell.q, cell.r, HEX_SIZE)
                center_scene = piece.mapToScene(center_local)
                marker.setPos(center_scene)
                marker.setScale(MARKER_SCALE_CANVAS)
                self.canvas.assign_marker(marker, row, col, cell_idx)
                marker.setZValue(5000)
                piece.stackBefore(marker)

        if freeze and self.cbFreezeMap:
            self.cbFreezeMap.setChecked(True)
            self.cbFreezeMap.setEnabled(True)

    def export_board_to_map_data(self) -> dict[str, Any]:
        """Export current board state (grid + markers) to map_data format. Used to save Build state."""
        from logic.map_builder import MapBuilder
        grid3x2: list[list[str]] = []
        for r in range(3):
            row_data: list[str] = []
            for c in range(2):
                item = self.canvas.occupied.get((r, c)) if self.canvas else None
                if item is None or item not in self.pieces:
                    # Empty slot: must not use default_grid tile ids — that would place every
                    # rack piece on load and duplicate the same piece_id across cells (last wins).
                    row_data.append("")
                    continue
                piece_idx = self.pieces.index(item)
                rotated = is_rotated_180(item.rotation())
                tile_id = str(piece_idx + 1) + ("t" if rotated else "")
                row_data.append(tile_id)
            grid3x2.append(row_data)
        structures: list[dict[str, Any]] = []
        slot_to_placements: dict[tuple[int, int], list[dict[str, Any]]] = {}
        if self.canvas:
            for m, slot in list(self.canvas.marker_slot.items()):
                if not isinstance(m, MarkerItem):
                    continue
                sr, sc, cell_idx = slot
                piece = self.canvas.occupied.get((sr, sc))
                if piece is None:
                    continue
                piece_rotated_180 = is_rotated_180(piece.rotation())
                rc = visual_row_col_for_cell_index(cell_idx, rotated_180=piece_rotated_180)
                if rc is None:
                    continue
                q, r = rc
                color_name = MapBuilder.COLOR_HEX_TO_NAME.get(
                    (m.fill_color or "").lower(), "white"
                )
                shape = m.shape_kind if m.shape_kind in ("circle", "triangle", "octagon") else "octagon"
                key = (sr, sc)
                if key not in slot_to_placements:
                    slot_to_placements[key] = []
                slot_to_placements[key].append({"q": q, "r": r, "color": color_name, "shape": shape})
        for (sr, sc), placements in slot_to_placements.items():
            if sr < len(grid3x2) and sc < len(grid3x2[sr]):
                tile_id = grid3x2[sr][sc]
                structures.append({"tileId": tile_id, "placements": placements})
        return {"grid3x2": grid3x2, "structures": structures}

    def _find_marker(self, shape_kind: str, fill_color: str) -> Optional[MarkerItem]:
        """Find first unused marker matching shape and color."""
        for m in self.markers:
            if not isinstance(m, MarkerItem):
                continue
            if m.shape_kind != shape_kind:
                continue
            if m.fill_color.lower() != fill_color.lower():
                continue
            if self.canvas and m in self.canvas.marker_slot:
                continue
            return m
        return None
