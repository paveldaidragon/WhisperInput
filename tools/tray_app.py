#!/usr/bin/env python3
"""
Whisper-PTT System Tray App using infi.systray.
Hold hotkey 1.5s -> mic -> speak -> release -> transcribe -> paste.
"""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from whisper_ptt import WhisperPTT, make_keyboard_backend, make_pynput_backend, make_win32_backend, _env


class TrayApp:
    def __init__(self):
        self.ptt = None
        self.state = "idle"

    def _on_ptt_status(self, status):
        self.state = status

    def open_settings(self, icon):
        env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
        if os.path.exists(env):
            os.startfile(env)

    def quit_app(self, icon):
        if self.ptt:
            self.ptt.shutdown()
        icon.stop()

    def init_ptt(self):
        self.ptt = WhisperPTT(
            model=_env("MODEL", "medium"),
            language=_env("LANGUAGE", "ru") if _env("LANGUAGE", "ru") != "auto" else "auto",
            paste=_env("PASTE", "true", type_=bool),
            copy=_env("COPY_TO_CLIPBOARD", "true", type_=bool),
            keys_after=None,
            hold_delay=1.5,
        )
        self.ptt.set_status_callback(lambda s: self._on_ptt_status(s))

        hotkey_raw = os.environ.get("WHISPER_PTT_HOTKEY", os.environ.get("HOTKEY", "f9")).strip().lower()
        if "+" in hotkey_raw:
            modifier, key = hotkey_raw.split("+", 1)
        else:
            modifier, key = None, hotkey_raw

        backend = _env("BACKEND", "auto")
        join_fn = None
        if backend in ("pynput", "auto"):
            result = make_pynput_backend(self.ptt, key, self.ptt.hold_delay)
            if result:
                join_fn, _ = result
        if not join_fn and backend in ("win32", "auto"):
            result = make_win32_backend(self.ptt, modifier, key)
            if result:
                join_fn, _ = result
        if not join_fn and backend in ("keyboard", "auto"):
            result = make_keyboard_backend(self.ptt, modifier, key, self.ptt.hold_delay)
            if result:
                join_fn, _ = result

        if join_fn:
            threading.Thread(target=join_fn, daemon=True).start()

    def run(self):
        import infi.systray
        from PIL import Image, ImageDraw

        # Create icon
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([2, 2, 30, 30], fill=(0, 200, 0))

        menu = (infi.systray.MenuItem("Settings", self.open_settings),
                infi.systray.MenuItem("Quit", self.quit_app))

        self.init_ptt()
        icon = infi.systray.Icon("WhisperPTT", img, "WhisperPTT - Idle", menu)
        icon.start()


if __name__ == "__main__":
    TrayApp().run()
