"""Tooltips, toast messages, and other user-facing strings."""

# Tooltip texts (Solve page)
TOOLTIP_SOLVE_BUILD = "Please set up all map tiles, structures and select clues to solve the game"
TOOLTIP_SOLVE_BUILD_DEDUCTION = "Please set up all map tiles and structures, select your clue to start simulation"
TOOLTIP_SOLVE_SELECT = "Please select a map first"
TOOLTIP_SOLVE_SELECT_DEDUCTION = "Please select a map and your clue firstly"
TOOLTIP_HELP_BUILD = (
    "<p style='line-height: 1.2;'>Build your map:</p>"
    "<p style='line-height: 1.2;'>1. Drag&drop all map tiles onto the canvas</p>"
    "<p style='line-height: 1.2;'>2. Double-click to rotate a map tile (180°)</p>"
    "<p style='line-height: 1.2;'>3. Freeze map when you are done with map tiles</p>"
    "<p style='line-height: 1.2;'>4. Place structures on hex centers</p>"
)
TOOLTIP_BUILD_SAVE_MAP = "Save map"
TOOLTIP_HELP_SIMULATION = (
    "<p style='line-height: 1.2;'>Look up for a target hex:</p>"
    "<p style='line-height: 1.2;'>1. Place player's circle/square chips on a map</p>"
    "<p style='line-height: 1.2;'>2. Use toggle \"Highlight valid spaces\" to see possible hex candidates</p>"
)
TOOLTIP_ADVANCED_MODE = "Add black structures and negative clues"
TOOLTIP_ADVANCED_MODE_SELECT = "Show maps with black structures and negative clues"
TOOLTIP_FREEZE_MAP = "Please place all map tiles on a canvas to create a full map"
TOOLTIP_FREEZE_MAP_ENABLED = "Freeze a map to avoid extra map tiles moves"
TOOLTIP_UNDO = "Undo"
TOOLTIP_MAP_SOURCE_BLOCKED_BY_SIM = "Please end a current simulation firstly"
TOOLTIP_MAPS_LIB_SAVE_DISABLED = "Please set up all map tiles and structures firstly"
TOOLTIP_MAPS_LIB_EDIT_CUSTOM = "Edit map"
TOOLTIP_MAPS_LIB_EDIT_MAP_NAME = "Edit map name"
TOOLTIP_MAPS_LIB_DELETE_CUSTOM = "Delete map"
TOOLTIP_MAPS_LIB_CUSTOM_EDIT_BACK = "Return to Custom Maps list without saving"

# Maps Library — save custom map
MAP_SAVE_DIALOG_TITLE = "Save map"
MAP_EDIT_MAP_NAME_DIALOG_TITLE = "Edit map name"
MAP_SAVE_NAME_LABEL = "Enter map name:"
MAP_SAVE_NAME_PLACEHOLDER = "Custom Map"
#MAP_SAVE_SUCCESS_TITLE = "Map saved"
# Toast after save; use .format(map_name=...)
MAP_SAVE_SUCCESS_TOAST = "{map_name} is saved successfully"
# After updating an existing custom map from the editor; use .format(map_name=...)
MAP_UPDATE_SUCCESS_TOAST = "{map_name} is updated successfully"
MAP_SAVE_ERROR_TITLE = "Save failed"
MAP_SAVE_ERROR_MSG = "Could not write custom_maps.json. Check file permissions."
MAP_CREATED_BY_DEFAULT = "Admin"  # future: username

# Maps Library — delete custom map (soft delete); use .format(map_name=...)
MAP_DELETE_CONFIRM_TITLE = "Delete map"
MAP_DELETE_CONFIRM_MSG = "Are you sure you want to delete {map_name}?"
MAP_DELETE_SUCCESS_TOAST = "{map_name} is deleted successfully"

# Maps Library — reset while editing a custom map (same button as full reset)
MAP_EDIT_REVERT_TITLE = "Reset All"
MAP_EDIT_REVERT_MSG = (
    "Restore this map to how it was when you opened the editor? "
    "All unsaved changes will be lost."
)

