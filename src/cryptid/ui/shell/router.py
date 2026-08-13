"""Navigation router: maps nav list row to pagesStack index."""
from PySide6.QtWidgets import QListWidget, QStackedWidget, QWidget
from typing import Optional


class Router:
    """Maps sidebar nav list row to pagesStack index and handles navigation."""

    def __init__(
        self,
        nav_list: QListWidget,
        pages_stack: QStackedWidget,
    ):
        self._nav_list = nav_list
        self._pages_stack = pages_stack
        self._row_to_index: dict[int, int] = {}

    def register(self, nav_text: str, page: QWidget) -> None:
        """Register a page for the given nav list text."""
        row = self._find_row(nav_text)
        if row != -1:
            idx = self._pages_stack.indexOf(page)
            if idx != -1:
                self._row_to_index[row] = idx

    def _find_row(self, text: str) -> int:
        for i in range(self._nav_list.count()):
            item = self._nav_list.item(i)
            if item and (item.text() or "").strip() == text:
                return i
        return -1

    def set_route(self, nav_text: str) -> bool:
        """Navigate to the page for the given nav text. Returns True if found."""
        row = self._find_row(nav_text)
        if row == -1:
            return False
        idx = self._row_to_index.get(row)
        if idx is None:
            return False
        if 0 <= idx < self._pages_stack.count():
            self._nav_list.setCurrentRow(row)
            self._pages_stack.setCurrentIndex(idx)
            return True
        return False

    def get_page_index_for_row(self, row: int) -> Optional[int]:
        """Return pagesStack index for the given nav row, or None."""
        return self._row_to_index.get(row)

    def get_row_for_nav_text(self, nav_text: str) -> int:
        """Return nav list row for the given text, or -1 if not found."""
        return self._find_row(nav_text)

    def on_nav_row_changed(self, row: int) -> None:
        """Called when nav list selection changes. Updates pagesStack."""
        idx = self.get_page_index_for_row(row)
        if idx is not None and 0 <= idx < self._pages_stack.count():
            self._pages_stack.setCurrentIndex(idx)
