# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Push-to-talk voice-to-text tool for Windows. Hold hotkey, speak, release — transcribed text is pasted into the active window.

**Status:** ✅ Работает. Mic closed by default, opens after 1.5s hold. Keyboard backend.
**Critical bug fixed:** `global` declarations in `main()` — без них module-level globals (_pyaudio_instance, _prebuffer_deque, _whisper_model) остаются None в потоках.

## Commands

```bash
python tools/whisper_ptt.py                        # defaults: F9, ru, small
python tools/whisper_ptt.py --key alt --lang en    # Alt key, English
python tools/whisper_ptt.py --key ctrl+f9          # combo
python tools/whisper_ptt.py --model base           # smaller model
python tools/whisper_ptt.py --list-keys            # available keys
python tools/whisper_ptt.py --backend win32        # force win32 backend
```

## Architecture

```
whisper_ptt.py
├── prebuffer_worker()     # Ring buffer thread (always recording last 0.5s)
├── start_recording()      # Copy prebuffer → _audio_frames, set flag
├── stop_recording_and_process()
│   ├── frames_to_wav_bytes()    # Bytes → WAV in memory
│   ├── transcribe_wav_bytes()   # faster-whisper (loaded once)
│   └── paste_to_front()
│       ├── pyperclip.copy()
│       ├── keyboard.send("ctrl+v")  (or pynput fallback)
│       ├── pyperclip.copy(old)     # restore clipboard
│       └── keyboard.send(enter)   # optional (configurable)
└── main()
    ├── WhisperModel(load once)
    ├── prebuffer_worker thread
    └── hotkey backend (keyboard → pynput → win32)
```

## Golden Rules

- **global declarations in main()** — ВСЕГДА добавлять `global` для module-level переменных, которые инициализируются в `main()`. Без этого они остаются None в потоках.
- **1.5с удержание до включения микрофона** — микрофон начинает слушать только после 1.5с удержания hotkey. Если отпустил раньше — запись отменяется.
- **Нет prebuffer** — микрофон полностью закрыт до нажатия. Prebuffer подхватывал шум → whisper галлюцинировал ("1,2,3...30" из тишины).
- **keyboard backend** — доказанно работает на этой машине. win32 имеет проблему с auto-repeat WM_HOTKEY при удержании.
- **Тестировать только в реальном терминале** — background bash процесс из Claude Code не получает keyboard events. Запускать через `cmd` или напрямую.

## Hotkey Backends (priority order)

| Backend | Pros | Cons |
|---------|------|------|
| keyboard (PyPI) | Simple API, `is_pressed()` for modifiers | Needs admin, false release events, Kaspersky blocks |
| pynput | No admin needed, cross-platform | Misses F-keys sometimes, needs active console |
| win32 RegisterHotKey | No deps, always works, system-wide | Toggle only (press/release merged), no modifier-only |

## Config

| Variable | Default | Description |
|----------|---------|-------------|
| WHISPER_PTT_HOTKEY | f9 | Hold key |
| WHISPER_PTT_LANGUAGE | ru | BCP-47 language |
| WHISPER_PTT_MODEL | small | Model size (tiny/base/small/medium/large-v3) |
| WHISPER_PTT_PASTE | true | Paste to active window |
| WHISPER_PTT_COPY_TO_CLIPBOARD | true | Copy to clipboard |
| WHISPER_PTT_KEYS_AFTER_PASTE | none | Key after paste (enter/ctrl+enter/none) |
| WHISPER_PTT_BACKEND | auto | Hotkey backend |

## Known Issues (open)

1. **Paste в неправильное окно** — `keyboard.send("ctrl+v")` срабатывает в окне активном в момент вызова, а не до нажатия hotkey
2. **faster-whisper модель загружается ~5-10с** при первом запуске
3. **keyboard library + Касперский** — может блокировать hooks

## Docs

- `docs/08_voice_input.md` — принятые решения, архитектура, hardware notes

## Rules

- **Start by using AskUserQuestion** — уточнить требования перед реализацией
- **Обсудить все вопросы перед реализацией** — не начинать код без обсуждения
- **If confidence is low**, say so — не гадать
- **Never delete files** without explicit user approval
- **Test in real terminal** — не信任 hotkey events from background process

## Superpowers Workflow

### 1. Brainstorming (перед любой реализацией)
- Не начинать код, пока не обсужден дизайн
- Контекст → вопросы → дизайн → согласование → реализация

### 2. Systematic Debugging
- Не чинить без поиска root cause
- 4 фазы: исследование → гипотеза → проверка → исправление
- Не применять "быстрые фиксы"

### 3. Verification Before Completion
- Нет "готово" без свежего запуска
- Define command → Run → Read output → Verify → Only then assert

## Hardware

- CPU: Intel i5-9500F (6 cores, 3.0 GHz)
- RAM: 16 GB
- GPU: AMD Radeon RX 5700 (8GB) — not used (no DirectML in CTranslate2)
- Mic: Realtek HD Audio (built-in)
- OS: Windows 10 Pro, with Kaspersky (may block hooks)
