#!/usr/bin/env python3
"""
Whisper-PTT: push-to-talk voice-to-text using faster-whisper.
Hold hotkey 1.5s → mic opens → speak → release → transcribe → paste.

No prebuffer. Mic is CLOSED until hotkey is held for hold_delay.

Usage:
    python whisper_ptt.py                        # F9, ru, small
    python whisper_ptt.py --key alt --lang en
    python whisper_ptt.py --key ctrl+f9
    python whisper_ptt.py --model base
    python whisper_ptt.py --list-keys

Dependencies: faster-whisper, pyaudio, pyperclip (optional: keyboard, pynput)
"""

import os
import io
import sys
import wave
import time
import threading
import ctypes
import logging

# Setup file logging — works in both dev and PyInstaller exe
def _setup_logging():
    _log_dir = os.environ.get("TEMP", os.path.expanduser("~"))
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, "WhisperPTT_debug.log")
    logger = logging.getLogger("WhisperPTT")
    if not logger.handlers:
        try:
            fh = logging.FileHandler(_log_file, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(fh)
            logger.setLevel(logging.DEBUG)
        except Exception:
            pass
    return logger


def _init_logging_once():
    if not _init_logging_once._called:
        _init_logging_once._called = True
        _setup_logging()


_init_logging_once._called = False

# Module-level debug — runs on import
for _lp in [r"D:\AI\WhisperInput\whisper_init.log",
             os.path.join(os.environ.get("TEMP", ""), "whisper_init.log"),
             os.path.join(os.path.expanduser("~"), "whisper_init.log")]:
    try:
        with open(_lp, "a", encoding="utf-8") as f:
            f.write(f"[MODULE] imported ok, name={__name__}, argv={sys.argv}\n")
    except Exception:
        pass

if sys.stdout and sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import numpy as np
import pyaudio
import pyperclip
from faster_whisper import WhisperModel

# Load .env
_script_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_script_dir, "..", ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    pass


def _env(key, default, *, type_=str):
    full_key = key if key.startswith("WHISPER_PTT_") else f"WHISPER_PTT_{key}"
    raw = os.environ.get(full_key, os.environ.get(key, default))
    if type_ is bool:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if type_ is int:
        return int(raw)
    return str(raw)


# Audio constants
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16
PADDING_SEC = 0.2
MIN_FRAMES = 5
SILENCE_THRESHOLD = 750


# -----------------------------------------------------------------------------
# WhisperPTT class — reusable by both CLI and tray app
# -----------------------------------------------------------------------------

class WhisperPTT:
    """Push-to-talk voice-to-text engine."""

    # Common IT/tech terms for initial_prompt — helps whisper recognize
    # English words in Russian speech (GitHub, Docker, pipeline, etc.)
    INITIAL_PROMPT = (
        " Ага, вот: GitHub, Docker, pipeline, deploy, commit, merge, "
        "pull request, backend, frontend, API, CLI, Ctrl, Alt, Shift, "
        "Windows, Linux, Python, npm, pip, webpack, config, debug, "
        "login, logout, token, server, client, cache, proxy, "
        "WebSocket, hook, middleware, scheduler, queue, thread."
    )

    def __init__(self, model="small", language="ru",
                 paste=True, copy=True, keys_after=None,
                 hold_delay=1.5, initial_prompt=None):
        _log_dir = os.path.expanduser(r"~\AppData\Local\WhisperPTT")
        os.makedirs(_log_dir, exist_ok=True)
        try:
            with open(os.path.join(_log_dir, "debug.log"), "a", encoding="utf-8") as f:
                f.write(f"[ENTER] __init__ model={model} lang={language}\n")
        except Exception:
            pass
        _init_logging_once()
        self.model_name = model
        self.language = language if language != "auto" else None
        self.paste_enabled = paste
        self.copy_enabled = copy
        self.keys_after_paste = keys_after
        self.hold_delay = hold_delay
        self.initial_prompt = initial_prompt or self.INITIAL_PROMPT

        self.recording = False
        self.audio_frames = []
        self.mic_stream = None
        self.foreground_hwnd = None  # saved before recording for paste bug fix
        self._wav_counter = 0
        self._on_status = None  # callback for tray: fn(status_str)
        self._on_transcribe = None  # callback for tray: fn(text)

        self.pyaudio_instance = pyaudio.PyAudio()
        print(f" Loading Whisper model ({model})...")
        self.whisper_model = WhisperModel(model, device="cpu", compute_type="int8")
        print(" Model loaded!")

    def set_status_callback(self, fn):
        """Set callback fn(status) where status = 'idle'|'armed'|'recording'."""
        self._on_status = fn

    def set_transcribe_callback(self, fn):
        """Set callback fn(text) called after successful transcription."""
        self._on_transcribe = fn

    def _log(self, msg):
        """Write debug message to log file — AppData."""
        log_dir = os.path.expanduser(r"~\AppData\Local\WhisperPTT")
        os.makedirs(log_dir, exist_ok=True)
        try:
            with open(os.path.join(log_dir, "debug.log"), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    def _status(self, s):
        if self._on_status:
            self._on_status(s)

    # -- mic control --

    def open_mic_and_record(self):
        """Open microphone, save foreground window, start collecting frames."""
        # Save foreground window BEFORE opening mic (paste bug fix)
        try:
            self.foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
            self._log(f"open_mic: saved hwnd={self.foreground_hwnd}")
        except Exception as e:
            self.foreground_hwnd = None
            self._log(f"open_mic: hwnd save failed: {e}")

        self.audio_frames = []
        self.mic_stream = self.pyaudio_instance.open(
            format=AUDIO_FORMAT, channels=CHANNELS,
            rate=SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE,
        )
        self.recording = True
        self._status("recording")
        print(" Recording...", flush=True)
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        """Read chunks from mic while recording."""
        while self.recording:
            try:
                chunk = self.mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
            except Exception:
                break
            self.audio_frames.append(chunk)

    def close_mic_and_process(self):
        """Close mic, snapshot frames, transcribe in background."""
        self.recording = False
        self._status("idle")

        if self.mic_stream:
            try:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
            except Exception:
                pass
            self.mic_stream = None

        frames = list(self.audio_frames)
        if not frames:
            print(" No audio captured", flush=True)
            return
        threading.Thread(target=self._process_and_paste, args=(frames,), daemon=True).start()

    # -- transcription pipeline --

    def _frames_to_wav_bytes(self, frames):
        if PADDING_SEC > 0:
            sw = self.pyaudio_instance.get_sample_size(AUDIO_FORMAT)
            silence_len = int(PADDING_SEC * SAMPLE_RATE) * sw
            frames = [b"\x00" * silence_len] + list(frames)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(self.pyaudio_instance.get_sample_size(AUDIO_FORMAT))
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(b"".join(frames))
        return buf.getvalue()

    def _transcribe_wav_bytes(self, wav_bytes):
        t0 = time.time()
        self._wav_counter += 1
        wav_path = os.path.join(
            os.environ.get("TEMP", "/tmp"),
            f"whisper_ptt_{os.getpid()}_{self._wav_counter}.wav",
        )
        with open(wav_path, "wb") as f:
            f.write(wav_bytes)
        try:
            segments, info = self.whisper_model.transcribe(
                wav_path, language=self.language,
                beam_size=1, best_of=1, temperature=0,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=1000),
                initial_prompt=self.initial_prompt,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            self._log(f"Whisper: {text}")
            return text
        finally:
            try:
                os.unlink(wav_path)
            except FileNotFoundError:
                pass

    def _paste_to_front(self, text):
        """Copy to clipboard and/or paste to active window."""
        log = []
        if not text.strip():
            return
        self._log(f"paste start: hwnd={self.foreground_hwnd}, text={text[:50]}")

        # Restore foreground window (paste bug fix)
        if self.foreground_hwnd:
            try:
                ctypes.windll.user32.SetForegroundWindow(self.foreground_hwnd)
                self._log("focus ok")
                time.sleep(0.1)
            except Exception as e:
                self._log(f"focus fail: {e}")

        try:
            old_clip = pyperclip.paste() if (self.copy_enabled or self.paste_enabled) else ""
        except Exception as e:
            old_clip = ""
            self._log(f"clip read fail: {e}")

        if self.copy_enabled:
            try:
                pyperclip.copy(text)
                self._log("copied")
            except Exception as e:
                self._log(f"copy fail: {e}")

        if self.paste_enabled:
            pasted = False

            # Primary: SendInput via ctypes (GUI-safe, no console needed)
            if not pasted:
                try:
                    user32 = ctypes.windll.user32
                    user32.keybd_event(0x11, 0, 0, 0)
                    user32.keybd_event(0x56, 0, 0, 0)
                    user32.keybd_event(0x56, 0, 2, 0)
                    user32.keybd_event(0x11, 0, 2, 0)
                    pasted = True
                    self._log("pasted via SendInput")
                except Exception as e:
                    self._log(f"SendInput fail: {e}")

            # Fallback: pynput
            if not pasted:
                try:
                    from pynput.keyboard import Controller, Key
                    ctrl_key = Key.ctrl_l if hasattr(Key, "ctrl_l") else Key.ctrl
                    c = Controller()
                    with c.pressed(ctrl_key):
                        c.press("v")
                        c.release("v")
                    pasted = True
                    self._log("pasted via pynput")
                except Exception as e:
                    self._log(f"pynput fail: {e}")

            # Fallback2: keyboard
            if not pasted:
                try:
                    import keyboard as kb
                    kb.send("ctrl+v")
                    pasted = True
                    self._log("pasted via keyboard")
                except Exception as e:
                    self._log(f"keyboard fail: {e}")

            if pasted:
                time.sleep(0.1)
                if self.copy_enabled and old_clip:
                    try:
                        pyperclip.copy(old_clip)
                    except Exception:
                        pass
                if self.keys_after_paste:
                    time.sleep(0.05)
                    try:
                        import keyboard as kb
                        kb.send(self.keys_after_paste)
                    except Exception:
                        pass
                    self._log(f"Pasted + {self.keys_after_paste.upper()} [{', '.join(log)}]")
                else:
                    self._log(f"Pasted [{', '.join(log)}]")
            else:
                self._log(f"Paste FAILED [{', '.join(log)}]")

    def _process_and_paste(self, frames):
        duration_sec = len(frames) * CHUNK_SIZE / SAMPLE_RATE
        self._log(f"Recorded {duration_sec:.1f}s")

        if duration_sec <= 0.5 or len(frames) < MIN_FRAMES:
            print(" Too short, skipping", flush=True)
            return

        raw = b"".join(frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        if audio_int16.size == 0 or np.max(np.abs(audio_int16)) < SILENCE_THRESHOLD:
            print(" Audio too quiet, skipping", flush=True)
            return

        wav_bytes = self._frames_to_wav_bytes(frames)
        text = self._transcribe_wav_bytes(wav_bytes)
        if text:
            if self._on_transcribe:
                self._on_transcribe(text)
            self._paste_to_front(text)

    def shutdown(self):
        """Clean up mic and pyaudio."""
        if self.recording:
            self.recording = False
        if self.mic_stream:
            try:
                self.mic_stream.stop_stream()
                self.mic_stream.close()
            except Exception:
                pass
            self.mic_stream = None
        try:
            self.pyaudio_instance.terminate()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Hotkey backends (module-level, reference ptt instance)
# -----------------------------------------------------------------------------

def make_keyboard_backend(ptt, hotkey_modifier, hotkey_key, hold_delay):
    """Use 'keyboard' library. Hold hotkey hold_delay → mic opens → release → transcribe."""
    try:
        import keyboard
    except ImportError:
        return None

    _armed = [False]
    _arm_time = [0.0]

    def on_press(event=None):
        if ptt.recording or _armed[0]:
            return
        if hotkey_modifier is None or keyboard.is_pressed(hotkey_modifier):
            _armed[0] = True
            _arm_time[0] = time.time()
            ptt._status("armed")
            print(f" Hold {hotkey_key.upper()}... (mic in {hold_delay}s)", flush=True)

            def _wait_and_open():
                time.sleep(hold_delay)
                if _armed[0]:
                    ptt.open_mic_and_record()
                _armed[0] = False

            threading.Thread(target=_wait_and_open, daemon=True).start()

    def on_release(event=None):
        if _armed[0] and not ptt.recording:
            held = time.time() - _arm_time[0]
            _armed[0] = False
            if held < hold_delay:
                print(f" Held {held:.1f}s (< {hold_delay}s), cancelled", flush=True)
            ptt._status("idle")
            return
        if ptt.recording:
            ptt.close_mic_and_process()

    keyboard.on_press_key(hotkey_key, on_press, suppress=False)
    keyboard.on_release_key(hotkey_key, on_release, suppress=False)

    def join():
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    return join, "keyboard"


def make_win32_backend(ptt, hotkey_modifier, hotkey_key):
    """Use win32 RegisterHotKey as TOGGLE with debounce."""
    if sys.platform != "win32":
        return None

    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
    except Exception:
        return None

    VK_MAP = {}
    for i in range(1, 13):
        VK_MAP[f"f{i}"] = 0x70 + (i - 1)
    VK_MAP["alt"] = 0x12
    VK_MAP["alt_l"] = 0xA4
    VK_MAP["space"] = 0x20
    VK_MAP["enter"] = 0x0D
    VK_MAP["tab"] = 0x09

    vk = VK_MAP.get(hotkey_key)
    if vk is None:
        return None

    MOD_MAP = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
    mod_flag = MOD_MAP.get(hotkey_modifier, 0) if hotkey_modifier else 0

    HOTKEY_ID = 9001

    if not user32.RegisterHotKey(None, HOTKEY_ID, mod_flag, vk):
        return None

    print(f" [win32] Registered: mod={hotkey_modifier or 'none'} key={hotkey_key} (vk=0x{vk:02X})", flush=True)

    _last_toggle_time = [0.0]

    def join():
        msg = wintypes.MSG()
        try:
            while True:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1) == 0:
                    time.sleep(0.01)
                    continue
                if msg.message == 0x0012:
                    break
                if msg.message == 0x0312:
                    if msg.wParam == HOTKEY_ID:
                        now = time.time()
                        if now - _last_toggle_time[0] < 0.8:
                            continue
                        _last_toggle_time[0] = now
                        if not ptt.recording:
                            ptt.open_mic_and_record()
                        else:
                            ptt.close_mic_and_process()
        except KeyboardInterrupt:
            pass
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)

    return join, "win32"


def make_pynput_backend(ptt, hotkey_key, hold_delay):
    """Use pynput. Hold hotkey hold_delay → mic opens → release → transcribe."""
    try:
        from pynput import keyboard as pynput_kb
    except ImportError:
        return None

    KEY_MAP = {
        "alt": "alt", "alt_l": "alt_l", "ctrl": "ctrl", "ctrl_l": "ctrl_l",
        "space": "space", "enter": "enter", "tab": "tab",
    }

    if hotkey_key.startswith("f") and hotkey_key[1:].isdigit():
        listen_key = getattr(pynput_kb.Key, hotkey_key)
    elif hotkey_key in KEY_MAP:
        listen_key = getattr(pynput_kb.Key, KEY_MAP[hotkey_key])
    else:
        listen_key = pynput_kb.KeyCode.from_char(hotkey_key)

    _armed = [False]
    _arm_time = [0.0]

    def on_press(key):
        if key != listen_key or ptt.recording or _armed[0]:
            return
        _armed[0] = True
        _arm_time[0] = time.time()
        ptt._status("armed")
        print(f" Hold {hotkey_key.upper()}... (mic in {hold_delay}s)", flush=True)

        def _wait_and_open():
            time.sleep(hold_delay)
            if _armed[0]:
                ptt.open_mic_and_record()
            _armed[0] = False

        threading.Thread(target=_wait_and_open, daemon=True).start()

    def on_release(key):
        if key != listen_key:
            return
        if _armed[0] and not ptt.recording:
            _armed[0] = False
            held = time.time() - _arm_time[0]
            print(f" Held {held:.1f}s (< {hold_delay}s), cancelled", flush=True)
            ptt._status("idle")
            return
        if ptt.recording:
            ptt.close_mic_and_process()

    listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    def join():
        try:
            while listener.is_alive():
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        listener.stop()

    return join, "pynput"


# -----------------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------------

def main():
    import argparse

    # Config from env
    hotkey_raw = os.environ.get("WHISPER_PTT_HOTKEY", os.environ.get("HOTKEY", "f9")).strip().lower()
    if "+" in hotkey_raw:
        hotkey_modifier, hotkey_key = hotkey_raw.split("+", 1)
    else:
        hotkey_modifier, hotkey_key = None, hotkey_raw

    parser = argparse.ArgumentParser(description="Whisper PTT")
    parser.add_argument("--key", help="Hotkey (overrides env)")
    parser.add_argument("--lang", help="Language code")
    parser.add_argument("--model", help="Whisper model size")
    parser.add_argument("--list-keys", action="store_true")
    parser.add_argument("--backend", choices=["win32", "keyboard", "pynput", "auto"],
                        default="auto")
    args = parser.parse_args()

    if args.list_keys:
        print("Key names: F1-F12, alt, alt_l, ctrl, ctrl_l, space, enter, tab")
        print("Modifiers: alt, ctrl, shift, win (e.g. ctrl+f9)")
        return

    if args.key:
        k = args.key.strip().lower()
        if "+" in k:
            hotkey_modifier, hotkey_key = k.split("+", 1)
        else:
            hotkey_modifier, hotkey_key = None, k

    language = args.lang or _env("LANGUAGE", "ru")
    model = args.model or _env("MODEL", "small")
    hold_delay = 1.5

    ptt = WhisperPTT(
        model=model, language=language,
        paste=_env("PASTE", "true", type_=bool),
        copy=_env("COPY_TO_CLIPBOARD", "true", type_=bool),
        keys_after=None,
        hold_delay=hold_delay,
    )

    # Select backend
    join_fn = None
    backend_name = None

    if args.backend in ("win32", "auto"):
        result = make_win32_backend(ptt, hotkey_modifier, hotkey_key)
        if result:
            join_fn, backend_name = result

    if not join_fn and args.backend in ("keyboard", "auto"):
        result = make_keyboard_backend(ptt, hotkey_modifier, hotkey_key, hold_delay)
        if result:
            join_fn, backend_name = result

    if not join_fn and args.backend in ("pynput", "auto"):
        result = make_pynput_backend(ptt, hotkey_key, hold_delay)
        if result:
            join_fn, backend_name = result

    if not join_fn:
        print(" ERROR: No hotkey backend available.", file=sys.stderr)
        sys.exit(1)

    hotkey_str = f"{hotkey_modifier}+{hotkey_key}".upper() if hotkey_modifier else hotkey_key.upper()
    mode_hint = "toggle: press→record, press→stop" if backend_name == "win32" else f"hold {hold_delay}s→mic→release→transcribe"

    banner = [
        "",
        " " * 10 + "=" * 50,
        " " * 10 + " Whisper-PTT ready!",
        f" {'':10} Hotkey: {hotkey_str}",
        f" {'':10} Language: {language}",
        f" {'':10} Model: {model}",
        f" {'':10} Hold delay: {hold_delay}s",
        " " * 10 + "=" * 50,
        "",
    ]
    print("\n".join(banner), flush=True)
    print(f" Backend: {backend_name} ({mode_hint})", flush=True)
    print(f" Mic CLOSED. Hold {hotkey_str} {hold_delay}s to start. Ctrl+C to quit.")
    print()

    try:
        join_fn()
    finally:
        ptt.shutdown()


if __name__ == "__main__":
    main()
