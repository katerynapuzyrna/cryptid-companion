@echo off
setlocal
cd /d "%~dp0"

python -m pip install -q -r requirements-build.txt
python -m PyInstaller --noconfirm --clean CryptidCompanion.spec

echo.
echo Output: dist\CryptidCompanion.exe   (single file; first launch unpacks to TEMP)
endlocal
