@echo off
cd /d "%~dp0"
echo Installing dependencies...
pip install -r requirements.txt pyinstaller
echo.
echo Building WhisperPTT.exe...
pyinstaller WhisperPTT.spec --clean --noconfirm
echo.
if exist "dist\WhisperPTT.exe" (
    echo Build complete: dist\WhisperPTT.exe
) else (
    echo Build FAILED - check errors above
)
pause
