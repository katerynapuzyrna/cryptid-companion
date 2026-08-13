"""Split 3×3 nav sprite sheet into named PNGs (_24 / _32 / _256) for assets/icons/nav bar."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

def _sprite_path(root: Path) -> Path:
    bundled = root / "src" / "cryptid" / "assets" / "icons" / "nav_bar_sprite_source.png"
    if bundled.is_file():
        return bundled
    return Path(
        r"C:\Users\kater\.cursor\projects\d-Kate-cryptid-app\assets"
        r"\c__Users_kater_AppData_Roaming_Cursor_User_workspaceStorage_2c556f1e1f63c24672277b00c0fbb496_images_c35245db-4184-4100-b530-818f6064119c-6df533b6-c668-40a3-a138-224a17b4c94a.png"
    )

# Row-major 3×3 — matches sprite sheet layout
NAMES_3X3 = [
    ["home", "play_online", "play_together"],
    ["maps_library", "solver_tool", "deduction_mode"],
    ["tutorials", "history", "settings"],
]

# Top fraction of each cell: excludes grey caption under each icon.
# Bottom sprite row has shorter icons + captions starting higher → tighter crop.
ICON_HEIGHT_FRAC_BY_ROW = (0.77, 0.77, 0.645)
WHITE_THRESH = 248
# Inner margin for fitting bbox into square canvas (scales up for large exports).
def _margin_for_target(target: int) -> int:
    return max(2, target // 16)


def _white_to_alpha(rgb: Image.Image, thresh: int = WHITE_THRESH) -> Image.Image:
    rgba = rgb.convert("RGBA")
    arr = np.array(rgba)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (r >= thresh) & (g >= thresh) & (b >= thresh)
    arr[:, :, 3] = np.where(mask, 0, 255)
    return Image.fromarray(arr, "RGBA")


def _fit_square(src: Image.Image, target: int, margin: int) -> Image.Image:
    bbox = src.split()[3].getbbox()
    if not bbox:
        return Image.new("RGBA", (target, target), (0, 0, 0, 0))
    crop = src.crop(bbox)
    cw, ch = crop.size
    inner = target - 2 * margin
    scale = min(inner / cw, inner / ch)
    nw = max(1, int(round(cw * scale)))
    nh = max(1, int(round(ch * scale)))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    resized = crop.resize((nw, nh), resample)
    out = Image.new("RGBA", (target, target), (0, 0, 0, 0))
    ox = (target - nw) // 2
    oy = (target - nh) // 2
    out.paste(resized, (ox, oy), resized)
    return out


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "src" / "cryptid" / "assets" / "icons" / "nav bar"
    out_dir.mkdir(parents=True, exist_ok=True)

    sprite = _sprite_path(root)
    if not sprite.is_file():
        raise FileNotFoundError(f"Sprite sheet not found: {sprite}")
    sheet = Image.open(sprite).convert("RGB")
    w, h = sheet.size
    cw = w // 3
    ch = h // 3
    x_bounds = [0, cw, 2 * cw, w]
    y_bounds = [0, ch, 2 * ch, h]

    for row in range(3):
        icon_h = max(1, int(ch * ICON_HEIGHT_FRAC_BY_ROW[row]))
        for col in range(3):
            name = NAMES_3X3[row][col]
            cell = sheet.crop(
                (x_bounds[col], y_bounds[row], x_bounds[col + 1], y_bounds[row + 1])
            )
            icon_rgb = cell.crop((0, 0, cell.width, min(icon_h, cell.height)))
            cut = _white_to_alpha(icon_rgb)
            for size in (24, 32, 256):
                fitted = _fit_square(cut, size, _margin_for_target(size))
                dest = out_dir / f"{name}_{size}.png"
                fitted.save(dest, "PNG")
                print("wrote", dest.relative_to(root))

    print("done")


if __name__ == "__main__":
    main()
