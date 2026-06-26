@echo off
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if exist "%STARTUP%\WhisperPTT.lnk" (
    del "%STARTUP%\WhisperPTT.lnk"
    echo Done! WhisperPTT will no longer start at logon.
) else (
    echo Shortcut not found - already removed.
)
pause
