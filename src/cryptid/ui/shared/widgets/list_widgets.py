"""QListWidget variants for status list and color combo popups."""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QListView,
    QListWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
)


def _status_list_text_wrap_width(view: QListWidget, option_template: QStyleOptionViewItem) -> int:
    """Pixel width available for status text (viewport minus icon and margins)."""
    w = max(80, view.viewport().width())
    opt = QStyleOptionViewItem(option_template)
    opt.rect = QRect(0, 0, w, 200)
    style = view.style()
    dec = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, opt, view)
    txt = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, view)
    if txt.isValid() and txt.width() > 0:
        return max(40, txt.width())
    icon_w = dec.width() if dec.isValid() else 0
    return max(40, w - icon_w - 28)


class StatusListWrappingDelegate(QStyledItemDelegate):
    """Paints list rows with QTextDocument so long tokens break; full line including counts stays visible."""

    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        widget = options.widget
        style = widget.style() if widget else QApplication.style()

        painter.save()
        try:
            # PySide6 does not expose QStyledItemDelegate.drawBackground(); use style primitive.
            style.drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem,
                options,
                painter,
                widget,
            )

            if not options.icon.isNull():
                icon_rect = style.subElementRect(
                    QStyle.SubElement.SE_ItemViewItemDecoration, options, widget
                )
                if icon_rect.isValid():
                    options.icon.paint(
                        painter,
                        icon_rect,
                        Qt.AlignmentFlag.AlignCenter,
                    )

            text_rect = style.subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, options, widget
            )
            if not options.text:
                return
            if not text_rect.isValid():
                text_rect = options.rect.adjusted(8, 4, -8, -4)
            else:
                # Style may assume single-line height; use full row height for wrapped text.
                text_rect = QRect(
                    text_rect.left(),
                    options.rect.top() + 2,
                    text_rect.width(),
                    max(text_rect.height(), options.rect.height() - 4),
                )

            doc = QTextDocument()
            doc.setPlainText(options.text)
            doc.setDefaultFont(options.font)
            t_opt = QTextOption()
            t_opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            doc.setDefaultTextOption(t_opt)
            doc.setTextWidth(max(1.0, float(text_rect.width())))

            painter.translate(text_rect.topLeft())
            painter.setClipRect(
                QRect(0, 0, text_rect.width(), text_rect.height())
            )
            doc.drawContents(painter)
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        view = option.widget
        if view is None or not isinstance(view, QListWidget):
            return super().sizeHint(option, index)

        tw = _status_list_text_wrap_width(view, options)
        doc = QTextDocument()
        doc.setPlainText(options.text or "")
        doc.setDefaultFont(options.font)
        t_opt = QTextOption()
        t_opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        doc.setDefaultTextOption(t_opt)
        doc.setTextWidth(float(tw))
        text_h = int(doc.size().height()) + 8

        deco_h = 0
        if not options.icon.isNull():
            deco_h = max(options.decorationSize.height(), 22) + 4
        row_h = max(text_h, deco_h, 28)
        return QSize(view.viewport().width(), row_h)


def configure_status_list_wrapping(list_widget: QListWidget) -> None:
    """Word-wrap status rows (including long unbroken names); trailing text stays visible."""
    list_widget.setWordWrap(True)
    list_widget.setTextElideMode(Qt.TextElideMode.ElideNone)
    list_widget.setResizeMode(QListView.ResizeMode.Adjust)
    list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    list_widget.setItemDelegate(StatusListWrappingDelegate(list_widget))


class StatusListWidget(QListWidget):
    """QListWidget that disables drag-scroll so items stay visible; wheel events are ignored so the parent scroll area can scroll."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoScroll(False)
        configure_status_list_wrapping(self)

    def wheelEvent(self, event):
        bar = self.verticalScrollBar()
        if bar is not None and bar.maximum() > 0:
            super().wheelEvent(event)
            return
        event.ignore()


class _NoWheelListWidget(QListWidget):
    """QListWidget that ignores wheel events (used for color combo popup to prevent accidental scroll)."""

    def wheelEvent(self, event):
        event.accept()