# Reset confirmation
RESET_CONFIRM_TITLE = "Reset All"
RESET_CONFIRM_MSG = "Are you sure you want to reset all settings and selections?"
RESET_CHIPS_CONFIRM_MSG = "Are you sure you want to reset all player chips settings?"
END_HOTSEAT_CONFIRM_TITLE = "End Game"
END_HOTSEAT_CONFIRM_MSG = (
    "Are you sure you want to end the current hotseat session? "
    "All moves and game progress will be lost."
)
HOTSEAT_END_TURN_DISABLED_TOOLTIP = (
    "Please finish either question or search action"
)
HOTSEAT_INCORRECT_MAP_NAME_TITLE = "Incorrect map name"
HOTSEAT_INCORRECT_MAP_NAME_MSG = (
    "The map name you entered doesn't exist. Please enter another one"
)
END_SIMULATION_CONFIRM_MSG = "Are you sure you want to reset all map settings and selections?"

# Toast messages (Solve page)
TOAST_NO_INTERSECTION = "No intersection found for the selected clues"
TOAST_HEX_HIGHLIGHTED = "1 space highlighted"
TOAST_HEXES_HIGHLIGHTED = "{count} spaces highlighted"

# Toast messages (Deduction page)
TOAST_VALID_SPACES_HIGHLIGHTED = "1 valid space highlighted"
TOAST_VALID_SPACES_HIGHLIGHTED_PLURAL = "{count} valid spaces highlighted"
BTN_END_SIMULATION = "End Simulation"
BTN_RESET_ALL = "Reset All"
BTN_RESET_CHIPS = "Reset Chips"
CALCULATING = "Calculating..."

# Home page
HOME_INTRO_HTML = """
<html><head><style>
p { margin: 0 0 10px 0; line-height: 1.45; }
p:last-child { margin-bottom: 0; }
.lead { font-size: 12.5pt; font-weight: 600; margin-bottom: 12px; }
</style></head><body>
<p class="lead">Welcome to Cryptid Companion!</p>
<p>Cryptid is a deduction board game where players search for a mysterious creature
hidden somewhere on the map. Each player knows one clue about its habitat, and by
asking questions and combining information, players gradually narrow down the
possible locations.</p>
<p>Cryptid Companion is a fan-made desktop application designed to complement the
board game and explore its deduction mechanics digitally. It provides tools for
playing, exploring maps, solving puzzles, and practicing deduction.</p>
</body></html>
"""

HOME_ABOUT_HTML = """
<html><head><style>
p { margin: 0 0 8px 0; line-height: 1.45; color: #4a5560; font-size: 9.5pt; }
p:last-child { margin-bottom: 0; }
.heading { font-size: 10.5pt; font-weight: 600; color: #182022; margin-bottom: 10px; }
</style></head><body>
<p class="heading">About this project:</p>
<p>Cryptid Companion is an independent, unofficial fan-made project created for
educational and portfolio purposes. It is not affiliated with, endorsed by, or
sponsored by Osprey Games, Osprey Publishing, or Bloomsbury Publishing.</p>
<p>Cryptid was designed by Hal Duncan (Anthony Duncan) and Ruth Veevers,
illustrated by Kwanchai Moriya, and published by Osprey Games. The original
game and its associated artwork and materials are the property of their
respective rights holders.</p>
<p>This project is non-commercial and is not intended for sale or monetization.</p>
</body></html>
"""

# (route_name, description, optional coming-soon footnote)
HOME_NAV_CARDS: list[tuple[str, str, str | None]] = [
    (
        "Play Online",
        "Play Cryptid remotely with other players. Create or join a game and use the app to manage the game state.",
        "Coming soon...",
    ),
    (
        "Play Hotseat",
        "Play Cryptid with friends using a single device. Pass the device between players while the app manages clues and turns.",
        None,
    ),
    (
        "Maps Library",
        "Browse available Cryptid maps and explore their terrain, structures, and animal territories.",
        None,
    ),
    (
        "Solver Tool",
        "Enter known clues and let the solver calculate all locations where the Cryptid could be hiding.",
        None,
    ),
    (
        "Deduction Mode",
        "Practice your deduction skills by analyzing clues and narrowing down possible Cryptid locations.",
        None,
    ),
]

# Tutorials page — section copy (HOW_TO_PLAY_HTML kept below for later reuse)
TUTORIAL_OVERVIEW_TITLE = "Overview"
TUTORIAL_OVERVIEW_BODY = (
    "You are all cryptozoologists, trying to be the first to discover definitive proof of a "
    "cryptid in the wilds of North America. Each player will be given a unique clue – one piece "
    "of crucial information about where the creature lives. When combined, the clues identify a "
    "single space on the map – the creature’s habitat.\n\n"
    "Each player’s clue either states an area where the creature can be found, or where it cannot "
    "be found, based on the terrain and structures on the board.\n\n"
    "During the game, you will ask each other questions with the aim of guessing each other’s "
    "clues. The first player to correctly use all of the clues to find the habitat wins the game."
)

