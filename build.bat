@echo off
chcp 65001 >nul
echo Building AIRobotUI...
uv run pyinstaller --onefile --windowed --clean --name AIRobotUI --icon assets/icon.ico --runtime-tmpdir "%%LOCALAPPDATA%%\AIRobotUI\runtime" --hidden-import pystray --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw --add-data "assets/icon.ico;assets" src/main.pyw
echo.
if exist "dist\AIRobotUI.exe" (
    echo Build successful: dist\AIRobotUI.exe
) else (
    echo Build FAILED - check output above
)
pause
