"""Small loading / busy indicators."""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QBrush, QColor


class DotsLoadingWidget(QWidget):
    """Three dots that blink cyclically in turn (one lit at a time)."""

    def __init__(self, parent=None, dot_color: QColor | None = None, dim_color: QColor | None = None):
        super().__init__(parent)
        self.setFixedSize(52, 16)
        self._dot_color = dot_color or QColor("#2f7d77")
        self._dim_color = dim_color or QColor("#c8d1d8")
        self._index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.setInterval(540)

    def _advance(self) -> None:
        self._index = (self._index + 1) % 3
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        r = 4
        gap = 10
        total_w = 3 * (2 * r) + 2 * gap
        left = (self.width() - total_w) // 2 + r
        cy = self.height() // 2
        for i in range(3):
            cx = left + i * (2 * r + gap)
            if i == self._index:
                painter.setBrush(QBrush(self._dot_color))
            else:
                painter.setBrush(QBrush(self._dim_color))
            painter.drawEllipse(int(cx - r), int(cy - r), 2 * r, 2 * r)
        painter.end()
