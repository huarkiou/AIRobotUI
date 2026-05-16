@echo off
chcp 65001 >nul
echo Building AIRobotUI...
uv run pyinstaller --onefile --windowed --clean --name AIRobotUI --icon icon.ico --runtime-tmpdir "%%LOCALAPPDATA%%\AIRobotUI\runtime" main.pyw
echo.
if exist "dist\AIRobotUI.exe" (
    echo Build successful: dist\AIRobotUI.exe
) else (
    echo Build FAILED - check output above
)
pause
