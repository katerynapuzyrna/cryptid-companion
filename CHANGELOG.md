# Changelog

All notable changes to **CryptidCompanion** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/). Version tags match GitHub Releases (`v0.x.y`).

## [Unreleased]

### Added

- GitHub Release workflow (Windows `.exe` on version tags)
- `custom_maps.example.json` template; local `custom_maps.json` gitignored
- Pre-push checklist and `tools/pre_push_check` script

## [0.2.0] - 2026-08-13

### Added

- pytest unit tests for `logic/` (`tests/unit/logic/`)
- Integration tests for predefined maps (`tests/integration/`)
- GitHub Actions CI (Python 3.11 and 3.12)
- `docs/architecture.md` and README screenshots
- Interactive Tutorials page (components, clues examples, setup, play rules)

### Changed

- App branding standardized to **Cryptid Companion** (UI) / **CryptidCompanion** (repo, exe)

## [0.1.0] - 2026-08-13

### Added

- Initial public release: Maps Library, Solver, Deduction, Hotseat, Tutorials
- PyInstaller packaging (`CryptidCompanion.exe`)
- MIT License, README, reproducible dev setup

[Unreleased]: https://github.com/katerynapuzyrna/cryptid-companion/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/katerynapuzyrna/cryptid-companion/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/katerynapuzyrna/cryptid-companion/releases/tag/v0.1.0
