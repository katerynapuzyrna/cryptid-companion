from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_CRYPTID = PROJECT_ROOT / "src" / "cryptid"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_CRYPTID) not in sys.path:
    sys.path.insert(0, str(SRC_CRYPTID))

from settings.config import MAPS_JSON  # type: ignore
from tests.support.map_validation import (  # type: ignore
    MapValidationError,
    iter_predefined_map_cases,
    validate_map_single_intersection,
)


def main() -> None:
    with open(MAPS_JSON, encoding="utf-8") as f:
        maps = json.load(f).get("maps") or []

    if not maps:
        print("No maps found in maps.json")
        sys.exit(1)

    cases = iter_predefined_map_cases(maps)
    failures: list[str] = []

    for map_data, players, advanced_mode in cases:
        map_id = map_data.get("id")
        map_name = (map_data.get("name") or "").strip()
        mode = "advanced" if advanced_mode else "normal"
        try:
            validate_map_single_intersection(
                map_data,
                players,
                advanced_mode=advanced_mode,
            )
        except MapValidationError as exc:
            failures.append(
                f"map id={map_id} name='{map_name}' players={players} mode={mode}: {exc}"
            )
        except Exception as exc:
            failures.append(
                f"map id={map_id} name='{map_name}' players={players} mode={mode}: "
                f"{type(exc).__name__}: {exc}"
            )

    total = len(cases)
    if failures:
        print(f"FAIL: {len(failures)} / {total} checks failed")
        for line in failures:
            print(line)
        sys.exit(1)

    print(f"PASS: all {total} checks succeeded")


if __name__ == "__main__":
    main()
