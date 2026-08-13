"""Unit tests for logic.clues."""
from __future__ import annotations

from logic.clues import BOOK_ORDER, get_clues_for_map


def test_get_clues_for_map_blackwater_three_players(blackwater_map: dict) -> None:
    clues = get_clues_for_map(blackwater_map, 3)
    assert len(clues) == 3
    assert clues == [
        "Within three spaces of a blue structure",
        "Not within one space of water",
        "Not within one space of forest",
    ]


def test_get_clues_for_map_invalid_player_count(blackwater_map: dict) -> None:
    assert get_clues_for_map(blackwater_map, 2) == []
    assert get_clues_for_map(blackwater_map, 6) == []


def test_book_order_is_stable() -> None:
    assert BOOK_ORDER == ["alpha", "beta", "gamma", "delta", "epsilon"]
