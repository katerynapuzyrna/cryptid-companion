"""Shared theme colors and radii for code and QSS consistency."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen

# ---- Colors (hex strings for QSS, QColor for painting) ----
BORDER = "#d6dde2"
BACKGROUND_LIGHT = "#ffffff"
BACKGROUND_CARD = "#f9fbfc"
GRAY_MUTED = "#808080"
HIGHLIGHT = "#00aa00"

# QColor instances for QPainter
BORDER_Q = QColor(BORDER)
BACKGROUND_LIGHT_Q = QColor(BACKGROUND_LIGHT)
GRAY_MUTED_Q = QColor(GRAY_MUTED)
HIGHLIGHT_Q = QColor(HIGHLIGHT)

# ---- Radii ----
SCROLLBAR_HANDLE_RADIUS = 5
CANVAS_RADIUS = 12
TOOLTIP_TOAST_RADIUS = 8

# ---- Pre-built pens for common use ----
PEN_BORDER = QPen(BORDER_Q, 1)
PEN_BORDER_COSMETIC = QPen(BORDER_Q, 1)
PEN_BORDER_COSMETIC.setCosmetic(True)
PEN_BORDER_DASHED = QPen(BORDER_Q, 0.5, Qt.PenStyle.DashLine)
PEN_BORDER_DASHED.setCosmetic(True)
PEN_LABEL = QPen(GRAY_MUTED_Q, 1)
PEN_HIGHLIGHT = QPen(HIGHLIGHT_Q, 4.0, Qt.PenStyle.SolidLine)
PEN_HIGHLIGHT.setCosmetic(True)
