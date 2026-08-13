"""Integration tests for predefined maps in maps.json."""
from __future__ import annotations

import json

import pytest

from settings.config import MAPS_JSON
from tests.support.map_validation import (
    MapValidationError,
    iter_predefined_map_cases,
    validate_map_single_intersection,
)


def _load_maps() -> list[dict]:
    with open(MAPS_JSON, encoding="utf-8") as f:
        return json.load(f).get("maps") or []


def _case_id(map_data: dict, players: int, advanced_mode: bool) -> str:
    map_id = map_data.get("id", "?")
    name = (map_data.get("name") or "unnamed").replace(" ", "_")
    mode = "advanced" if advanced_mode else "normal"
    return f"id{map_id}-{name}-p{players}-{mode}"


_MAP_CASES = [
    pytest.param(map_data, players, advanced_mode, id=_case_id(map_data, players, advanced_mode))
    for map_data, players, advanced_mode in iter_predefined_map_cases(_load_maps())
]


@pytest.mark.integration
@pytest.mark.parametrize("map_data,players,advanced_mode", _MAP_CASES)
def test_predefined_map_single_intersection(
    map_data: dict,
    players: int,
    advanced_mode: bool,
) -> None:
    """Each predefined map must have exactly one habitat for 3/4/5 players."""
    try:
        validate_map_single_intersection(
            map_data,
            players,
            advanced_mode=advanced_mode,
        )
    except MapValidationError as exc:
        map_id = map_data.get("id")
        map_name = map_data.get("name")
        pytest.fail(f"map id={map_id} name={map_name!r} players={players}: {exc}")


def test_maps_json_not_empty() -> None:
    assert _load_maps(), "maps.json must contain at least one map"
