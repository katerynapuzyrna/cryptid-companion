# Changelog

All notable changes to **CryptidCompanion** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version tags match GitHub Releases (`v0.x.y`).

## [Unreleased]

### Planned

- Manual QA checklist
- UI automation for critical paths
- ML-assisted deduction

## [0.3.2] - 2026-08-20

Play Hotseat placement rules, a bundled custom map, and a quit crash fix.

### Added

- Shared Play Hotseat chip placement checks (sharing squares, Question, Search)
- Bundled custom map **Dan broke everything** (copied into `custom_maps.json` on first run or upgrade)

### Changed

- Play Hotseat defaults to Random Map; Specific Map name is no longer prefilled

### Fixed

- Crash on quit from recursive app-wide event filters (`QGraphicsView.eventFilter` / tooltips)

## [0.3.1] - 2026-08-15

Faster Windows startup. First public download remains **v0.3.0**.

### Changed

- Windows release is an **onedir** zip (`CryptidCompanion-win.zip`) instead of a single-file exe
- Home and shell load first; Solver, Deduction, Tutorials, Maps Library, and Hotseat load on first visit
- Map cards and the Hotseat board are created when those screens are used
- Release builds pre-generate predefined map thumbnails so Select / browse tabs open without rendering every map

## [0.3.0] - 2026-08-13

First public download. Earlier roadmap work (Phases 1–2) shipped in this release, not as separate GitHub tags.

### Added

- Maps Library, Solver, Deduction, Hotseat, Tutorials
- PyInstaller packaging and GitHub Release workflow (Windows build on version tags)
- `custom_maps.example.json` template; local `custom_maps.json` gitignored
- Pre-push checklist and `tools/pre_push_check` script
- `docs/PUBLISHING.md` first-push and release guide
- pytest unit tests for `logic/` (`tests/unit/logic/`)
- Integration tests for predefined maps (`tests/integration/`)
- GitHub Actions CI (Python 3.11 and 3.12)
- `docs/architecture.md` and README screenshots
- MIT License, README, reproducible dev setup

### Changed

- App branding standardized to **Cryptid Companion** (UI) / **CryptidCompanion** (repo, exe)

[Unreleased]: https://github.com/katerynapuzyrna/cryptid-companion/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/katerynapuzyrna/cryptid-companion/releases/tag/v0.3.2
[0.3.1]: https://github.com/katerynapuzyrna/cryptid-companion/releases/tag/v0.3.1
[0.3.0]: https://github.com/katerynapuzyrna/cryptid-companion/releases/tag/v0.3.0
