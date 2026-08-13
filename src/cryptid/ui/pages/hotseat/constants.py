"""Hotseat UI tuning constants (map scale, chip sizes, proxy Z-order)."""
from board.markers import MARKER_SCALE_HOME
from settings.config import MARKER_SIZE

# Match map canvas: MARKER_SCALE_HOME × 1.0 (same as MARKER_SCALE_CANVAS multiplier on the board).
_HOTSEAT_VIEW_SCALE = 1.0
_HOTSEAT_CHIP_HOME_PX = int(
    round(MARKER_SIZE * 2 * MARKER_SCALE_HOME * _HOTSEAT_VIEW_SCALE)
)
# Map chip strip uses the same multiplier as the sidebar bank.
_HOTSEAT_MAP_CHIP_STRIP_VIEW_SCALE = 1.0
_HOTSEAT_MAP_CHIP_STRIP_CHIP_HOME_PX = int(
    round(MARKER_SIZE * 2 * MARKER_SCALE_HOME * _HOTSEAT_MAP_CHIP_STRIP_VIEW_SCALE)
)
_HOTSEAT_CHIP_MIME = "application/x-cryptid-hotseat-chip"
_HOTSEAT_QPICK_PROXY_Z = 16000
# Single Question-row chip: solid neutral gray on the map (matches unknown-player chip tone).
_HOTSEAT_QUESTION_CHIP_HEX = "#98a4ac"
# Circular meeple-picker: distance from chip center to button center (scene px).
_HOTSEAT_QPICK_RING_RADIUS = 40
_HOTSEAT_QPICK_MEEPLE_ICON_PX = 29
_HOTSEAT_QPICK_MEEPLE_BTN_PX = 36
_HOTSEAT_QPICK_ACTION_ICON_PX = 29
# Map chip strip: scene proxy, fixed on-screen size (ItemIgnoresTransformations); below question picker in Z.
_HOTSEAT_MAP_CHIP_STRIP_PROXY_Z = 12000
_HOTSEAT_MAP_CHIP_STRIP_GAP_SCENE = 8
# Padding below the strip inside the viewport (px); too small clips content (proxy / DPI).
_HOTSEAT_MAP_CHIP_STRIP_VIEWPORT_GAP_PX = 16
# Padding inside the viewport when centering the canvas (scene px at 1:1); avoids the canvas
# rounded-rect stroke sitting on the last pixel beside the viewport edge.
_HOTSEAT_VIEW_MAP_INSET_PX = 8
# Margins between the QGraphicsView widget edge (incl. QSS border) and the viewport; keeps the
# scene from painting under the outer frame so the canvas border is not overlapped by the view border.
_HOTSEAT_VIEW_VIEWPORT_FRAME_MARGIN_PX = 0

_QWIDGETSIZE_MAX = 16777215

# Turn-status dots (Active / Waiting / Done)
_STATUS_BLUE = "#3498db"
_STATUS_GREEN = "#2ecc71"
_TURN_STATUS_DOT_PX = 16
# Extra width beyond font metrics so status words are not clipped by style/DPI.
_TURN_STATUS_LABEL_PAD = 14
