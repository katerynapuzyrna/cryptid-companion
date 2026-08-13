"""Textured terrain painting for hex cells. Use when TEXTURED_HEX_FILL is True."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal, Dict

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QBrush,
    QPen,
    QPainter,
    QPainterPath,
    QRadialGradient,
    QLinearGradient,
    QImage,
    QPixmap,
)

Terrain = Literal["forest", "desert", "swamp", "mountain", "sea"]


# -----------------------------
# Shared texture cache (grain)
# -----------------------------

def _make_grain_pixmap(size: int = 32, strength: int = 18, alpha: int = 40, seed: int = 12345) -> QPixmap:
    """
    A tiny tiled noise texture used across all terrains to unify the style.
    """
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)

    rng = random.Random(seed)
    for y in range(size):
        for x in range(size):
            v = 128 + rng.randint(-strength, strength)
            v = max(0, min(255, v))
            img.setPixelColor(x, y, QColor(v, v, v, alpha))

    return QPixmap.fromImage(img)


_GRAIN_CACHE: QPixmap | None = None


def _get_grain() -> QPixmap:
    """Lazy-initialize grain texture (requires QGuiApplication to exist)."""
    global _GRAIN_CACHE
    if _GRAIN_CACHE is None:
        _GRAIN_CACHE = _make_grain_pixmap(size=32, strength=18, alpha=40, seed=12345)
    return _GRAIN_CACHE


# -----------------------------
# Style config
# -----------------------------

@dataclass(frozen=True)
class TerrainStyle:
    light: str
    mid: str
    dark: str

    grain_opacity: float = 0.12
    grain_strength_hint: str = "default"  # for you, if you want variants

    gloss_opacity_top: float = 0.16
    gloss_enabled: bool = True


STYLES: Dict[Terrain, TerrainStyle] = {
    # Greens
    "forest": TerrainStyle(
        light="#6AE7A2",
        mid="#2FAE66",
        dark="#1C6F44",
        grain_opacity=0.14,
        gloss_opacity_top=0.16,
    ),
    # Sand
    "desert": TerrainStyle(
        light="#FFE08A",
        mid="#F1C86A",
        dark="#D7A94E",
        grain_opacity=0.10,
        gloss_opacity_top=0.14,
    ),
    # Purple swamp (per your request)
    "swamp": TerrainStyle(
        light="#D0C1F7",
        mid="#8266C6",
        dark="#3A2D66",
        grain_opacity=0.13,
        gloss_opacity_top=0.14,
    ),
    # Stone
    "mountain": TerrainStyle(
        light="#D7DADF",
        mid="#9AA2AD",
        dark="#5F6670",
        grain_opacity=0.16,
        gloss_opacity_top=0.12,
    ),
    # Water
    "sea": TerrainStyle(
        light="#6DB6FF",
        mid="#2E86E6",
        dark="#1E5FAE",
        grain_opacity=0.08,
        gloss_opacity_top=0.14,
    ),
}


# -----------------------------
# Core shading building blocks
# -----------------------------

def _bevel_brush(rect: QRectF, c_light: str, c_mid: str, c_dark: str) -> QBrush:
    """
    Volumetric look: radial gradient with focal point shifted top-left.
    """
    center = rect.center()
    radius = max(rect.width(), rect.height()) * 0.65
    focus = center - QPointF(radius * 0.25, radius * 0.25)  # light from top-left
    g = QRadialGradient(center, radius, focus)
    g.setColorAt(0.00, QColor(c_light))
    g.setColorAt(0.55, QColor(c_mid))
    g.setColorAt(1.00, QColor(c_dark))
    return QBrush(g)


def _gloss_brush(rect: QRectF, opacity_top: float) -> QBrush:
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    c1 = QColor("#FFFFFF"); c1.setAlphaF(opacity_top)
    c2 = QColor("#FFFFFF"); c2.setAlphaF(0.0)
    g.setColorAt(0.0, c1)
    g.setColorAt(0.65, c2)
    return QBrush(g)


def _tile_grain(p: QPainter, rect: QRectF, opacity: float):
    p.save()
    p.setOpacity(opacity)
    p.setCompositionMode(QPainter.CompositionMode_SoftLight)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_get_grain()))
    p.drawRect(rect.adjusted(-2, -2, 2, 2))
    p.restore()


# -----------------------------
# Terrain detail overlays
# -----------------------------

def _draw_forest_spots(p: QPainter, rect: QRectF, seed: int):
    rng = random.Random(seed)
    p.save()
    p.setPen(Qt.NoPen)

    # Tree-like dots: dark trunk base + rounded canopy on top (top-down view: canopy = tree crown)
    # Dark trunks (small vertical streaks)
    trunk = QColor("#0F3D25")
    trunk.setAlphaF(0.18)
    p.setBrush(QBrush(trunk))
    for _ in range(14):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        rx = 0.4 + rng.random() * 0.6
        ry = 0.8 + rng.random() * 1.4
        p.drawEllipse(QPointF(cx, cy), rx, ry)

    # Canopy blobs (round tree crowns - larger, layered)
    dark = QColor("#0F3D25")
    dark.setAlphaF(0.14)
    mid = QColor("#1C6F44")
    mid.setAlphaF(0.10)
    light = QColor("#BFF6D7")
    light.setAlphaF(0.08)
    for i in range(18):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        r = 1.2 + rng.random() * 2.8
        col = dark if i % 4 == 0 else (mid if i % 4 == 1 else light)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(cx, cy), r, r * 0.9)

    p.restore()


def _draw_desert_dunes(p: QPainter, rect: QRectF, seed: int):
    rng = random.Random(seed)
    p.save()
    p.setPen(Qt.NoPen)

    # Fine sand speckles (many tiny dots)
    speck = QColor("#CFA04E")
    speck.setAlphaF(0.12)
    p.setBrush(QBrush(speck))
    for _ in range(35):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        r = 0.25 + rng.random() * 0.6
        p.drawEllipse(QPointF(cx, cy), r, r * 0.85)

    # Subtle sand ripples / drifts (soft ellipses)
    drift = QColor("#B8925A")
    drift.setAlphaF(0.08)
    p.setBrush(QBrush(drift))
    for _ in range(8):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        rx = 2.5 + rng.random() * 4.0
        ry = 1.0 + rng.random() * 2.0
        p.drawEllipse(QPointF(cx, cy), rx, ry)

    # Dune ridges (wave curves)
    c = QColor("#CFA04E")
    c.setAlphaF(0.10)
    pen = QPen(c, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    for k in range(-2, 9):
        y = rect.top() + k * 3.2
        path = QPainterPath()
        path.moveTo(rect.left() - 4, y)
        path.cubicTo(rect.left() + 6, y - 2, rect.right() - 6, y + 2, rect.right() + 4, y)
        p.drawPath(path)

    p.restore()


def _draw_swamp_blobs(p: QPainter, rect: QRectF, seed: int):
    rng = random.Random(seed)

    p.save()
    p.setPen(Qt.NoPen)

    # dark water pools
    base = QColor("#1E2433"); base.setAlphaF(0.22)
    p.setBrush(QBrush(base))
    for _ in range(6):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        rx = 2.3 + rng.random() * 3.6
        ry = 1.9 + rng.random() * 3.0
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), rx, ry)
        p.drawPath(path)

    # tiny water highlights
    p.setCompositionMode(QPainter.CompositionMode_Screen)
    hl = QColor("#FFFFFF"); hl.setAlphaF(0.10)
    p.setBrush(QBrush(hl))
    for _ in range(4):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        rx = 1.0 + rng.random() * 1.8
        ry = 0.6 + rng.random() * 1.2
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), rx, ry)
        p.drawPath(path)

    # muted green tufts
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    tuft = QColor("#3B7F55"); tuft.setAlphaF(0.16)
    p.setBrush(QBrush(tuft))
    for _ in range(7):
        cx = rect.left() + rng.random() * rect.width()
        cy = rect.top() + rng.random() * rect.height()
        r = 1.4 + rng.random() * 2.2
        p.drawEllipse(QPointF(cx, cy), r, r * 0.85)

    p.restore()


def _draw_mountain_cracks(p: QPainter, rect: QRectF, seed: int):
    rng = random.Random(seed)
    p.save()

    c = QColor("#2F3640")
    c.setAlphaF(0.14)
    pen = QPen(c, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    # More veins: main cracks (longer, more segments)
    for _ in range(14):
        x = rect.left() + rng.random() * rect.width()
        y = rect.top() + rng.random() * rect.height()
        path = QPainterPath(QPointF(x, y))
        for _ in range(4 + rng.randint(0, 3)):
            x += (-1 + rng.random() * 2) * 3.5
            y += (-1 + rng.random() * 2) * 2.8
            x = max(rect.left(), min(rect.right(), x))
            y = max(rect.top(), min(rect.bottom(), y))
            path.lineTo(QPointF(x, y))
        p.drawPath(path)

    # Extra fine branching veins (shorter)
    c.setAlphaF(0.10)
    pen = QPen(c, 0.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    for _ in range(10):
        x = rect.left() + rng.random() * rect.width()
        y = rect.top() + rng.random() * rect.height()
        path = QPainterPath(QPointF(x, y))
        for _ in range(2):
            x += (-1 + rng.random() * 2) * 2.5
            y += (-1 + rng.random() * 2) * 2.0
            x = max(rect.left(), min(rect.right(), x))
            y = max(rect.top(), min(rect.bottom(), y))
            path.lineTo(QPointF(x, y))
        p.drawPath(path)

    p.restore()


def _draw_sea_waves(p: QPainter, rect: QRectF, alpha: float = 0.10, step: float = 4.3):
    p.save()
    c = QColor("#FFFFFF"); c.setAlphaF(alpha)
    pen = QPen(c, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)

    y = rect.top() + 2
    i = 0
    while y < rect.bottom() - 1:
        amp = 0.8 + (i % 3) * 0.25
        path = QPainterPath()
        x0 = rect.left() - 2
        path.moveTo(x0, y)
        x = x0
        while x < rect.right() + 2:
            path.quadTo(x + 1.5, y - amp, x + 3.0, y)
            path.quadTo(x + 4.5, y + amp, x + 6.0, y)
            x += 6.0
        p.drawPath(path)
        y += step
        i += 1

    p.restore()


# -----------------------------
# Public API
# -----------------------------

def paint_terrain(
    p: QPainter,
    shape: QPainterPath,
    terrain: Terrain,
    *,
    seed: int = 0,
    outline: bool = False,
    outline_color: str = "#24323A",
    outline_width: float = 1.2,
):
    """
    Paint a single terrain inside any shape path (hex/triangle/octagon/etc).

    - terrain: "forest" | "desert" | "swamp" | "mountain" | "sea"
    - seed: use different per-tile seeds so patterns don't repeat (e.g. tile index)
    - outline: optional border, off by default (your current style often uses no border)
    """
    style = STYLES[terrain]
    rect = shape.boundingRect()

    p.setRenderHint(QPainter.Antialiasing, True)

    p.save()
    p.setClipPath(shape)

    # 1) base bevel
    p.setPen(Qt.NoPen)
    p.setBrush(_bevel_brush(rect, style.light, style.mid, style.dark))
    p.drawPath(shape)

    # 2) shared grain
    _tile_grain(p, rect, opacity=style.grain_opacity)

    # 3) terrain-specific micro details
    if terrain == "forest":
        _draw_forest_spots(p, rect, seed=seed + 101)
    elif terrain == "desert":
        _draw_desert_dunes(p, rect, seed=seed + 202)
    elif terrain == "swamp":
        _draw_swamp_blobs(p, rect, seed=seed + 303)
    elif terrain == "mountain":
        _draw_mountain_cracks(p, rect, seed=seed + 505)
    elif terrain == "sea":
        _draw_sea_waves(p, rect, alpha=0.10, step=4.3)

    # 4) subtle shared gloss
    if style.gloss_enabled:
        p.setCompositionMode(QPainter.CompositionMode_Screen)
        p.setOpacity(1.0)
        p.setPen(Qt.NoPen)
        p.setBrush(_gloss_brush(rect, opacity_top=style.gloss_opacity_top))
        p.drawRoundedRect(
            QRectF(rect.left() - 2, rect.top() - 2, rect.width() + 4, rect.height() * 0.55),
            rect.width() * 0.25,
            rect.width() * 0.25,
        )

    p.restore()

    # optional outline (outside clip so it stays crisp)
    if outline:
        pen = QPen(QColor(outline_color), outline_width)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(shape)


# -----------------------------
# Hex color -> terrain mapping (for piece cells)
# -----------------------------

# Map hex color strings used in piece definitions to terrain names.
# Factory uses: #7aa8ff (blue), #bdbdbd (gray), #f2d25a (yellow), #7fb26c (green), #6a5875 (purple)
COLOR_HEX_TO_TERRAIN: dict[str, Terrain] = {
    "#7aa8ff": "sea",
    "#107dc2": "sea",
    "#bdbdbd": "mountain",
    "#9a9899": "mountain",
    "#f2d25a": "desert",
    "#d9b009": "desert",
    "#7fb26c": "forest",
    "#0b9539": "forest",
    "#6a5875": "swamp",
    "#3b173d": "swamp",
}


def color_hex_to_terrain(color_hex: str) -> Terrain | None:
    """
    Map a hex color string (e.g. from Cell.color) to a terrain name.
    Returns None if the color has no terrain mapping (caller should use flat fill).
    """
    c = color_hex.strip().lower()
    return COLOR_HEX_TO_TERRAIN.get(c, None)
