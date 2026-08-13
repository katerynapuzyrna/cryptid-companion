"""Remove solid / near-white backgrounds from nav bar PNGs (edge flood + light island wipe)."""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

NAV_DIR = Path(__file__).resolve().parents[1] / "src" / "cryptid" / "assets" / "icons" / "nav bar"


def edge_flood_transparent(im: Image.Image, tol: int = 20) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    pixels = im.load()
    bg = pixels[0, 0][:3]

    def close(c: tuple[int, int, int]) -> bool:
        return all(abs(c[i] - bg[i]) <= tol for i in range(3))

    visited = bytearray(w * h)

    def idx(x: int, y: int) -> int:
        return y * w + x

    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            i = idx(x, y)
            if not visited[i]:
                visited[i] = 1
                if close(pixels[x, y][:3]):
                    q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            i = idx(x, y)
            if not visited[i]:
                visited[i] = 1
                if close(pixels[x, y][:3]):
                    q.append((x, y))

    while q:
        x, y = q.popleft()
        r, g, b, a = pixels[x, y]
        if a == 0:
            continue
        pixels[x, y] = (r, g, b, 0)
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                j = idx(nx, ny)
                if not visited[j]:
                    visited[j] = 1
                    if close(pixels[nx, ny][:3]):
                        q.append((nx, ny))
    return im


def wipe_enclosed_light_rgba(im: Image.Image) -> Image.Image:
    a = np.array(im.convert("RGBA"), dtype=np.uint8)
    rgb = a[:, :, :3].astype(np.int16)
    al = a[:, :, 3].astype(np.int16)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    wipe = (al > 0) & (rgb.min(axis=2) >= 246) & (chroma <= 12)
    al[wipe] = 0
    a[:, :, 3] = np.clip(al, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def process_png(path: Path) -> None:
    im = Image.open(path)
    im = edge_flood_transparent(im)
    im = wipe_enclosed_light_rgba(im)
    im.save(path, "PNG", optimize=True)
    print(path.name, "ok")


def main() -> None:
    if not NAV_DIR.is_dir():
        raise SystemExit(f"Missing: {NAV_DIR}")
    for p in sorted(NAV_DIR.glob("*.png")):
        process_png(p)


if __name__ == "__main__":
    main()
