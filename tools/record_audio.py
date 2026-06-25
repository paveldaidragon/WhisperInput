#!/usr/bin/env python3
"""Record audio from microphone until a stop flag file is created.

Usage:
    python record_audio.py <output_wav> <stop_flag_path>

Records continuously, checking for the stop flag every 0.5s.
When the flag is detected, stops and saves the WAV file.
"""

import sys
import os
import time
import threading

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sounddevice as sd
import scipy.io.wavfile as wavfile
import numpy as np


def main():
    if len(sys.argv) < 3:
        print("Usage: python record_audio.py <output_wav> <stop_flag_path>", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    stop_flag_path = sys.argv[2]

    sample_rate = 16000
    channels = 1
    frames = []
    recording = True

    def audio_callback(indata, frame_count, time_info, status):
        if recording:
            frames.append(indata.copy())

    try:
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype='int16',
            callback=audio_callback,
            blocksize=1024
        )
        stream.start()
        print(f"Recording to {output_path}... (stop flag: {stop_flag_path})", flush=True)

        while recording:
            if os.path.exists(stop_flag_path):
                recording = False
                break
            time.sleep(0.3)

        stream.stop()
        stream.close()

        if frames:
            audio_data = np.concatenate(frames, axis=0)
            wavfile.write(output_path, sample_rate, audio_data)
            print(f"Saved: {output_path} ({len(audio_data)/sample_rate:.1f}s)", flush=True)
        else:
            print("ERROR: No audio recorded", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
