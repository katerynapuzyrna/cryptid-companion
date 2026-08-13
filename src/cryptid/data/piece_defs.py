from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

# ------------------------------------------------------------
# Pure piece definitions (no Qt). Single source of truth for:
# - HexPiece construction (UI)
# - Logic terrain matrices (current_map)
# ------------------------------------------------------------

InnerDotted = Optional[Literal["red", "black"]]


@dataclass(frozen=True)
class CellSpec:
    q: int
    r: int
    color: str
    inner_dotted: InnerDotted = None


# Factory palette (default theme). These hex strings are also used by
# the terrain paint module for visuals.
COLOR_WATER = "#7aa8ff"  # BLUE
COLOR_MOUNTAIN = "#bdbdbd"  # GRAY
COLOR_DESERT = "#f2d25a"  # YELL
COLOR_FOREST = "#7fb26c"  # GREEN
COLOR_SWAMP = "#6a5875"  # PURP

# Alternate palette (kept for compatibility with the commented-out factory palette)
COLOR_WATER_ALT = "#107dc2"
COLOR_MOUNTAIN_ALT = "#9a9899"
COLOR_DESERT_ALT = "#d9b009"
COLOR_FOREST_ALT = "#0b9539"
COLOR_SWAMP_ALT = "#3b173d"

TERRAIN_BY_COLOR: dict[str, Literal["water", "mountain", "desert", "forest", "swamp"]] = {
    COLOR_WATER: "water",
    COLOR_MOUNTAIN: "mountain",
    COLOR_DESERT: "desert",
    COLOR_FOREST: "forest",
    COLOR_SWAMP: "swamp",
    COLOR_WATER_ALT: "water",
    COLOR_MOUNTAIN_ALT: "mountain",
    COLOR_DESERT_ALT: "desert",
    COLOR_FOREST_ALT: "forest",
    COLOR_SWAMP_ALT: "swamp",
}


def cell_spec_to_terrain(spec: CellSpec) -> str:
    """
    Convert a cell spec to the terrain string stored in current_map.

    Rules (per user request):
    - colors → base terrain
    - inner_dotted="black" → "_bear"
    - inner_dotted="red" → "_cougar"
    """
    base = TERRAIN_BY_COLOR.get(spec.color.strip().lower(), "forest")
    if spec.inner_dotted == "black":
        return f"{base}_bear"
    if spec.inner_dotted == "red":
        return f"{base}_cougar"
    return base


# Piece metadata: index 0..5 corresponds to tiles 1..6.
PIECE_NUMS = ["1", "2", "3", "4", "5", "6"]
PIECE_MATRIX_IDS: list[Literal["A", "B", "C", "D", "E", "F"]] = ["A", "B", "C", "D", "E", "F"]


