# Whisper-PTT

Push-to-talk voice-to-text for Windows. Hold a hotkey 1.5s, speak, release — transcribed text is pasted into the active window.

## Features

- **System tray app** — green/yellow/gray icon, left-click toggle, right-click menu
- **No prebuffer** — mic is CLOSED by default, opens only after 1.5s hold (no noise, no hallucinations)
- **faster-whisper** — CTranslate2 inference, model loaded once at startup
- **English words in Russian speech** — `initial_prompt` with IT vocabulary (Docker, GitHub, pipeline...)
- **Auto language detection** — `--lang auto` for RU/EN mixed speech
- **Paste bug fix** — saves foreground window before recording, restores it before paste
- **PyInstaller exe** — single-file distribution, no Python required
- **Autostart** — Task Scheduler integration

## Quick Start

### Option A: Run from source

```bash
pip install -r requirements.txt
python tools/tray_app.py          # system tray app (recommended)
# or
python tools/whisper_ptt.py       # CLI mode
```

### Option B: Build .exe

```bash
build.bat                         # produces dist\WhisperPTT.exe
install_task.bat                  # autostart at logon
```

### Option C: Download release

Grab `WhisperPTT.exe` from [Releases](https://github.com/paveldaidragon/WhisperInput/releases), run it.

## Usage

Hold your hotkey (default: `F9`) for 1.5 seconds → "Recording..." → speak → release → text appears in the active window.

**Tray controls:**
- Left-click icon: toggle recording
- Right-click: Start / Stop / Settings / Quit

**CLI options:**
```bash
python tools/whisper_ptt.py --key f9 --model medium --lang auto --backend keyboard
python tools/whisper_ptt.py --key alt                    # Alt key
python tools/whisper_ptt.py --key ctrl+f9                # Ctrl+F9 combo
python tools/whisper_ptt.py --model base                 # faster, lower quality
python tools/whisper_ptt.py --list-keys                  # show available keys
```

## Configuration

Copy `.env.example` to `.env` and edit:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_PTT_HOTKEY` | `f9` | Hold key (F1-F12, alt, space, ctrl+f9, etc.) |
| `WHISPER_PTT_LANGUAGE` | `ru` | BCP-47 code, or `auto` for mixed RU/EN |
| `WHISPER_PTT_MODEL` | `medium` | tiny / base / small / medium / large-v3 |
| `WHISPER_PTT_PASTE` | `true` | Paste via Ctrl+V |
| `WHISPER_PTT_COPY_TO_CLIPBOARD` | `true` | Copy to clipboard |
| `WHISPER_PTT_KEYS_AFTER_PASTE` | `none` | Key after paste (enter, ctrl+enter, none) |
| `WHISPER_PTT_BACKEND` | `auto` | keyboard / pynput / win32 / auto |

## Performance

Benchmarked on Intel i5-9500F (6 cores, 3.0 GHz), 16GB RAM:

| Model | Size | 12s audio | Quality |
|-------|------|-----------|---------|
| base | 142MB | ~1s | Fair |
| small | 466MB | ~5s | Good |
| **medium** | **1.5GB** | **~13s** | **Very good** |
| large-v3 | 2.9GB | ~30-40s | Best |

Optimizations applied: `beam_size=1`, `best_of=1`, `temperature=0`, `vad_filter=True`.

## Architecture

```
whisper_ptt.py
├── WhisperPTT class
│   ├── open_mic_and_record()     # save foreground HWND, open mic
│   ├── close_mic_and_process()   # close mic, transcribe in background
│   ├── _transcribe_wav_bytes()   # faster-whisper (loaded once)
│   └── _paste_to_front()         # restore foreground HWND, Ctrl+V
├── make_keyboard_backend()       # hold/release
├── make_win32_backend()          # toggle (press/press)
├── make_pynput_backend()         # hold/release
└── main()                        # CLI entry point

tray_app.py                       # system tray (pystray + Pillow)
WhisperPTT.spec                   # PyInstaller spec
build.bat                         # build .exe
install_task.bat / uninstall_task.bat  # autostart via Task Scheduler
```

## Requirements

- Python 3.9-3.11
- Windows 10/11
- Microphone
- For `.exe`: no Python needed

## References

- [sancau/whisper_ptt](https://github.com/sancau/whisper_ptt) — original architecture
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2
- [OpenAI Whisper](https://github.com/openai/whisper)
