@echo off
chcp 65001 >nul
echo Building TrayForge...
uv run pyinstaller --onefile --windowed --clean --name TrayForge --icon assets/icon.ico --runtime-tmpdir "%%LOCALAPPDATA%%\TrayForge\runtime" --hidden-import pystray --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw --hidden-import startup --add-data "assets/icon.ico;assets" src/main.pyw
echo.
if exist "dist\TrayForge.exe" (
    echo Build successful: dist\TrayForge.exe
) else (
    echo Build FAILED - check output above
)
pause
