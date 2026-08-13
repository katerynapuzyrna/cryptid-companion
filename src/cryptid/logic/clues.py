"""Resolve player clues from maps.json books and *_book.json files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from settings.config import DATA_DIR

# Book order for clue resolution (hint is NOT a book)
BOOK_ORDER = ["alpha", "beta", "gamma", "delta", "epsilon"]

# Cached book data: book_name -> { id: text }
_BOOK_CACHE: dict[str, dict[int, str]] = {}


def _load_book(book_name: str) -> dict[int, str]:
    """Load a clue book and return id -> text mapping."""
    if book_name in _BOOK_CACHE:
        return _BOOK_CACHE[book_name]
    path = DATA_DIR / f"{book_name}_book.json"
    result: dict[int, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("clues") or []:
            cid = item.get("id")
            text = item.get("text") or ""
            if cid is not None:
                result[int(cid)] = text
    except Exception:
        pass
    _BOOK_CACHE[book_name] = result
    return result


def get_clues_for_map(
    map_data: dict,
    players: int,
) -> list[str]:
    """
    Return list of clue texts for each player (1st, 2nd, ... Nth).

    For N players we need N clues from books. Books are checked in order:
    alpha, beta, gamma, delta, epsilon. For each player, we take the Nth
    non-null value from that sequence. hint is NOT a book.
    """
    if players not in (3, 4, 5):
        return []
    books_data = map_data.get("books") or {}
    player_key = str(players)
    book_entries = books_data.get(player_key) or {}

    # Collect (book_name, clue_id) for non-null book entries, in order
    ordered: list[tuple[str, int]] = []
    for book_name in BOOK_ORDER:
        val = book_entries.get(book_name)
        if val is not None:
            try:
                ordered.append((book_name, int(val)))
            except (TypeError, ValueError):
                pass

    # Take first N for N players
    result: list[str] = []
    for i in range(players):
        if i >= len(ordered):
            result.append("")
            continue
        book_name, clue_id = ordered[i]
        book = _load_book(book_name)
        text = book.get(clue_id, "")
        result.append(text)
    return result
