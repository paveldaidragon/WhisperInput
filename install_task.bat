@echo off
cd /d "%~dp0"
set EXE=%~dp0dist\WhisperPTT.exe
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if not exist "%EXE%" (
    echo ERROR: dist\WhisperPTT.exe not found. Run build.bat first.
    pause
    exit /b 1
)
echo Creating startup shortcut...
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\install.vbs"
echo sLinkFile = "%STARTUP%\WhisperPTT.lnk" >> "%TEMP%\install.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\install.vbs"
echo oLink.TargetPath = "%EXE%" >> "%TEMP%\install.vbs"
echo oLink.WorkingDirectory = "%~dp0dist" >> "%TEMP%\install.vbs"
echo oLink.Save >> "%TEMP%\install.vbs"
cscript //nologo "%TEMP%\install.vbs"
del "%TEMP%\install.vbs"
if exist "%STARTUP%\WhisperPTT.lnk" (
    echo Done! WhisperPTT starts automatically at logon.
    echo Shortcut: %STARTUP%\WhisperPTT.lnk
) else (
    echo Failed.
)
pause
