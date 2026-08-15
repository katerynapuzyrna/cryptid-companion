# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: onedir GUI build for CryptidCompanion (PySide6).

Onedir avoids extracting the full bundle to %TEMP% on every launch (much faster
startup than --onefile). Ship dist/CryptidCompanion/ as a zip for releases.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

ROOT = Path(SPEC).resolve().parent
CRYPTID = ROOT / "src" / "cryptid"

datas = [
    (str(CRYPTID / "assets"), "assets"),
    (str(CRYPTID / "data"), "data"),
]

binaries = collect_dynamic_libs("PySide6")

block_cipher = None

a = Analysis(
    [str(CRYPTID / "app.py")],
    pathex=[str(CRYPTID)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["resources_rc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CryptidCompanion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(CRYPTID / "assets" / "icons" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CryptidCompanion",
)
