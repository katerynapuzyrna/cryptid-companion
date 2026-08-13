"""OR divider widget and blocky arrow pixmaps for the map chip strip."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class _OrDivider(QWidget):
    """Vertical line with 'OR' in a circle at the vertical center."""

    _LINE_COLOR = "#d6dde2"
    _TEXT_COLOR = "#5a6a72"
    _BG_COLOR = "#ffffff"
    _CIRCLE_R = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(36)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        r = float(self._CIRCLE_R)
        line_c = QColor(self._LINE_COLOR)
        pen = QPen(line_c, 1)
        p.setPen(pen)
        p.drawLine(int(cx), 0, int(cx), int(cy - r))
        p.drawLine(int(cx), int(cy + r), int(cx), h)
        p.setBrush(QBrush(QColor(self._BG_COLOR)))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor(self._TEXT_COLOR)))
        font = p.font()
        font.setPointSizeF(7.5)
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            QRectF(cx - r, cy - r, r * 2, r * 2),
            Qt.AlignmentFlag.AlignCenter,
            "OR",
        )
        p.end()


def _hotseat_additional_sharing_arrow_pixmap(width: int, height: int) -> QPixmap:
    """Blocky right arrow with rounded corners (shaft + head), matches Additional sharing row."""
    pix = QPixmap(width, height)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3A8BC1"))

    m = max(0.5, min(width, height) * 0.08)
    iw = width - 2.0 * m
    ih = height - 2.0 * m
    cy = height / 2.0

    shaft_w = iw * 0.48
    shaft_h = ih * 0.40
    tri_h = ih * 0.88
    rr = min(2.8, shaft_h * 0.24, iw * 0.09)

    x0 = m
    y_shaft_t = cy - shaft_h / 2.0
    shaft = QPainterPath()
    shaft.addRoundedRect(QRectF(x0, y_shaft_t, shaft_w, shaft_h), rr, rr)

    base_x = x0 + shaft_w - rr * 0.35
    tip_x = m + iw - 0.5
    y_top = cy - tri_h / 2.0
    y_bot = cy + tri_h / 2.0
    tip = QPointF(tip_x, cy)
    bt = QPointF(base_x, y_top)
    bb = QPointF(base_x, y_bot)
    tri_path = _hotseat_rounded_triangle_path(tip, bt, bb, min(rr, 2.4))

    combined = shaft.united(tri_path)
    p.drawPath(combined)
    p.end()
    return pix


def _hotseat_rounded_triangle_path(
    tip: QPointF, base_top: QPointF, base_bottom: QPointF, r: float
) -> QPainterPath:
    """CCW triangle tip → base_top → base_bottom with quadratic fillets at vertices."""
    pts = [tip, base_top, base_bottom]
    n = 3
    segs: list[tuple[QPointF, QPointF, QPointF]] = []
    for i in range(n):
        a = pts[(i - 1) % n]
        b = pts[i]
        c = pts[(i + 1) % n]
        abx = b.x() - a.x()
        aby = b.y() - a.y()
        bcx = c.x() - b.x()
        bcy = c.y() - b.y()
        la = math.hypot(abx, aby)
        lc = math.hypot(bcx, bcy)
        if la < 1e-6 or lc < 1e-6:
            continue
        v1 = QPointF(abx / la, aby / la)
        v2 = QPointF(bcx / lc, bcy / lc)
        cos_turn = max(-1.0, min(1.0, -v1.x() * v2.x() - v1.y() * v2.y()))
        ang = math.acos(cos_turn)
        if ang < 1e-4:
            continue
        tan_h = math.tan(ang / 2.0)
        if tan_h < 1e-6:
            continue
        d = min(r / tan_h, la * 0.48, lc * 0.48)
        p1 = QPointF(b.x() - v1.x() * d, b.y() - v1.y() * d)
        p2 = QPointF(b.x() + v2.x() * d, b.y() + v2.y() * d)
        segs.append((p1, b, p2))

    path = QPainterPath()
    if not segs:
        path.moveTo(tip)
        path.lineTo(base_top)
        path.lineTo(base_bottom)
        path.closeSubpath()
        return path

    path.moveTo(segs[0][0])
    for p1, b, p2 in segs:
        path.quadTo(b, p2)
    path.closeSubpath()
    return path


def _hotseat_arrow_right_label() -> QLabel:
    """Right-arrow for Additional sharing (custom rounded block arrow, not theme SP_ArrowRight)."""
    w, h = 24, 22
    lab = QLabel()
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setPixmap(_hotseat_additional_sharing_arrow_pixmap(w, h))
    lab.setFixedSize(w, h)
    return lab
