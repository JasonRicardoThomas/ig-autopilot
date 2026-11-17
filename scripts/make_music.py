"""Generate original royalty-free ambient loops into assets/audio (no licensing needed).
Run: python scripts/make_music.py   (needs numpy + ffmpeg). Drop your own licensed tracks in the same folder to add variety."""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"
A4 = 440.0


def hz(midi):
    return A4 * 2 ** ((midi - 69) / 12)


def pad(freqs, dur, rng):
    t = np.arange(int(SR * dur)) / SR
    s = np.zeros_like(t)
    for f in freqs:
        for det in (-0.12, 0.0, 0.12):  # slight detune = warm chorus
            ph = rng.uniform(0, 6.28)
            s += np.sin(2 * np.pi * (f + det) * t + ph) + 0.25 * np.sin(2 * np.pi * 2 * (f + det) * t + ph)
    env = np.minimum(1, np.minimum(t / (dur * 0.35), (dur - t) / (dur * 0.35)))
    return s * env ** 1.5 / (len(freqs) * 3)


def pluck(f, dur=1.6):
    t = np.arange(int(SR * dur)) / SR
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-3.2 * t) * np.minimum(1, t / 0.01)


def track(name, root, chords, bpm, seed):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    total = bar * len(chords) * 2  # two passes through the progression
    n = int(SR * (total + 2))
    mix = np.zeros(n)
    for rep in range(2):
        for i, (offs) in enumerate(chords):
            start = (rep * len(chords) + i) * bar
            notes = [root + o for o in offs]
            p = pad([hz(m) for m in notes], bar + 1.2, rng)
            a = int(SR * start)
            mix[a:a + len(p)] += p * 0.9
            for k, m in enumerate(notes + [notes[1] + 12, notes[2] + 12]):  # gentle arpeggio
                pl = pluck(hz(m + 12))
                b = int(SR * (start + k * beat * 0.5 + (0.0 if k % 2 == 0 else 0.02)))
                if b + len(pl) < n:
                    mix[b:b + len(pl)] += pl * 0.16
    mix = mix[: int(SR * total)]
    mix /= np.max(np.abs(mix)) * 1.05
    tmp = OUT / f"{name}.wav"
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    mp3 = OUT / f"{name}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-af",
                    "aecho=0.8:0.6:60|120:0.25|0.15,loudnorm=I=-18:TP=-2:LRA=7,afade=t=in:d=0.5,afade=t=out:st=%.1f:d=1.5" % (total - 1.5),
                    "-ac", "2", "-b:a", "128k", str(mp3)], check=True)
    tmp.unlink()
    print("wrote", mp3.name, f"{total:.0f}s")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    track("calm-morning", 57, [[0, 4, 7, 11], [-3, 0, 4, 7], [-7, -3, 0, 4], [-5, -1, 2, 7]], 84, 1)       # A major-ish, Cmaj7 feel
    track("focus-flow", 52, [[0, 3, 7, 10], [-4, 0, 3, 7], [-9, -5, -2, 3], [-2, 2, 5, 9]], 92, 2)
    track("bright-start", 60, [[0, 4, 7, 12], [-5, 0, 4, 7], [-3, 0, 4, 9], [-7, -3, 0, 5]], 100, 3)
    track("evening-city", 55, [[0, 7, 10, 14], [-2, 5, 9, 12], [-5, 2, 7, 10], [-7, 0, 5, 9]], 76, 4)
