"""Turn-order status dot (Active / Waiting / Done)."""
from enum import Enum, auto

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap

from .constants import _STATUS_BLUE, _STATUS_GREEN


class _TurnStatus(Enum):
    ACTIVE = auto()
    WAITING = auto()
    DONE = auto()


def _status_dot_pixmap(kind: _TurnStatus, diameter: int = 14) -> QPixmap:
    pix = QPixmap(diameter, diameter)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    blue = QColor(_STATUS_BLUE)
    green = QColor(_STATUS_GREEN)
    r = diameter / 2.0
    cx, cy = r, r
    if kind is _TurnStatus.ACTIVE:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(blue))
        p.drawEllipse(1, 1, diameter - 2, diameter - 2)
    elif kind is _TurnStatus.WAITING:
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(blue, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawEllipse(2, 2, diameter - 4, diameter - 4)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(green))
        p.drawEllipse(1, 1, diameter - 2, diameter - 2)
    p.end()
    return pix
