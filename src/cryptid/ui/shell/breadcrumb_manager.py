"""Breadcrumb line below page title: Home / … segments per top-level page."""
from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QLabel, QStackedWidget, QWidget


def inject_page_breadcrumb(title_host: QWidget) -> QLabel:
    """Add a QLabel below existing title row inside ``title_host`` layout."""
    layout = title_host.layout()
    if layout is None:
        raise RuntimeError(f"{title_host.objectName() or title_host}: no layout for breadcrumb")
    lbl = QLabel()
    lbl.setObjectName("pageBreadcrumb")
    lbl.setWordWrap(True)
    layout.addWidget(lbl)
    lbl.hide()
    return lbl


def touch_breadcrumbs(controller: object) -> None:
    fn = getattr(controller, "_breadcrumb_refresh", None)
    if callable(fn):
        fn()


class BreadcrumbManager:
    """Maps ``pagesStack`` index → QLabel + segment provider; ``refresh()`` updates visible crumb."""

    def __init__(self, pages_stack: QStackedWidget) -> None:
        self._pages_stack = pages_stack
        self._labels: dict[int, QLabel] = {}
        self._providers: dict[int, Callable[[], Sequence[str]]] = {}

    def register(
        self,
        page: QWidget,
        label: QLabel,
        segments_fn: Callable[[], Sequence[str]],
    ) -> None:
        idx = self._pages_stack.indexOf(page)
        if idx < 0:
            return
        self._labels[idx] = label
        self._providers[idx] = segments_fn

    def refresh(self) -> None:
        idx = self._pages_stack.currentIndex()
        label = self._labels.get(idx)
        if label is None:
            return
        fn = self._providers.get(idx)
        parts = list(fn()) if fn is not None else []
        if not parts:
            label.clear()
            label.hide()
        else:
            label.setText(" / ".join(parts))
            label.show()
