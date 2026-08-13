# Publishing guide

Steps to publish **CryptidCompanion** on GitHub and ship Windows releases.

## Before the first push

### 1. Run pre-push checks

From the repository root:

```bash
tools\pre_push_check.bat
```

Or on PowerShell:

```powershell
.\tools\pre_push_check.ps1
```

### 2. Initialize git (if not done yet)

```bash
git init
git add .
git status
```

Confirm **`src/cryptid/data/custom_maps.json` is NOT staged** (it is gitignored). Your local file stays on disk; only `custom_maps.example.json` is committed.

If `custom_maps.json` was ever committed earlier:

```bash
git rm --cached src/cryptid/data/custom_maps.json
```

### 3. Create the GitHub repository

1. On GitHub: **New repository** → name `cryptid-companion` (or your choice).
2. Do **not** initialize with README (you already have one locally).

### 4. First push

```bash
git commit -m "Initial public release (v0.2.0)"
git branch -M main
git remote add origin https://github.com/katerynapuzyrna/cryptid-companion.git
git push -u origin main
```

Verify the **CI** badge in README turns green after the first workflow run.

---

## Custom maps (local data)

| File | In git? | Purpose |
|------|---------|---------|
| `src/cryptid/data/custom_maps.example.json` | Yes | Empty template for new clones |
| `src/cryptid/data/custom_maps.json` | **No** | Your saved custom maps (local only) |

On first run, the app copies the example file to `custom_maps.json` if it is missing.

To reset manually:

```bash
copy src\cryptid\data\custom_maps.example.json src\cryptid\data\custom_maps.json
```

---

## GitHub Release (Windows `.exe`)

Releases are built automatically when you push a **version tag**.

### Create a release

```bash
# Ensure main is clean and tests pass
tools\pre_push_check.bat

git tag -a v0.3.0 -m "v0.3.0 — first public Windows release"
git push origin v0.3.0
```

The [Release workflow](../.github/workflows/release.yml) will:

1. Run tests on Ubuntu
2. Build `CryptidCompanion.exe` on Windows
3. Attach the exe to a GitHub Release with auto-generated notes

### Manual release (fallback)

If you prefer to build locally:

```bash
pip install -r requirements-build.txt
build_exe.bat
```

Then on GitHub: **Releases → Draft new release** → upload `dist/CryptidCompanion.exe`.

---

## After publishing

- [ ] Add repo **description** and **topics**: `python`, `pyside6`, `board-game`, `deduction`
- [ ] Pin the latest Release on the repo home page
- [ ] Link the repo from your CV
- [ ] Update `CHANGELOG.md` when tagging new versions

---

## What stays local (never commit)

- `dist/`, `build/` — PyInstaller output
- `.venv/` — virtual environment
- `src/cryptid/data/custom_maps.json` — personal map library
- `.env`, `.cursor/`
