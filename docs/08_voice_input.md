# 08. Голосовой ввод (Voice Input)

## Статус

Рабочий прототип. `python tools/whisper_ptt.py` запускается, распознаёт речь, вставляет через Ctrl+V. Проблема: вставка попадает не в целевое окно, а в активное на момент отпускания клавиши.

## Контекст

Пользователь хочет голосовой ввод как основной метод взаимодействия с Claude Code в VS Code на Windows 10. Требуется push-to-talk: удержание клавиши → речь → отпускание → текст в поле ввода.

## Принятые решения

### 1. Whisper backend: faster-whisper (CTranslate2)
- **Почему:** модель загружается один раз при старте, инференс на CPU int8 быстрее чем openai-whisper
- **Альтернатива:** whisper.cpp (C++) — быстрее и меньше, но требует сборки. Приоритет: low, возможна миграция позже
- **Выбранная модель по умолчанию:** small (466MB, ~90-95% accuracy for clean Russian)

### 2. Аудиозапись: PyAudio + ring buffer prebuffer
- **Архитектура:** `prebuffer_worker()` фоновый поток постоянно пишет 0.5с в `collections.deque(maxlen=N)`. При нажатии hotkey копирует предбуфер в `_audio_frames`, затем добавляет новые чанки
- **Библиотека:** `pyaudio` (звук) + `sounddevice` (alternative)
- **Формат:** 16kHz mono int16
- **Silence gate:** `np.max(np.abs(audio_int16)) < 750` — пропускает тишину
- **Min length:** 0.7s или 5 фреймов
- **VAD:** `vad_filter=True`, `min_silence_duration_ms=500`

### 3. Hotkey backends: тройной fallback
Порядок: `keyboard` → `pynput` → `win32 RegisterHotKey`

| Библиотека | Плюсы | Минусы |
|------------|-------|--------|
| keyboard (PyPI) | Простой API, `is_pressed()` для modifier | Требует admin на некоторых системах, детектируется AV |
| pynput | Работает без admin, кросс-платформа | Плохо ловит F9/F12 в некоторых условиях |
| win32api RegisterHotKey | Нет зависимостей, работает всегда | Нет поддержки modifier-only hotkey, только одиночные клавиши или комбо через MOD |

**Проблема с Касперским:** keyboard library детектируется как кейлоггер. Решение — добавить скрипт в доверенные или использовать `win32 RegisterHotKey` как основной backend.

### 4. Paste: Ctrl+V через clipboard
- Сохраняем старый clipboard
- Копируем текст в clipboard через `pyperclip.copy()`
- Отправляем `Ctrl+V` через `keyboard.send()` или pynput
- Восстанавливаем старый clipboard (policy: restore/clear/preserve)
- После paste можно отправить Enter (настраивается)

**Известная проблема:** `keyboard.send("ctrl+v")` вставляет в окно, которое было активным в момент вызова, а не в окно которое было активным до нажатия hotkey. Решение: при нажатии hotkey запоминать `win32gui.GetForegroundWindow()`, перед paste активировать его через `win32gui.SetForegroundWindow()`.

### 5. Конфигурация через env vars / `.env`
Префикс `WHISPER_PTT_`. Загрузка через `python-dotenv`.

## Отложенные решения

- [ ] Окончательный выбор hotkey backend — требуется тест с отключенным Касперским
- [ ] Миграция на whisper.cpp для снижения latency (optional)
- [ ] HuggingFace mirror для загрузки моделей (`HF_ENDPOINT` env var)

## Файлы

```
tools/whisper_ptt.py          # Основной скрипт (hotkey + record + paste)
tools/whisper_ptt.ahk        # AHK v2 версия (экспериментальная)
tools/record_audio.py         # Отдельный скрипт записи (для AHK)
tools/run_whisper.py          # Отдельный скрипт распознавания (для AHK)
tools/voice_input.py          # Google STT версия (reference)
.env.example                  # Шаблон конфига
```

## Hardware notes

Пользователь:
- CPU: Intel i5-9500F (6 ядер, 3.0 GHz)
- RAM: 16 GB
- GPU: AMD Radeon RX 5700 (8GB) — не используется CTranslate2 (нет DirectML)
- Микрофон: Realtek HD Audio (встроен)
- ОС: Windows 10 Pro, с Касперским (может блокировать hooks)

## Известные проблемы (open)

1. **Paste в неправильное окно** — `keyboard.send("ctrl+v")` срабатывает в окне активном в момент вызова
2. **faster-whisper модель загружается ~5-10с** при первом запуске
3. **keyboard library конфликтует с Касперским** — нужен whitelist или win32 backend
4. **Нет поддержки `--step` streaming** — запись сохраняется целиком, распознавание после отпускания

## Ссылки

- [sancau/whisper_ptt](https://github.com/sancau/whisper_ptt) — reference implementation
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) — C++ whisper
- [Habr article](https://habr.com/ru/articles/1009538/) — Whisper PTT overview
