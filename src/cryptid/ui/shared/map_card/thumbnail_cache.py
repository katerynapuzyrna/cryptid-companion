"""On-disk map card thumbnail paths and rendering (shared by UI and build tools)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap

from settings.config import DATA_DIR
from ui.shared.map_card.scene import _get_preview_canvas_size, build_map_preview_scene

THUMBNAIL_VERSION = 4


def thumbnail_cache_dir() -> Path:
    return DATA_DIR / f"map_thumbnails_v{THUMBNAIL_VERSION}"


def thumbnail_path_for_map_id(map_id: int | str) -> Path:
    return thumbnail_cache_dir() / f"{map_id}.png"


def render_map_thumbnail_png(map_data: dict[str, Any], dest_path: Path | None = None) -> bool:
    """Render one map preview PNG using the same pipeline as MapCard thumbnails."""
    map_id = map_data.get("id")
    if map_id is None:
        return False
    path = dest_path or thumbnail_path_for_map_id(map_id)
    thumb_w, thumb_h = _get_preview_canvas_size()

    scene, _, _ = build_map_preview_scene(map_data)
    src = scene.sceneRect()
    img_w = max(1, int(round(src.width())))
    img_h = max(1, int(round(src.height())))
    img = QImage(img_w, img_h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    scene.render(painter, QRectF(0, 0, img_w, img_h), src)
    painter.end()
    pix = QPixmap.fromImage(img)
    if pix.isNull():
        return False
    if pix.width() != thumb_w or pix.height() != thumb_h:
        pix = pix.scaled(
            thumb_w,
            thumb_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return pix.save(str(path), "PNG")
