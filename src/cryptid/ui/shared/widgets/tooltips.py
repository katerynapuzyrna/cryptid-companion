"""Unified hover tooltip manager (rounded display + timer-based hover logic)."""
from typing import Callable, Optional, Union

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFrame,
    QVBoxLayout,
    QApplication,
    QSizePolicy,
)
from PySide6.QtCore import QTimer, Qt, QRect, QObject, QEvent, QPoint
from PySide6.QtGui import QCursor


class HoverTooltipManager(QObject):
    """Unified hover tooltip: rounded display + timer-based hover logic."""

    def __init__(self, root: QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self._root = root
        self._targets: list[
            tuple[QWidget, Union[str, Callable[[], QWidget]], bool, Optional[Callable[[], bool]]]
        ] = []
        self._tooltip: QFrame | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check)
        self._timer.start(100)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._showing_for: tuple[QWidget, Union[str, Callable[[], QWidget]]] | None = None
        self._global_condition: Optional[Callable[[], bool]] = None
        self._custom_tooltip: QFrame | None = None

    def show_custom_content(
        self,
        content: QWidget,
        viewport: QWidget,
        viewport_pos: QPoint,
        *,
        mouse_transparent: bool = False,
    ) -> None:
        """Show a tooltip with custom widget content, positioned near viewport_pos. Hide on hide_custom()."""
        self.hide_custom()
        if self._tooltip:
            self._tooltip.hide()
        self._showing_for = None
        frame = QFrame()
        frame.setObjectName("tooltipWindow")
        frame.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        frame.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if mouse_transparent:
            frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        inner = QFrame(frame)
        inner.setObjectName("roundedTooltip")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.addWidget(content)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(inner)
        frame.adjustSize()
        if not self._root.isVisible():
            return
        pos_global = viewport.mapToGlobal(viewport_pos)
        x = pos_global.x() + 12
        y = pos_global.y() + 12
        tw, th = frame.width(), frame.height()
        win_geom = QRect(self._root.mapToGlobal(QPoint(0, 0)), self._root.size())
        screen = QApplication.primaryScreen().geometry() if QApplication.primaryScreen() else win_geom
        if x + tw > screen.right():
            x = pos_global.x() - tw - 12
        if y + th > screen.bottom():
            y = pos_global.y() - th - 12
        x = max(win_geom.left(), min(x, win_geom.right() - tw))
        y = max(win_geom.top(), min(y, win_geom.bottom() - th))
        frame.move(int(x), int(y))
        frame.show()
        self._custom_tooltip = frame

    def hide_custom(self) -> None:
        """Hide the custom content tooltip."""
        if self._custom_tooltip is not None:
            self._custom_tooltip.hide()
            self._custom_tooltip.deleteLater()
            self._custom_tooltip = None

    def set_global_condition(self, condition: Optional[Callable[[], bool]]) -> None:
        """When set, tooltips are suppressed when condition() returns False (e.g. during calculation)."""
        self._global_condition = condition

    def add(
        self,
        widget: QWidget,
        tooltip: str | Callable[[], QWidget],
        only_when_disabled: bool = False,
        only_when: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._targets.append((widget, tooltip, only_when_disabled, only_when))

    def remove_target(self, widget: QWidget) -> None:
        """Stop managing ``widget`` (e.g. before the widget is destroyed)."""
        if self._showing_for is not None and self._showing_for[0] is widget:
            if self._tooltip is not None:
                self._tooltip.hide()
                self._tooltip.deleteLater()
                self._tooltip = None
            self._showing_for = None
        self._targets = [t for t in self._targets if t[0] is not widget]

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Re-check tooltip visibility after scroll: cursor may no longer be over target."""
        if event.type() in (QEvent.Type.Wheel, QEvent.Type.Scroll):
            QTimer.singleShot(20, self._check)
        return False

    def _make_tooltip_frame(self, content: str | QWidget) -> QFrame:
        """Create a fresh tooltip frame (avoids stretching from reusing previous size)."""
        outer = QFrame()
        outer.setObjectName("tooltipWindow")
        outer.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        outer.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Let hover stay on the target when the tip overlaps it (e.g. strip help icon).
        outer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        inner = QFrame(outer)
        inner.setObjectName("roundedTooltip")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        if isinstance(content, QWidget):
            inner_layout.addWidget(content)
        else:
            label = QLabel(inner)
            label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            label.setText(content)
            inner_layout.addWidget(label)

        layout = QVBoxLayout(outer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(inner)
        outer.adjustSize()
        return outer

    def _show_tooltip(self, tip: str | Callable[[], QWidget], target: QWidget) -> None:
        if self._tooltip is not None:
            self._tooltip.hide()
            self._tooltip.deleteLater()
            self._tooltip = None
        content: str | QWidget = tip() if callable(tip) else tip
        frame = self._make_tooltip_frame(content)
        self._tooltip = frame
        if not self._root.isVisible():
            return
        win_geom = QRect(self._root.mapToGlobal(QPoint(0, 0)), self._root.size())
        target_geom = QRect(target.mapToGlobal(QPoint(0, 0)), target.size())
        gap = 0
        tw, th = frame.width(), frame.height()
        room_below = win_geom.bottom() - target_geom.bottom()
        room_above = target_geom.top() - win_geom.top()
        room_right = win_geom.right() - target_geom.right()
        room_left = target_geom.left() - win_geom.left()
        if room_below >= th + gap:
            x = target_geom.left()
            y = target_geom.bottom() + gap
        elif room_above >= th + gap:
            x = target_geom.left()
            y = target_geom.top() - th - gap
        elif room_right >= tw + gap:
            x = target_geom.right() + gap
            y = target_geom.top()
        elif room_left >= tw + gap:
            x = target_geom.left() - tw - gap
            y = target_geom.top()
        else:
            x = target_geom.left()
            y = target_geom.bottom() + gap
        x = max(win_geom.left(), min(x, win_geom.right() - tw))
        y = max(win_geom.top(), min(y, win_geom.bottom() - th))
        frame.move(x, y)
        frame.show()

    def _check(self) -> None:
        try:
            if self._custom_tooltip is not None and self._custom_tooltip.isVisible():
                return
            if not self._root.isVisible() or not self._targets:
                if self._tooltip:
                    self._tooltip.hide()
                self._showing_for = None
                return
            win = self._root.window()
            if win and (win.windowState() & Qt.WindowState.WindowMinimized):
                if self._tooltip:
                    self._tooltip.hide()
                self._showing_for = None
                return
            if self._global_condition is not None:
                try:
                    if not self._global_condition():
                        if self._tooltip:
                            self._tooltip.hide()
                        self._showing_for = None
                        return
                except Exception:
                    if self._tooltip:
                        self._tooltip.hide()
                    self._showing_for = None
                    return
            pos = QCursor.pos()
            w_at = QApplication.widgetAt(pos)
            if self._tooltip and w_at and (w_at == self._tooltip or self._tooltip.isAncestorOf(w_at)):
                return
            top_at = QApplication.topLevelAt(pos)
            our_window = self._root.window()
            if top_at is None or top_at.window() != our_window:
                if self._tooltip:
                    self._tooltip.hide()
                self._showing_for = None
                return
            for target, tip_text, only_disabled, only_when in self._targets:
                try:
                    if not target.isVisible():
                        continue
                    if only_disabled and target.isEnabled():
                        continue
                    if only_when is not None and not only_when():
                        continue
                    hit = w_at and (w_at == target or target.isAncestorOf(w_at))
                    if not hit:

                        def _in_proxy(w) -> bool:
                            if hasattr(w, "graphicsProxyWidget") and w.graphicsProxyWidget() is not None:
                                return True
                            p = w.parentWidget()
                            return p is not None and _in_proxy(p)

                        use_rect = w_at is None or _in_proxy(target)
                        if use_rect:
                            r = target.rect()
                            hit = r.contains(target.mapFromGlobal(pos))
                    if hit:
                        if self._showing_for != (target, tip_text):
                            self._showing_for = (target, tip_text)
                            self._show_tooltip(tip_text, target)
                        return
                except (RuntimeError, AttributeError):
                    pass
            if self._tooltip:
                self._tooltip.hide()
            self._showing_for = None
        except Exception:
            pass
