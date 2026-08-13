"""Remove outer (edge-connected) light background from nav bar PNGs; keeps interior whites.

Run from repo root: python tools/nav_png_transparent_bg.py
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

# Pixels >= this on all RGB channels count as "background" for flood from edges.
THRESH = 245


def flood_transparent(rgba: np.ndarray, thresh: int = THRESH) -> np.ndarray:
    h, w = rgba.shape[:2]
    r, g, b = rgba[:, :, 0], rgba[:, :, 1], rgba[:, :, 2]
    light = (r >= thresh) & (g >= thresh) & (b >= thresh)
    visited = np.zeros((h, w), dtype=np.bool_)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if light[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if light[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    bg = np.zeros((h, w), dtype=np.bool_)
    while q:
        y, x = q.popleft()
        bg[y, x] = True
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and light[ny, nx] and not visited[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))
    out = rgba.copy()
    out[bg, 3] = 0
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    nav = root / "src" / "cryptid" / "assets" / "icons" / "nav bar"
    if not nav.is_dir():
        raise SystemExit(f"Missing folder: {nav}")
    for p in sorted(nav.glob("*.png")):
        im = Image.open(p).convert("RGBA")
        arr = flood_transparent(np.array(im), THRESH)
        Image.fromarray(arr, "RGBA").save(p, "PNG")
        print("wrote", p.relative_to(root))


if __name__ == "__main__":
    main()
