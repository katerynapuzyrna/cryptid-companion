"""Home page: intro, navigation cards, and about / copyright text."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from settings.config import ASSETS_DIR, ICON_UNDER_DEVELOPMENT
from settings.strings import HOME_ABOUT_HTML, HOME_INTRO_HTML, HOME_NAV_CARDS

# Same slugs as sidebar nav icons in main_window._NAV_ICON_SLUGS
_HOME_NAV_ICON_SLUGS: dict[str, str] = {
    "Play Online": "play_online",
    "Play Hotseat": "play_together",
    "Maps Library": "maps_library",
    "Solver Tool": "solver_tool",
    "Deduction Mode": "deduction_mode",
}

_ICON_PX = 32
_COMING_SOON_ICON_PX = 24


class HomeNavCard(QFrame):
    """Clickable navigation card (title + description + optional icon)."""

    clicked = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        icon: QIcon | None = None,
        coming_soon: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("homeNavCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(140)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.setContentsMargins(0, 0, 0, 0)

        if icon is not None and not icon.isNull():
            icon_lbl = QLabel()
            icon_lbl.setObjectName("homeNavCardIcon")
            icon_lbl.setFixedSize(_ICON_PX, _ICON_PX)
            pm = icon.pixmap(_ICON_PX, _ICON_PX)
            if not pm.isNull():
                icon_lbl.setPixmap(pm)
            header.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("homeNavCardTitle")
        title_lbl.setWordWrap(True)
        header.addWidget(title_lbl, 1)
        layout.addLayout(header)

        body_lbl = QLabel(body)
        body_lbl.setObjectName("homeNavCardBody")
        body_lbl.setWordWrap(True)
        body_lbl.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body_lbl, 1)

        if coming_soon:
            soon_row = QHBoxLayout()
            soon_row.setSpacing(6)
            soon_row.setContentsMargins(0, 2, 0, 0)
            soon_icon = QLabel()
            soon_icon.setObjectName("homeNavCardComingSoonIcon")
            soon_icon.setFixedSize(_COMING_SOON_ICON_PX, _COMING_SOON_ICON_PX)
            ud = QIcon(str(ICON_UNDER_DEVELOPMENT))
            pm = ud.pixmap(_COMING_SOON_ICON_PX, _COMING_SOON_ICON_PX)
            if not pm.isNull():
                soon_icon.setPixmap(pm)
            soon_row.addWidget(soon_icon, 0, Qt.AlignmentFlag.AlignVCenter)
            soon_lbl = QLabel(coming_soon)
            soon_lbl.setObjectName("homeNavCardComingSoon")
            soon_lbl.setWordWrap(True)
            soon_row.addWidget(soon_lbl, 1)
            layout.addLayout(soon_row)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setProperty("pressed", True)
            self.style().unpolish(self)
            self.style().polish(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_pressed = bool(self.property("pressed"))
        if was_pressed:
            self.setProperty("pressed", False)
            self.style().unpolish(self)
            self.style().polish(self)
        if (
            event.button() == Qt.MouseButton.LeftButton
            and was_pressed
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self.property("pressed"):
            self.setProperty("pressed", False)
            self.style().unpolish(self)
            self.style().polish(self)
        super().leaveEvent(event)


def _load_nav_icon(route: str) -> QIcon:
    slug = _HOME_NAV_ICON_SLUGS.get(route)
    icon = QIcon()
    if not slug:
        return icon
    path = ASSETS_DIR / "icons" / "nav bar" / f"{slug}.png"
    if path.is_file():
        icon.addFile(str(path))
    return icon


class HomePageController:
    """Populate Home intro / nav cards / about and route card clicks."""

    def __init__(self, page: QWidget, navigate: Callable[[str], bool]):
        self._page = page
        self._navigate = navigate

    def setup(self) -> None:
        intro = self._page.findChild(QLabel, "homeIntro")
        about = self._page.findChild(QLabel, "homeAbout")
        cards_host = self._page.findChild(QWidget, "homeNavCards")
        if intro is None or about is None or cards_host is None:
            raise RuntimeError("Home page widgets missing (homeIntro / homeAbout / homeNavCards)")

        for name in ("homeIntroCard", "homeAboutCard"):
            frame = self._page.findChild(QFrame, name)
            if frame is not None:
                frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                frame.setFrameShape(QFrame.Shape.NoFrame)

        intro.setText(HOME_INTRO_HTML.strip())
        about.setText(HOME_ABOUT_HTML.strip())

        layout = cards_host.layout()
        if layout is None:
            raise RuntimeError("homeNavCards has no layout")

        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for route, body, coming_soon in HOME_NAV_CARDS:
            card = HomeNavCard(
                route,
                body,
                _load_nav_icon(route),
                coming_soon=coming_soon,
                parent=cards_host,
            )
            card.clicked.connect(lambda r=route: self._navigate(r))
            layout.addWidget(card)
