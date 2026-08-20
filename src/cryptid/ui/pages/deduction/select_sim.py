"""Select-sim panel wiring and view reparenting (Deduction mode)."""
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import (
    QWidget,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QLabel,
    QListWidget,
    QFrame,
    QScrollArea,
)
from PySide6.QtUiTools import QUiLoader

from logic.conditions import all_condition_labels
from settings.strings import TOOLTIP_ADVANCED_MODE
from settings.config import SIMULATION_SETTINGS_DEDUCTION_UI
from ui.shared.rules_dropdowns_manager import RuleDropdownsManager
from ui.shared.status_list_manager import StatusListManager
from ui.shared.widgets import (
    setup_player_color_combo,
    add_clear_button_inside_combo,
    configure_status_list_wrapping,
)


class DeductionSelectSimMixin:
    # Stack indices: 0=Build, 1=Select browse, 2=Select sim
    _IDX_BUILD = 0
    _IDX_SELECT_BROWSE = 1
    _IDX_SELECT_SIM = 2

    def _setup_select_sim_panel(self) -> None:
        """Load and wire the Select-sim settings panel (independent copy, no UI duplication)."""
        # Select-sim .ui duplicates objectNames (cbBuildPlayers, edtPlayer*, cbColorP*). After load,
        # page.findChild would be ambiguous — cache Create Map widgets before adding sim UI.
        self._build_cb_players = self.cbBuildPlayers
        self._build_cb_advanced = self.cbBuildAdvancedMode
        self._build_edt_player = list(self.edtPlayer)
        self._build_cb_color_p = list(self.cbColorP)
        self._rules_build = self.rules
        self._status_list_manager_build = self.status_list_manager
        select_sim_settings_container = self._page.findChild(QWidget, "selectSimSettingsContainer")
        self._select_sim_view_container = self._page.findChild(QWidget, "selectSimViewContainer")
        self._build_view_container = self._page.findChild(QWidget, "viewContainer")
        select_sim_content = self._page.findChild(QWidget, "selectSimContent")
        if not select_sim_settings_container or not self._select_sim_view_container:
            return

        # Wheel/scroll regression guard:
        # `selectSimContent` is not a QScrollArea in the .ui. When switching to the
        # Select-sim layout (mapSourceStack index 2), mouse wheel can end up scrolling
        # the outer page instead of the simulation section.
        # Wrap `selectSimContent` in a QScrollArea at runtime to ensure predictable
        # scrollbar sizing and wheel behavior.
        scroll_wrapper: QScrollArea | None = None
        if (
            select_sim_content is not None
            and hasattr(self, "mapSourceStack")
        ):
            # Robust index lookup: some PySide/QStackedWidget combinations don't
            # reliably support indexOf(widget), so we scan by identity.
            idx = -1
            try:
                target_name = select_sim_content.objectName()
                for i in range(self.mapSourceStack.count()):
                    w = self.mapSourceStack.widget(i)
                    if w is select_sim_content or (target_name and w and w.objectName() == target_name):
                        idx = i
                        break
            except Exception:
                idx = -1
            if idx != -1:
                scroll = QScrollArea(self.mapSourceStack)
                scroll.setObjectName("selectSimScroll")
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setWidgetResizable(True)
                scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

                # Replace the widget in the stacked container with the scroll wrapper.
                self.mapSourceStack.removeWidget(select_sim_content)
                scroll.setWidget(select_sim_content)
                self.mapSourceStack.insertWidget(idx, scroll)
                scroll_wrapper = scroll
            else:
                # Could not locate the widget inside the stack; don't wrap.
                scroll_wrapper = None

        self._select_sim_scroll_wrapper = scroll_wrapper

        # Ensure wheel events scroll the Select-sim scroll area, not the outer mainScroll.
        if select_sim_content is not None and scroll_wrapper is not None:
            deduction = self
            class _WheelForwarder(QObject):
                def eventFilter(self, obj, event):
                    # Only forward wheel events while we're actually on Select-sim.
                    # Otherwise we could interfere with Build-sim wheel handling.
                    try:
                        if deduction.mapSourceStack.currentIndex() != deduction._IDX_SELECT_SIM:
                            return False
                    except Exception:
                        pass
                    if event.type() in (QEvent.Type.Wheel, QEvent.Type.Scroll):
                        vbar = scroll_wrapper.verticalScrollBar() if scroll_wrapper else None
                        if vbar is not None:
                            try:
                                delta = event.angleDelta().y()
                            except Exception:
                                try:
                                    delta = event.pixelDelta().y()
                                except Exception:
                                    return False
                            step = max(vbar.singleStep(), 1) * 3
                            vbar.setValue(vbar.value() - int(delta / 120) * step)
                            return True
                    return False

            forwarder = _WheelForwarder(select_sim_content)
            # Keep a reference so we can install this filter on the reparented BoardView.
            self._select_sim_wheel_forwarder = forwarder
            select_sim_content.installEventFilter(forwarder)
            for c in select_sim_content.findChildren(QWidget):
                c.installEventFilter(forwarder)

            # Belt-and-suspenders: wheel events often end up on the mainScroll viewport.
            # If Select-sim is active, forward those wheel events into the selectSim scroll wrapper.
            try:
                main_scroll = getattr(self, "window", None) and self.window.findChild(QScrollArea, "mainScroll")
                if main_scroll is not None:
                    class _MainScrollWheelForwarder(QObject):
                        def eventFilter(self, obj, event):
                            try:
                                if deduction.mapSourceStack.currentIndex() != deduction._IDX_SELECT_SIM:
                                    return False
                            except Exception:
                                return False
                            if event.type() in (QEvent.Type.Wheel, QEvent.Type.Scroll):
                                vbar = deduction._select_sim_scroll_wrapper.verticalScrollBar() if deduction._select_sim_scroll_wrapper else None
                                if vbar is not None:
                                    try:
                                        delta = event.angleDelta().y()
                                    except Exception:
                                        try:
                                            delta = event.pixelDelta().y()
                                        except Exception:
                                            return False
                                    step = max(vbar.singleStep(), 1) * 3
                                    vbar.setValue(vbar.value() - int(delta / 120) * step)
                                    return True
                            return False

                    main_forwarder = _MainScrollWheelForwarder(main_scroll)
                    main_scroll.installEventFilter(main_forwarder)
                    main_scroll.viewport().installEventFilter(main_forwarder)
                    self._main_scroll_wheel_forwarder = main_forwarder
            except Exception:
                pass
        loader = QUiLoader()
        settings_widget = loader.load(str(SIMULATION_SETTINGS_DEDUCTION_UI))
        if settings_widget is None:
            return
        layout = select_sim_settings_container.layout()
        if layout:
            layout.addWidget(settings_widget)
        # Wire Select-sim panel: same structure as Build (cbBuildPlayers, cbRuleP1, edtPlayer, cbColorP)
        self._select_sim_cb_players = settings_widget.findChild(QComboBox, "cbBuildPlayers")
        self._select_sim_cb_advanced = settings_widget.findChild(QCheckBox, "cbBuildAdvancedMode")
        if self._select_sim_cb_advanced is not None:
            self._select_sim_cb_advanced.toggled.connect(self.on_advanced_mode_toggled)
        self._select_sim_cb_rule_p = [settings_widget.findChild(QComboBox, f"cbRuleP{i}") for i in range(1, 6)]
        self._select_sim_edt_player = [settings_widget.findChild(QLineEdit, f"edtPlayer{i}") for i in range(1, 6)]
        self._select_sim_cb_color = [settings_widget.findChild(QComboBox, f"cbColorP{i}") for i in range(1, 6)]
        status_list = settings_widget.findChild(QListWidget, "statusList") if settings_widget else None
        if status_list is not None:
            configure_status_list_wrapping(status_list)
        rule_rows = [settings_widget.findChild(QWidget, f"ruleRow{i}") for i in range(1, 6)]
        lbl_rule_p = [settings_widget.findChild(QLabel, f"lblRuleP{i}") for i in range(1, 6)]
        rule_labels_select = all_condition_labels(advanced_mode=False)
        self._rules_select = RuleDropdownsManager(
            lblRulesTitle=settings_widget.findChild(QLabel, "lblRulesTitle"),
            ruleRows=rule_rows,
            lblRuleP=lbl_rule_p,
            cbRuleP=self._select_sim_cb_rule_p,
            rule_labels=rule_labels_select,
        )
        self._rules_select.setup_once()
        self._rules_select.set_deduction_layout(3)
        for cb in self._select_sim_cb_color:
            if cb is not None:
                setup_player_color_combo(cb)
                add_clear_button_inside_combo(cb)
                cb.currentIndexChanged.connect(self._on_color_combo_changed)
        placeholders = ["Player 1 (you)", "Player 2", "Player 3", "Player 4", "Player 5"]
        for i, edt in enumerate(self._select_sim_edt_player):
            if edt is not None and i < len(placeholders):
                edt.setPlaceholderText(placeholders[i])
                edt.textChanged.connect(lambda _t, idx=i: self._on_player_name_changed(idx))
        if self._select_sim_cb_advanced is not None and hasattr(self, "_app_tooltip"):
            self._app_tooltip.add(self._select_sim_cb_advanced, TOOLTIP_ADVANCED_MODE, only_when_disabled=False)
        chips = getattr(self.board_builder, "chips", []) if self.board_builder else []
        self._status_list_manager_select = StatusListManager(
            status_list if status_list else QListWidget(),
            self._icon_status_ok,
            self._icon_status_error,
            self._rules_select,
            self._select_sim_cb_players,
            self.btnSolve,
            self.cbFreezeMap,
            self.canvas,
            self.pieces,
            self.markers,
            chips=chips,
            rule_check_count=1,
            icon_warning=self._icon_status_warning,
            edt_player=self._select_sim_edt_player,
            cb_color=self._select_sim_cb_color,
            board_builder=self.board_builder,
            get_simulation_status=getattr(self, "_get_simulation_status", None),
        )

    def _reparent_view_to(self, target_container: QWidget | None) -> None:
        """Move the board view into target_container (build or select-sim layout)."""
        view = getattr(self, "view", None)
        if view is None or target_container is None:
            return
        old_parent = view.parent()
        if old_parent and hasattr(old_parent, "layout") and old_parent.layout():
            old_parent.layout().removeWidget(view)
        layout = target_container.layout() if target_container else None
        if layout:
            layout.addWidget(view, 0, 0)

    def _swap_to_select_sim_panel(self) -> None:
        """Point controller refs to Select-sim panel for simulation."""
        self.cbBuildPlayers = self._select_sim_cb_players
        self.cbBuildAdvancedMode = self._select_sim_cb_advanced
        self.rules = self._rules_select
        self.edtPlayer = self._select_sim_edt_player
        self.cbColorP = self._select_sim_cb_color
        self.status_list_manager = self._status_list_manager_select

    def _swap_to_build_panel(self) -> None:
        """Point controller refs back to Build panel."""
        if getattr(self, "_build_cb_players", None) is not None:
            self.cbBuildPlayers = self._build_cb_players
            self.cbBuildAdvancedMode = self._build_cb_advanced
            self.edtPlayer = list(self._build_edt_player)
            self.cbColorP = list(self._build_cb_color_p)
        else:
            self.cbBuildPlayers = self._page.findChild(QComboBox, "cbBuildPlayers")
            self.cbBuildAdvancedMode = self._page.findChild(QCheckBox, "cbBuildAdvancedMode")
            self.edtPlayer = [self._page.findChild(QLineEdit, f"edtPlayer{i}") for i in range(1, 6)]
            self.cbColorP = [self._page.findChild(QComboBox, f"cbColorP{i}") for i in range(1, 6)]
        self.rules = getattr(self, "_rules_build", self.rules)
        self.status_list_manager = getattr(self, "_status_list_manager_build", self.status_list_manager)

