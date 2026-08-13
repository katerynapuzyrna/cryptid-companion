"""Custom combo popup positioning and QUiLoader hook for rounded combos."""
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QFrame,
    QVBoxLayout,
    QScrollArea,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, QRectF, QRect, QPoint
from PySide6.QtGui import QPainterPath, QRegion, QIcon
from PySide6.QtUiTools import QUiLoader

from .list_widgets import StatusListWidget, _NoWheelListWidget


class ComboBoxWithPopupAbove(QComboBox):
    """QComboBox with custom rounded popup (border-radius only, no acute angles)."""

    class _RoundedComboPopup(QFrame):
        """Popup with rounded corners, used only by ComboBoxWithPopupAbove."""

        def __init__(self, combo: "ComboBoxWithPopupAbove", root_window: QWidget, parent: QWidget | None = None):
            super().__init__(parent)
            self._combo = combo
            self._root_window = root_window
            self.setObjectName("roundedComboPopup")
            self.setWindowFlags(
                Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            name = combo.objectName() or ""
            is_color_combo = name.startswith("cbColorP") or name == "mapCardColorCombo"
            self._list = _NoWheelListWidget() if is_color_combo else QListWidget()
            self._list.setObjectName("roundedComboPopupList")
            self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._list.itemClicked.connect(self._on_item_clicked)
            layout.addWidget(self._list)

            self._index_map: list[int] = []

        def _apply_rounded_mask(self) -> None:
            r = self.rect()
            if r.width() > 0 and r.height() > 0:
                path = QPainterPath()
                path.addRoundedRect(QRectF(r), 10, 10)
                try:
                    self.setMask(QRegion(path.toFillPolygon().toPolygon()))
                except Exception:
                    pass

        def _visible_bottom(self) -> int:
            p = self._combo.parentWidget()
            while p and p is not self._root_window:
                if isinstance(p, QScrollArea):
                    vp = p.viewport()
                    if vp and vp.isVisible():
                        return vp.mapToGlobal(QPoint(0, vp.height())).y()
                p = p.parentWidget() if p else None
            return self._root_window.mapToGlobal(QPoint(0, self._root_window.height())).y()

        def _populate(self) -> None:
            self._list.clear()
            self._index_map.clear()
            model = self._combo.model()
            view = self._combo.view()
            if model is None:
                return
            icon_size = self._combo.iconSize()
            if icon_size.width() > 0 and icon_size.height() > 0:
                self._list.setIconSize(icon_size)
            for row in range(model.rowCount()):
                if view is not None and view.isRowHidden(row):
                    continue
                idx = model.index(row, 0)
                text = model.data(idx, Qt.ItemDataRole.DisplayRole) or ""
                icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
                if isinstance(icon, QIcon) and not icon.isNull():
                    self._list.addItem(QListWidgetItem(icon, text))
                else:
                    self._list.addItem(text)
                self._index_map.append(row)

        def _position(self) -> None:
            combo = self._combo
            root = self._root_window
            cg = combo.mapToGlobal(QPoint(0, 0))
            ch = combo.height()
            visible_bottom = self._visible_bottom()
            available_below = visible_bottom - cg.y() - ch
            row_h = self._list.sizeHintForRow(0) if self._list.count() else 24
            max_visible = 10
            popup_h = row_h * min(max_visible, self._list.count()) + 20
            min_room = 80
            open_above = (
                combo.objectName() not in ("cbBuildPlayers", "cbSelectPlayers")
                and (available_below < min_room or popup_h > available_below)
            )
            if open_above:
                y = cg.y() - self.height()
            else:
                y = cg.y() + ch
            x = cg.x()
            win_rect = QRect(root.mapToGlobal(QPoint(0, 0)), root.size())
            if x + self.width() > win_rect.right():
                x = win_rect.right() - self.width()
            if x < win_rect.left():
                x = win_rect.left()
            if y + self.height() > win_rect.bottom():
                y = win_rect.bottom() - self.height()
            if y < win_rect.top():
                y = win_rect.top()
            self.move(x, y)

        def show_popup(self) -> None:
            self._populate()
            self._list.setCurrentRow(-1)
            current = self._combo.currentIndex()
            if current >= 0 and current in self._index_map:
                try:
                    row = self._index_map.index(current)
                    self._list.setCurrentRow(row)
                    midx = self._list.model().index(row, 0)
                    self._list.scrollTo(midx, QAbstractItemView.ScrollHint.PositionAtCenter)
                except (ValueError, TypeError):
                    pass
            self.setFixedWidth(self._combo.width())
            count = self._list.count()
            row_h = self._list.sizeHintForRow(0) if count else 24
            name = self._combo.objectName() or ""
            is_color_combo = name.startswith("cbColorP") or name == "mapCardColorCombo"
            if is_color_combo:
                n = count
                row_h = max(row_h, 32)
            else:
                max_visible = 10
                n = min(max_visible, count)
            h = row_h * n + 20
            self.setFixedHeight(h)
            self._list.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff if is_color_combo else Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self._position()
            self._apply_rounded_mask()
            self.show()
            self._list.setFocus()

        def _on_item_clicked(self, item) -> None:
            row = self._list.row(item)
            if 0 <= row < len(self._index_map):
                self._combo.setCurrentIndex(self._index_map[row])
            self.hide()

    _root_window: Optional[QWidget] = None
    _custom_popup: Optional[QFrame] = None

    def wheelEvent(self, event):
        event.accept()

    def set_root_window(self, root_window: QWidget) -> None:
        self._root_window = root_window

    def showPopup(self) -> None:
        if self._root_window is None:
            super().showPopup()
            return
        if self._custom_popup is None:
            self._custom_popup = self._RoundedComboPopup(self, self._root_window)
        self._custom_popup.show_popup()


class ComboPopupUiLoader(QUiLoader):
    """Creates ComboBoxWithPopupAbove for QComboBox, StatusListWidget for statusList."""

    def createWidget(self, class_name: str, parent: Optional[QWidget], name: str):
        if class_name == "QComboBox":
            return ComboBoxWithPopupAbove(parent)
        if class_name == "QListWidget" and name == "statusList":
            return StatusListWidget(parent)
        return super().createWidget(class_name, parent, name)
