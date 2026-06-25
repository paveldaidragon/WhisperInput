; === Push-to-Talk Whisper ===
; Hold F9 to record, release to transcribe and paste into the active window.

#Requires AutoHotkey v2.0
#SingleInstance Force

; === Configuration ===
PYTHON_EXE := "C:\Users\dD\AppData\Local\Microsoft\WindowsApps\python.exe"
SCRIPT_DIR := A_ScriptDir
RECORD_SCRIPT := SCRIPT_DIR "\record_audio.py"
WHISPER_SCRIPT := SCRIPT_DIR "\run_whisper.py"

; Temp files (unique per session to avoid conflicts)
TEMP_WAV := A_Temp "\whisper_ptt_audio.wav"
TEMP_STOP := A_Temp "\whisper_ptt_stop.flag"
LOG_FILE := A_Temp "\whisper_ptt_log.txt"

; Clean up leftover files
FileDelete(TEMP_WAV)
FileDelete(TEMP_STOP)

; Debug log helper
Log(msg) {
    FileAppend(msg . "`n", LOG_FILE, "UTF-8")
}

Log(Format("[{1}] Script loaded, waiting for F9", A_Now))

; === Hotkey ===
F9::{
    Log(Format("[{1}] F9 pressed", A_Now))

    ; Remember the active window
    targetID := WinGetID("A")
    targetTitle := WinGetTitle("A")
    Log("Target window: " . targetTitle . " (ID: " . targetID . ")")

    ; Clean up temp files
    FileDelete(TEMP_WAV)
    FileDelete(TEMP_STOP)

    ToolTip("Recording...")

    ; Start recording using WScript.Shell.Run
    shell := ComObject("WScript.Shell")
    fullCmd := Format('"{1}" "{2}" "{3}" "{4}"', PYTHON_EXE, RECORD_SCRIPT, TEMP_WAV, TEMP_STOP)
    Log("Run: " . fullCmd)

    try {
        shell.Run(fullCmd, 0, false)
        Log(Format("[{1}] Recording started", A_Now))
    } catch Error as e {
        Log("FAILED to start recording: " & e.Message)
        ToolTip("ERROR: " . e.Message)
        SetTimer(() => ToolTip(), -3000)
        return
    }

    ; Wait for F9 release
    KeyWait("F9")
    Log(Format("[{1}] F9 released", A_Now))

    ; --- PTT released: stop recording ---
    ToolTip("Transcribing...")

    ; Create stop flag
    FileAppend("", TEMP_STOP)
    Log("Stop flag created")

    ; Wait for WAV file to appear
    waited := 0
    while (!FileExist(TEMP_WAV) && waited < 300) {
        Sleep(100)
        waited += 1
    }

    if (!FileExist(TEMP_WAV)) {
        Log("ERROR: WAV file did not appear")
        ToolTip("ERROR: Recording timed out")
        SetTimer(() => ToolTip(), -3000)
        FileDelete(TEMP_STOP)
        return
    }
    Log("WAV file saved")

    ; Run whisper transcription
    fullWhisperCmd := Format('"{1}" "{2}" "{3}" --model small --lang ru', PYTHON_EXE, WHISPER_SCRIPT, TEMP_WAV)
    Log("Whisper: " . fullWhisperCmd)

    try {
        whisperExec := shell.Exec(fullWhisperCmd)
    } catch Error as e {
        Log("FAILED to start whisper: " & e.Message)
        ToolTip("ERROR: " . e.Message)
        SetTimer(() => ToolTip(), -3000)
        FileDelete(TEMP_STOP)
        FileDelete(TEMP_WAV)
        return
    }

    ; Read stdout from whisper
    stdout := ""
    while (!whisperExec.StdOut.AtEndOfStream) {
        stdout .= whisperExec.StdOut.ReadLine() "`n"
    }
    exitCode := whisperExec.ExitCode
    Log("Whisper exit code: " . exitCode)

    ; Clean up
    FileDelete(TEMP_STOP)
    FileDelete(TEMP_WAV)

    if (exitCode != 0) {
        errMsg := ""
        while (!whisperExec.StdErr.AtEndOfStream) {
            errMsg := whisperExec.StdErr.ReadLine()
        }
        Log("Whisper error: " & errMsg)
        ToolTip("ERROR: " . (errMsg != "" ? errMsg : "Transcription failed"))
        SetTimer(() => ToolTip(), -3000)
        return
    }

    ; Extract last non-empty line (the transcribed text)
    lines := StrSplit(stdout, "`n")
    text := ""
    for line in lines {
        if (Trim(line) != "")
            text := line
    }
    Log("Transcribed: " . text)

    if (Trim(text) = "") {
        ToolTip("No speech detected")
        SetTimer(() => ToolTip(), -2000)
        return
    }

    ; --- Paste into target window ---
    if (targetID != "") {
        try {
            WinActivate(targetID)
            WinWaitActive(targetID, , 3)
            Sleep(300)
            Log("Activated target window")
        } catch Error as e {
            Log("Could not activate target: " . e.Message)
        }
    }

    ; Save clipboard, paste text, restore clipboard
    ClipSaved := ClipboardAll()
    Clipboard := text
    Sleep(200)
    Send("^v")
    Sleep(200)
    Clipboard := ClipSaved
    ClipSaved := ""

    Log("Pasted to window")
    ToolTip("Pasted: " . SubStr(text, 1, 50))
    SetTimer(() => ToolTip(), -2000)
}

; === Emergency exit ===
^Esc::{
    FileDelete(TEMP_STOP)
    FileDelete(TEMP_WAV)
    Log(Format("[{1}] Emergency exit", A_Now))
    ExitApp()
}
