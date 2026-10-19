"""Synthesise an original lo-fi background track and mux it into the videos. No samples, no third-party audio.

    python scripts/make_music.py            # both videos -> video/*-music.mp4

The track follows each video's shape: soft pads over the intro, the full groove during the countdown,
drums out and one long resolving chord over the final hold, then a fade.
Needs numpy and imageio-ffmpeg.
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VIDEO = ROOT / "video"
SR = 44100
BPM = 92
BEAT = 60 / BPM
BAR = 4 * BEAT

# (name, duration, intro, hold) — must match make_video.py and make_video_vertical.py.
VIDEOS = [("passport-real-ranking-2026", 255.0, 7.0, 8.0),
          ("passport-real-ranking-2026-vertical", 179.0, 8.0, 6.0)]

# Fmaj7 – G6 – Em7 – Am7, as MIDI notes (pad voicing) and bass roots.
CHORDS = [[53, 57, 60, 64], [55, 59, 62, 64], [52, 55, 59, 62], [57, 60, 64, 67]]
ROOTS = [41, 43, 40, 45]
FINAL = [48, 55, 60, 64, 67, 71]  # Cmaj7, the resolution under #1

rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env(n, attack, release):
    e = np.ones(n)
    a, r = min(int(attack * SR), n), min(int(release * SR), n)
    e[:a] = np.linspace(0, 1, a)
    if r:
        e[n - r:] *= np.linspace(1, 0, r)
    return e


def pad_note(f, dur):
    t = np.arange(int(dur * SR)) / SR
    tone = sum(np.sin(2 * np.pi * f * d * t + p) for d, p in ((1.0, 0), (1.003, 1.1), (0.997, 2.3)))
    tone += 0.25 * np.sin(2 * np.pi * 2 * f * t)
    return tone / 3.3 * env(len(t), 0.6, 0.8)


def pluck(f, dur):
    t = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.12 * np.sin(2 * np.pi * 3 * f * t)
    return tone * np.exp(-t * 5.5) * env(len(t), 0.004, 0.05)


def bass_note(f, dur):
    t = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t * 1.6) * env(len(t), 0.01, 0.08)


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    freq = 50 + 70 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 9)


def snare():
    t = np.arange(int(0.25 * SR)) / SR
    noise = np.convolve(rng.standard_normal(len(t)), np.ones(4) / 4, "same")  # soften the hiss
    return (0.6 * noise + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 18)


def hat():
    t = np.arange(int(0.06 * SR)) / SR
    noise = rng.standard_normal(len(t))
    noise = noise - np.convolve(noise, np.ones(3) / 3, "same")  # crude high-pass
    return noise * np.exp(-t * 70)


def add(track, sound, start, gain, pan=0.0):
    i = int(start * SR)
    if i >= track.shape[0]:
        return
    s = sound[: track.shape[0] - i] * gain
    track[i:i + len(s), 0] += s * (1 - pan) / 2 * 2 ** 0.5
    track[i:i + len(s), 1] += s * (1 + pan) / 2 * 2 ** 0.5


def reverb(x, seconds=2.2, mix=0.22):
    n = int(seconds * SR)
    ir = rng.standard_normal((n, 2)) * np.exp(-np.arange(n) / SR * 3.2)[:, None]
    ir[:, 0] = np.convolve(ir[:, 0], np.ones(8) / 8, "same")
    ir[:, 1] = np.convolve(ir[:, 1], np.ones(8) / 8, "same")
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(ir, size, axis=0), size, axis=0)[: len(x)]
    wet *= np.abs(x).max() / (np.abs(wet).max() + 1e-9)
    return (1 - mix) * x + mix * wet


def compose(duration, intro, hold):
    track = np.zeros((int(duration * SR), 2))
    groove_end = duration - hold
    arp_order = [0, 2, 1, 3, 2, 1, 3, 2]
    bar = 0
    t = 0.0
    while t < groove_end:
        k = bar % 4
        in_groove = t >= intro - 0.01
        for m in CHORDS[k]:
            add(track, pad_note(hz(m), BAR + 0.8), t, 0.10, pan=0.0)
        if in_groove:
            add(track, bass_note(hz(ROOTS[k]), BAR * 0.5), t, 0.34)
            add(track, bass_note(hz(ROOTS[k]), BAR * 0.5), t + 2 * BEAT, 0.26)
            for b in range(4):
                if b in (0, 2):
                    add(track, kick(), t + b * BEAT, 0.42)
                else:
                    add(track, snare(), t + b * BEAT, 0.10, pan=0.1)
            for e in range(8):
                swing = 0.03 if e % 2 else 0.0
                add(track, hat(), t + e * BEAT / 2 + swing, 0.05 if e % 2 else 0.07, pan=0.35)
            # Arpeggio from the second groove bar on; every fourth bar breathes.
            if t >= intro + BAR and bar % 8 != 7:
                notes = CHORDS[k]
                for e in range(8):
                    m = notes[arp_order[e]] + 12
                    add(track, pluck(hz(m), BEAT), t + e * BEAT / 2 + (0.03 if e % 2 else 0.0), 0.085,
                        pan=-0.3 if e % 2 else 0.3)
        bar += 1
        t += BAR
    # Resolution: one long Cmaj7 under the final hold, no drums.
    for m in FINAL:
        add(track, pad_note(hz(m), hold + 1.5), groove_end, 0.11)
    add(track, pluck(hz(72), 3.0), groove_end, 0.12)
    add(track, pluck(hz(79), 3.0), groove_end + BEAT, 0.09, pan=0.3)

    track = reverb(track)
    track *= env(len(track), 1.5, min(4.0, hold))[:, None]
    track = np.tanh(track * 1.4)  # gentle limiting
    return track / np.abs(track).max() * 0.71  # about -3 dBFS peak


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for name, duration, intro, hold in VIDEOS:
        src = VIDEO / f"{name}.mp4"
        wav = VIDEO / f"{name}.wav"
        write_wav(wav, compose(duration, intro, hold))
        out = VIDEO / f"{name}-music.mp4"
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", str(src), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        str(out)], check=True)
        wav.unlink()
        print(f"{out.name}: {duration:.0f}s")


if __name__ == "__main__":
    main()
