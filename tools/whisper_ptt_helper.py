#!/usr/bin/env python3
"""Helper for whisper_ptt.ahk: records audio, transcribes, prints text to stdout.

Called by AHK with no arguments. Records for a configurable duration,
transcribes via faster-whisper, and prints the result to stdout.
"""

import sys
import os
import time
import tempfile

# Fix Windows terminal encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import speech_recognition as sr


def record_audio(duration: float = 30.0, device_index: int | None = None) -> str:
    """Record audio from microphone for up to `duration` seconds.

    Returns path to WAV file. Caller must delete it.
    """
    recognizer = sr.Recognizer()
    frames = []

    with sr.Microphone(device_index=device_index) as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        start = time.time()
        while time.time() - start < duration:
            try:
                audio = recognizer.listen(source, timeout=1.0, phrase_time_limit=3)
                frames.append(audio)
            except sr.WaitTimeoutError:
                continue
            except OSError:
                break

    if not frames:
        return ""

    combined = frames[0]
    for f in frames[1:]:
        combined = combined + f

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(combined.get_wav_data())
        return f.name


def transcribe(audio_path: str, model_size: str = "small", language: str = "ru") -> str:
    """Transcribe audio file using faster-whisper."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language=language, beam_size=5)
    return " ".join(seg.text for seg in segments).strip()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--model", default="small")
    parser.add_argument("--lang", default="ru")
    args = parser.parse_args()

    # Signal ready to AHK
    print("READY", flush=True)

    wav_path = record_audio(duration=args.duration)
    if not wav_path:
        print("ERROR: No audio recorded", file=sys.stderr)
        sys.exit(1)

    try:
        text = transcribe(wav_path, model_size=args.model, language=args.lang)
    finally:
        os.unlink(wav_path)

    if not text:
        print("ERROR: No speech detected", file=sys.stderr)
        sys.exit(1)

    # Print transcribed text to stdout (AHK reads this)
    print(text)


if __name__ == "__main__":
    main()
