#!/usr/bin/env python3
"""
Whisper-PTT System Tray App.

Runs in system tray with icon:
  - Gray = idle (mic closed)
  - Yellow = armed (hotkey held, waiting for hold_delay)
  - Green = recording (mic open)

Right-click menu: Start, Stop, Settings, Quit
Left-click: toggle recording
"""

import os
import sys
import time
import threading

# Add parent to path so we can import whisper_ptt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from whisper_ptt import WhisperPTT, make_keyboard_backend, make_win32_backend, make_pynput_backend, _env


def resource_path(relative):
    """Resolve path for both dev and PyInstaller _MEIPASS."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


def _env_path():
    """Find .env file — next to the .exe, or next to script in dev."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller: .exe is in dist/, look next to it
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        return os.path.join(exe_dir, ".env")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


class TrayApp:
    def __init__(self):
        self.ptt = None
        self.icon = None
        self.state = "idle"  # idle | armed | recording
        self._hotkey_thread = None

    # -- Icons (generated with Pillow, no external files) --

    def _make_icon(self, color):
        """64x64 circle with mic symbol."""
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Circle
        d.ellipse([4, 4, 60, 60], fill=color, outline="white", width=2)
        # Mic body (vertical rectangle)
        d.rounded_rectangle([26, 16, 38, 36], radius=3, fill="white")
        # Mic holder (arc)
        d.arc([20, 24, 44, 46], 200, 340, fill="white", width=3)
        # Stand (short vertical line + base)
        d.line([32, 46, 32, 52], fill="white", width=2)
        d.line([26, 52, 38, 52], fill="white", width=2)
        return img

    def _gray_icon(self):
        return self._make_icon((128, 128, 128, 255))

    def _yellow_icon(self):
        return self._make_icon((220, 200, 0, 255))

    def _green_icon(self):
        return self._make_icon((0, 200, 0, 255))

    def _update_icon(self):
        if not self.icon:
            return
        icons = {"idle": self._gray_icon, "armed": self._yellow_icon, "recording": self._green_icon}
        tips = {"idle": "WhisperPTT - Idle", "armed": "WhisperPTT - Hold...", "recording": "WhisperPTT - Recording"}
        self.icon.icon = icons.get(self.state, self._gray_icon)()
        self.icon.title = tips.get(self.state, "WhisperPTT")

    # -- PTT status callback --

    def _on_ptt_status(self, status):
        """Called by WhisperPTT when status changes."""
        self.state = status
        self._update_icon()

    def _on_transcription(self, text):
        """Show transcription result in tray tooltip."""
        if self.icon and text:
            short = text[:60] + "..." if len(text) > 60 else text
            self.icon.title = f"WhisperPTT: {short}"

    # -- Menu actions --

    def _on_start(self, icon, item):
        if self.ptt and not self.ptt.recording:
            self.ptt.open_mic_and_record()

    def _on_stop(self, icon, item):
        if self.ptt and self.ptt.recording:
            self.ptt.close_mic_and_process()

    def _on_settings(self, icon, item):
        """Open .env in Notepad."""
        env = _env_path()
        example = os.path.join(os.path.dirname(env), ".env.example")
        if not os.path.exists(env) and os.path.exists(example):
            import shutil
            shutil.copy(example, env)
        if os.path.exists(env):
            os.startfile(env)

    def _on_quit(self, icon, item):
        if self.ptt:
            self.ptt.shutdown()
        self.icon.stop()

    def _on_left_click(self, icon, button):
        """Toggle recording on left-click."""
        if button != 1:  # left mouse only
            return
        if self.state == "idle":
            self._on_start(icon, None)
        elif self.state == "recording":
            self._on_stop(icon, None)

    # -- Menu --

    def _build_menu(self):
        from pystray import MenuItem, Menu
        return Menu(
            MenuItem("Start recording", self._on_start,
                     enabled=lambda i: self.state == "idle"),
            MenuItem("Stop recording", self._on_stop,
                     enabled=lambda i: self.state == "recording"),
            MenuItem("Settings...", self._on_settings),
            Menu.SEPARATOR,
            MenuItem("Quit", self._on_quit),
        )

    # -- Init PTT in background (model loading takes ~10s) --

    def _init_ptt(self):
        """Initialize WhisperPTT (heavy: loads model)."""
        try:
            env = _env_path()
            try:
                from dotenv import load_dotenv as ld
                ld(env)
            except ImportError:
                pass
        except Exception:
            pass

        self.ptt = WhisperPTT(
            model=_env("MODEL", "medium"),
            language=_env("LANGUAGE", "ru") if _env("LANGUAGE", "ru") != "auto" else "auto",
            paste=_env("PASTE", "true", type_=bool),
            copy=_env("COPY_TO_CLIPBOARD", "true", type_=bool),
            keys_after=None,
            hold_delay=1.5,
        )
        self.ptt.set_status_callback(self._on_ptt_status)
        self.ptt.set_transcribe_callback(self._on_transcription)

        # Start hotkey backend
        hotkey_raw = os.environ.get("WHISPER_PTT_HOTKEY", os.environ.get("HOTKEY", "f9")).strip().lower()
        if "+" in hotkey_raw:
            modifier, key = hotkey_raw.split("+", 1)
        else:
            modifier, key = None, hotkey_raw

        backend = _env("BACKEND", "auto")
        join_fn = None

        # For tray app: keyboard first (supports hold/release), win32 last (toggle only)
        if backend in ("keyboard", "auto"):
            result = make_keyboard_backend(self.ptt, modifier, key, self.ptt.hold_delay)
            if result:
                join_fn, _ = result

        if not join_fn and backend in ("pynput", "auto"):
            result = make_pynput_backend(self.ptt, key, self.ptt.hold_delay)
            if result:
                join_fn, _ = result

        if not join_fn and backend in ("win32", "auto"):
            result = make_win32_backend(self.ptt, modifier, key)
            if result:
                join_fn, _ = result

        if join_fn:
            self._hotkey_thread = threading.Thread(target=join_fn, daemon=True)
            self._hotkey_thread.start()

    # -- Main run --

    def run(self):
        import pystray
        import signal

        # Ctrl+C handler — stop tray and exit
        def _sigint(s, f):
            if self.ptt:
                self.ptt.shutdown()
            if self.icon:
                self.icon.stop()
            os._exit(0)

        signal.signal(signal.SIGINT, _sigint)

        # Show tray immediately (gray icon while model loads)
        self.icon = pystray.Icon(
            "WhisperPTT",
            self._gray_icon(),
            "WhisperPTT - Loading...",
            self._build_menu(),
        )

        # Load model in background so tray appears instantly
        def _load_and_run_icon():
            self._init_ptt()
            self.state = "idle"
            self._update_icon()

        threading.Thread(target=_load_and_run_icon, daemon=True).start()

        # Keep main thread alive and responsive to Ctrl+C
        # pystray runs its own message loop in a separate thread
        self.icon.run_detached()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            if self.ptt:
                self.ptt.shutdown()
            self.icon.stop()


if __name__ == "__main__":
    TrayApp().run()
