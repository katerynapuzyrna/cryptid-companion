"""Solver page: Widget wiring, map cards, rules, tooltips, and deferred board build."""
from PySide6.QtWidgets import (
    QGridLayout,
    QMessageBox,
    QWidget,
    QPushButton,
    QComboBox,
    QLabel,
    QCheckBox,
    QLineEdit,
    QGraphicsScene,
    QListWidget,
    QStackedWidget,
    QScrollArea,
    QButtonGroup,
    QHBoxLayout,
    QToolButton,
)
from PySide6.QtCore import QTimer, Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QIcon
from typing import Optional

from board.board_view import BoardView
from board.board_builder import BoardBuilder
from board.canvas import PuzzleCanvas
from board.markers import MarkerItem
from logic.conditions import all_condition_labels, compute_all_conditions
from logic.map_builder import MapBuilder
from logic.clues import get_clues_for_map
from logic.map_loader import build_map_from_data, targets_to_highlighted_cells

from settings.config import ICON_HELP, ICON_STATUS_OK, ICON_STATUS_ERROR, ICON_STATUS_WARNING
from settings.strings import (
    TOOLTIP_SOLVE_BUILD,
    TOOLTIP_SOLVE_BUILD_DEDUCTION,
    TOOLTIP_SOLVE_SELECT,
    TOOLTIP_SOLVE_SELECT_DEDUCTION,
    TOOLTIP_HELP_BUILD,
    TOOLTIP_BUILD_SAVE_MAP,
    TOOLTIP_HELP_SIMULATION,
    TOOLTIP_ADVANCED_MODE,
    TOOLTIP_ADVANCED_MODE_SELECT,
    TOOLTIP_FREEZE_MAP,
    TOOLTIP_FREEZE_MAP_ENABLED,
    TOAST_NO_INTERSECTION,
    TOAST_HEX_HIGHLIGHTED,
    TOAST_HEXES_HIGHLIGHTED,
    RESET_CONFIRM_TITLE,
    RESET_CONFIRM_MSG,
    MAP_SAVE_SUCCESS_TOAST,
    MAP_SAVE_ERROR_TITLE,
    MAP_SAVE_ERROR_MSG,
)
from ui.shared.rules_dropdowns_manager import RuleDropdownsManager
from ui.shared.custom_map_save import append_custom_map_to_json, prompt_save_map_name
from ui.shared.map_cards_manager import MapCardsManager
from ui.shared.status_list_manager import StatusListManager
from ui.shared.widgets import (
    HoverTooltipManager,
    ComboBoxWithPopupAbove,
    add_clear_button_inside_combo,
    show_toast,
)



