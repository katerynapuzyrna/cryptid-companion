"""Transient toast notifications."""
from PySide6.QtWidgets import QWidget, QLabel, QFrame, QHBoxLayout
from PySide6.QtCore import QTimer, Qt, QRect, QRectF, QPoint
from PySide6.QtGui import QPainterPath, QRegion


def show_toast(parent: QWidget, message: str, duration_ms: int = 2500) -> None:
    """Show a transient toast message at the bottom center of the parent window."""
    toast = QFrame()
    toast.setObjectName("toast")
    toast.setWindowFlags(
        Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
    )
    toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    layout = QHBoxLayout(toast)
    layout.setContentsMargins(16, 10, 16, 10)
    label = QLabel(message)
    layout.addWidget(label)
    toast.adjustSize()

    radius = 8
    path = QPainterPath()
    path.addRoundedRect(QRectF(toast.rect()), radius, radius)
    try:
        toast.setMask(QRegion(path.toFillPolygon().toPolygon()))
    except Exception:
        pass

    win_rect = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
    x = win_rect.left() + (win_rect.width() - toast.width()) // 2
    y = win_rect.bottom() - toast.height() - 24
    toast.move(x, y)
    toast.show()

    def hide_and_delete():
        toast.hide()
        toast.deleteLater()

    QTimer.singleShot(duration_ms, hide_and_delete)
