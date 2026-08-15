"""Maps Library page: create maps (no clues) or browse predefined/custom JSON lists."""
from __future__ import annotations

import copy
import json
import math

from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QAbstractButton,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QLabel,
    QListWidget,
    QGraphicsScene,
    QGraphicsItem,
    QStackedWidget,
    QButtonGroup,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QIcon, QColor, QPalette, QPixmap

from board.board_view import BoardView
from board.board_builder import BoardBuilder
from settings.config import (
    ICON_HELP,
    ICON_STATUS_OK,
    ICON_STATUS_ERROR,
    MAPS_JSON,
    CUSTOM_MAPS_JSON,
)
from settings.strings import (
    TOOLTIP_FREEZE_MAP,
    TOOLTIP_FREEZE_MAP_ENABLED,
    TOOLTIP_HELP_BUILD,
    TOOLTIP_ADVANCED_MODE,
    TOOLTIP_ADVANCED_MODE_SELECT,
    TOOLTIP_MAPS_LIB_SAVE_DISABLED,
    TOOLTIP_MAPS_LIB_CUSTOM_EDIT_BACK,
    TOOLTIP_UNDO,
    MAP_SAVE_NAME_PLACEHOLDER,
    MAP_EDIT_MAP_NAME_DIALOG_TITLE,
    MAP_SAVE_SUCCESS_TOAST,
    MAP_SAVE_ERROR_TITLE,
    MAP_SAVE_ERROR_MSG,
    MAP_DELETE_CONFIRM_TITLE,
    MAP_DELETE_CONFIRM_MSG,
    MAP_DELETE_SUCCESS_TOAST,
    MAP_EDIT_REVERT_TITLE,
    MAP_EDIT_REVERT_MSG,
    MAP_UPDATE_SUCCESS_TOAST,
    RESET_CONFIRM_TITLE,
    RESET_CONFIRM_MSG,
)
from ui.shared.map_card import invalidate_map_thumbnail_on_disk
from ui.shared.custom_map_save import (
    append_custom_map_to_json,
    prompt_save_map_name,
    rename_custom_map_in_json,
)
from ui.shared.map_cards_manager import MapCardsManager
from ui.shared.widgets import HoverTooltipManager, configure_status_list_wrapping, show_toast
from ui.pages.maps_library.maps_library_status import MapsLibraryStatusManager
from ui.shell.breadcrumb_manager import touch_breadcrumbs
from ui.shared.board_undo import BoardUndoController


