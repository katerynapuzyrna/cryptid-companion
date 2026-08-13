"""Blurred placeholder text rendering for map card clue overlays."""
from PySide6.QtCore import Qt, QRectF, QRect
from PySide6.QtGui import QImage, QPixmap, QColor, QPainter, QTextOption
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsBlurEffect,
)


_BLUR_TEXT_PIXMAP_CACHE: dict[tuple, QPixmap] = {}


def _font_cache_key(font) -> tuple:
    """Key for caching pixmaps rendered with a specific QFont."""
    return (font.family(), float(font.pointSizeF()), bool(font.bold()), bool(font.italic()))


def _color_cache_key(color: QColor) -> str:
    """Key for caching pixmaps rendered with a specific color."""
    return color.name(QColor.NameFormat.HexRgb)


def _create_blurred_text_pixmap(
    text: str, font, color: QColor, width: int, height: int, sigma: float = 3.0
) -> QPixmap:
    """Render text to a pixmap with blur applied via QGraphicsBlurEffect."""
    cache_key = (
        text,
        width,
        height,
        float(sigma),
        _font_cache_key(font),
        _color_cache_key(color),
    )
    cached = _BLUR_TEXT_PIXMAP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        pad = int(sigma * 2) + 4
        img_w = width + 2 * pad
        img_h = height + 2 * pad

        scene = QGraphicsScene(0, 0, img_w, img_h)
        scene.setSceneRect(0, 0, img_w, img_h)

        text_item = QGraphicsTextItem(text)
        text_item.setFont(font)
        text_item.setDefaultTextColor(color)

        doc = text_item.document()
        opt = QTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        doc.setDefaultTextOption(opt)

        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(sigma)
        text_item.setGraphicsEffect(effect)

        br = text_item.boundingRect()
        y = pad + (height - br.height()) / 2.0
        x = pad
        text_item.setPos(x, y)

        scene.addItem(text_item)

        img = QImage(img_w, img_h, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        scene.render(
            painter,
            QRectF(0, 0, img_w, img_h),
            QRectF(0, 0, img_w, img_h),
        )
        painter.end()

        pix = QPixmap.fromImage(img)
        if pix.isNull():
            raise RuntimeError("blur pixmap rendered as null")
        _BLUR_TEXT_PIXMAP_CACHE[cache_key] = pix
        return pix
    except Exception:
        return _create_blurred_text_pixmap_fallback(text, font, color, width, height)


def _create_blurred_text_pixmap_fallback(
    text: str, font, color: QColor, width: int, height: int
) -> QPixmap:
    """Fallback: draw text multiple times with offset to simulate blur (no numpy)."""
    pad = 12
    img = QImage(width + 2 * pad, height + 2 * pad, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setFont(font)
    faded = QColor(color)
    faded.setAlpha(40)
    p.setPen(faded)
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            if dx != 0 or dy != 0:
                p.drawText(
                    QRect(pad + dx, pad + dy, width, height),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    text,
                )
    faded.setAlpha(180)
    p.setPen(faded)
    p.drawText(
        QRect(pad, pad, width, height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        text,
    )
    p.end()
    return QPixmap.fromImage(img)
