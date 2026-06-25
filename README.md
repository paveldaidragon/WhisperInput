# Whisper-PTT

Push-to-talk voice-to-text tool for Windows. Hold a hotkey, speak, release — transcribed text is pasted into the active window.

## Features

- **Multi-backend hotkey**: `keyboard` → `pynput` → `win32 RegisterHotKey` (auto-fallback)
- **Ring buffer prebuffer**: captures the first word (no clipping)
- **faster-whisper**: CTranslate2-based inference, model loaded once at startup
- **Silence gate**: skips low-energy audio
- **VS Code / any app**: pastes via Ctrl+V into whatever was active
- **HuggingFace mirror support**: `HF_ENDPOINT` env var

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure (optional — see `.env.example`):
   ```bash
   cp .env.example .env
   # Edit .env to change hotkey, language, model
   ```

3. Run:
   ```bash
   python tools/whisper_ptt.py
   ```

4. Hold your hotkey (default: `Alt`), speak, release. Text appears in the active window.

## Usage

```bash
python tools/whisper_ptt.py                        # defaults
python tools/whisper_ptt.py --key F9               # F9 key
python tools/whisper_ptt.py --key ctrl+f9          # Ctrl+F9 combo
python tools/whisper_ptt.py --lang en --model base # English, base model
python tools/whisper_ptt.py --backend win32        # force win32 backend
python tools/whisper_ptt.py --list-keys           # show available keys
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_PTT_HOTKEY` | `alt` | Hold key (F1-F12, alt, space, ctrl+f9, etc.) |
| `WHISPER_PTT_LANGUAGE` | `en` | BCP-47 language code |
| `WHISPER_PTT_MODEL` | `small` | Model size (tiny/base/small/medium/large-v3) |
| `WHISPER_PTT_PASTE` | `true` | Paste to active window |
| `WHISPER_PTT_COPY_TO_CLIPBOARD` | `true` | Copy to clipboard |
| `WHISPER_PTT_KEYS_AFTER_PASTE` | `enter` | Key to send after paste (enter, ctrl+enter, none) |
| `WHISPER_PTT_BACKEND` | `auto` | Hotkey backend (keyboard/pynput/win32/auto) |

## Architecture

```
whisper_ptt.py
├── prebuffer_worker()     # Ring buffer thread (always recording last 0.5s)
├── start_recording()      # Copy prebuffer → _audio_frames, set flag
├── ring buffer append    # While _recording, append new chunks
├── stop_recording_and_process()
│   ├── frames_to_wav_bytes()    # Bytes → WAV in memory
│   ├── transcribe_wav_bytes()   # faster-whisper (loaded once)
│   └── paste_to_front()
│       ├── pyperclip.copy()
│       ├── keyboard.send("ctrl+v")  (or pynput fallback)
│       ├── pyperclip.copy(old)     # restore clipboard
│       └── keyboard.send(enter)   # optional
└── main()
    ├── WhisperModel(load once)
    ├── prebuffer_worker thread
    └── hotkey backend (keyboard → pynput → win32)
```

## Requirements

- Python 3.9-3.11
- Windows 10/11 (win32 backend) or Linux/macOS (keyboard/pynput)
- Microphone

## References

- Based on [sancau/whisper_ptt](https://github.com/sancau/whisper_ptt) architecture (prebuffer ring buffer, keyboard+pynput backends)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2)