class MapsLibraryPageController:
    def __init__(self, page: QWidget, window: QWidget):
        self._page = page
        self.window = window
        self.pages_stack: QStackedWidget | QWidget = window.findChild(QStackedWidget, "pagesStack") or window
        self.scene: QGraphicsScene | None = None
        self.view: BoardView | None = None
        self.board_builder: BoardBuilder | None = None
        self.canvas = None
        self.pieces: list = []
        self.markers: list = []
        self.advanced_mode: bool = False
        self.custom_edit_advanced_mode: bool = False
        self._editing_custom_map_id: int | None = None
        self._editing_custom_map_name: str | None = None
        self._edit_session_baseline_map: dict | None = None
        self._status_proxy = None
        self.mapsLibStatusList: QListWidget | None = None
        self._help_icon_proxy = None
        self._help_icon_wrapper: QWidget | None = None
        self._ce_scene: QGraphicsScene | None = None
        self._ce_view: BoardView | None = None
        self._ce_board_builder: BoardBuilder | None = None
        self._ce_canvas = None
        self._ce_pieces: list = []
        self._ce_markers: list = []
        self._ce_status_proxy = None
        self._ce_mapsLibStatusList: QListWidget | None = None
        self.cbMapsLibCustomEditAdvanced: QCheckBox | None = None
        self._ce_help_icon_proxy = None
        self._ce_help_icon_wrapper: QWidget | None = None
        self._ce_status_manager: MapsLibraryStatusManager | None = None
        self._app_tooltip = HoverTooltipManager(window, window)

    def setup(self) -> None:
        w = self._page
        self.btnMapsLibCreate: QPushButton = w.findChild(QPushButton, "btnMapsLibCreate")
        self.btnMapsLibPredefined: QPushButton = w.findChild(QPushButton, "btnMapsLibPredefined")
        self.btnMapsLibCustom: QPushButton = w.findChild(QPushButton, "btnMapsLibCustom")
        self.mapsLibStack: QStackedWidget = w.findChild(QStackedWidget, "mapsLibStack")
        self.mapsLibBrowseStack: QStackedWidget | None = w.findChild(
            QStackedWidget, "mapsLibBrowseStack"
        )
        self.mapsLibViewContainer: QWidget = w.findChild(QWidget, "mapsLibViewContainer")
        self.mapsLibBoardHost: QWidget | None = w.findChild(QWidget, "mapsLibBoardHost")
        self.mapsLibCustomEditBoardHost: QWidget | None = w.findChild(
            QWidget, "mapsLibCustomEditBoardHost"
        )
        self.mapsLibCustomEditViewContainer: QWidget | None = w.findChild(
            QWidget, "mapsLibCustomEditViewContainer"
        )
        self.btnMapsLibClearAll: QPushButton = w.findChild(QPushButton, "btnMapsLibClearAll")
        self.btnMapsLibSave: QPushButton = w.findChild(QPushButton, "btnMapsLibSave")
        self.btnMapsLibCustomEditBack: QPushButton | None = w.findChild(
            QPushButton, "btnMapsLibCustomEditBack"
        )
        self.btnMapsLibClearAllCustomEdit: QPushButton | None = w.findChild(
            QPushButton, "btnMapsLibClearAllCustomEdit"
        )
        self.btnMapsLibSaveCustomEdit: QPushButton | None = w.findChild(
            QPushButton, "btnMapsLibSaveCustomEdit"
        )
        self.cbMapsLibBrowseAdvanced: QCheckBox = w.findChild(QCheckBox, "cbMapsLibBrowseAdvanced")
        self.edtMapsLibBrowseSearch: QLineEdit = w.findChild(QLineEdit, "edtMapsLibBrowseSearch")
        self.lblMapsLibNoCards: QLabel | None = w.findChild(QLabel, "lblMapsLibNoCards")
        self.mapsLibMapCardsContainer: QWidget = w.findChild(QWidget, "mapsLibMapCardsContainer")
        self.mapsLibMapListScroll: QScrollArea | None = w.findChild(QScrollArea, "mapsLibMapListScroll")
        # QScrollArea viewport ignores generic QScrollArea { background: transparent } fixes poorly;
        # match page background so empty list space does not read as a second “card” layer.
        if self.mapsLibMapListScroll is not None:
            page_bg = QColor("#f2f4f6")
            self.mapsLibMapListScroll.setAutoFillBackground(True)
            pal_sa = self.mapsLibMapListScroll.palette()
            pal_sa.setColor(QPalette.ColorRole.Window, page_bg)
            self.mapsLibMapListScroll.setPalette(pal_sa)
            vp = self.mapsLibMapListScroll.viewport()
            vp.setAutoFillBackground(True)
            pal_vp = vp.palette()
            pal_vp.setColor(QPalette.ColorRole.Window, page_bg)
            vp.setPalette(pal_vp)

        self._seg_group = QButtonGroup(self.window)
        self._seg_group.addButton(self.btnMapsLibCreate)
        self._seg_group.addButton(self.btnMapsLibPredefined)
        self._seg_group.addButton(self.btnMapsLibCustom)
        self._seg_group.setExclusive(True)
        self.btnMapsLibCreate.setChecked(True)
        # Match stack to Create Map (UI file or prior session may leave browse index visible).
        if self.mapsLibStack is not None:
            self.mapsLibStack.setCurrentIndex(0)

        # Controller is not a QObject — cannot use sender(); QButtonGroup passes the clicked button.
        self._seg_group.buttonClicked.connect(self._on_segment_button_clicked)

        self.btnMapsLibClearAll.clicked.connect(self._on_clear_all)
        self.btnMapsLibSave.clicked.connect(self._on_save)
        if self.btnMapsLibSave:
            self.btnMapsLibSave.setEnabled(False)
        if self.btnMapsLibCustomEditBack:
            self.btnMapsLibCustomEditBack.clicked.connect(self._on_custom_edit_back)
        if self.btnMapsLibClearAllCustomEdit:
            self.btnMapsLibClearAllCustomEdit.clicked.connect(self._on_custom_edit_clear_all)
        if self.btnMapsLibSaveCustomEdit:
            self.btnMapsLibSaveCustomEdit.clicked.connect(self._on_custom_edit_save)
            self.btnMapsLibSaveCustomEdit.setEnabled(False)

        if self.edtMapsLibBrowseSearch:
            clear_action = self.edtMapsLibBrowseSearch.addAction(
                QIcon(":/assets/icons/close.svg"),
                QLineEdit.ActionPosition.TrailingPosition,
            )
            clear_action.triggered.connect(self.edtMapsLibBrowseSearch.clear)
            clear_action.setVisible(False)

            def _upd_clear() -> None:
                clear_action.setVisible(len(self.edtMapsLibBrowseSearch.text()) >= 1)

            self.edtMapsLibBrowseSearch.textChanged.connect(_upd_clear)

        self._dummy_players = QComboBox()
        for t in ("3", "4", "5"):
            self._dummy_players.addItem(t)
        self._dummy_players.hide()
        self._dummy_solve = QPushButton()
        self._dummy_solve.hide()
        self._dummy_map_select = QPushButton()
        self._dummy_map_select.setCheckable(True)
        self._dummy_map_select.setChecked(True)
        self._dummy_map_select.hide()

        self._browse_manager = MapCardsManager(
            self.mapsLibMapCardsContainer,
            self.cbMapsLibBrowseAdvanced,
            self._dummy_players,
            self._dummy_solve,
            self._dummy_map_select,
            edt_search=self.edtMapsLibBrowseSearch,
            lbl_no_cards=self.lblMapsLibNoCards,
            deduction_mode=False,
            browse_only=True,
            maps_json_path=MAPS_JSON,
            hover_tooltip=self._app_tooltip,
        )
        self._browse_cards_loaded = False
        self._browse_manager.custom_map_edit_requested.connect(self._on_custom_map_edit)
        self._browse_manager.custom_map_delete_requested.connect(self._on_custom_map_delete)
        self._browse_manager.custom_map_rename_map_name_requested.connect(
            self._on_custom_map_rename_name
        )

        self._app_tooltip.add(
            self.cbMapsLibBrowseAdvanced,
            TOOLTIP_ADVANCED_MODE_SELECT,
            only_when_disabled=False,
        )

        def _tooltip_on_page() -> bool:
            if self.pages_stack is None:
                return False
            return self.pages_stack.currentWidget() == self._page

        self._app_tooltip.set_global_condition(_tooltip_on_page)

        if self.btnMapsLibSave:
            self._app_tooltip.add(
                self.btnMapsLibSave,
                TOOLTIP_MAPS_LIB_SAVE_DISABLED,
                only_when_disabled=True,
            )
        if self.btnMapsLibSaveCustomEdit:
            self._app_tooltip.add(
                self.btnMapsLibSaveCustomEdit,
                TOOLTIP_MAPS_LIB_SAVE_DISABLED,
                only_when_disabled=True,
            )
        if self.btnMapsLibCustomEditBack:
            self._app_tooltip.add(
                self.btnMapsLibCustomEditBack,
                TOOLTIP_MAPS_LIB_CUSTOM_EDIT_BACK,
                only_when_disabled=False,
            )

        QTimer.singleShot(0, self._build_create_board)

    def _exit_custom_map_edit_ui(self) -> None:
        """Leave Custom Maps inline editor: show card grid again."""
        if self.mapsLibBrowseStack is not None and self.mapsLibBrowseStack.currentIndex() != 0:
            self.mapsLibBrowseStack.setCurrentIndex(0)

    def _leave_custom_map_edit_session(self) -> None:
        """Clear custom-map edit state (e.g. when switching browse tabs)."""
        self._editing_custom_map_id = None
        self._editing_custom_map_name = None
        self._edit_session_baseline_map = None
        self._exit_custom_map_edit_ui()

    def _ensure_browse_cards_loaded(self) -> None:
        if getattr(self, "_browse_cards_loaded", False):
            return
        self._browse_manager.setup()
        self._browse_cards_loaded = True

    def _reload_custom_maps_browse_list(self) -> None:
        """Load custom_maps.json and reset browse filters so cards are not all hidden.

        Predefined browsing shares the Advanced / search row; leaving Advanced checked while
        switching to Custom hides every non-advanced custom map (empty list after Back).

        Always rebuild from disk (do not only ``filter_map_cards``): maps saved from Solver /
        Deduction otherwise stay invisible until the user leaves and re-enters this tab.
        """
        cb_adv = self.cbMapsLibBrowseAdvanced
        if cb_adv is not None:
            cb_adv.blockSignals(True)
            cb_adv.setChecked(False)
            cb_adv.blockSignals(False)
        if self.edtMapsLibBrowseSearch:
            self.edtMapsLibBrowseSearch.blockSignals(True)
            self.edtMapsLibBrowseSearch.clear()
            self.edtMapsLibBrowseSearch.blockSignals(False)
        bm = self._browse_manager
        if bm is not None:
            self._ensure_browse_cards_loaded()
            bm.set_maps_json_path(CUSTOM_MAPS_JSON)

    def _reset_create_tab_to_new_map(self) -> None:
        """Blank create board + default advanced off (no edit session)."""
        if not self.board_builder:
            return
        self.board_builder.reset_board()
        self.cbMapsLibCreateAdvanced.blockSignals(True)
        self.cbMapsLibCreateAdvanced.setChecked(False)
        self.cbMapsLibCreateAdvanced.blockSignals(False)
        self.advanced_mode = False
        self.board_builder.apply_marker_visibility(False)
        if hasattr(self, "status_manager") and self.status_manager:
            self.status_manager.reset_for_build()
        self._status_touch()
        self._refresh_freeze_row_checkbox_paint(self.board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self.board_builder))
        if getattr(self, "_maps_undo_create", None) is not None:
            self._maps_undo_create.reset()

    def _on_segment_button_clicked(self, btn: QAbstractButton) -> None:
        if btn is self.btnMapsLibCreate:
            # Keep inline custom-map edit session so Custom Maps returns to the editor, not the grid.
            self.mapsLibStack.setCurrentIndex(0)
        elif btn is self.btnMapsLibPredefined:
            self.mapsLibStack.setCurrentIndex(1)
            self._exit_custom_map_edit_ui()
            self._ensure_browse_cards_loaded()
            self._browse_manager.set_maps_json_path(MAPS_JSON)
        elif btn is self.btnMapsLibCustom:
            self.mapsLibStack.setCurrentIndex(1)
            if self._editing_custom_map_id is None:
                self._leave_custom_map_edit_session()
            self._ensure_browse_cards_loaded()
            self._reload_custom_maps_browse_list()
            if (
                self._editing_custom_map_id is not None
                and self.mapsLibBrowseStack is not None
            ):
                self.mapsLibBrowseStack.setCurrentIndex(1)
        touch_breadcrumbs(self)
        self._maps_lib_update_undo_tracking()

    def _build_create_board(self) -> None:
        if self.mapsLibViewContainer is None:
            return
        self.scene = QGraphicsScene()
        # Use BoardView (same sceneRect = viewport as Deduction/build). Host min-height shows advanced row.
        self.view = BoardView(self.scene)
        vl = self.mapsLibViewContainer.layout()
        if vl is None:
            vl = QGridLayout(self.mapsLibViewContainer)
        vl.addWidget(self.view, 0, 0)
        vl.setColumnStretch(0, 1)
        vl.setRowStretch(0, 1)

        self.board_builder = BoardBuilder(self.scene, self.view)

        def _create_add_tooltip(widget, text, **kw):
            if text == TOOLTIP_FREEZE_MAP:
                kw["only_when"] = lambda: (
                    self.mapsLibStack is not None and self.mapsLibStack.currentIndex() == 0
                )
            self._app_tooltip.add(widget, text, **kw)

        self.board_builder.build(
            add_tooltip=_create_add_tooltip,
            tooltip_freeze_map=TOOLTIP_FREEZE_MAP,
            tooltip_manager=self._app_tooltip,
        )
        self.canvas = self.board_builder.canvas
        self.pieces = self.board_builder.pieces
        self.markers = self.board_builder.markers
        if self.board_builder.cbFreezeMap:
            self._app_tooltip.add(
                self.board_builder.cbFreezeMap,
                TOOLTIP_FREEZE_MAP_ENABLED,
                only_when_disabled=False,
                only_when=lambda: (
                    self.mapsLibStack is not None
                    and self.mapsLibStack.currentIndex() == 0
                    and self.board_builder is not None
                    and self.board_builder.cbFreezeMap is not None
                    and self.board_builder.cbFreezeMap.isEnabled()
                ),
            )

        self._maps_lib_repack_create_freeze_row()

        self.mapsLibStatusList = QListWidget()
        self.mapsLibStatusList.setObjectName("mapsLibStatusList")
        self.mapsLibStatusList.setMinimumHeight(0)
        configure_status_list_wrapping(self.mapsLibStatusList)
        # Header + two status rows (icons + wrapped text).
        self.mapsLibStatusList.setMaximumHeight(110)
        self.mapsLibStatusList.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.mapsLibStatusList.adjustSize()

        self._status_proxy = self.scene.addWidget(self.mapsLibStatusList)
        self._status_proxy.setZValue(10005)

        self._position_status_proxy()

        # Help (?): same overlay pattern as Solve/Deduction; icon px matches map card edit/delete (20).
        icon_indent = 12
        help_icon_px = 20
        help_icon = QLabel()
        help_icon.setObjectName("helpIconOverlay")
        help_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if ICON_HELP.exists():
            pix = QPixmap(str(ICON_HELP))
            if not pix.isNull():
                help_icon.setPixmap(
                    pix.scaled(
                        help_icon_px,
                        help_icon_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        help_icon.setFixedSize(help_icon_px, help_icon_px)
        help_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._help_icon_wrapper = QWidget()
        self._help_icon_wrapper.setObjectName("helpIconWrapper")
        self._help_icon_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._help_icon_wrapper.setFixedSize(help_icon_px + icon_indent, help_icon_px + icon_indent)
        wl = QHBoxLayout(self._help_icon_wrapper)
        wl.setContentsMargins(0, icon_indent, icon_indent, 0)
        wl.addStretch()
        wl.addWidget(help_icon, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self._help_icon_proxy = self.scene.addWidget(self._help_icon_wrapper)
        self._help_icon_proxy.setZValue(100)
        self._update_help_icon_pos()
        self._app_tooltip.add(
            self._help_icon_wrapper,
            TOOLTIP_HELP_BUILD,
            only_when_disabled=False,
            only_when=lambda: self.mapsLibStack is not None
            and self.mapsLibStack.currentIndex() == 0,
        )

        self._app_tooltip.add(
            self.cbMapsLibCreateAdvanced,
            TOOLTIP_ADVANCED_MODE,
            only_when_disabled=False,
            only_when=lambda: self.mapsLibStack is not None
            and self.mapsLibStack.currentIndex() == 0,
        )
        self.cbMapsLibCreateAdvanced.toggled.connect(self._on_create_advanced_toggled)

        self._icon_ok = QIcon(str(ICON_STATUS_OK))
        self._icon_error = QIcon(str(ICON_STATUS_ERROR))
        self.status_manager = MapsLibraryStatusManager(
            self.mapsLibStatusList,
            self._icon_ok,
            self._icon_error,
            self.board_builder.cbFreezeMap,
            self.canvas,
            self.pieces,
            self.markers,
        )

        def _on_marker_assigned() -> None:
            self._status_touch()

        self.canvas._on_marker_assigned = lambda: QTimer.singleShot(0, _on_marker_assigned)

        def _on_marker_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot and self.board_builder:
                self.board_builder.clear_highlights()
            QTimer.singleShot(0, self._status_touch)

        self.canvas._on_marker_reassigned = _on_marker_reassigned

        def _on_piece_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot and self.board_builder:
                self.board_builder.clear_highlights()
            QTimer.singleShot(0, self._status_touch)

        self.canvas._on_piece_reassigned = _on_piece_reassigned

        self.view._on_resize = lambda: QTimer.singleShot(0, self._on_view_resized)
        self.board_builder.apply_marker_visibility(self.advanced_mode)
        self._status_touch()
        self._apply_maps_lib_board_minimum_height()
        QTimer.singleShot(0, self._apply_maps_lib_board_minimum_height)
        self._setup_maps_undo_create_if_needed()
        self._maps_lib_update_undo_tracking()

    def _setup_maps_undo_create_if_needed(self) -> None:
        if getattr(self, "_maps_undo_create", None) is not None:
            return
        bb = self.board_builder
        if bb is None or getattr(bb, "btnUndoFreeze", None) is None:
            return

        def _after() -> None:
            self._status_touch()
            if self.board_builder:
                self._refresh_freeze_row_checkbox_paint(self.board_builder)

        self._maps_undo_create = BoardUndoController(
            bb,
            [bb.btnUndoFreeze],
            self._app_tooltip,
            TOOLTIP_UNDO,
            after_undo=lambda: QTimer.singleShot(0, _after),
        )

    def _setup_maps_undo_custom_if_needed(self) -> None:
        if getattr(self, "_maps_undo_custom", None) is not None:
            return
        bb = self._ce_board_builder
        if bb is None or getattr(bb, "btnUndoFreeze", None) is None:
            return

        def _after() -> None:
            self._ce_status_touch()
            if self._ce_board_builder:
                self._refresh_freeze_row_checkbox_paint(self._ce_board_builder)

        self._maps_undo_custom = BoardUndoController(
            bb,
            [bb.btnUndoFreeze],
            self._app_tooltip,
            TOOLTIP_UNDO,
            after_undo=lambda: QTimer.singleShot(0, _after),
        )

    def _maps_lib_update_undo_tracking(self) -> None:
        create_on = self.mapsLibStack is not None and self.mapsLibStack.currentIndex() == 0
        custom_on = (
            self.mapsLibStack is not None
            and self.mapsLibStack.currentIndex() == 1
            and self.mapsLibBrowseStack is not None
            and self.mapsLibBrowseStack.currentIndex() == 1
        )
        u = getattr(self, "_maps_undo_create", None)
        if u is not None:
            u.set_tracking(create_on)
        u2 = getattr(self, "_maps_undo_custom", None)
        if u2 is not None:
            u2.set_tracking(custom_on)

    def _ensure_custom_edit_board(self) -> None:
        if self._ce_board_builder is not None:
            return
        self._build_custom_edit_board()

    def _build_custom_edit_board(self) -> None:
        if self.mapsLibCustomEditViewContainer is None:
            return
        self._ce_scene = QGraphicsScene()
        self._ce_view = BoardView(self._ce_scene)
        vl = self.mapsLibCustomEditViewContainer.layout()
        if vl is None:
            vl = QGridLayout(self.mapsLibCustomEditViewContainer)
        vl.addWidget(self._ce_view, 0, 0)
        vl.setColumnStretch(0, 1)
        vl.setRowStretch(0, 1)

        self._ce_board_builder = BoardBuilder(self._ce_scene, self._ce_view)

        def _ce_add_tooltip(widget, text, **kw):
            if text == TOOLTIP_FREEZE_MAP:
                kw["only_when"] = lambda: (
                    self.mapsLibStack is not None
                    and self.mapsLibStack.currentIndex() == 1
                    and self.mapsLibBrowseStack is not None
                    and self.mapsLibBrowseStack.currentIndex() == 1
                )
            self._app_tooltip.add(widget, text, **kw)

        self._ce_board_builder.build(
            add_tooltip=_ce_add_tooltip,
            tooltip_freeze_map=TOOLTIP_FREEZE_MAP,
            tooltip_manager=self._app_tooltip,
        )
        self._ce_canvas = self._ce_board_builder.canvas
        self._ce_pieces = self._ce_board_builder.pieces
        self._ce_markers = self._ce_board_builder.markers
        if self._ce_board_builder.cbFreezeMap:
            self._app_tooltip.add(
                self._ce_board_builder.cbFreezeMap,
                TOOLTIP_FREEZE_MAP_ENABLED,
                only_when_disabled=False,
                only_when=lambda: (
                    self.mapsLibStack is not None
                    and self.mapsLibStack.currentIndex() == 1
                    and self.mapsLibBrowseStack is not None
                    and self.mapsLibBrowseStack.currentIndex() == 1
                    and self._ce_board_builder is not None
                    and self._ce_board_builder.cbFreezeMap is not None
                    and self._ce_board_builder.cbFreezeMap.isEnabled()
                ),
            )

        self._maps_lib_repack_custom_edit_freeze_row()

        self._ce_mapsLibStatusList = QListWidget()
        self._ce_mapsLibStatusList.setObjectName("mapsLibCustomEditStatusList")
        self._ce_mapsLibStatusList.setMinimumHeight(0)
        configure_status_list_wrapping(self._ce_mapsLibStatusList)
        self._ce_mapsLibStatusList.setMaximumHeight(110)
        self._ce_mapsLibStatusList.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._ce_mapsLibStatusList.adjustSize()

        self._ce_status_proxy = self._ce_scene.addWidget(self._ce_mapsLibStatusList)
        self._ce_status_proxy.setZValue(10005)

        self._ce_position_status_proxy()

        icon_indent = 12
        help_icon_px = 20
        help_icon = QLabel()
        help_icon.setObjectName("helpIconOverlayCustomEdit")
        help_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if ICON_HELP.exists():
            pix = QPixmap(str(ICON_HELP))
            if not pix.isNull():
                help_icon.setPixmap(
                    pix.scaled(
                        help_icon_px,
                        help_icon_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        help_icon.setFixedSize(help_icon_px, help_icon_px)
        help_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ce_help_icon_wrapper = QWidget()
        self._ce_help_icon_wrapper.setObjectName("helpIconWrapperCustomEdit")
        self._ce_help_icon_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._ce_help_icon_wrapper.setFixedSize(help_icon_px + icon_indent, help_icon_px + icon_indent)
        wl = QHBoxLayout(self._ce_help_icon_wrapper)
        wl.setContentsMargins(0, icon_indent, icon_indent, 0)
        wl.addStretch()
        wl.addWidget(help_icon, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self._ce_help_icon_proxy = self._ce_scene.addWidget(self._ce_help_icon_wrapper)
        self._ce_help_icon_proxy.setZValue(100)
        self._ce_update_help_icon_pos()
        self._app_tooltip.add(
            self._ce_help_icon_wrapper,
            TOOLTIP_HELP_BUILD,
            only_when_disabled=False,
            only_when=lambda: (
                self.mapsLibStack is not None
                and self.mapsLibStack.currentIndex() == 1
                and self.mapsLibBrowseStack is not None
                and self.mapsLibBrowseStack.currentIndex() == 1
            ),
        )

        self._app_tooltip.add(
            self.cbMapsLibCustomEditAdvanced,
            TOOLTIP_ADVANCED_MODE,
            only_when_disabled=False,
            only_when=lambda: (
                self.mapsLibStack is not None
                and self.mapsLibStack.currentIndex() == 1
                and self.mapsLibBrowseStack is not None
                and self.mapsLibBrowseStack.currentIndex() == 1
            ),
        )
        self.cbMapsLibCustomEditAdvanced.toggled.connect(self._on_custom_edit_advanced_toggled)

        if not hasattr(self, "_icon_ok"):
            self._icon_ok = QIcon(str(ICON_STATUS_OK))
            self._icon_error = QIcon(str(ICON_STATUS_ERROR))
        self._ce_status_manager = MapsLibraryStatusManager(
            self._ce_mapsLibStatusList,
            self._icon_ok,
            self._icon_error,
            self._ce_board_builder.cbFreezeMap,
            self._ce_canvas,
            self._ce_pieces,
            self._ce_markers,
        )

        def _ce_on_marker_assigned() -> None:
            self._ce_status_touch()

        self._ce_canvas._on_marker_assigned = lambda: QTimer.singleShot(0, _ce_on_marker_assigned)

        def _ce_on_marker_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot and self._ce_board_builder:
                self._ce_board_builder.clear_highlights()
            QTimer.singleShot(0, self._ce_status_touch)

        self._ce_canvas._on_marker_reassigned = _ce_on_marker_reassigned

        def _ce_on_piece_reassigned(old_slot, new_slot) -> None:
            if old_slot != new_slot and self._ce_board_builder:
                self._ce_board_builder.clear_highlights()
            QTimer.singleShot(0, self._ce_status_touch)

        self._ce_canvas._on_piece_reassigned = _ce_on_piece_reassigned

        self._ce_view._on_resize = lambda: QTimer.singleShot(0, self._ce_on_view_resized)
        self._ce_board_builder.apply_marker_visibility(self.custom_edit_advanced_mode)
        self._ce_status_touch()
        self._apply_custom_edit_board_minimum_height()
        QTimer.singleShot(0, self._apply_custom_edit_board_minimum_height)
        self._setup_maps_undo_custom_if_needed()
        self._maps_lib_update_undo_tracking()

    def _status_touch(self) -> None:
        if hasattr(self, "status_manager") and self.status_manager is not None:
            self.status_manager.update()
        self._refresh_structures_region_visibility()
        self._position_create_freeze_row()
        self._position_status_proxy()
        self._update_help_icon_pos()
        self._refresh_save_enabled()
        # Proxy + QSS: programmatic enable/check uses blockSignals — repaint like user toggle.
        if self.board_builder is not None:
            self._refresh_freeze_row_checkbox_paint(self.board_builder)

    def _refresh_save_enabled(self) -> None:
        sm = getattr(self, "status_manager", None)
        en = bool(sm and sm.is_save_ready())
        if self.btnMapsLibSave:
            self.btnMapsLibSave.setEnabled(en)

    def _ce_refresh_save_enabled(self) -> None:
        sm = self._ce_status_manager
        en = bool(sm and sm.is_save_ready())
        if self.btnMapsLibSaveCustomEdit:
            self.btnMapsLibSaveCustomEdit.setEnabled(en)

    def _refresh_structures_region_visibility(self) -> None:
        """When all structure markers are placed, hide only the panel backdrop; labels/stack stay visible."""
        bb = self.board_builder
        sm = getattr(self, "status_manager", None)
        if bb is None or sm is None:
            return
        if getattr(bb, "_chips_mode", False):
            return
        all_struct = getattr(sm, "all_struct", False)
        if all_struct and hasattr(bb, "hide_structures_background_only"):
            bb.hide_structures_background_only()
        elif not all_struct and hasattr(bb, "show_structures_region"):
            bb.show_structures_region()

    def _on_view_resized(self) -> None:
        self._position_create_freeze_row()
        self._position_status_proxy()
        self._update_help_icon_pos()

    def _maps_lib_repack_create_freeze_row(self) -> None:
        """Create Map: Advanced mode left of Freeze map on one row under the canvas."""
        bb = self.board_builder
        if bb is None or getattr(bb, "_freeze_row", None) is None:
            return
        fr = bb._freeze_row
        fl = fr.layout()
        if fl is None:
            return
        while fl.count():
            it = fl.takeAt(0)
            w = it.widget()
            if w is None:
                continue
            w.setParent(None)
            if w is bb.cbFreezeMap or w is getattr(bb, "btnUndoFreeze", None):
                continue
            w.deleteLater()
        self.cbMapsLibCreateAdvanced = QCheckBox()
        self.cbMapsLibCreateAdvanced.setObjectName("cbMapsLibCreateAdvanced")
        fl.addStretch(1)
        fl.addWidget(QLabel("Advanced mode:"))
        fl.addWidget(self.cbMapsLibCreateAdvanced)
        fl.addWidget(QLabel("Freeze map:"))
        fl.addWidget(bb.cbFreezeMap)
        if getattr(bb, "btnUndoFreeze", None) is not None:
            fl.addWidget(bb.btnUndoFreeze)
        fr.adjustSize()
        self._position_create_freeze_row()
        self._refresh_freeze_row_checkbox_paint(bb)
        if bb.cbFreezeMap is not None:
            bb.cbFreezeMap.stateChanged.connect(
                lambda _s, b=bb: self._refresh_freeze_row_checkbox_paint(b)
            )

    def _position_create_freeze_row(self) -> None:
        bb = self.board_builder
        proxy = getattr(bb, "_proxy_freeze", None) if bb else None
        fr = getattr(bb, "_freeze_row", None) if bb else None
        if bb is None or proxy is None or fr is None:
            return
        canvas_w = float(getattr(bb, "_canvas_w", 0))
        canvas_h = float(getattr(bb, "_canvas_h", 0))
        fr.setFixedWidth(int(max(1, canvas_w)))
        fr.adjustSize()
        proxy.setPos(9.0, 9.0 + canvas_h + 8.0)

    def _refresh_freeze_row_checkbox_paint(self, bb: BoardBuilder | None) -> None:
        """QGraphicsProxyWidget + app QSS: force toggle indicators to repaint after :checked changes."""
        if bb is None:
            return
        fr = getattr(bb, "_freeze_row", None)
        proxy = getattr(bb, "_proxy_freeze", None)
        if fr is not None:
            for cb in fr.findChildren(QCheckBox):
                st = cb.style()
                if st is not None:
                    st.unpolish(cb)
                    st.polish(cb)
                cb.updateGeometry()
                cb.update()
            fr.update()
        if proxy is not None:
            proxy.setCacheMode(QGraphicsItem.CacheMode.NoCache)
            proxy.update()

    def _maps_lib_big_board_rect(self) -> QRectF | None:
        """Canvas + structures band + spare tiles bank (layout at home), in scene coordinates."""
        bb = self.board_builder
        if bb is None or not getattr(bb, "pieces", None):
            return None
        canvas_w = float(getattr(bb, "_canvas_w", 0))
        canvas_h = float(getattr(bb, "_canvas_h", 0))
        st = float(getattr(bb, "_structures_top", 0))
        sh = float(getattr(bb, "_structures_height", 100))
        r = QRectF(9, 9, canvas_w, canvas_h)
        r |= QRectF(9, st, canvas_w, sh)
        for p in bb.pieces:
            hp = getattr(p, "_home_pos", None)
            if hp is None:
                continue
            br = p.boundingRect()
            r |= QRectF(
                hp.x() + br.left(),
                hp.y() + br.top(),
                br.width(),
                br.height(),
            )
        return r

    def _maps_lib_layout_bottom(self) -> float:
        """Bottom Y below structures; pad matches former separate Advanced strip (stable boardHost min-height)."""
        bb = self.board_builder
        if bb is None:
            return 620.0
        structures_top = float(getattr(bb, "_structures_top", 0))
        structures_h = float(getattr(bb, "_structures_height", 100))
        gap = 10
        below_struct_pad = 38
        return structures_top + structures_h + gap + below_struct_pad + 16

    def _apply_maps_lib_board_minimum_height(self) -> None:
        """Set min height on the Create page board host from the create board layout."""
        need = int(math.ceil(self._maps_lib_layout_bottom()))
        h = max(need, 620)
        if self.mapsLibBoardHost is not None:
            self.mapsLibBoardHost.setMinimumHeight(h)

    def _apply_custom_edit_board_minimum_height(self) -> None:
        """Set min height on the custom-edit board host from the CE board layout."""
        need = int(math.ceil(self._ce_maps_lib_layout_bottom()))
        h = max(need, 620)
        if self.mapsLibCustomEditBoardHost is not None:
            self.mapsLibCustomEditBoardHost.setMinimumHeight(h)

    def _position_status_proxy(self) -> None:
        if (
            self._status_proxy is None
            or self.scene is None
            or self.mapsLibStatusList is None
            or self.board_builder is None
        ):
            return
        self.mapsLibStatusList.adjustSize()
        w = float(self.mapsLibStatusList.width())
        h = float(self.mapsLibStatusList.height())
        margin = 6

        host = self.mapsLibBoardHost
        view = self.view
        vp = view.viewport() if view is not None else None
        if host is not None and view is not None and vp is not None:
            # Bottom-right of card host → viewport → scene (matches visible host border, incl. area below structures).
            br_host = host.rect().bottomRight()
            vp_pt = vp.mapFrom(host, br_host)
            scene_br = view.mapToScene(vp_pt)
            x = float(scene_br.x()) - w - margin
            y = float(scene_br.y()) - h - margin
        else:
            big = self._maps_lib_big_board_rect()
            if big is None or not big.isValid():
                return
            x = big.right() - w - margin
            y = big.bottom() - h - margin

        self._status_proxy.setPos(x, y)

    def _update_help_icon_pos(self) -> None:
        """Top-right of visible viewport in scene coords — matches ``board_mixin._update_help_icon_pos``."""
        if (
            self._help_icon_proxy is None
            or self._help_icon_wrapper is None
            or self.scene is None
            or self.view is None
        ):
            return
        vp = self.view.viewport().rect()
        vr = self.view.mapToScene(vp).boundingRect()
        if not vr.isValid() or vr.width() < 1.0 or vr.height() < 1.0:
            r = self.scene.sceneRect()
        else:
            r = vr
        w = self._help_icon_wrapper.width()
        self._help_icon_proxy.setPos(r.right() - w - 8, r.top() + 8)
        self._help_icon_proxy.setZValue(100)

    def _on_create_advanced_toggled(self, checked: bool) -> None:
        self.advanced_mode = bool(checked)
        if self.board_builder:
            self.board_builder.apply_marker_visibility(self.advanced_mode)
        # Refresh status rows + structures visibility (advanced markers appear at home).
        self._status_touch()
        self._refresh_freeze_row_checkbox_paint(self.board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self.board_builder))
        if not self.advanced_mode:
            def _rewrite_create_undo() -> None:
                u = getattr(self, "_maps_undo_create", None)
                if u is not None:
                    u.rewrite_snapshots_strip_advanced_markers()

            _rewrite_create_undo()
            QTimer.singleShot(0, _rewrite_create_undo)

    def _ce_status_touch(self) -> None:
        if self._ce_status_manager is not None:
            self._ce_status_manager.update()
        self._ce_refresh_structures_region_visibility()
        self._position_custom_edit_freeze_row()
        self._ce_position_status_proxy()
        self._ce_update_help_icon_pos()
        self._ce_refresh_save_enabled()
        if self._ce_board_builder is not None:
            self._refresh_freeze_row_checkbox_paint(self._ce_board_builder)

    def _ce_on_view_resized(self) -> None:
        self._position_custom_edit_freeze_row()
        self._ce_position_status_proxy()
        self._ce_update_help_icon_pos()

    def _ce_refresh_structures_region_visibility(self) -> None:
        bb = self._ce_board_builder
        sm = self._ce_status_manager
        if bb is None or sm is None:
            return
        if getattr(bb, "_chips_mode", False):
            return
        all_struct = getattr(sm, "all_struct", False)
        if all_struct and hasattr(bb, "hide_structures_background_only"):
            bb.hide_structures_background_only()
        elif not all_struct and hasattr(bb, "show_structures_region"):
            bb.show_structures_region()

    def _ce_maps_lib_big_board_rect(self) -> QRectF | None:
        bb = self._ce_board_builder
        if bb is None or not getattr(bb, "pieces", None):
            return None
        canvas_w = float(getattr(bb, "_canvas_w", 0))
        canvas_h = float(getattr(bb, "_canvas_h", 0))
        st = float(getattr(bb, "_structures_top", 0))
        sh = float(getattr(bb, "_structures_height", 100))
        r = QRectF(9, 9, canvas_w, canvas_h)
        r |= QRectF(9, st, canvas_w, sh)
        for p in bb.pieces:
            hp = getattr(p, "_home_pos", None)
            if hp is None:
                continue
            br = p.boundingRect()
            r |= QRectF(
                hp.x() + br.left(),
                hp.y() + br.top(),
                br.width(),
                br.height(),
            )
        return r

    def _ce_maps_lib_layout_bottom(self) -> float:
        bb = self._ce_board_builder
        if bb is None:
            return 620.0
        structures_top = float(getattr(bb, "_structures_top", 0))
        structures_h = float(getattr(bb, "_structures_height", 100))
        gap = 10
        below_struct_pad = 38
        return structures_top + structures_h + gap + below_struct_pad + 16

    def _ce_position_status_proxy(self) -> None:
        if (
            self._ce_status_proxy is None
            or self._ce_scene is None
            or self._ce_mapsLibStatusList is None
            or self._ce_board_builder is None
        ):
            return
        self._ce_mapsLibStatusList.adjustSize()
        w = float(self._ce_mapsLibStatusList.width())
        h = float(self._ce_mapsLibStatusList.height())
        margin = 6

        host = self.mapsLibCustomEditBoardHost
        view = self._ce_view
        vp = view.viewport() if view is not None else None
        if host is not None and view is not None and vp is not None:
            br_host = host.rect().bottomRight()
            vp_pt = vp.mapFrom(host, br_host)
            scene_br = view.mapToScene(vp_pt)
            x = float(scene_br.x()) - w - margin
            y = float(scene_br.y()) - h - margin
        else:
            big = self._ce_maps_lib_big_board_rect()
            if big is None or not big.isValid():
                return
            x = big.right() - w - margin
            y = big.bottom() - h - margin

        self._ce_status_proxy.setPos(x, y)

    def _ce_update_help_icon_pos(self) -> None:
        if (
            self._ce_help_icon_proxy is None
            or self._ce_help_icon_wrapper is None
            or self._ce_scene is None
            or self._ce_view is None
        ):
            return
        vp = self._ce_view.viewport().rect()
        vr = self._ce_view.mapToScene(vp).boundingRect()
        if not vr.isValid() or vr.width() < 1.0 or vr.height() < 1.0:
            r = self._ce_scene.sceneRect()
        else:
            r = vr
        w = self._ce_help_icon_wrapper.width()
        self._ce_help_icon_proxy.setPos(r.right() - w - 8, r.top() + 8)
        self._ce_help_icon_proxy.setZValue(100)

    def _maps_lib_repack_custom_edit_freeze_row(self) -> None:
        """Custom edit: same row as Create Map — Advanced left of Freeze, group right-aligned."""
        bb = self._ce_board_builder
        if bb is None or getattr(bb, "_freeze_row", None) is None:
            return
        fr = bb._freeze_row
        fl = fr.layout()
        if fl is None:
            return
        while fl.count():
            it = fl.takeAt(0)
            w = it.widget()
            if w is None:
                continue
            w.setParent(None)
            if w is bb.cbFreezeMap or w is getattr(bb, "btnUndoFreeze", None):
                continue
            w.deleteLater()
        self.cbMapsLibCustomEditAdvanced = QCheckBox()
        self.cbMapsLibCustomEditAdvanced.setObjectName("cbMapsLibCustomEditAdvanced")
        fl.addStretch(1)
        fl.addWidget(QLabel("Advanced mode:"))
        fl.addWidget(self.cbMapsLibCustomEditAdvanced)
        fl.addWidget(QLabel("Freeze map:"))
        fl.addWidget(bb.cbFreezeMap)
        if getattr(bb, "btnUndoFreeze", None) is not None:
            fl.addWidget(bb.btnUndoFreeze)
        fr.adjustSize()
        self._position_custom_edit_freeze_row()
        self._refresh_freeze_row_checkbox_paint(bb)
        if bb.cbFreezeMap is not None:
            bb.cbFreezeMap.stateChanged.connect(
                lambda _s, b=bb: self._refresh_freeze_row_checkbox_paint(b)
            )

    def _position_custom_edit_freeze_row(self) -> None:
        bb = self._ce_board_builder
        proxy = getattr(bb, "_proxy_freeze", None) if bb else None
        fr = getattr(bb, "_freeze_row", None) if bb else None
        if bb is None or proxy is None or fr is None:
            return
        canvas_w = float(getattr(bb, "_canvas_w", 0))
        canvas_h = float(getattr(bb, "_canvas_h", 0))
        fr.setFixedWidth(int(max(1, canvas_w)))
        fr.adjustSize()
        proxy.setPos(9.0, 9.0 + canvas_h + 8.0)

    def _on_custom_edit_advanced_toggled(self, checked: bool) -> None:
        self.custom_edit_advanced_mode = bool(checked)
        if self._ce_board_builder:
            self._ce_board_builder.apply_marker_visibility(self.custom_edit_advanced_mode)
        self._ce_status_touch()
        self._refresh_freeze_row_checkbox_paint(self._ce_board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self._ce_board_builder))
        if not self.custom_edit_advanced_mode:
            def _rewrite_ce_undo() -> None:
                u = getattr(self, "_maps_undo_custom", None)
                if u is not None:
                    u.rewrite_snapshots_strip_advanced_markers()

            _rewrite_ce_undo()
            QTimer.singleShot(0, _rewrite_ce_undo)

    def _on_clear_all(self) -> None:
        mb = QMessageBox(self.window)
        mb.setWindowTitle(RESET_CONFIRM_TITLE)
        mb.setText(RESET_CONFIRM_MSG)
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        no_btn = mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        yes_btn.style().unpolish(yes_btn)
        yes_btn.style().polish(yes_btn)
        gl = mb.findChild(QGridLayout)
        if gl:
            gl.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        self._leave_custom_map_edit_session()
        if self.board_builder:
            self.board_builder.reset_board()
        self.cbMapsLibCreateAdvanced.blockSignals(True)
        self.cbMapsLibCreateAdvanced.setChecked(False)
        self.cbMapsLibCreateAdvanced.blockSignals(False)
        self.advanced_mode = False
        if self.board_builder:
            self.board_builder.apply_marker_visibility(False)
        if hasattr(self, "status_manager") and self.status_manager:
            self.status_manager.reset_for_build()
            self._status_touch()
        self._refresh_freeze_row_checkbox_paint(self.board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self.board_builder))
        if getattr(self, "_maps_undo_create", None) is not None:
            self._maps_undo_create.reset()

    def _on_custom_edit_back(self) -> None:
        """Show Custom Maps grid; discard edit session (unsaved changes are not written to JSON)."""
        self._leave_custom_map_edit_session()
        self._reload_custom_maps_browse_list()
        touch_breadcrumbs(self)
        self._maps_lib_update_undo_tracking()

    def _on_custom_edit_clear_all(self) -> None:
        if (
            self._editing_custom_map_id is None
            or self._edit_session_baseline_map is None
            or not self._ce_board_builder
            or self.cbMapsLibCustomEditAdvanced is None
        ):
            return
        mb = QMessageBox(self.window)
        mb.setWindowTitle(MAP_EDIT_REVERT_TITLE)
        mb.setText(MAP_EDIT_REVERT_MSG)
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        no_btn = mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        yes_btn.style().unpolish(yes_btn)
        yes_btn.style().polish(yes_btn)
        gl = mb.findChild(QGridLayout)
        if gl:
            gl.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        base = copy.deepcopy(self._edit_session_baseline_map)
        advanced = bool(base.get("advancedMode", False))
        self.cbMapsLibCustomEditAdvanced.blockSignals(True)
        self.cbMapsLibCustomEditAdvanced.setChecked(advanced)
        self.cbMapsLibCustomEditAdvanced.blockSignals(False)
        self.custom_edit_advanced_mode = advanced
        self._ce_board_builder.apply_marker_visibility(advanced)
        self._ce_board_builder.load_from_map_data(base, freeze=True)
        self._ce_status_touch()
        self._ce_refresh_save_enabled()
        self._refresh_freeze_row_checkbox_paint(self._ce_board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self._ce_board_builder))
        if getattr(self, "_maps_undo_custom", None) is not None:
            self._maps_undo_custom.reset()

    def _reload_edit_baseline_from_disk(self, map_id: int) -> None:
        """Refresh edit snapshot after a successful save (matches JSON on disk)."""
        try:
            with open(CUSTOM_MAPS_JSON, encoding="utf-8") as f:
                root = json.load(f)
            for m in root.get("maps") or []:
                if m.get("id") == map_id:
                    self._edit_session_baseline_map = copy.deepcopy(m)
                    nm = (m.get("name") or "").strip()
                    if nm:
                        self._editing_custom_map_name = nm
                    return
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    def _on_save(self) -> None:
        if not self.board_builder or not self.board_builder.canvas:
            return
        name = prompt_save_map_name(self.window, default_name=None)
        if name is None:
            return
        ok = append_custom_map_to_json(
            name, self.board_builder, bool(self.advanced_mode)
        )
        if not ok:
            mb = QMessageBox(self.window)
            mb.setWindowTitle(MAP_SAVE_ERROR_TITLE)
            mb.setText(MAP_SAVE_ERROR_MSG)
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.exec()
            return
        self._leave_custom_map_edit_session()
        self._maps_lib_update_undo_tracking()
        show_toast(self.pages_stack, MAP_SAVE_SUCCESS_TOAST.format(map_name=name))
        bm = self._browse_manager
        p = getattr(bm, "_maps_json_path", None)
        if p is not None and p.resolve() == CUSTOM_MAPS_JSON.resolve():
            bm.setup()

    def _on_custom_edit_save(self) -> None:
        if not self._ce_board_builder or not self._ce_board_builder.canvas:
            return
        editing_id = self._editing_custom_map_id
        if editing_id is None:
            return
        name = (
            (self._editing_custom_map_name or "").strip() or MAP_SAVE_NAME_PLACEHOLDER
        )
        ok = self._update_custom_map_in_json(
            editing_id,
            name,
            builder=self._ce_board_builder,
            advanced_mode=self.custom_edit_advanced_mode,
        )
        if not ok:
            mb = QMessageBox(self.window)
            mb.setWindowTitle(MAP_SAVE_ERROR_TITLE)
            mb.setText(MAP_SAVE_ERROR_MSG)
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.exec()
            return
        # Browse list filter matches "Advanced mode" checkbox to map advancedMode; if the map's
        # mode changed on save, a stale checkbox hides every card (empty list).
        cb_adv = self.cbMapsLibBrowseAdvanced
        if cb_adv is not None:
            cb_adv.blockSignals(True)
            cb_adv.setChecked(bool(self.custom_edit_advanced_mode))
            cb_adv.blockSignals(False)
        # Show the card grid before rebuilding so layout/scroll viewport width is valid.
        self._leave_custom_map_edit_session()
        self._maps_lib_update_undo_tracking()
        show_toast(self.pages_stack, MAP_UPDATE_SUCCESS_TOAST.format(map_name=name))
        bm = self._browse_manager
        p = getattr(bm, "_maps_json_path", None)
        if p is None or p.resolve() != CUSTOM_MAPS_JSON.resolve():
            bm.set_maps_json_path(CUSTOM_MAPS_JSON)
        else:
            bm.setup()
        touch_breadcrumbs(self)

    def _on_custom_map_rename_name(self, map_data: dict) -> None:
        mid = map_data.get("id")
        if not isinstance(mid, int):
            return
        current_raw = (map_data.get("name") or "").strip()
        current = current_raw if current_raw else MAP_SAVE_NAME_PLACEHOLDER
        name = prompt_save_map_name(
            self.window,
            default_name=current,
            window_title=MAP_EDIT_MAP_NAME_DIALOG_TITLE,
        )
        if name is None or name == current:
            return
        if not rename_custom_map_in_json(mid, name):
            mb = QMessageBox(self.window)
            mb.setWindowTitle(MAP_SAVE_ERROR_TITLE)
            mb.setText(MAP_SAVE_ERROR_MSG)
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.exec()
            return
        if self._editing_custom_map_id == mid:
            self._editing_custom_map_name = name
            if self._edit_session_baseline_map is not None:
                self._edit_session_baseline_map["name"] = name
            touch_breadcrumbs(self)
        bm = self._browse_manager
        p = getattr(bm, "_maps_json_path", None)
        if p is not None and p.resolve() == CUSTOM_MAPS_JSON.resolve():
            bm.setup()
        show_toast(self.pages_stack, MAP_SAVE_SUCCESS_TOAST.format(map_name=name))

    def _on_custom_map_edit(self, map_data: dict) -> None:
        if self.mapsLibCustomEditViewContainer is None or self.mapsLibBrowseStack is None:
            return
        self._ensure_custom_edit_board()
        if not self._ce_board_builder:
            md = dict(map_data)
            QTimer.singleShot(0, lambda: self._on_custom_map_edit(md))
            return
        self._seg_group.blockSignals(True)
        try:
            if self.mapsLibStack is not None:
                self.mapsLibStack.setCurrentIndex(1)
            self.btnMapsLibCustom.setChecked(True)
            self._browse_manager.set_maps_json_path(CUSTOM_MAPS_JSON)
            self.mapsLibBrowseStack.setCurrentIndex(1)
            mid = map_data.get("id")
            self._editing_custom_map_id = mid if isinstance(mid, int) else None
            nm = (map_data.get("name") or "").strip()
            self._editing_custom_map_name = nm or None
            self._edit_session_baseline_map = copy.deepcopy(map_data)

            advanced = bool(map_data.get("advancedMode", False))
            self.custom_edit_advanced_mode = advanced
            if self.cbMapsLibCustomEditAdvanced is not None:
                self.cbMapsLibCustomEditAdvanced.blockSignals(True)
                self.cbMapsLibCustomEditAdvanced.setChecked(advanced)
                self.cbMapsLibCustomEditAdvanced.blockSignals(False)
            self._ce_board_builder.apply_marker_visibility(advanced)
            self._ce_board_builder.load_from_map_data(map_data, freeze=True)
        finally:
            self._seg_group.blockSignals(False)
        self._apply_custom_edit_board_minimum_height()
        QTimer.singleShot(0, self._apply_custom_edit_board_minimum_height)
        self._ce_status_touch()
        self._ce_refresh_save_enabled()
        self._refresh_freeze_row_checkbox_paint(self._ce_board_builder)
        QTimer.singleShot(0, lambda: self._refresh_freeze_row_checkbox_paint(self._ce_board_builder))
        touch_breadcrumbs(self)
        if getattr(self, "_maps_undo_custom", None) is not None:
            self._maps_undo_custom.reset()
        self._maps_lib_update_undo_tracking()

    def _on_custom_map_delete(self, map_data: dict) -> None:
        mid = map_data.get("id")
        if not isinstance(mid, int):
            return
        name = map_data.get("name") or f"Map {mid}"
        mb = QMessageBox(self.window)
        mb.setWindowTitle(MAP_DELETE_CONFIRM_TITLE)
        mb.setText(MAP_DELETE_CONFIRM_MSG.format(map_name=name))
        if ICON_HELP.exists():
            icon = QIcon(str(ICON_HELP))
            pix = icon.pixmap(48, 48)
            if not pix.isNull():
                mb.setIconPixmap(pix)
        mb.setStandardButtons(QMessageBox.StandardButton.NoButton)
        no_btn = mb.addButton("No", QMessageBox.ButtonRole.NoRole)
        yes_btn = mb.addButton("Yes", QMessageBox.ButtonRole.NoRole)
        mb.setDefaultButton(yes_btn)
        yes_btn.setProperty("primary", True)
        yes_btn.style().unpolish(yes_btn)
        yes_btn.style().polish(yes_btn)
        gl = mb.findChild(QGridLayout)
        if gl:
            gl.setHorizontalSpacing(0)
        mb.exec()
        if mb.clickedButton() != yes_btn:
            return
        if not self._soft_delete_custom_map(mid):
            err = QMessageBox(self.window)
            err.setWindowTitle(MAP_SAVE_ERROR_TITLE)
            err.setText(MAP_SAVE_ERROR_MSG)
            err.setIcon(QMessageBox.Icon.Warning)
            err.exec()
            return
        if self._editing_custom_map_id == mid:
            self._leave_custom_map_edit_session()
            self._maps_lib_update_undo_tracking()
        bm = self._browse_manager
        p = getattr(bm, "_maps_json_path", None)
        if p is not None and p.resolve() == CUSTOM_MAPS_JSON.resolve():
            bm.setup()
        show_toast(self.pages_stack, MAP_DELETE_SUCCESS_TOAST.format(map_name=name))

    def _soft_delete_custom_map(self, map_id: int) -> bool:
        path = CUSTOM_MAPS_JSON
        try:
            with open(path, encoding="utf-8") as f:
                root = json.load(f)
            maps_list = root.get("maps") or []
            found = False
            for m in maps_list:
                if m.get("id") == map_id:
                    m["soft_deleted"] = 1
                    found = True
                    break
            if not found:
                return False
            root["maps"] = maps_list
            with open(path, "w", encoding="utf-8") as f:
                json.dump(root, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError, ValueError):
            return False
        return True

    def _update_custom_map_in_json(
        self,
        map_id: int,
        name: str,
        *,
        builder: BoardBuilder | None = None,
        advanced_mode: bool | None = None,
    ) -> bool:
        bb = self.board_builder if builder is None else builder
        if bb is None:
            return False
        adv = self.advanced_mode if advanced_mode is None else advanced_mode
        exported = bb.export_board_to_map_data()
        path = CUSTOM_MAPS_JSON
        try:
            with open(path, encoding="utf-8") as f:
                root = json.load(f)
            maps_list = list(root.get("maps") or [])
            found = False
            for i, m in enumerate(maps_list):
                if m.get("id") == map_id:
                    maps_list[i] = {
                        **m,
                        "name": name,
                        "advancedMode": bool(adv),
                        "grid3x2": exported["grid3x2"],
                        "structures": exported["structures"],
                        "soft_deleted": 0,
                    }
                    found = True
                    break
            if not found:
                return False
            root["maps"] = maps_list
            with open(path, "w", encoding="utf-8") as f:
                json.dump(root, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError, ValueError):
            return False
        invalidate_map_thumbnail_on_disk(map_id)
        return True

    def on_navigate_away(self) -> None:
        """Maps Library state (create board, browse filters) lives in widgets — no teardown."""

    def on_navigate_to(self) -> None:
        """Refresh Custom Maps cards when returning (e.g. after Solver save)."""
        if self.btnMapsLibCustom is not None and self.btnMapsLibCustom.isChecked():
            if self._editing_custom_map_id is None:
                self._reload_custom_maps_browse_list()