@echo off
chcp 65001 >nul
echo Building AIRobotUI...
uv run pyinstaller --onefile --windowed --clean --name AIRobotUI --icon assets/icon.ico --runtime-tmpdir "%%LOCALAPPDATA%%\AIRobotUI\runtime" src/main.pyw
echo.
if exist "dist\AIRobotUI.exe" (
    echo Build successful: dist\AIRobotUI.exe
) else (
    echo Build FAILED - check output above
)
pause
