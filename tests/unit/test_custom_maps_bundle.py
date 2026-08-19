"""Bundled starter custom maps must ship for new installs and upgrades."""
from __future__ import annotations

import json

from settings.config import CUSTOM_MAPS_EXAMPLE_JSON
from ui.shared.custom_map_save import ensure_custom_maps_json

_DAN = "dan broke everything"


def test_example_includes_dan_broke_everything() -> None:
    with open(CUSTOM_MAPS_EXAMPLE_JSON, encoding="utf-8") as f:
        maps = json.load(f).get("maps") or []
    names = {str(m.get("name") or "").strip().lower() for m in maps}
    assert _DAN in names


def test_ensure_creates_file_with_bundled_map(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "custom_maps.json"
    monkeypatch.setattr("ui.shared.custom_map_save.CUSTOM_MAPS_JSON", dest)
    monkeypatch.setattr("ui.shared.custom_map_save.DATA_DIR", tmp_path)
    assert not dest.exists()
    ensure_custom_maps_json()
    root = json.loads(dest.read_text(encoding="utf-8"))
    names = {str(m.get("name") or "").strip().lower() for m in root.get("maps") or []}
    assert _DAN in names


def test_ensure_merges_bundled_map_into_existing_file(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "custom_maps.json"
    dest.write_text('{"version": 1, "maps": []}\n', encoding="utf-8")
    monkeypatch.setattr("ui.shared.custom_map_save.CUSTOM_MAPS_JSON", dest)
    monkeypatch.setattr("ui.shared.custom_map_save.DATA_DIR", tmp_path)
    ensure_custom_maps_json()
    root = json.loads(dest.read_text(encoding="utf-8"))
    names = {str(m.get("name") or "").strip().lower() for m in root.get("maps") or []}
    assert _DAN in names
    ensure_custom_maps_json()
    again = json.loads(dest.read_text(encoding="utf-8"))
    dan_maps = [
        m
        for m in again.get("maps") or []
        if str(m.get("name") or "").strip().lower() == _DAN
    ]
    assert len(dan_maps) == 1
