"""
Clue icon grid: maps slot numbers 1–48 to clue labels in the fixed 4×12 layout.
Row-major order: slot = row * 4 + col + 1 (1-based).
Icons in CLUES_ICONS_DIR use filenames 1.png .. 48.png for each slot.
"""

# Grid order: 4 columns × 12 rows, row-major (same as deduction clue icon grid).
# Slot index = row * 4 + col (0-based) → slot number = index + 1.
CLUE_GRID_LABELS: list[str] = [
    # Row 0
    "On forest or desert",
    "On desert or swamp",
    "Not on forest or desert",
    "Not on desert or swamp",
    # Row 1
    "On forest or water",
    "On desert or mountain",
    "Not on forest or water",
    "Not on desert or mountain",
    # Row 2
    "On forest or swamp",
    "On water or swamp",
    "Not on forest or swamp",
    "Not on water or swamp",
    # Row 3
    "On forest or mountain",
    "On water or mountain",
    "Not on forest or mountain",
    "Not on water or mountain",
    # Row 4
    "On desert or water",
    "On swamp or mountain",
    "Not on desert or water",
    "Not on swamp or mountain",
    # Row 5
    "Within one space of forest",
    "Within one space of water",
    "Not within one space of forest",
    "Not within one space of water",
    # Row 6
    "Within one space of desert",
    "Within one space of mountain",
    "Not within one space of desert",
    "Not within one space of mountain",
    # Row 7
    "Within one space of swamp",
    "Within one space of cougar or bear territory",
    "Not within one space of swamp",
    "Not within one space of cougar or bear territory",
    # Row 8
    "Within two spaces of a standing stone",
    "Within two spaces of cougar territory",
    "Not within two spaces of a standing stone",
    "Not within two spaces of cougar territory",
    # Row 9
    "Within two spaces of an abandoned shack",
    "Within two spaces of bear territory",
    "Not within two spaces of an abandoned shack",
    "Not within two spaces of bear territory",
    # Row 10
    "Within three spaces of a white structure",
    "Within three spaces of a green structure",
    "Not within three spaces of a white structure",
    "Not within three spaces of a green structure",
    # Row 11
    "Within three spaces of a blue structure",
    "Within three spaces of a black structure",
    "Not within three spaces of a blue structure",
    "Not within three spaces of a black structure",
]


def get_clue_label_for_slot(slot: int) -> str:
    """Return the clue label for grid slot 1–48. Out of range returns empty string."""
    if 1 <= slot <= 48:
        return CLUE_GRID_LABELS[slot - 1]
    return ""


def get_slot_for_clue_label(label: str) -> int:
    """Return slot number 1–48 for the given clue label, or 0 if not found."""
    try:
        return CLUE_GRID_LABELS.index(label) + 1
    except ValueError:
        return 0


# Slot ranges for grouped clue display (matches CLUE_GRID_LABELS order).
CLUE_GRID_GROUP_SLOT_RANGES: list[tuple[str, range]] = [
    ("terrain_pair", range(1, 21)),
    ("one_space", range(21, 33)),
    ("two_spaces", range(33, 41)),
    ("three_spaces", range(41, 49)),
]


def split_group_slots_positive_negative(slots: range) -> tuple[list[int], list[int]]:
    """Split a group's slots into positive and negative clues (4-column grid order)."""
    positive: list[int] = []
    negative: list[int] = []
    for i, slot in enumerate(slots):
        if i % 4 < 2:
            positive.append(slot)
        else:
            negative.append(slot)
    return positive, negative
