#!/usr/bin/env python3
"""Voice-to-text from default microphone on Windows."""

import argparse
import sys
from pathlib import Path

# Fix Windows terminal encoding (cp1251 → utf-8)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import speech_recognition as sr


def record_and_transcribe(
    duration: float = 5.0,
    language: str = "ru-RU",
    output_wav: str | None = None,
    energy_threshold: int | None = None,
) -> str:
    """Record `duration` seconds from mic, save to WAV, return transcribed text."""
    recognizer = sr.Recognizer()
    if energy_threshold is not None:
        recognizer.energy_threshold = energy_threshold

    # Pre-flight: check microphone is available
    try:
        mic = sr.Microphone()
        mic.__enter__()
        mic.__exit__(None, None, None)
    except OSError as exc:
        raise RuntimeError(
            f"No microphone available: {exc}. "
            "Check Windows Sound settings → Input device."
        ) from exc

    try:
        with sr.Microphone() as source:
            print(f"Recording for {duration}s... Speak now!", flush=True)
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, phrase_time_limit=duration)
    except OSError as exc:
        raise RuntimeError(f"Microphone error during recording: {exc}") from exc

    wav_path = Path(output_wav or "voice_output.wav")
    wav_path.write_bytes(audio.get_wav_data())
    print(f"Saved: {wav_path}", flush=True)

    try:
        text = recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError:
        raise RuntimeError("Could not understand audio — silence or unintelligible speech")
    except sr.RequestError as exc:
        raise RuntimeError(f"Google STT API error: {exc}") from exc

    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Voice input → text")
    parser.add_argument("-d", "--duration", type=float, default=5.0, help="Recording duration in seconds (default: 5)")
    parser.add_argument("-l", "--language", default="ru-RU", help="BCP-47 language code (default: ru-RU)")
    parser.add_argument("-o", "--output", default="voice_output.wav", help="WAV output path (default: voice_output.wav)")
    args = parser.parse_args(argv)

    try:
        text = record_and_transcribe(
            duration=args.duration,
            language=args.language,
            output_wav=args.output,
        )
        print(text)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
