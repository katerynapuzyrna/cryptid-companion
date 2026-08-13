"""Player color combobox helpers (Deduction mode and map cards)."""
from PySide6.QtWidgets import QComboBox, QToolButton
from PySide6.QtCore import Qt, QObject, QEvent, QSize, QRect, QRectF
from PySide6.QtGui import (
    QFont,
    QPixmap,
    QIcon,
    QColor,
    QPainter,
    QPen,
    QBrush,
    QPainterPath,
    QRadialGradient,
)

from settings.theme import PEN_BORDER


PLAYER_COLORS: list[tuple[str, str]] = [
    ("light green", "#2ecc71"),
    ("light blue", "#5dade2"),
    ("purple", "#9b59b6"),
    ("orange", "#e67e22"),
    ("red", "#e74c3c"),
]


def get_colored_square_pixmap(color_hex: str, size: int = 14, grayed: bool = False) -> QPixmap:
    """Return brush-stroke color pixmap (deduction panels / clues; comboboxes use meeple icons).
    If grayed=True, use a desaturated blend with gray for inactive state."""
    return _colored_square_icon(color_hex, size, grayed).pixmap(QSize(size, size))


def _colored_square_icon(color_hex: str, size: int = 14, grayed: bool = False) -> QIcon:
    """Create a QIcon with brush-stroke style color swatches for combo items."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    c = QColor(color_hex)
    if grayed:
        gray = QColor("#9e9e9e")
        c = QColor(
            int(c.red() * 0.4 + gray.red() * 0.6),
            int(c.green() * 0.4 + gray.green() * 0.6),
            int(c.blue() * 0.4 + gray.blue() * 0.6),
        )
    stroke_w = 3.0
    pen = QPen(c, stroke_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    s = size

    def stroke(x0: float, y0: float, x1: float, y1: float, ctrl_x: float, ctrl_y: float) -> None:
        p = QPainterPath()
        p.moveTo(x0, y0)
        p.quadTo(ctrl_x, ctrl_y, x1, y1)
        painter.drawPath(p)

    stroke(1, s - 2, s - 2, 2, 2, 4)
    stroke(2, 3, s - 3, s - 2, s // 2, s // 2)
    stroke(s - 2, 4, 4, s - 3, 6, 6)
    painter.end()
    icon = QIcon(pix)
    icon.addPixmap(pix, QIcon.Mode.Disabled, QIcon.State.Off)
    return icon


def setup_player_color_combo(combo: QComboBox) -> None:
    """Populate combo: empty first (index 0), then (meeple icon) (color name). Initially empty."""
    combo.clear()
    _icon_px = 18
    combo.setIconSize(QSize(_icon_px, _icon_px))
    combo.addItem("<Select color>")
    for name, _hex in PLAYER_COLORS:
        combo.addItem(get_color_icon(name, _icon_px), name)
    combo.setCurrentIndex(0)
    sync_combo_placeholder_style(combo)


def _get_selected_color(combo: QComboBox) -> str:
    """Return the selected color name, or empty string if none."""
    if combo.currentIndex() <= 0:
        return ""
    txt = (combo.currentText() or "").strip()
    return txt if txt in [c[0] for c in PLAYER_COLORS] else ""


def get_color_icon(color_name: str, size: int = 18) -> QIcon:
    """Meeple icon from ``icons/players`` for color name; empty QIcon if not found.

    The same pixmap is registered for Normal and Disabled (and Active/Selected) so
    QComboBox in disabled state does not gray the meeple (deduction/build modes).
    """
    if not get_player_meeple_resource(color_name):
        return QIcon()
    pix = get_player_meeple_pixmap(color_name, size)
    if pix.isNull():
        return QIcon()
    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Disabled,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        icon.addPixmap(pix, mode, QIcon.State.Off)
        icon.addPixmap(pix, mode, QIcon.State.On)
    return icon


def get_selected_player_color(combo: QComboBox) -> str:
    """Return the selected color name for the combo, or empty string if none."""
    return _get_selected_color(combo)


def get_player_color_hex(color_name: str) -> str:
    """Return hex color for a player color name, or #ffffff if not found."""
    for name, hex_color in PLAYER_COLORS:
        if name == color_name:
            return hex_color
    return "#ffffff"


