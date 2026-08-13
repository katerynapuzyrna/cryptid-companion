"""Main window shell: loads UI, navigation, page setup."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QFile, QIODevice, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)

from settings.config import (
    ASSETS_DIR,
    APP_DISPLAY_NAME,
    ICON_UNDER_DEVELOPMENT,
    UI_PATH,
    PAGE_MAIN_MENU_UI,
    PAGE_DEDUCTION_UI,
    PAGE_SOLVE_UI,
    PAGE_HOW_TO_PLAY_UI,
    PAGE_MAPS_LIBRARY_UI,
    PAGE_PLAY_HOTSEAT_UI,
)
from settings.theme import BACKGROUND_CARD
from ui.shared.widgets import (
    ComboPopupUiLoader,
    ComboBoxWithPopupAbove,
)
from ui.shell.router import Router
from ui.shell.breadcrumb_manager import BreadcrumbManager, inject_page_breadcrumb
from ui.shell.page_breadcrumbs import (
    segments_deduction_mode,
    segments_maps_library,
    segments_play_hotseat,
    segments_solve_tool,
    segments_static,
)
from ui.pages.page_home import HomePageController
from ui.pages.page_tutorials import TutorialsPageController
from ui.pages.page_solve import SolvePageController
from ui.pages.page_deduction import DeductionPageController
from ui.pages.maps_library.page_maps_library import MapsLibraryPageController
from ui.pages.page_play_hotseat import PlayHotseatPageController


_PLACEHOLDER_COMING_SOON_ICON_PX = 24


def _make_nav_placeholder_page(_title: str, object_name: str) -> tuple[QWidget, QLabel]:
    """Placeholder page for unfinished nav entries (breadcrumb + coming soon)."""
    w = QWidget()
    w.setObjectName(object_name)
    layout = QVBoxLayout(w)
    layout.setContentsMargins(9, 0, 12, 12)
    layout.setSpacing(8)
    title_host = QWidget()
    tl = QVBoxLayout(title_host)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(0)
    crumb = inject_page_breadcrumb(title_host)
    layout.addWidget(title_host)

    soon_row = QWidget()
    soon_lay = QHBoxLayout(soon_row)
    soon_lay.setContentsMargins(2, 4, 0, 0)
    soon_lay.setSpacing(8)
    soon_icon = QLabel()
    soon_icon.setObjectName("pageComingSoonIcon")
    soon_icon.setFixedSize(_PLACEHOLDER_COMING_SOON_ICON_PX, _PLACEHOLDER_COMING_SOON_ICON_PX)
    pm = QIcon(str(ICON_UNDER_DEVELOPMENT)).pixmap(
        _PLACEHOLDER_COMING_SOON_ICON_PX, _PLACEHOLDER_COMING_SOON_ICON_PX
    )
    if not pm.isNull():
        soon_icon.setPixmap(pm)
    soon_lay.addWidget(soon_icon, 0, Qt.AlignmentFlag.AlignVCenter)
    soon_lbl = QLabel("Coming soon...")
    soon_lbl.setObjectName("pageComingSoon")
    soon_lay.addWidget(soon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
    soon_lay.addStretch(1)
    layout.addWidget(soon_row)

    layout.addStretch()
    return w, crumb


def _nav_icon_pixmap_trimmed(icon: QIcon, dec: QRect) -> QPixmap | None:
    """Crop icon to tight alpha bounds and scale into decoration rect (removes visible 'mat' around art)."""
    if icon.isNull():
        return None
    target = QSize(max(dec.width(), 1), max(dec.height(), 1))
    pm = icon.pixmap(target * 2)
    if pm.isNull():
        pm = icon.pixmap(target)
    if pm.isNull():
        return None
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    min_x, min_y = w, h
    max_x, max_y = -1, -1
    for yy in range(h):
        for xx in range(w):
            if QColor(img.pixel(xx, yy)).alpha() > 12:
                min_x = min(min_x, xx)
                min_y = min(min_y, yy)
                max_x = max(max_x, xx)
                max_y = max(max_y, yy)
    if max_x < min_x:
        return pm.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    cropped = img.copy(QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1))
    tight = QPixmap.fromImage(cropped)
    return tight.scaled(
        target,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


class _NavListItemDelegate(QStyledItemDelegate):
    """Paint list row chrome; hover/selected fill covers the full row including the icon."""

    _RADIUS = 10
    _ACCENT_W = 4
    _HOVER_BG = QColor("#f5f7f9")
    _SEL_BG = QColor("#d8ecea")
    _SEL_ACCENT = QColor("#2f7d77")
    _SEL_TEXT = QColor("#1f5d59")
    _NORMAL_TEXT = QColor("#182022")
    _UNDER_DEV_LABELS = frozenset({"Play Online", "History", "Settings"})
    _UNDER_DEV_ICON_PX = 22
    _UNDER_DEV_GAP = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._under_dev_pm = QIcon(str(ICON_UNDER_DEVELOPMENT)).pixmap(
            self._UNDER_DEV_ICON_PX, self._UNDER_DEV_ICON_PX
        )

    def paint(self, painter: QPainter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.showDecorationSelected = False

        widget = opt.widget
        style = widget.style() if widget else QApplication.style()

        dec = style.subElementRect(QStyle.SubElement.SE_ItemViewItemDecoration, opt, widget)
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)

        if not dec.isValid():
            super().paint(painter, option, index)
            return

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if selected:
            row_rf = QRectF(opt.rect)
            r = float(self._RADIUS)
            sel_shape = QPainterPath()
            sel_shape.addRoundedRect(row_rf, r, r)

            painter.fillPath(sel_shape, self._SEL_BG)

            # Left accent = same rounded rect, clipped to a left strip (continues border radius).
            strip = QPainterPath()
            strip.addRect(
                QRectF(row_rf.left(), row_rf.top(), float(self._ACCENT_W), row_rf.height())
            )
            painter.fillPath(sel_shape.intersected(strip), self._SEL_ACCENT)

            # No full outline stroke: top/bottom segments read as dividers between nav rows.
        elif hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._HOVER_BG)
            painter.drawRoundedRect(opt.rect, self._RADIUS, self._RADIUS)

        painter.restore()

        if not opt.icon.isNull():
            pm = _nav_icon_pixmap_trimmed(opt.icon, dec)
            if pm is not None and not pm.isNull():
                x = dec.left() + (dec.width() - pm.width()) // 2
                y = dec.top() + (dec.height() - pm.height()) // 2
                painter.drawPixmap(x, y, pm)
            else:
                opt.icon.paint(painter, dec, Qt.AlignmentFlag.AlignCenter)

        if opt.text and text_rect.isValid():
            pal = QPalette(opt.palette)
            pal.setColor(QPalette.ColorRole.Text, self._SEL_TEXT if selected else self._NORMAL_TEXT)
            pal.setColor(QPalette.ColorRole.WindowText, self._SEL_TEXT if selected else self._NORMAL_TEXT)
            font = QFont(opt.font)
            if selected:
                font.setBold(True)
            painter.setFont(font)
            text_flags = int(
                Qt.AlignmentFlag.AlignVCenter
                | Qt.AlignmentFlag.AlignLeft
                | Qt.TextFlag.TextSingleLine
            )
            style.drawItemText(
                painter,
                text_rect,
                text_flags,
                pal,
                True,
                opt.text,
                QPalette.ColorRole.Text,
            )

            label = (opt.text or "").strip()
            if (
                label in self._UNDER_DEV_LABELS
                and self._under_dev_pm is not None
                and not self._under_dev_pm.isNull()
            ):
                tw = painter.fontMetrics().horizontalAdvance(label)
                bx = text_rect.left() + tw + self._UNDER_DEV_GAP
                by = text_rect.top() + (text_rect.height() - self._under_dev_pm.height()) // 2
                # Keep badge inside the row; skip if it would clip past the right edge.
                if bx + self._under_dev_pm.width() <= opt.rect.right() - 4:
                    painter.drawPixmap(bx, by, self._under_dev_pm)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.showDecorationSelected = False


# QListWidget row icon size (24 * 1.2); keep QSS icon-size and .ui iconSize in sync.
_NAV_LIST_ICON_PX = 29


_NAV_ICON_SLUGS: dict[str, str] = {
    "Home": "home",
    "Play Online": "play_online",
    "Play Hotseat": "play_together",
    "Maps Library": "maps_library",
    "Solver Tool": "solver_tool",
    "Deduction Mode": "deduction_mode",
    "Tutorials": "tutorials",
    "History": "history",
    "Settings": "settings",
}


def _apply_nav_list_icons(nav: QListWidget) -> None:
    """Assign PNG icons to the left of each row (assets/icons/nav bar)."""
    nav_dir = ASSETS_DIR / "icons" / "nav bar"
    for i in range(nav.count()):
        item = nav.item(i)
        if item is None:
            continue
        text = (item.text() or "").strip()
        slug = _NAV_ICON_SLUGS.get(text)
        if not slug:
            continue
        icon = QIcon()
        p_flat = nav_dir / f"{slug}.png"
        if p_flat.is_file():
            icon.addFile(str(p_flat), QSize(256, 256))
            icon.addFile(str(p_flat), QSize(_NAV_LIST_ICON_PX, _NAV_LIST_ICON_PX))
        else:
            for size in (256, 32, 24):
                p = nav_dir / f"{slug}_{size}.png"
                if p.is_file():
                    icon.addFile(str(p), QSize(size, size))
        if icon.isNull():
            continue
        item.setIcon(icon)
    nav.setIconSize(QSize(_NAV_LIST_ICON_PX, _NAV_LIST_ICON_PX))
    nav.setViewMode(QListView.ViewMode.ListMode)
    nav.setUniformItemSizes(True)


class CryptidApp:
    """Main window shell, navigation, page wiring."""

    def __init__(self):
        loader = ComboPopupUiLoader()
        ui_path = str(UI_PATH.resolve())
        f = QFile(ui_path)
        if not f.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Cannot open UI file: {ui_path} - {f.errorString()}")
        self.window = loader.load(f, None)
        f.close()
        if self.window is None:
            raise RuntimeError("Failed to load main_window.ui")
        if not isinstance(self.window, QMainWindow):
            raise RuntimeError("main_window.ui must have QMainWindow as root.")

        pages_stack = self.window.findChild(QStackedWidget, "pagesStack")
        if pages_stack is None:
            raise RuntimeError("pagesStack not found in main_window.ui")

        def load_page(path, name: str):
            p = str(path.resolve())
            f = QFile(p)
            if not f.open(QIODevice.OpenModeFlag.ReadOnly):
                raise RuntimeError(f"Cannot open UI file: {p}")
            w = loader.load(f, None)
            f.close()
            if w is None:
                raise RuntimeError(f"Failed to load {name}")
            pages_stack.addWidget(w)
            return w

        load_page(PAGE_MAIN_MENU_UI, "page_main_menu.ui")
        load_page(PAGE_DEDUCTION_UI, "page_deduction.ui")
        load_page(PAGE_SOLVE_UI, "page_solve.ui")
        page_how_to_play = load_page(PAGE_HOW_TO_PLAY_UI, "page_how_to_play.ui")
        self._tutorials_page = TutorialsPageController(page_how_to_play)
        self._tutorials_page.setup()

        self.pageMapsLibrary = load_page(PAGE_MAPS_LIBRARY_UI, "page_maps_library.ui")
        self.pagePlayOnline, self._crumbPlayOnline = _make_nav_placeholder_page("Play Online", "pagePlayOnline")
        self.pagePlayTogether = load_page(PAGE_PLAY_HOTSEAT_UI, "page_play_hotseat.ui")
        self.pageHistory, self._crumbHistory = _make_nav_placeholder_page("History", "pageHistory")
        self.pageSettings, self._crumbSettings = _make_nav_placeholder_page("Settings", "pageSettings")
        for p in (
            self.pagePlayOnline,
            self.pageHistory,
            self.pageSettings,
        ):
            pages_stack.addWidget(p)

        self.navList: QListWidget = self.window.findChild(QListWidget, "navList")
        if self.navList is None:
            raise RuntimeError("navList not found")
        _apply_nav_list_icons(self.navList)
        self.navList.setItemDelegate(_NavListItemDelegate(self.navList))

        nav_vp = self.navList.viewport()
        nav_vp.setAutoFillBackground(True)
        nav_vp_pal = nav_vp.palette()
        nav_vp_pal.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND_CARD))
        nav_vp.setPalette(nav_vp_pal)

        lbl_logo = self.window.findChild(QLabel, "lblSidebarLogo")
        if lbl_logo is not None:
            pix = QPixmap()
            for path in (":/assets/icons/cryptid.png", ":/assets/icons/app_icon.png"):
                pix = QPixmap(path)
                if not pix.isNull():
                    break
            if not pix.isNull():
                max_w = 176
                max_h = 56
                scaled = pix.scaled(
                    max_w,
                    max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                lbl_logo.setPixmap(scaled)
                lbl_logo.setFixedHeight(max(scaled.height(), 1))

        self.pagesStack: QStackedWidget = pages_stack
        self.pageMainMenu: QWidget = self.window.findChild(QWidget, "pageMainMenu")
        self.pageDeduction: QWidget = self.window.findChild(QWidget, "pageDeduction")
        self.pageSolve: QWidget = self.window.findChild(QWidget, "pageSolve")
        self.pageHowToPlay: QWidget = self.window.findChild(QWidget, "pageHowToPlay")
        if not all(
            [
                self.pageMainMenu,
                self.pageDeduction,
                self.pageSolve,
                self.pageHowToPlay,
                self.pageMapsLibrary,
            ]
        ):
            raise RuntimeError(
                "Required pages not found (pageMainMenu, pageDeduction, pageSolve, pageHowToPlay, pageMapsLibrary)"
            )

        self.router = Router(self.navList, self.pagesStack)
        self.router.register("Home", self.pageMainMenu)
        self.router.register("Play Online", self.pagePlayOnline)
        self.router.register("Play Hotseat", self.pagePlayTogether)
        self.router.register("Maps Library", self.pageMapsLibrary)
        self.router.register("Solver Tool", self.pageSolve)
        self.router.register("Deduction Mode", self.pageDeduction)
        self.router.register("Tutorials", self.pageHowToPlay)
        self.router.register("History", self.pageHistory)
        self.router.register("Settings", self.pageSettings)

        self.navList.currentRowChanged.connect(self.router.on_nav_row_changed)

        # Default to Home
        self.router.set_route("Home")

        self._home_page = HomePageController(self.pageMainMenu, self.router.set_route)
        self._home_page.setup()

        # Solve page setup (combo filters must be installed before SolvePageController accesses combos)
        self._install_combo_filters()
        self._solve_page = SolvePageController(self.pageSolve, self.window)
        self._solve_page.setup()

        # Deduction page setup
        self._deduction_page = DeductionPageController(self.pageDeduction, self.window)
        self._deduction_page.setup()

        self._maps_library_page = MapsLibraryPageController(self.pageMapsLibrary, self.window)
        self._maps_library_page.setup()

        self._play_hotseat_page = PlayHotseatPageController(self.pagePlayTogether, self.window)
        self._play_hotseat_page.setup()

        self._breadcrumbs = BreadcrumbManager(self.pagesStack)
        for ctrl in (self._solve_page, self._deduction_page, self._maps_library_page, self._play_hotseat_page):
            ctrl._breadcrumb_refresh = self._breadcrumbs.refresh

        def _inj(host_name: str, page: QWidget) -> QLabel:
            h = page.findChild(QWidget, host_name)
            if h is None:
                raise RuntimeError(f"{host_name} not found on {page.objectName()}")
            return inject_page_breadcrumb(h)

        self._breadcrumbs.register(
            self.pageMainMenu,
            _inj("titlePageMainMenu", self.pageMainMenu),
            lambda: [],
        )
        self._breadcrumbs.register(
            self.pageDeduction,
            _inj("titlePageDeduction", self.pageDeduction),
            lambda: segments_deduction_mode(self._deduction_page),
        )
        self._breadcrumbs.register(
            self.pageSolve,
            _inj("titlePageSolve", self.pageSolve),
            lambda: segments_solve_tool(self._solve_page),
        )
        self._breadcrumbs.register(
            self.pageHowToPlay,
            _inj("titlePageHowToPlay", self.pageHowToPlay),
            segments_static("Tutorials"),
        )
        self._breadcrumbs.register(
            self.pageMapsLibrary,
            _inj("titlePageMapsLibrary", self.pageMapsLibrary),
            lambda: segments_maps_library(self._maps_library_page),
        )
        self._breadcrumbs.register(self.pagePlayOnline, self._crumbPlayOnline, segments_static("Play Online"))
        self._breadcrumbs.register(
            self.pagePlayTogether,
            _inj("titlePagePlayHotseat", self.pagePlayTogether),
            lambda: segments_play_hotseat(self._play_hotseat_page),
        )
        self._breadcrumbs.register(self.pageHistory, self._crumbHistory, segments_static("History"))
        self._breadcrumbs.register(self.pageSettings, self._crumbSettings, segments_static("Settings"))

        self.pagesStack.currentChanged.connect(lambda _i: self._breadcrumbs.refresh())
        self._breadcrumbs.refresh()

        # When leaving Solve / Deduction pages, preserve state; when returning, restore
        self._solve_page_index = self.pagesStack.indexOf(self.pageSolve)
        self._deduction_page_index = self.pagesStack.indexOf(self.pageDeduction)
        self._play_hotseat_page_index = self.pagesStack.indexOf(self.pagePlayTogether)
        self._maps_library_page_index = self.pagesStack.indexOf(self.pageMapsLibrary)
        self._last_page_index = self.pagesStack.currentIndex()

        def on_page_changed(idx: int) -> None:
            if self._last_page_index == self._solve_page_index and idx != self._solve_page_index:
                self._solve_page.on_navigate_away()
            elif idx == self._solve_page_index:
                self._solve_page.on_navigate_to()

            if self._last_page_index == self._deduction_page_index and idx != self._deduction_page_index:
                self._deduction_page.on_navigate_away()
            elif idx == self._deduction_page_index:
                self._deduction_page.on_navigate_to()

            if idx == self._play_hotseat_page_index:
                self._play_hotseat_page.on_navigate_to()

            if idx == self._maps_library_page_index:
                self._maps_library_page.on_navigate_to()

            self._last_page_index = idx

        self.pagesStack.currentChanged.connect(on_page_changed)

        # mainScroll horizontal bar: direct stylesheet + remove corner overlap
        main_scroll = self.window.findChild(QScrollArea, "mainScroll")
        if main_scroll is not None:
            corner = QWidget()
            corner.setFixedSize(0, 0)
            main_scroll.setCornerWidget(corner)
            main_scroll.setStyleSheet("""
                QScrollBar:horizontal {
                    height: 14px;
                    min-height: 14px;
                    max-height: 14px;
                    margin: 6px 4px 0px 4px;
                    padding: 0;
                    background: transparent;
                    border: none;
                }
                QScrollBar::handle:horizontal {
                    min-width: 24px;
                    height: 14px;
                    margin: 0;
                    padding: 0;
                    background: #d6dde2;
                    border: none;
                    border-radius: 5px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    width: 0;
                    height: 0;
                }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                    background: none;
                }
                QAbstractScrollArea::corner {
                    background: transparent;
                }
            """)

        self.window.setWindowTitle(APP_DISPLAY_NAME)

    def _install_combo_filters(self) -> None:
        """Wire root window for custom combo popups."""
        for cb in self.window.findChildren(QComboBox):
            if isinstance(cb, ComboBoxWithPopupAbove):
                cb.set_root_window(self.window)
