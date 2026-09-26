#!/usr/bin/env python3
"""Generate every sound effect and music loop for Valthera: Dragon's Edge.

    python3 tools/audio/generate.py              # render everything + verify
    python3 tools/audio/generate.py --only hit town
    python3 tools/audio/generate.py --verify     # only check the existing files
    python3 tools/audio/generate.py --godot-loops  # set loop points in music .wav.import files

Output: assets/audio/sfx/*.wav (44.1 kHz) and assets/audio/music/*.wav (22.05 kHz),
16-bit PCM mono. Fully deterministic (fixed seeds).
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import music  # noqa: E402
import sfx  # noqa: E402
from dsp import (db, fade, fft_filter, hp, limit, lufs_integrated, lufs_max_short,  # noqa: E402
                 peak_db, read_wav, rng, to_db, write_wav)

ROOT = HERE.parent.parent
SFX_DIR = ROOT / "assets" / "audio" / "sfx"
MUSIC_DIR = ROOT / "assets" / "audio" / "music"

SFX_TARGET = -12.0      # loudest 200 ms window, LUFS-ish, phone-weighted
SFX_CEILING = -1.0      # dBFS
SFX_MAX_LIMIT = 5.0     # dB of peak limiting allowed before we just turn it down
SFX_LEN = (0.1, 1.2)
SFX_LEN_LONG = {"victory": (1.2, 1.6), "defeat": (1.2, 1.6)}
MUSIC_LEN = (32.0, 48.0)


def master_sfx(x, trim):
    sr = sfx.SR
    x = fft_filter(x, sr, lambda f: hp(f, 100, 2))  # little sub energy: phones can't play it
    x = x - np.mean(x)
    x = fade(x, sr, 0.001, 0.015)
    x = x * db(SFX_TARGET + trim - lufs_max_short(x, sr, phone=True))
    over = peak_db(x) - SFX_CEILING
    if over > SFX_MAX_LIMIT:
        x = x * db(-(over - SFX_MAX_LIMIT))
    return limit(x, sr, SFX_CEILING)


def render_sfx(names):
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        fn, seed, trim = sfx.SFX[name]
        t = time.time()
        x = master_sfx(fn(rng(seed)), trim)
        write_wav(SFX_DIR / f"{name}.wav", x, sfx.SR)
        print(f"  sfx   {name:16s} {len(x) / sfx.SR:5.2f}s  ({time.time() - t:.1f}s)")


def render_music(names):
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        t = time.time()
        _, x = music.TRACKS[name]()
        write_wav(MUSIC_DIR / f"{name}.wav", x, music.SR)
        print(f"  music {name:16s} {len(x) / music.SR:5.2f}s  ({time.time() - t:.1f}s)")


# ---------------------------------------------------------------- verification

def verify():
    ok = True
    total = 0
    print(f"\n{'file':28s} {'sr':>6s} {'len s':>6s} {'KB':>6s} {'peak':>6s} {'loud':>6s}  notes")
    for name in sfx.SFX:
        p = SFX_DIR / f"{name}.wav"
        if not p.exists():
            print(f"MISSING {p}")
            ok = False
            continue
        x, sr, ch, sw = read_wav(p)
        size = p.stat().st_size
        total += size
        dur = len(x) / sr
        lo, hi = SFX_LEN_LONG.get(name, SFX_LEN)
        pk = peak_db(x)
        notes = []
        if ch != 1 or sw != 2:
            notes.append("NOT 16-bit mono")
        if not lo <= dur <= hi:
            notes.append(f"LENGTH outside {lo}-{hi}s")
        if pk > -0.9:
            notes.append("PEAK too hot")
        if abs(x[0]) > 0.01 or abs(x[-1]) > 0.01:
            notes.append("EDGE click?")
        ok &= not notes
        print(f"sfx/{name + '.wav':24s} {sr:6d} {dur:6.2f} {size / 1024:6.0f} {pk:6.1f} "
              f"{lufs_max_short(x, sr, phone=True):6.1f}  {' '.join(notes) or 'ok'}")
    for name in music.TRACKS:
        p = MUSIC_DIR / f"{name}.wav"
        if not p.exists():
            print(f"MISSING {p}")
            ok = False
            continue
        x, sr, ch, sw = read_wav(p)
        size = p.stat().st_size
        total += size
        dur = len(x) / sr
        pk = peak_db(x)
        d = np.abs(np.diff(x))
        jump = abs(x[0] - x[-1])
        p99 = np.percentile(d, 99)
        notes = []
        if ch != 1 or sw != 2:
            notes.append("NOT 16-bit mono")
        if not MUSIC_LEN[0] <= dur <= MUSIC_LEN[1]:
            notes.append("LENGTH")
        if pk > -0.9:
            notes.append("PEAK too hot")
        if jump > p99:
            notes.append("LOOP SEAM")
        ok &= not notes
        print(f"music/{name + '.wav':22s} {sr:6d} {dur:6.2f} {size / 1024:6.0f} {pk:6.1f} "
              f"{lufs_integrated(x, sr, circular=True):6.1f}  seam {jump:.4f} "
              f"(median step {np.median(d):.4f}, p99 {p99:.4f}) frames {len(x)} {' '.join(notes) or 'ok'}")
    print(f"\ntotal {total / 1024 / 1024:.2f} MB   (sfx loud = max 200 ms LUFS phone-weighted, music loud = integrated LUFS)")
    print("ALL OK" if ok else "PROBLEMS FOUND")
    return ok


# ---------------------------------------------------------------- godot import loop points

def godot_loops():
    """Music .wav.import files: loop forward over the whole file.

    Godot's importer enum is 0 Detect From WAV, 1 Disabled, 2 Forward, 3 Ping-Pong, 4 Backward."""
    for name in music.TRACKS:
        wav = MUSIC_DIR / f"{name}.wav"
        imp = Path(str(wav) + ".import")
        if not imp.exists():
            print(f"  no {imp.name} yet - run Godot --import first")
            continue
        frames = len(read_wav(wav)[0])
        s = imp.read_text()
        for key, val in (("edit/loop_mode", 2), ("edit/loop_begin", 0), ("edit/loop_end", frames)):
            if re.search(rf"^{re.escape(key)}=.*$", s, flags=re.M):
                s = re.sub(rf"^{re.escape(key)}=.*$", f"{key}={val}", s, flags=re.M)
            else:
                s = s.rstrip("\n") + f"\n{key}={val}\n"
        imp.write_text(s)
        print(f"  {imp.name}: loop_mode=2 (Forward) 0..{frames}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="render just these names")
    ap.add_argument("--verify", action="store_true", help="only verify existing files")
    ap.add_argument("--godot-loops", action="store_true", help="patch music .wav.import loop points")
    a = ap.parse_args()
    if a.godot_loops:
        godot_loops()
        return 0
    if not a.verify:
        want = a.only or list(sfx.SFX) + list(music.TRACKS)
        unknown = [n for n in want if n not in sfx.SFX and n not in music.TRACKS]
        if unknown:
            ap.error(f"unknown names: {unknown}")
        render_sfx([n for n in want if n in sfx.SFX])
        render_music([n for n in want if n in music.TRACKS])
    return 0 if verify() else 1


if __name__ == "__main__":
    sys.exit(main())
