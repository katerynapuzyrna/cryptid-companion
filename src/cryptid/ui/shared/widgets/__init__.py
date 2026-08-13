"""Shared UI widgets: combo popup, tooltips, toast, player colors, loading."""
from .list_widgets import StatusListWidget, configure_status_list_wrapping
from .combo_popup import ComboBoxWithPopupAbove, ComboPopupUiLoader
from .tooltips import HoverTooltipManager
from .toast import show_toast
from .player_colors import (
    PLAYER_COLORS,
    get_colored_square_pixmap,
    setup_player_color_combo,
    get_color_icon,
    get_selected_player_color,
    get_player_color_hex,
    assign_colors_to_empty_combos,
    refresh_player_color_combos,
    sync_combo_placeholder_style,
    sync_clear_button_visibility,
    add_clear_button_inside_combo,
)
from .loading import DotsLoadingWidget

__all__ = [
    "StatusListWidget",
    "configure_status_list_wrapping",
    "ComboBoxWithPopupAbove",
    "ComboPopupUiLoader",
    "HoverTooltipManager",
    "show_toast",
    "PLAYER_COLORS",
    "get_colored_square_pixmap",
    "setup_player_color_combo",
    "get_color_icon",
    "get_selected_player_color",
    "get_player_color_hex",
    "assign_colors_to_empty_combos",
    "refresh_player_color_combos",
    "sync_combo_placeholder_style",
    "sync_clear_button_visibility",
    "add_clear_button_inside_combo",
    "DotsLoadingWidget",
]
