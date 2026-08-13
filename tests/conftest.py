"""Shared pytest fixtures for CryptidCompanion tests."""
from __future__ import annotations

import json

import pytest

from settings.config import MAPS_JSON


@pytest.fixture
def maps_data() -> list[dict]:
    with open(MAPS_JSON, encoding="utf-8") as f:
        return json.load(f).get("maps") or []


@pytest.fixture
def blackwater_map(maps_data: list[dict]) -> dict:
    for entry in maps_data:
        if entry.get("name") == "Blackwater Expanse":
            return entry
    pytest.skip("Blackwater Expanse not found in maps.json")