def get_player_meeple_resource(color_name: str) -> str:
    """Qt resource path (:/...) for ``assets/icons/players/{color}.svg``, or empty if unknown."""
    for name, _ in PLAYER_COLORS:
        if name == color_name:
            return f":/assets/icons/players/{name}.svg"
    return ""


def get_player_meeple_icon(color_name: str) -> QIcon:
    """Player meeple SVG from ``icons/players``; empty QIcon if color name is unknown."""
    path = get_player_meeple_resource(color_name)
    return QIcon(path) if path else QIcon()


def get_player_meeple_pixmap(color_name: str, size: int = 20) -> QPixmap:
    """Rasterized meeple icon at ``size``×``size``, or a transparent pixmap if unknown."""
    icon = get_player_meeple_icon(color_name)
    if icon.isNull():
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        return pix
    return icon.pixmap(QSize(size, size))


def _player_chip_base_color(color_name: str) -> QColor:
    if not get_player_meeple_resource(color_name):
        return QColor("#98a4ac")
    return QColor(get_player_color_hex(color_name))


def _player_chip_gradient_brush(r: QRectF, base: QColor) -> QBrush:
    """Same volumetric radial fill as ``ChipItem`` on the board."""
    cx = r.center().x()
    cy = r.center().y()
    radius = max(r.width(), r.height()) / 2
    grad = QRadialGradient(cx, cy, radius, cx - 3, cy - 3, 0)
    grad.setColorAt(0, base.lighter(140))
    grad.setColorAt(0.6, base)
    grad.setColorAt(1, base.darker(120))
    return QBrush(grad)


def get_player_circle_chip_pixmap(color_name: str, size: int = 20) -> QPixmap:
    """Circle chip in the player's color (hotseat Search; matches board circle chip look)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = max(1.0, float(size) * 0.06)
    r = QRectF(margin, margin, float(size) - 2 * margin, float(size) - 2 * margin)
    base = _player_chip_base_color(color_name)
    p.setPen(PEN_BORDER)
    p.setBrush(_player_chip_gradient_brush(r, base))
    p.drawEllipse(r)
    p.end()
    return pix


def get_player_square_chip_pixmap(color_name: str, size: int = 20) -> QPixmap:
    """Square chip in the player's color (hotseat Sharing hint; matches board square chip look)."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = max(1.0, float(size) * 0.06)
    r = QRectF(margin, margin, float(size) - 2 * margin, float(size) - 2 * margin)
    base = _player_chip_base_color(color_name)
    p.setPen(PEN_BORDER)
    p.setBrush(_player_chip_gradient_brush(r, base))
    p.drawRect(r)
    p.end()
    return pix


def get_player_question_chip_pixmap(color_name: str, size: int = 20) -> QPixmap:
    """Circle chip in the player's color with a white «?» (hotseat Question / ask-player hint)."""
    pix = get_player_circle_chip_pixmap(color_name, size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(max(8, int(round(size * 0.52))))
    p.setFont(font)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "?")
    p.end()
    return pix


def assign_colors_to_empty_combos(combos: list[QComboBox], player_count: int) -> None:
    """
    Assign available colors to any combo in range(player_count) that has no selection.
    No color repeats; uses remaining colors from PLAYER_COLORS.
    Call refresh_player_color_combos after this to sync dropdowns.
    """
    color_names = [c[0] for c in PLAYER_COLORS]
    selected = set()
    empty_indices: list[int] = []
    for i in range(min(player_count, len(combos))):
        cb = combos[i]
        if cb is None:
            continue
        c = _get_selected_color(cb)
        if c:
            selected.add(c)
        else:
            empty_indices.append(i)
    available = [n for n in color_names if n not in selected]
    for idx, combo_idx in enumerate(empty_indices):
        if idx >= len(available):
            break
        cb = combos[combo_idx]
        if cb is None:
            continue
        color_name = available[idx]
        if cb.findText(color_name) >= 0:
            cb.blockSignals(True)
            cb.setCurrentIndex(cb.findText(color_name))
            cb.blockSignals(False)
            sync_combo_placeholder_style(cb)
            sync_clear_button_visibility(cb)
    if empty_indices:
        refresh_player_color_combos(combos)


