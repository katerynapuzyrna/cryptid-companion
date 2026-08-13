"""Application QIcon tuned for sharp title bars on high-DPI (dialogs, main window)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


def load_application_icon() -> QIcon:
    """
    Windows scales title-bar icons by devicePixelRatio. A single small pixmap is upscaled
    and looks soft. We register variants: logical_size * dpr for common DPRs.
    """
    src = QPixmap(":/assets/icons/app_icon.png")
    if src.isNull():
        ico = QIcon(":/assets/icons/app_icon.ico")
        return ico if not ico.isNull() else QIcon()

    icon = QIcon()
    logical_sizes = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
    dprs = (1.0, 1.25, 1.5, 2.0)
    for dpr in dprs:
        for logical in logical_sizes:
            side = max(1, int(round(logical * dpr)))
            pm = src.scaled(
                side,
                side,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pm.setDevicePixelRatio(dpr)
            icon.addPixmap(pm, QIcon.Mode.Normal, QIcon.State.Off)
    return icon