class SolveSetupMixin:
    def setup(self) -> None:
        """Wire all Solve page widgets and build board."""
        w = self._page
        must = lambda n, c: w.findChild(c, n)
        get_any = lambda names, c: next((w.findChild(c, n) for n in names if w.findChild(c, n)), None)

        self.pages_stack = self.window.findChild(QStackedWidget, "pagesStack") or self.window

        self.btnReset: QPushButton = must("btnReset", QPushButton)
        self.btnSolve: QPushButton = must("btnSolve", QPushButton)

        self.cbBuildPlayers: QComboBox = must("cbBuildPlayers", QComboBox)
        self.cbBuildAdvancedMode: QCheckBox = must("cbBuildAdvancedMode", QCheckBox)
        self.cbFreezeMap: Optional[QCheckBox] = None

        self.lblRulesTitle: QLabel = get_any(["lblRulesTitle", "lblRules"], QLabel)

        self.mapSourceSegment: QWidget = must("mapSourceSegment", QWidget)
        self.btnMapBuild: QPushButton = must("btnMapBuild", QPushButton)
        self.btnMapSelect: QPushButton = must("btnMapSelect", QPushButton)
        self._map_source_group = QButtonGroup(self.window)
        self._map_source_group.addButton(self.btnMapBuild)
        self._map_source_group.addButton(self.btnMapSelect)
        self._map_source_group.setExclusive(True)
        self.btnMapBuild.setChecked(True)

        self.boardHost: QWidget = must("boardHost", QWidget)
        self.buildSettings: QWidget = must("buildSettings", QWidget)
        self.buildScroll: QScrollArea = must("buildScroll", QScrollArea)
        self.mapSourceStack: QStackedWidget = must("mapSourceStack", QStackedWidget)
        self.mapListScroll: QScrollArea = must("mapListScroll", QScrollArea)
        self.selectContent: QWidget = must("selectContent", QWidget)
        self.mapListCardsContainer: QWidget = must("mapListCardsContainer", QWidget)
        self.cbSelectPlayers: QComboBox = must("cbSelectPlayers", QComboBox)
        self.cbSelectAdvancedMode: QCheckBox = must("cbSelectAdvancedMode", QCheckBox)
        self.edtSelectSearch: QLineEdit | None = self._page.findChild(QLineEdit, "edtSelectSearch")
        self.lblNoMapCardsFound: QLabel | None = self._page.findChild(QLabel, "lblNoMapCardsFound")

        if self.edtSelectSearch:
            clear_action = self.edtSelectSearch.addAction(
                QIcon(":/assets/icons/close.svg"),
                QLineEdit.ActionPosition.TrailingPosition,
            )
            clear_action.triggered.connect(self.edtSelectSearch.clear)
            clear_action.setVisible(False)

            def _update_clear_visibility():
                clear_action.setVisible(len(self.edtSelectSearch.text()) >= 1)

            self.edtSelectSearch.textChanged.connect(_update_clear_visibility)

        if isinstance(self.cbSelectPlayers, ComboBoxWithPopupAbove):
            self.cbSelectPlayers.set_root_window(self.window)

        deduction = getattr(self, "_deduction_mode", False)
        # Map cards
        self.map_cards_manager = MapCardsManager(
            self.mapListCardsContainer,
            self.cbSelectAdvancedMode,
            self.cbSelectPlayers,
            self.btnSolve,
            self.btnMapSelect,
            edt_search=self.edtSelectSearch,
            lbl_no_cards=self.lblNoMapCardsFound,
            deduction_mode=deduction,
        )
        self.map_cards_manager.setup()
        self.cbSelectPlayers.currentTextChanged.connect(self._on_select_players_changed)

        def _crumb_on_map_selection() -> None:
            fn = getattr(self, "_breadcrumb_refresh", None)
            if callable(fn):
                fn()

        self.map_cards_manager.map_selection_changed.connect(_crumb_on_map_selection)

        self.mapSourceStack.setCurrentIndex(0)
        self.btnMapBuild.toggled.connect(self._on_map_source_toggled)
        self.btnMapSelect.toggled.connect(self._on_map_source_toggled)

        self.statusList: QListWidget = must("statusList", QListWidget)
        self._icon_status_ok = QIcon(str(ICON_STATUS_OK))
        self._icon_status_error = QIcon(str(ICON_STATUS_ERROR))
        self._icon_status_warning = QIcon(str(ICON_STATUS_WARNING))

        self.ruleRows: list[Optional[QWidget]] = [
            self._page.findChild(QWidget, f"ruleRow{i}") for i in range(1, 6)
        ]
        self.lblRuleP: list[QLabel] = [must(f"lblRuleP{i}", QLabel) for i in range(1, 6)]
        self.cbRuleP: list[QComboBox] = [must(f"cbRuleP{i}", QComboBox) for i in range(1, 6)]

        # Board
        self.scene = QGraphicsScene()
        self.view = BoardView(self.scene)
        view_container = self._page.findChild(QWidget, "viewContainer")
        if view_container is None:
            raise RuntimeError("viewContainer not found in page_solve (check objectName)")
        view_layout = view_container.layout()
        if view_layout is not None:
            view_layout.addWidget(self.view, 0, 0)
        # Help: plain QLabel (no hover chrome). Save: QToolButton + map_card.qss like edit/delete.
        icon_indent = 12
        icon_px = 20
        save_btn_px = 24  # icon 20 + qss padding 2px each side
        icon_spacing = 6

        help_icon = QLabel()
        help_icon.setObjectName("helpIconOverlay")
        help_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # SVG: QPixmap(":/...svg") is null; QIcon renders SVG at the requested size.
        _help_ic = QIcon(":/assets/icons/help_question_icon.svg")
        pm_help = _help_ic.pixmap(QSize(icon_px, icon_px), QIcon.Mode.Normal, QIcon.State.Off)
        if pm_help.isNull() and ICON_HELP.exists():
            pm_help = QIcon(str(ICON_HELP)).pixmap(
                QSize(icon_px, icon_px), QIcon.Mode.Normal, QIcon.State.Off
            )
        if not pm_help.isNull():
            help_icon.setPixmap(pm_help)
        help_icon.setFixedSize(icon_px, icon_px)
        help_icon.setCursor(Qt.CursorShape.PointingHandCursor)

        save_btn = QToolButton()
        save_btn.setObjectName("boardOverlaySave")
        save_btn.setIcon(QIcon(":/assets/icons/floppy-disk-save-button-svgrepo-com.svg"))
        save_btn.setIconSize(QSize(icon_px, icon_px))
        save_btn.setAutoRaise(True)
        save_btn.setFixedSize(save_btn_px, save_btn_px)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        save_btn.clicked.connect(self._on_build_save_icon_clicked)
        self._build_save_icon = save_btn

        self._help_icon_wrapper = QWidget()
        self._help_icon_wrapper.setObjectName("helpIconWrapper")
        self._help_icon_wrapper.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        inner_w = icon_px + icon_spacing + save_btn_px
        self._help_icon_wrapper.setFixedSize(icon_indent + inner_w, icon_indent + save_btn_px)
        wl = QHBoxLayout(self._help_icon_wrapper)
        wl.setContentsMargins(0, icon_indent, icon_indent, 0)
        wl.setSpacing(icon_spacing)
        wl.addStretch()
        wl.addWidget(help_icon, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        wl.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self._app_tooltip = HoverTooltipManager(self.window, self.window)
        def _help_icon_in_simulation() -> bool:
            bb = getattr(self, "board_builder", None)
            return bb is not None and getattr(bb, "_chips_mode", False)

        def _help_icon_select_sim() -> bool:
            """Select-sim: Select tab + in solve mode (deduction only)."""
            if not getattr(self, "btnMapSelect", None) or not self.btnMapSelect.isChecked():
                return False
            return bool(getattr(self, "_in_solve_mode", False) and getattr(self, "_solve_mode_map_data", None))

        def _save_icon_tooltip_when() -> bool:
            if not self.btnMapBuild.isChecked():
                return False
            if _help_icon_in_simulation() and not getattr(self, "_deduction_mode", False):
                return False
            slm = getattr(self, "status_list_manager", None)
            return bool(
                slm is not None
                and getattr(slm, "all_tiles", False)
                and getattr(slm, "all_struct", False)
            )

        # Select-sim tooltip first (deduction): when on Select tab in simulation
        self._app_tooltip.add(
            help_icon,
            TOOLTIP_HELP_SIMULATION,
            only_when_disabled=False,
            only_when=lambda: _help_icon_select_sim(),
        )
        self._app_tooltip.add(
            help_icon,
            TOOLTIP_HELP_SIMULATION,
            only_when_disabled=False,
            only_when=lambda: self.btnMapBuild.isChecked() and _help_icon_in_simulation(),
        )
        self._app_tooltip.add(
            help_icon,
            TOOLTIP_HELP_BUILD,
            only_when_disabled=False,
            only_when=lambda: self.btnMapBuild.isChecked() and not _help_icon_in_simulation(),
        )
        self._app_tooltip.add(
            save_btn,
            TOOLTIP_BUILD_SAVE_MAP,
            only_when_disabled=False,
            only_when=_save_icon_tooltip_when,
        )
        solve_tooltip_build = TOOLTIP_SOLVE_BUILD_DEDUCTION if getattr(self, "_deduction_mode", False) else TOOLTIP_SOLVE_BUILD
        self._app_tooltip.add(
            self.btnSolve, solve_tooltip_build,
            only_when_disabled=True,
            only_when=lambda: not getattr(self, "_calculating_simulation", False) and self.btnMapBuild.isChecked(),
        )
        select_tooltip = TOOLTIP_SOLVE_SELECT_DEDUCTION if getattr(self, "_deduction_mode", False) else TOOLTIP_SOLVE_SELECT
        self._app_tooltip.add(
            self.btnSolve, select_tooltip,
            only_when_disabled=True,
            only_when=lambda: not getattr(self, "_calculating_simulation", False) and self.btnMapSelect.isChecked(),
        )
        self._app_tooltip.add(
            self.cbBuildAdvancedMode,
            TOOLTIP_ADVANCED_MODE,
            only_when_disabled=False,
        )
        self._app_tooltip.add(
            self.cbSelectAdvancedMode,
            TOOLTIP_ADVANCED_MODE_SELECT,
            only_when_disabled=False,
        )
        # Only show tooltips when user is on this page (avoids duplicate tooltips when switching pages)
        def _tooltip_global_condition() -> bool:
            if getattr(self, "pages_stack", None) is None:
                return False
            if self.pages_stack.currentWidget() != self._page:
                return False
            if getattr(self, "_deduction_mode", False):
                return not getattr(self, "_calculating_simulation", False)
            return True

        self._app_tooltip.set_global_condition(_tooltip_global_condition)

        self.pieces: list = []
        self.markers: list = []
        self.canvas: Optional[PuzzleCanvas] = None
        self.controller: Optional[MapBuilder] = None
        self.advanced_mode: bool = bool(self.cbBuildAdvancedMode.isChecked())
        self._in_solve_mode: bool = False
        self._solve_mode_map_data: Optional[dict] = None  # map being solved in select mode
        self._build_tab_solve_active: bool = False  # Create Map: after Solve until highlights cleared
        self._rule_labels: list[str] = all_condition_labels(advanced_mode=self.advanced_mode)
        self.rules = RuleDropdownsManager(
            lblRulesTitle=self.lblRulesTitle,
            ruleRows=self.ruleRows,
            lblRuleP=self.lblRuleP,
            cbRuleP=self.cbRuleP,
            rule_labels=self._rule_labels,
        )
        self.rules.setup_once()
        self.rules.set_players_count(1 if deduction else 3)
        for cb in self.cbRuleP:
            add_clear_button_inside_combo(cb)

        self.btnReset.clicked.connect(self._on_reset_clicked_wrapper)
        self.btnSolve.clicked.connect(self._on_solve_or_confirm_clicked)
        self.cbBuildPlayers.currentTextChanged.connect(self.on_players_changed)
        self.cbBuildAdvancedMode.toggled.connect(self.on_advanced_mode_toggled)
        self.btnMapBuild.toggled.connect(self._on_map_source_mode_changed)
        self.btnMapSelect.toggled.connect(self._on_map_source_mode_changed)

        self._set_players_combo_to_3()
        self._on_map_source_mode_changed()

        QTimer.singleShot(0, self._build_board_content)

    def _on_build_save_icon_clicked(self) -> None:
        bb = getattr(self, "board_builder", None)
        if bb is None or bb.canvas is None:
            return
        name = prompt_save_map_name(self.window, default_name=None)
        if name is None:
            return
        ok = append_custom_map_to_json(name, bb, bool(self.advanced_mode))
        if not ok:
            mb = QMessageBox(self.window)
            mb.setWindowTitle(MAP_SAVE_ERROR_TITLE)
            mb.setText(MAP_SAVE_ERROR_MSG)
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.exec()
            return
        show_toast(self.pages_stack, MAP_SAVE_SUCCESS_TOAST.format(map_name=name))

