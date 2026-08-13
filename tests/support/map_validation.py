"""Shared validation helpers for predefined map data."""
from __future__ import annotations

from logic.clues import get_clues_for_map
from logic.conditions import compute_all_conditions
from logic.map_loader import build_map_from_data


class MapValidationError(Exception):
    """Raised when a predefined map fails solvability checks."""


def validate_map_single_intersection(
    map_data: dict,
    players: int,
    *,
    advanced_mode: bool | None = None,
) -> None:
    """
    Verify that the map's book clues for ``players`` intersect at exactly one hex.

    Uses ``advanced_mode`` from ``map_data['advancedMode']`` when not provided.
    Raises ``MapValidationError`` on failure.
    """
    if players not in (3, 4, 5):
        raise MapValidationError(f"unsupported player count: {players}")

    if advanced_mode is None:
        advanced_mode = bool(map_data.get("advancedMode", False))

    clues = get_clues_for_map(map_data, players)
    if len(clues) != players:
        raise MapValidationError(
            f"resolved clue count {len(clues)} != players {players}"
        )
    if any(not clue for clue in clues):
        raise MapValidationError(f"empty clue(s) in resolved rules: {clues}")

    for clue in clues:
        if not advanced_mode and clue.startswith("Not "):
            raise MapValidationError(
                f"normal mode cannot evaluate negative clue: {clue!r}"
            )
        if not advanced_mode and "black" in clue.lower():
            raise MapValidationError(
                f"normal mode cannot evaluate black-structure clue: {clue!r}"
            )

    current_map = build_map_from_data(map_data)
    all_conds = compute_all_conditions(current_map, advanced_mode=advanced_mode)

    try:
        targets = all_conds.intersection_hexes(clues)
    except KeyError as exc:
        raise MapValidationError(f"unknown clue label: {exc}") from exc

    count = len(targets)
    if count != 1:
        raise MapValidationError(
            f"intersection count {count}, expected 1; rules={clues}"
        )


def iter_predefined_map_cases(
    maps: list[dict],
    *,
    player_counts: tuple[int, ...] = (3, 4, 5),
) -> list[tuple[dict, int, bool]]:
    """
    Yield (map_data, players, advanced_mode) cases for integration tests.

    Each map is checked at its configured mode (``advancedMode`` flag).
    Advanced maps use advanced rules; normal maps use normal rules.
    """
    cases: list[tuple[dict, int, bool]] = []
    for map_data in maps:
        advanced_mode = bool(map_data.get("advancedMode", False))
        for players in player_counts:
            cases.append((map_data, players, advanced_mode))
    return cases