TUTORIAL_COMPONENTS_TITLE = "Components"
TUTORIAL_MAP_TITLE = "The map"
TUTORIAL_MAP_BODY = (
    "The map is the area where your search will be taking place, and serves as the focus of the "
    "game. It consists of six numbered map tiles, divided into hexagonal spaces. One corner of "
    "each tile shows a number, which is used for setup."
)

TUTORIAL_TERRAIN_TITLE = "Terrain types"
TUTORIAL_TERRAIN_BODY = (
    "There are five different types of space: desert, forest, water, mountain, and swamp."
)
TUTORIAL_TERRAIN_LABELS = (
    ("water", "Water"),
    ("mountain", "Mountain"),
    ("forest", "Forest"),
    ("swamp", "Swamp"),
    ("desert", "Desert"),
)

TUTORIAL_TERRITORY_TITLE = "Animal territory"
TUTORIAL_TERRITORY_BODY = (
    "In addition to having a terrain type, a space might be part of a bear or a cougar’s "
    "territory, as indicated by its outline."
)
TUTORIAL_TERRITORY_LABELS = (
    ("bear", "Bear territory"),
    ("cougar", "Cougar territory"),
)

TUTORIAL_STRUCTURES_TITLE = "Structures"
TUTORIAL_STRUCTURES_BODY = (
    "Each space may also contain a structure. There are two types of structure: standing stones "
    "and abandoned shacks. Please note that black type of structures is valid for advanced mode only."
)
TUTORIAL_STRUCTURES_GROUP_STONES = "Standing stones"
TUTORIAL_STRUCTURES_GROUP_SHACKS = "Abandoned shacks"

TUTORIAL_PIECES_TITLE = "Playing pieces"
TUTORIAL_PIECES_BODY = (
    "Each player has their own set of squares and circles, which they will place on the board when "
    "they are forced to give the other players information. A square means that space cannot be the "
    "creature’s habitat, according to that player’s clue. There can only be a single square on any "
    "space. A circle means that space could be the creature’s habitat, according to that player’s "
    "clue. There may be multiple circles stacked on a space. Pieces are never removed from the "
    "board, unless a mistake has been made."
)
TUTORIAL_PIECES_CUBE_CAPTION = "Square (cannot be the habitat)"
TUTORIAL_PIECES_DISC_CAPTION = "Circle (could be the habitat)"

TUTORIAL_CLUES_EXAMPLES_TITLE = "Clues examples"
TUTORIAL_CLUES_TITLE = "Possible clues"
TUTORIAL_CLUES_BODY = (
    "Positive clues are applicable for both normal and advanced mode, negative clues and "
    'the clue "Within three spaces of a black structure" are applicable for advanced mode only.'
)
TUTORIAL_CLUES_GROUP_TERRAIN_PAIR = "On one of two types of terrain"
TUTORIAL_CLUES_GROUP_TERRAIN_PAIR_NOT = "NOT on one of two types of terrain"
TUTORIAL_CLUES_GROUP_ONE_SPACE = "Within one space of a terrain type or animal territory"
TUTORIAL_CLUES_GROUP_ONE_SPACE_NOT = (
    "NOT within one space of a terrain type or animal territory"
)
TUTORIAL_CLUES_GROUP_TWO_SPACES = (
    "Within two spaces of a type of animal territory or a type of structure"
)
TUTORIAL_CLUES_GROUP_TWO_SPACES_NOT = (
    "NOT within two spaces of a type of animal territory or a type of structure"
)
TUTORIAL_CLUES_GROUP_THREE_SPACES = "Within three spaces of a color of a structure"
TUTORIAL_CLUES_GROUP_THREE_SPACES_NOT = (
    "NOT within three spaces of a color of a structure"
)

TUTORIAL_SETUP_TITLE = "Setup"
TUTORIAL_SETUP_BODY = (
    "Set up the random or a specific map. Choose a game mode: Normal or Advanced. "
    "Normal is recommended for new players.\n\n"
    "Choose a starting player and assign each player a color. The clue will be assigned by the "
    "application. Keep your clue hidden from the other players.\n\n"
    "Initial sharing: starting with the first player and continuing clockwise, each player places "
    "a square on a space that cannot contain the habitat according to their clue. Continue until "
    "every player has placed two squares.\n\n"
    "The starting player then takes the first turn."
)

