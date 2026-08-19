# CryptidCompanion — Architecture

This document describes how **CryptidCompanion** is structured: layers, main modules, data flow, and extension points. The design goal is to keep **game rules and map logic independent of the Qt UI**, so they can be unit-tested and reused (including future ML features).

**Naming:** the desktop UI displays **Cryptid Companion** (`APP_DISPLAY_NAME` in `settings/config.py`). The repository, Windows executable (`CryptidCompanion.exe`), and PyInstaller spec use **CryptidCompanion** without a space.

---

## High-level overview

CryptidCompanion is a **PySide6 desktop application** with four main layers:

```text
┌─────────────────────────────────────────────────────────────┐
│  app.py          Entry point, QApplication, global styles   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  ui/             Pages, shell, shared widgets, QSS          │
└──────────────────────────────┬──────────────────────────────┘
                               │ calls
┌──────────────────────────────▼──────────────────────────────┐
│  logic/          Rules engine, maps, clues (pure Python)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ uses
┌──────────────────────────────▼──────────────────────────────┐
│  board/          Hex geometry, canvas, interactive pieces     │
│  data/           JSON maps, clue books, hints               │
└─────────────────────────────────────────────────────────────┘
```

**Dependency rule:** `logic/` must not import from `ui/`. The board layer may use `logic/` for coordinate mapping and terrain matrices; the UI orchestrates both.

---

## Repository layout

```text
cryptid_app/
├── src/cryptid/
│   ├── app.py                 # Main entry
│   ├── settings/              # config.py, theme.py, strings.py
│   ├── logic/                 # Rules engine (testable)
│   ├── board/                 # Interactive hex board (Qt graphics)
│   ├── ui/
│   │   ├── shell/             # Main window, router, breadcrumbs
│   │   ├── pages/             # Feature pages (controllers)
│   │   └── shared/            # Map cards, widgets, styles helpers
│   ├── data/                  # maps.json, *_book.json, hints.json
│   └── assets/                # .ui files, icons, QSS
├── tests/
│   ├── unit/logic/            # pytest unit tests
│   ├── integration/           # maps.json validation
│   ├── support/               # shared test helpers
│   └── validate_maps_intersections.py
├── docs/
│   ├── architecture.md        # This file
│   ├── PUBLISHING.md          # First push & GitHub Release guide
│   └── screenshots/
└── CryptidCompanion.spec      # PyInstaller packaging
```

---

## Application entry and shell

### `app.py`

1. Creates `QApplication` (Fusion style, high-DPI, app icon).
2. Loads global QSS via `ui.shared.styles.apply_app_style`.
3. Instantiates `CryptidApp` (`ui.shell.main_window`) and shows the main window.

### Main window (`ui/shell/main_window.py`)

- Loads `main_window.ui` and per-page `.ui` files from `assets/ui/`.
- **Sidebar navigation** — `QListWidget` + `Router` maps nav labels to `QStackedWidget` pages.
- **Breadcrumbs** — `BreadcrumbManager` tracks context within multi-step pages (Solve, Deduction, Hotseat, Maps Library).
- Wires **page controllers** that own business logic for each feature area.

### Router (`ui/shell/router.py`)

Maps sidebar row text (e.g. `"Solver Tool"`) to a stack index. Pages register themselves at startup; navigation is text-driven, not hard-coded indices.

---

## UI pages

| Nav item | Controller | Role |
|----------|------------|------|
| Home | `HomePageController` | Intro, feature cards, about/disclaimer |
| Maps Library | `MapsLibraryPageController` | Browse/create/edit predefined and custom maps |
| Solver Tool | `SolvePageController` | Build or select a map; enter clues; highlight habitat |
| Deduction Mode | `DeductionPageController` | Clue chips, simulations, valid-combo analysis |
| Play Hotseat | `PlayHotseatPageController` | Pass-and-play session on one device |
| Tutorials | `TutorialsPageController` | Rules, components, interactive clue examples |
| Play Online, History, Settings | Placeholders | Coming soon |

Large pages use **mixins** (e.g. `ui/pages/solve/*_mixin.py`) to split setup, board interaction, highlights, and navigation without a single giant class.

### Shared UI (`ui/shared/`)

