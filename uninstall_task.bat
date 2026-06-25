@echo off
echo Removing Task Scheduler entry "WhisperPTT"...
schtasks /delete /tn "WhisperPTT" /f
if %errorlevel% equ 0 (
    echo Done! WhisperPTT will no longer start at logon.
) else (
    echo Task not found or already removed.
)
pause
