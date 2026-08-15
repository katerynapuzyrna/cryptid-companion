"""Pre-render map card thumbnails for all maps in maps.json.

Used before PyInstaller builds so releases ship with PNGs on disk (no UI jank on
first open of Solver / Maps Library browse tabs).

Usage (from repo root, with requirements.txt installed):

    python tools/generate_map_thumbnails.py
    python tools/generate_map_thumbnails.py --force
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRYPTID = ROOT / "src" / "cryptid"
sys.path.insert(0, str(CRYPTID))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from settings.config import MAPS_JSON
from ui.shared.map_card.thumbnail_cache import (
    THUMBNAIL_VERSION,
    render_map_thumbnail_png,
    thumbnail_cache_dir,
    thumbnail_path_for_map_id,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-generate map card thumbnail PNGs.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate thumbnails even when the PNG already exists.",
    )
    args = parser.parse_args()

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)

    with open(MAPS_JSON, encoding="utf-8") as f:
        payload = json.load(f)
    maps = payload.get("maps") or []

    out_dir = thumbnail_cache_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    valid_ids = {str(m.get("id")) for m in maps if m.get("id") is not None}
    if args.force:
        for stale in out_dir.glob("*.png"):
            if stale.stem not in valid_ids:
                stale.unlink()

    written = skipped = failed = 0
    for map_data in maps:
        map_id = map_data.get("id")
        if map_id is None:
            continue
        dest = thumbnail_path_for_map_id(map_id)
        if dest.exists() and not args.force:
            skipped += 1
            continue
        name = map_data.get("name") or f"Map {map_id}"
        if render_map_thumbnail_png(map_data, dest):
            written += 1
            print(f"  {dest.name}  ({name})")
        else:
            failed += 1
            print(f"  FAILED id={map_id} ({name})", file=sys.stderr)

    print(
        f"map_thumbnails_v{THUMBNAIL_VERSION}: "
        f"{written} written, {skipped} skipped, {failed} failed -> {out_dir}"
    )
    app.quit()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