TUTORIAL_PLAY_TITLE = "Play the game"
TUTORIAL_PLAY_SECTION_GOAL = "Goal"
TUTORIAL_PLAY_GOAL_BODY = (
    "Find the one space on the map that satisfies every player's secret clue. "
    "This space is the Cryptid's habitat."
)
TUTORIAL_PLAY_SECTION_TURN = "On Your Turn"
TUTORIAL_PLAY_TURN_INTRO = "Choose one of two actions:"
TUTORIAL_PLAY_SECTION_QUESTION = "Question"
TUTORIAL_PLAY_QUESTION_BODY = (
    "Select any space and ask one other player whether the Cryptid could be there "
    "according to their clue.\n\n"
    "Yes → they place a circle on the space.\n"
    "No → they place a square on the space. You must then place one of your own squares on "
    "another space that cannot be the habitat according to your clue."
)
TUTORIAL_PLAY_SECTION_SEARCH = "Search"
TUTORIAL_PLAY_SEARCH_BODY = (
    "Choose a space that could be the habitat according to your own clue and place one "
    "of your circles there.\n\n"
    "Starting with the next player and continuing clockwise, every other player indicates "
    "whether the Cryptid could be there according to their clue.\n\n"
    "If a player places a square, the search immediately ends. You must also place one of "
    "your squares on another invalid space.\n"
    "If every player confirms the space with a circle, you found the Cryptid and win the game."
)
TUTORIAL_PLAY_SECTION_PIECES = "Pieces"
TUTORIAL_PLAY_PIECES_BODY = (
    "Circle = could be the habitat according to that player's clue.\n"
    "Square = cannot be the habitat according to that player's clue."
)
TUTORIAL_PLAY_SECTION_RULES = "Important Rules"
TUTORIAL_PLAY_RULES_BODY = (
    "Always place squares and circles truthfully according to your clue.\n"
    "Pieces remain on the board for the rest of the game.\n"
    "You cannot question, search, or place a piece on a space containing any square.\n"
    "You cannot place another of your pieces on a space that already contains one of your pieces.\n"
    "Multiple players' circles may occupy the same space."
)

# Tutorials page (HTML for QTextBrowser; nav label "Tutorials") — kept for later reuse
HOW_TO_PLAY_HTML = """
<html><head><style>
body { color: #182022; font-family: 'Segoe UI', sans-serif; font-size: 10.5pt; line-height: 1.45; }
h2 { font-size: 11.5pt; margin: 18px 0 8px 0; color: #182022; }
h2:first-child { margin-top: 0; }
p { margin: 6px 0; }
ul { margin: 6px 0 6px 20px; padding: 0; }
li { margin: 4px 0; }
.note { color: #4a5560; font-size: 10pt; margin-top: 16px; }
</style></head><body>

<h2>The board game</h2>
<p><b>Cryptid</b> is a hidden-information deduction game. One hex on the map hides the cryptid.
Each player has a unique clue that narrows where the cryptid can be. By asking questions and
reasoning about others&rsquo; answers, you try to be the first to find the correct space.</p>
<p class="note">This app is a digital companion for planning and analysis&mdash;it does not replace
the official rulebook or components.</p>

<h2>Deduction Mode</h2>
<p>Use this mode to practice or explore a map when you only know <b>your own</b> clue (the first
player&rsquo;s rule).</p>
<ul>
<li><b>Create Map</b> or <b>Load Map</b> to set up the board and structures.</li>
<li>Choose player count, names, colors, and whether <b>Advanced mode</b> (black structures / negative clues) applies.</li>
<li>Select <b>your</b> rule, then start the simulation.</li>
<li>Place circle and square chips for each player, use <b>Highlight valid spaces</b> to see hexes
still consistent with the remaining combinations, and narrow down the target.</li>
</ul>

<h2>Solver Tool</h2>
<p>Use this when you want to enter <b>all</b> players&rsquo; clues and analyze intersections on a
fixed map: build or load the map, assign every clue, then run the solver to highlight candidate hexes.</p>

<h2>Map building tips</h2>
<ul>
<li>Drag map tiles onto the canvas; double-click a tile to rotate it 180&deg;.</li>
<li>Freeze the map when tile placement is complete, then place structures on hex centers.</li>
<li>End an active simulation before changing map source or resetting, when the UI asks you to.</li>
</ul>

</body></html>
"""

