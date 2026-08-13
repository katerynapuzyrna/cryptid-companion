"""Unit tests for logic.clue_grid."""
from __future__ import annotations

from logic.clue_grid import (
    CLUE_GRID_GROUP_SLOT_RANGES,
    CLUE_GRID_LABELS,
    get_clue_label_for_slot,
    get_slot_for_clue_label,
    split_group_slots_positive_negative,
)


def test_clue_grid_has_48_labels() -> None:
    assert len(CLUE_GRID_LABELS) == 48


def test_slot_label_roundtrip() -> None:
    for slot in range(1, 49):
        label = get_clue_label_for_slot(slot)
        assert label
        assert get_slot_for_clue_label(label) == slot


def test_out_of_range_slot_returns_empty_label() -> None:
    assert get_clue_label_for_slot(0) == ""
    assert get_clue_label_for_slot(49) == ""


def test_unknown_label_returns_zero_slot() -> None:
    assert get_slot_for_clue_label("Not a real clue") == 0


def test_group_slot_ranges_cover_all_slots_once() -> None:
    all_slots = []
    for _key, slots in CLUE_GRID_GROUP_SLOT_RANGES:
        all_slots.extend(slots)
    assert sorted(all_slots) == list(range(1, 49))


def test_split_positive_negative_counts_per_group() -> None:
    expected = {
        "terrain_pair": (10, 10),
        "one_space": (6, 6),
        "two_spaces": (4, 4),
        "three_spaces": (4, 4),
    }
    for key, slots in CLUE_GRID_GROUP_SLOT_RANGES:
        positive, negative = split_group_slots_positive_negative(slots)
        exp_pos, exp_neg = expected[key]
        assert len(positive) == exp_pos
        assert len(negative) == exp_neg
        for slot in positive:
            assert get_clue_label_for_slot(slot).startswith(("On ", "Within "))
        for slot in negative:
            assert get_clue_label_for_slot(slot).startswith("Not ")