| Area | Purpose |
|------|---------|
| `map_card/` | Map list cards, preview scene, clue dropdowns, highlights |
| `map_cards_manager.py` | Card grid, selection, filtering |
| `widgets/` | Combos, tooltips, player color chips, list widgets |
| `custom_map_save.py` | Persist custom maps to `custom_maps.json` |
| `styles.py` | Loads and merges QSS files from `assets/styles/` |

Styling is split across themed `.qss` files (see `assets/styles/info.txt`).

---

## Logic layer (`logic/`)

Pure Python + NumPy/SciPy. No Qt imports. This is the **source of truth** for clue semantics.

| Module | Responsibility |
|--------|----------------|
| `conditions.py` | Evaluate all clue types on a map; `ConditionsGrid` with bitmask intersections |
| `clues.py` | Resolve player clues from map `books` + `*_book.json` files |
| `clue_grid.py` | Fixed 48-slot clue icon grid; label ↔ slot mapping |
| `map_loader.py` | Build map array from JSON; parse tile IDs; highlight cell conversion |
| `map_builder.py` | Build map array from **live board** state (pieces + markers) |
| `terrain_matrices.py` | Per-tile 3×6 terrain matrices (A–F, rotation) |
| `coord_mapping.py` | Visual row/col ↔ cell index ↔ big-map (Y, X) coordinates |
| `rule_combinations.py` | Enumerate clue combos with exactly one intersection (deduction) |
| `hints.py` | Hint text lookup from `hints.json` |

### Map representation

The internal map is a **9×12 string array** (“big map”):

- 3×2 slots of puzzle tiles, each slot is 3×6 hexes.
- Cell strings encode terrain and optional structure suffixes (e.g. `_standingstone_blue`).

Two paths produce this array:

1. **`build_map_from_data(map_data)`** — from JSON (Maps Library, Solve select mode, Tutorials preview).
2. **`MapBuilder.build_current_map()`** — from the interactive Qt board (Build mode, Deduction, Hotseat).

Both feed the same condition engine.

### Condition evaluation pipeline

```text
map_data or live board
        │
        ▼
 build_map_from_data / MapBuilder.build_current_map
        │
        ▼
 compute_all_conditions(map, advanced_mode)
        │
        ▼
 ConditionsGrid  (bitmask per hex, ordered labels)
        │
        ├── intersection_hexes([clue labels])  → habitat candidates
        ├── intersection_count(...)
        └── rules_true_at_hex(y, x)
```

**Normal vs advanced mode:**

- Normal: 23 positive clues only (no `Not …`, no black structure).
- Advanced: all 48 clues (24 positive + 24 negative, including black structure).

### Highlighting on map previews

UI highlight tuples are `(slot_row, slot_col, cell_idx)`:

```text
intersection_hexes → {(Y, X), ...}
        │
        ▼
targets_to_highlighted_cells(targets, map_data)
        │
        ▼
{(row, col, cell_idx), ...}  → MapCanvasPreviewWidget.apply_highlights
```

---

## Board layer (`board/`)

Qt **QGraphicsScene** rendering of the physical puzzle board.

| Module | Responsibility |
|--------|----------------|
| `canvas.py` | `PuzzleCanvas` — 3×2 slot grid, piece/marker assignment |
| `pieces.py` | `HexPiece` — terrain fill, territories, highlights |
| `markers.py` | Structure markers (standing stones, shacks) |
| `board_builder.py` | Scene setup for build/play modes |
| `board_view.py` | `QGraphicsView` wrapper, zoom/pan |
| `highlight_overlay.py` | Dim non-target hexes when highlighting |
| `geometry.py` | Axial hex coordinates, pixel conversion |
| `factory.py` | Standard six puzzle piece definitions |

The board layer is **interactive** (drag pieces, place markers). Map previews in cards/tutorials reuse the same scene builder (`ui/shared/map_card/scene.py`) in non-interactive mode.

---

## Data layer (`data/`)

| File | Content |
|------|---------|
| `maps.json` | All official-style predefined maps (grid, structures, books, advanced flag) |
| `custom_maps.example.json` | Committed starter custom maps (includes **Dan broke everything**) |
| `custom_maps.json` | User-created maps (local only, gitignored; auto-created from example on first run) |
| `alpha_book.json` … `epsilon_book.json` | Clue text by book ID |
| `hints.json` | Optional hint strings |
| `piece_defs.py` | Tile matrix IDs and terrain specs (in `data/` package) |

