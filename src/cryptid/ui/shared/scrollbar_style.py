"""Custom style to draw horizontal scrollbar identically to vertical."""
from PySide6.QtWidgets import QProxyStyle, QScrollBar, QStyle, QStyleOptionSlider
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QBrush

from settings.theme import BORDER_Q, SCROLLBAR_HANDLE_RADIUS

HORIZONTAL_SCROLLBAR_HEIGHT = 14


class ScrollBarStyle(QProxyStyle):
    """Draws horizontal scrollbar with same appearance as vertical."""

    def pixelMetric(self, metric, option=None, widget=None):
        if (
            metric == QStyle.PixelMetric.PM_ScrollBarExtent
            and widget is not None
            and isinstance(widget, QScrollBar)
            and widget.orientation() == Qt.Orientation.Horizontal
        ):
            return HORIZONTAL_SCROLLBAR_HEIGHT
        return super().pixelMetric(metric, option, widget)

    def drawComplexControl(self, control, option, painter, widget=None):
        if control != QStyle.ComplexControl.CC_ScrollBar:
            return super().drawComplexControl(control, option, painter, widget)
        opt = QStyleOptionSlider(option)
        if opt.orientation != Qt.Orientation.Horizontal:
            return super().drawComplexControl(control, option, painter, widget)
        self._draw_horizontal_scrollbar(opt, painter, widget)

    def _draw_horizontal_scrollbar(self, opt, painter, widget):
        # Draw handle only (add-page/sub-page stay transparent)
        handle_rect = self.subControlRect(
            QStyle.ComplexControl.CC_ScrollBar,
            opt,
            QStyle.SubControl.SC_ScrollBarSlider,
            widget,
        )
        if handle_rect.isValid():
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(BORDER_Q))
            painter.drawRoundedRect(handle_rect, SCROLLBAR_HANDLE_RADIUS, SCROLLBAR_HANDLE_RADIUS)
            painter.restore()