PIECE_SPECS: list[list[CellSpec]] = [
    # Tile 1 / Matrix A
    [
        CellSpec(-3, 5, COLOR_WATER),
        CellSpec(-2, 4, COLOR_WATER),
        CellSpec(-2, 3, COLOR_WATER),
        CellSpec(-1, 2, COLOR_WATER),
        CellSpec(-1, 1, COLOR_FOREST),
        CellSpec(0, 0, COLOR_FOREST),
        CellSpec(-2, 5, COLOR_SWAMP),
        CellSpec(-1, 4, COLOR_SWAMP),
        CellSpec(-1, 3, COLOR_WATER),
        CellSpec(0, 2, COLOR_DESERT),
        CellSpec(0, 1, COLOR_FOREST),
        CellSpec(1, 0, COLOR_FOREST),
        CellSpec(-1, 5, COLOR_SWAMP),
        CellSpec(0, 4, COLOR_SWAMP),
        CellSpec(0, 3, COLOR_DESERT),
        CellSpec(1, 2, COLOR_DESERT, inner_dotted="black"),
        CellSpec(1, 1, COLOR_DESERT, inner_dotted="black"),
        CellSpec(2, 0, COLOR_FOREST, inner_dotted="black"),
    ],
    # Tile 2 / Matrix B
    [
        CellSpec(-3, 5, COLOR_SWAMP, inner_dotted="red"),
        CellSpec(-2, 4, COLOR_FOREST, inner_dotted="red"),
        CellSpec(-2, 3, COLOR_FOREST, inner_dotted="red"),
        CellSpec(-1, 2, COLOR_FOREST),
        CellSpec(-1, 1, COLOR_FOREST),
        CellSpec(0, 0, COLOR_FOREST),
        CellSpec(-2, 5, COLOR_SWAMP),
        CellSpec(-1, 4, COLOR_SWAMP),
        CellSpec(-1, 3, COLOR_FOREST),
        CellSpec(0, 2, COLOR_DESERT),
        CellSpec(0, 1, COLOR_DESERT),
        CellSpec(1, 0, COLOR_DESERT),
        CellSpec(-1, 5, COLOR_SWAMP),
        CellSpec(0, 4, COLOR_MOUNTAIN),
        CellSpec(0, 3, COLOR_MOUNTAIN),
        CellSpec(1, 2, COLOR_MOUNTAIN),
        CellSpec(1, 1, COLOR_MOUNTAIN),
        CellSpec(2, 0, COLOR_DESERT),
    ],
    # Tile 3 / Matrix C
    [
        CellSpec(-3, 5, COLOR_SWAMP),
        CellSpec(-2, 4, COLOR_SWAMP),
        CellSpec(-2, 3, COLOR_FOREST),
        CellSpec(-1, 2, COLOR_FOREST),
        CellSpec(-1, 1, COLOR_FOREST),
        CellSpec(0, 0, COLOR_WATER),
        CellSpec(-2, 5, COLOR_SWAMP, inner_dotted="red"),
        CellSpec(-1, 4, COLOR_SWAMP, inner_dotted="red"),
        CellSpec(-1, 3, COLOR_FOREST),
        CellSpec(-0, 2, COLOR_MOUNTAIN),
        CellSpec(0, 1, COLOR_WATER),
        CellSpec(1, 0, COLOR_WATER),
        CellSpec(-1, 5, COLOR_MOUNTAIN, inner_dotted="red"),
        CellSpec(0, 4, COLOR_MOUNTAIN),
        CellSpec(0, 3, COLOR_MOUNTAIN),
        CellSpec(1, 2, COLOR_MOUNTAIN),
        CellSpec(1, 1, COLOR_WATER),
        CellSpec(2, 0, COLOR_WATER),
    ],
    # Tile 4 / Matrix D
    [
        CellSpec(-3, 5, COLOR_DESERT),
        CellSpec(-2, 4, COLOR_DESERT),
        CellSpec(-2, 3, COLOR_MOUNTAIN),
        CellSpec(-1, 2, COLOR_MOUNTAIN),
        CellSpec(-1, 1, COLOR_MOUNTAIN),
        CellSpec(0, 0, COLOR_MOUNTAIN),
        CellSpec(-2, 5, COLOR_DESERT),
        CellSpec(-1, 4, COLOR_DESERT),
        CellSpec(-1, 3, COLOR_MOUNTAIN),
        CellSpec(0, 2, COLOR_WATER),
        CellSpec(0, 1, COLOR_WATER),
        CellSpec(1, 0, COLOR_WATER, inner_dotted="red"),
        CellSpec(-1, 5, COLOR_DESERT),
        CellSpec(0, 4, COLOR_DESERT),
        CellSpec(0, 3, COLOR_DESERT),
        CellSpec(1, 2, COLOR_FOREST),
        CellSpec(1, 1, COLOR_FOREST),
        CellSpec(2, 0, COLOR_FOREST, inner_dotted="red"),
    ],
    # Tile 5 / Matrix E
    [
        CellSpec(-3, 5, COLOR_SWAMP),
        CellSpec(-2, 4, COLOR_SWAMP),
        CellSpec(-2, 3, COLOR_SWAMP),
        CellSpec(-1, 2, COLOR_MOUNTAIN),
        CellSpec(-1, 1, COLOR_MOUNTAIN),
        CellSpec(0, 0, COLOR_MOUNTAIN),
        CellSpec(-2, 5, COLOR_SWAMP),
        CellSpec(-1, 4, COLOR_DESERT),
        CellSpec(-1, 3, COLOR_DESERT),
        CellSpec(0, 2, COLOR_WATER),
        CellSpec(0, 1, COLOR_MOUNTAIN),
        CellSpec(1, 0, COLOR_MOUNTAIN, inner_dotted="black"),
        CellSpec(-1, 5, COLOR_DESERT),
        CellSpec(0, 4, COLOR_DESERT),
        CellSpec(0, 3, COLOR_WATER),
        CellSpec(1, 2, COLOR_WATER),
        CellSpec(1, 1, COLOR_WATER, inner_dotted="black"),
        CellSpec(2, 0, COLOR_WATER, inner_dotted="black"),
    ],
    # Tile 6 / Matrix F
    [
        CellSpec(-3, 5, COLOR_DESERT, inner_dotted="black"),
        CellSpec(-2, 4, COLOR_DESERT),
        CellSpec(-2, 3, COLOR_SWAMP),
        CellSpec(-1, 2, COLOR_SWAMP),
        CellSpec(-1, 1, COLOR_SWAMP),
        CellSpec(0, 0, COLOR_FOREST),
        CellSpec(-2, 5, COLOR_MOUNTAIN, inner_dotted="black"),
        CellSpec(-1, 4, COLOR_MOUNTAIN),
        CellSpec(-1, 3, COLOR_SWAMP),
        CellSpec(0, 2, COLOR_SWAMP),
        CellSpec(0, 1, COLOR_FOREST),
        CellSpec(1, 0, COLOR_FOREST),
        CellSpec(-1, 5, COLOR_MOUNTAIN),
        CellSpec(0, 4, COLOR_WATER),
        CellSpec(0, 3, COLOR_WATER),
        CellSpec(1, 2, COLOR_WATER),
        CellSpec(1, 1, COLOR_WATER),
        CellSpec(2, 0, COLOR_FOREST),
    ],
]

