@echo off
cd /d "%~dp0"
set EXE=%~dp0dist\WhisperPTT.exe
if not exist "%EXE%" (
    echo ERROR: dist\WhisperPTT.exe not found. Run build.bat first.
    pause
    exit /b 1
)
echo Creating Task Scheduler entry "WhisperPTT" (run at logon)...
schtasks /create /tn "WhisperPTT" /tr "%EXE%" /sc onlogon /rl limited /f
if %errorlevel% equ 0 (
    echo Done! WhisperPTT will start automatically at logon.
    echo Manage it via Task Scheduler (taskschd.msc^)
) else (
    echo Failed. Try running as administrator.
)
pause
