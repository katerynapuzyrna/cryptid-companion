from typing import Callable, Optional

from PySide6.QtWidgets import QFrame, QGraphicsView, QToolTip, QWidget
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QEvent, QPoint, QRectF


class BoardView(QGraphicsView):
    def __init__(self, scene, parent: Optional[QWidget] = None):
        super().__init__(scene, parent)
        self._on_resize: Optional[Callable[[], None]] = None
        # Avoid stacking a native QAbstractScrollArea frame on top of QSS (board.qss border).
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(self.renderHints())
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() is not None:
            vp = self.viewport().rect()
            br = self.scene().itemsBoundingRect()
            # During maximize/restore the viewport can briefly be 0×0; don't shrink sceneRect
            # to a degenerate union with visible (hides items anchored to sceneRect.right()).
            if vp.width() < 2 or vp.height() < 2:
                if br.isValid():
                    self.scene().setSceneRect(br)
            else:
                visible = self.mapToScene(vp).boundingRect()
                # Viewport-only rect breaks when the view was hidden / zero-sized during build
                # (e.g. Play Hotseat stack): scene must still span all board items.
                if br.isValid():
                    self.scene().setSceneRect(visible.united(br))
                else:
                    self.scene().setSceneRect(visible if visible.isValid() else QRectF())
        if self._on_resize:
            self._on_resize()

    def wheelEvent(self, event):
        # Don't zoom/pan here; let ancestors handle scroll if any.
        event.ignore()

    def viewportEvent(self, event):
        # QGraphicsView often fails to show tooltips for QGraphicsProxyWidget items.
        # Manually show tooltip when the app requests one for an item under the cursor.
        if event.type() == QEvent.Type.ToolTip:
            pos = self.mapFromGlobal(event.globalPos())
            scene_pos = self.mapToScene(pos)
            item = self.scene().itemAt(scene_pos, self.viewportTransform()) if self.scene() else None
            if item is not None:
                tip = item.toolTip() if hasattr(item, "toolTip") else ""
                if tip:
                    QToolTip.showText(event.globalPos(), tip)
                    return True
        return super().viewportEvent(event)
