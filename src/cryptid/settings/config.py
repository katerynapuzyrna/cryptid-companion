from pathlib import Path
import math

HEX_SIZE = 25

GRID_ROT_DEG = 90
GRID_ROT_RAD = math.radians(GRID_ROT_DEG)

SLOT_OVERLAP_X = 11.1
SLOT_OVERLAP_Y = 21

MARKER_SIZE = 12
PIECE_CORNER_DOT_R = 2

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
MAPS_JSON = DATA_DIR / "maps.json"
CUSTOM_MAPS_JSON = DATA_DIR / "custom_maps.json"
CUSTOM_MAPS_EXAMPLE_JSON = DATA_DIR / "custom_maps.example.json"
ICONS_DIR = (ASSETS_DIR / "icons").as_posix()

# Shown in the main window title bar and as the Qt application display name (modals / taskbar).
APP_DISPLAY_NAME = "Cryptid Companion"

ICON_HELP = ASSETS_DIR / "icons" / "help_question_icon.svg"
ICON_STATUS_OK = ASSETS_DIR / "icons" / "status_ok.svg"
ICON_STATUS_ERROR = ASSETS_DIR / "icons" / "status_error.svg"
ICON_STATUS_WARNING = ASSETS_DIR / "icons" / "status_warning.svg"
ICON_UNDER_DEVELOPMENT = ASSETS_DIR / "icons" / "under_development.svg"
ICON_CLUE = ASSETS_DIR / "icons" / "icon_clue.svg"
CLUES_ICONS_DIR = ASSETS_DIR / "icons" / "clues"

# Testing: pre-load Atlantis map (tiles + markers) on Deduction page at startup.
# True = testing mode (preload Atlantis), False = regular behavior (empty board).
PRELOAD_ATLANTIS_IN_DEDUCTION = False

# Testing: Play Hotseat uses hardcoded clues when the custom map "Dan broke everything" is played.
# True = keep that clue set, False = assign clues normally. Does not pre-select the map.
HOTSEAT_TEST_DAN_BROKE_EVERYTHING = True

# Hex fill style: True = textured terrain (grain, bevel, gloss, terrain details), False = flat solid fill.
TEXTURED_HEX_FILL = False

UI_DIR = ASSETS_DIR / "ui"
UI_PATH = UI_DIR / "main_window.ui"
PAGE_MAIN_MENU_UI = UI_DIR / "page_main_menu.ui"
PAGE_DEDUCTION_UI = UI_DIR / "page_deduction.ui"
PAGE_SOLVE_UI = UI_DIR / "page_solve.ui"
PAGE_HOW_TO_PLAY_UI = UI_DIR / "page_how_to_play.ui"
PAGE_MAPS_LIBRARY_UI = UI_DIR / "page_maps_library.ui"
PAGE_PLAY_HOTSEAT_UI = UI_DIR / "page_play_hotseat.ui"
SIMULATION_SETTINGS_DEDUCTION_UI = UI_DIR / "simulation_settings_deduction.ui"
QSS_DIR = ASSETS_DIR / "styles"

QSS_FILES = [
    "base.qss",
    "dialog.qss",
    "cards.qss",
    "home.qss",
    "tutorials.qss",
    "buttons.qss",
    "map_source.qss",
    "combobox.qss",
    "combo_popup.qss",
    "board.qss",
    "toggle.qss",
    "sidebar.qss",
    "map_card.qss",
    "status_list.qss",
    "progress.qss",
    "scroll_area.qss",
    "search.qss",
    "tooltip.qss",
    "valid_clues.qss",
    "table.qss",
]
