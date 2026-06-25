#!/usr/bin/env python3
"""Transcribe a WAV file using faster-whisper and print result to stdout.

Usage:
    python run_whisper.py <input_wav> [--model small] [--lang ru]
"""

import sys
import os

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_path", help="Path to WAV file")
    parser.add_argument("--model", default="small")
    parser.add_argument("--lang", default="ru")
    args = parser.parse_args()

    if not os.path.exists(args.wav_path):
        print(f"ERROR: File not found: {args.wav_path}", file=sys.stderr)
        sys.exit(1)

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(args.wav_path, language=args.lang, beam_size=5)
    text = " ".join(seg.text for seg in segments).strip()

    if not text:
        print("ERROR: No speech detected", file=sys.stderr)
        sys.exit(1)

    print(text)


if __name__ == "__main__":
    main()