Map JSON schema (simplified):

```json
{
  "id": 3,
  "name": "Blackwater Expanse",
  "advancedMode": true,
  "grid3x2": [["4", "2t"], ["1t", "3"], ["5t", "6t"]],
  "structures": [{ "tileId": "2t", "placements": [...] }],
  "books": {
    "3": { "alpha": 36, "beta": null, "gamma": 62, ... }
  }
}
```

Tile IDs: `"1"`–`"6"` with optional `"t"` suffix for 180° rotation (e.g. `"2t"`).

---

## Feature flows

### Solver Tool

1. User selects **Build** (place tiles/markers) or **Select** (predefined map).
2. Enters player count and clues (from map books or manual dropdowns).
3. `compute_all_conditions` + `intersection_hexes` → highlight unique habitat (or toast if zero/multiple).

### Deduction Mode

1. Load map (predefined, custom, or empty board).
2. User assigns clue chips / runs simulation settings.
3. `rule_combinations.find_rule_combinations_with_exactly_one_intersection` searches valid clue sets for N players.
4. Results drive status lists and optional board highlights.

### Play Hotseat

1. Setup: map, mode, players, colors; app assigns clues from books.
2. Session state: turn order, question/search flow, square/circle placement.
3. Board undo stack (`board/undo_state.py`, `ui/shared/board_undo.py`).

### Tutorials

- Static content from `settings/strings.py` + preview widgets (`tutorials_previews.py`).
- **Clues examples:** dropdown drives same highlight pipeline as Solver (`compute_all_conditions` → `targets_to_highlighted_cells`).

---

## Settings and copy

| Module | Role |
|--------|------|
| `settings/config.py` | Paths, UI file locations, QSS file list, app name |
| `settings/theme.py` | Shared colors/pens (aligned with QSS) |
| `settings/strings.py` | User-visible copy, home HTML, tutorial text |

Keeping copy in `strings.py` avoids scattering literals across UI code.

---

## Testing

| Layer | Tool | Location |
|-------|------|----------|
| Logic unit tests | pytest | `tests/unit/logic/` |
| Map data integration | pytest | `tests/integration/test_maps_json.py` |
| Map solvability (legacy CLI) | Script | `tests/validate_maps_intersections.py` |

CI (GitHub Actions) runs unit and integration tests on push/PR.

Run unit tests:

```bash
pip install -r requirements-dev.txt
pytest
```

Logic tests import from `src/cryptid` via `pythonpath` in `pytest.ini`.

---

## Build and deployment

- **Development:** `cd src/cryptid && python app.py`
- **Qt resources:** `resources_rc.py` is committed; regenerate with `pyside6-rcc` when `resources.qrc` changes (see README).
- **Release:** `tools/generate_map_thumbnails.py --force` then `build_exe.bat` → PyInstaller onedir → `dist/CryptidCompanion/` (zip as `CryptidCompanion-win.zip`)
- **Startup:** Home and shell load first; other pages, map cards, and the Hotseat board load on first use
- Bundled data: `assets/` and `data/` (including pre-generated map thumbnails) via `CryptidCompanion.spec`

---

## Extension points

### Adding a clue type

1. Implement evaluation in `conditions.py` (`compute_all_conditions`).
2. Add label to `all_condition_labels` (order matters for bit indices).
3. Add slot/label in `clue_grid.py` if it appears in the icon grid.
4. Add unit tests in `tests/unit/logic/test_conditions.py`.

### Future ML module (planned)

Recommended location: `src/cryptid/ml/`

- **Input:** feature vectors from `logic/` (board state, partial clues).
- **Output:** ranked hexes or suggested clues.
- **Constraint:** must call existing `compute_all_conditions` / `intersection_hexes` — do not duplicate rules in ML code.

### New UI page

1. Add `.ui` file under `assets/ui/`.
2. Create page controller under `ui/pages/`.
3. Register in `main_window.py` (load page, `router.register`, breadcrumbs).
4. Add nav icon under `assets/icons/nav bar/`.

---

## External dependencies

| Package | Used by |
|---------|---------|
| PySide6 | All UI and board graphics |
| NumPy | Map arrays, condition bitmasks |
| SciPy | `convolve` in proximity clue evaluation (`conditions.py`) |

See `requirements.txt` for runtime versions.
