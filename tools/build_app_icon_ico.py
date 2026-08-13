"""Rebuild assets/icons/app_icon.ico from app_icon.png (Windows taskbar / exe icon)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "src" / "cryptid" / "assets" / "icons" / "app_icon.png"
ICO = ROOT / "src" / "cryptid" / "assets" / "icons" / "app_icon.ico"

# Sizes Windows / Qt commonly pick for taskbar, title bar, Alt+Tab
_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    im = Image.open(PNG).convert("RGBA")
    im.save(ICO, format="ICO", sizes=_SIZES)
    print("Wrote", ICO)


if __name__ == "__main__":
    main()
