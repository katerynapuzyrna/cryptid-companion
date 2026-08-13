"""Unit tests for logic.map_loader."""
from __future__ import annotations

from logic.map_loader import (
    build_map_from_data,
    parse_tile_id,
    slot_for_tile_id,
    targets_to_highlighted_cells,
)
from logic.conditions import compute_all_conditions


def test_parse_tile_id() -> None:
    assert parse_tile_id("4") == (3, False)
    assert parse_tile_id("2t") == (1, True)
    assert parse_tile_id("") == (0, False)
    assert parse_tile_id("9") == (5, False)


def test_slot_for_tile_id() -> None:
    grid = [["4", "2t"], ["1t", "3"], ["5t", "6t"]]
    assert slot_for_tile_id(grid, "2t") == (0, 1)
    assert slot_for_tile_id(grid, "missing") is None


def test_build_map_from_data_shape(blackwater_map: dict) -> None:
    current_map = build_map_from_data(blackwater_map)
    assert current_map.shape == (9, 12)
    assert "EMPTY" not in current_map[0, 0]


def test_targets_to_highlighted_cells_roundtrip(blackwater_map: dict) -> None:
    current_map = build_map_from_data(blackwater_map)
    conditions = compute_all_conditions(current_map, advanced_mode=True)
    targets = conditions.intersection_hexes(["On forest or desert"])
    highlighted = targets_to_highlighted_cells(targets, blackwater_map)

    assert highlighted
    for row, col, cell_idx in highlighted:
        assert 0 <= row < 3
        assert 0 <= col < 2
        assert 0 <= cell_idx < 18
