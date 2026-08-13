"""Load map hints and filter possible clue labels when Apply hint is on."""
from __future__ import annotations

import json
from typing import Optional

from settings.config import DATA_DIR

HINTS_JSON = DATA_DIR / "hints.json"

_HINTS_CACHE: dict[str, str] | None = None

_TERRAIN_WORDS = ("forest", "desert", "swamp", "water", "mountain")


def load_hints() -> dict[str, str]:
    """Return hint id (string) -> description from hints.json."""
    global _HINTS_CACHE
    if _HINTS_CACHE is not None:
        return _HINTS_CACHE
    result: dict[str, str] = {}
    try:
        with open(HINTS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                if v is None:
                    continue
                text = str(v).strip()
                if text:
                    result[str(k)] = text
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        result = {}
    _HINTS_CACHE = result
    return result


def get_hint_id_for_map(map_data: dict, players: int) -> Optional[int]:
    """Return the map's hint code for this player count, or None if missing/null."""
    if players not in (3, 4, 5):
        return None
    books = (map_data.get("books") or {}).get(str(players)) or {}
    val = books.get("hint")
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def get_hint_description(hint_id: int | None) -> Optional[str]:
    """Look up hint text; missing id → None (caller treats as no filter)."""
    if hint_id is None:
        return None
    text = load_hints().get(str(hint_id))
    if not text:
        return None
    return text


def is_on_x_or_y_clue(label: str) -> bool:
    """True for 'On A or B' / 'Not on A or B' terrain-pair clues."""
    low = (label or "").strip().lower()
    return low.startswith("on ") or low.startswith("not on ")


def is_within_one_space_of_terrain_clue(label: str) -> bool:
    """Within one space of a terrain type (excludes cougar/bear territory)."""
    low = (label or "").strip().lower()
    if "within one space of" not in low:
        return False
    if "cougar" in low or "bear" in low:
        return False
    return any(t in low for t in _TERRAIN_WORDS)


def clue_excluded_by_hint(label: str, hint_description: str) -> bool:
    """Return True if this clue label should be hidden for the given hint text."""
    hint = (hint_description or "").strip().lower()
    if not hint:
        return False
    low = (label or "").strip().lower()
    if not low:
        return False

    if hint == "no within one space clues":
        return "within one space" in low
    if hint == "no within two spaces clues":
        return "within two spaces" in low
    if hint == "no within three spaces clues":
        return "within three spaces" in low
    if hint == "no clues that mention any animal territory":
        return "cougar" in low or "bear" in low
    if hint == "no on x or y clues":
        return is_on_x_or_y_clue(label)
    if hint == "no clues that mention any type of terrain":
        return is_on_x_or_y_clue(label) or is_within_one_space_of_terrain_clue(label)
    for terrain in _TERRAIN_WORDS:
        if hint == f"no clues that mention {terrain}":
            return terrain in low
    # Unknown description → no filter
    return False


def filter_clue_labels_by_hint(
    labels: list[str],
    hint_description: str | None,
) -> list[str]:
    """Drop labels excluded by hint; unknown/empty hint returns labels unchanged."""
    if not hint_description:
        return list(labels)
    return [lab for lab in labels if not clue_excluded_by_hint(lab, hint_description)]
