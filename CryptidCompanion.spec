# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: single-file (--onefile) GUI build for CryptidCompanion (PySide6)."""
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CryptidCompanion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(CRYPTID / "assets" / "icons" / "app_icon.ico"),
)