def refresh_player_color_combos(combos: list[QComboBox]) -> None:
    """
    Update all color combos so each shows only colors not selected by other players.
    When a color is selected for one player, it disappears from other players' dropdowns.
    """
    for i, combo in enumerate(combos):
        if combo is None:
            continue
        my_color = _get_selected_color(combo)
        other_selected = set()
        for j, other in enumerate(combos):
            if other is not None and j != i:
                c = _get_selected_color(other)
                if c:
                    other_selected.add(c)
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("<Select color>")
        _icon_px = int(combo.iconSize().width()) if combo.iconSize().width() > 0 else 18
        for name, _hex in PLAYER_COLORS:
            if name not in other_selected:
                combo.addItem(get_color_icon(name, _icon_px), name)
        if my_color and my_color not in other_selected:
            idx = combo.findText(my_color)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        sync_combo_placeholder_style(combo)
        sync_clear_button_visibility(combo)


_COMBO_ARROW_WIDTH = 24


def _position_clear_button(combo: QComboBox, btn: QToolButton) -> None:
    """Position clear button inside combo, to the left of the dropdown arrow."""
    w, h = combo.width(), combo.height()
    btn_w, btn_h = 22, 22
    x = w - _COMBO_ARROW_WIDTH - btn_w - 12
    y = (h - btn_h) // 2
    btn.setGeometry(x, y, btn_w, btn_h)


class _ComboClearButtonFilter(QObject):
    """Event filter: reposition clear button on resize; hide when combo is disabled."""

    def __init__(self, combo: QComboBox, btn: QToolButton):
        super().__init__(combo)
        self._combo = combo
        self._btn = btn

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._combo:
            return False
        if event.type() == QEvent.Type.Resize:
            _position_clear_button(self._combo, self._btn)
        elif event.type() == QEvent.Type.EnabledChange:
            sync_clear_button_visibility(self._combo)
        return False


_CLEAR_BTN_OBJECT_NAME = "comboClearBtn"


def sync_combo_placeholder_style(combo: QComboBox) -> None:
    """Update placeholder property so stylesheet applies placeholder color (matches text boxes)."""
    if combo is None:
        return
    combo.setProperty("isPlaceholder", combo.currentIndex() == 0)
    style = combo.style()
    if style is not None:
        style.unpolish(combo)
        style.polish(combo)


def sync_clear_button_visibility(combo: QComboBox) -> None:
    """Show/hide the clear button based on combo's current index and enabled state. Call after programmatic changes."""
    btn = combo.findChild(QToolButton, _CLEAR_BTN_OBJECT_NAME)
    if btn is not None:
        if combo.isEnabled() and combo.currentIndex() > 0:
            _position_clear_button(combo, btn)
            btn.raise_()
            btn.show()
        else:
            btn.hide()


def add_clear_button_inside_combo(combo: QComboBox) -> None:
    """
    Add a clear (X) button inside the combobox, to the left of the dropdown arrow.
    The button appears only when a color is selected.
    """
    clear_btn = QToolButton(combo)
    clear_btn.setObjectName(_CLEAR_BTN_OBJECT_NAME)
    clear_btn.setIcon(QIcon(":/assets/icons/close.svg"))
    clear_btn.setFixedSize(22, 22)
    clear_btn.setToolTip("")
    clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    clear_btn.hide()

    def on_index_changed(index: int) -> None:
        sync_clear_button_visibility(combo)
        sync_combo_placeholder_style(combo)

    def on_clear_clicked() -> None:
        combo.setCurrentIndex(0)

    clear_btn.clicked.connect(on_clear_clicked)
    combo.currentIndexChanged.connect(on_index_changed)

    combo.installEventFilter(_ComboClearButtonFilter(combo, clear_btn))
    _position_clear_button(combo, clear_btn)
    sync_combo_placeholder_style(combo)
