@echo off
setlocal
cd /d "%~dp0"

python -m pip install -q -r requirements-build.txt
python tools\generate_map_thumbnails.py --force
python -m PyInstaller --noconfirm --clean CryptidCompanion.spec

echo.
echo Output folder: dist\CryptidCompanion\
echo Run: dist\CryptidCompanion\CryptidCompanion.exe
endlocal
