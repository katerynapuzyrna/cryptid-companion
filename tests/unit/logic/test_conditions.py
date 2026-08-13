"""Unit tests for logic.conditions."""
from __future__ import annotations

import numpy as np

from logic.conditions import (
    ConditionsGrid,
    all_condition_labels,
    compute_all_conditions,
    one_of_two_terrains,
)
from logic.map_loader import build_map_from_data


def test_all_condition_labels_normal_mode_excludes_negative_and_black() -> None:
    labels = all_condition_labels(advanced_mode=False)
    assert len(labels) == 23
    assert all(not label.startswith("Not ") for label in labels)
    assert all("black" not in label for label in labels)


def test_all_condition_labels_advanced_mode_includes_all_48() -> None:
    labels = all_condition_labels(advanced_mode=True)
    assert len(labels) == 48
    assert sum(1 for label in labels if label.startswith("Not ")) == 24
    assert "Within three spaces of a black structure" in labels


def test_one_of_two_terrains_marks_matching_cells() -> None:
    current_map = np.array([["forest", "water"], ["mountain", "desert"]], dtype="U20")
    mask = one_of_two_terrains("forest", "desert", current_map)
    assert mask.tolist() == [[1, 0], [0, 1]]


def test_conditions_grid_intersection_hexes() -> None:
    grid = np.array([[0b011, 0b001], [0b010, 0b011]], dtype=np.uint64)
    labels = ["a", "b", "c"]
    conditions = ConditionsGrid(grid=grid, labels=labels)

    assert conditions.intersection_count(["a", "b"]) == 2
    assert conditions.intersection_hexes(["a", "b"]) == {(0, 0), (1, 1)}
    assert conditions.rules_true_at_hex(0, 0) == {"a", "b"}
    assert conditions.selection_mask(["a"]) == 0b001


def test_conditions_grid_unknown_label_raises() -> None:
    conditions = ConditionsGrid(grid=np.zeros((1, 1), dtype=np.uint64), labels=["a"])
    try:
        conditions.intersection_hexes(["missing"])
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError for unknown label")


def test_compute_all_conditions_blackwater_advanced(blackwater_map: dict) -> None:
    current_map = build_map_from_data(blackwater_map)
    conditions = compute_all_conditions(current_map, advanced_mode=True)

    assert len(conditions.labels) == 48
    assert conditions.intersection_count(["On forest or desert"]) > 0

    clues = ["Within three spaces of a blue structure"]
    hexes = conditions.intersection_hexes(clues)
    assert len(hexes) > 0
