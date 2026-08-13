from PySide6.QtCore import QPointF
import math
from settings.config import GRID_ROT_RAD, GRID_ROT_DEG

def rotate_point(p: QPointF, rad: float) -> QPointF:
    c = math.cos(rad); s = math.sin(rad)
    return QPointF(p.x() * c - p.y() * s, p.x() * s + p.y() * c)

def rotate_about(p: QPointF, origin: QPointF, rad: float) -> QPointF:
    v = QPointF(p.x() - origin.x(), p.y() - origin.y())
    vr = rotate_point(v, rad)
    return QPointF(vr.x() + origin.x(), vr.y() + origin.y())

def axial_to_pixel(q: int, r: int, size: float) -> QPointF:
    x = size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
    y = size * (3 / 2 * r)
    return rotate_point(QPointF(x, y), GRID_ROT_RAD)

def hex_polygon(center: QPointF, size: float):
    pts = []
    for i in range(6):
        angle = math.radians(60 * i - 30 + GRID_ROT_DEG)
        pts.append(QPointF(center.x() + size * math.cos(angle),
                           center.y() + size * math.sin(angle)))
    return pts
