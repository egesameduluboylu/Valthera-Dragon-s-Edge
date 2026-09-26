"""Synth instruments and drums. Each returns a mono float array at `sr`.

`dur` is how long the note is held; most voices add a release tail after it.
"""
import math

import numpy as np

from dsp import (TAU, ar_env, bp, exp_decay, fft_filter, formant_resp, harmonic_table,
                 hp, lp, noise, phase_of, ramp_in, rng, saturate, saw_amps, secs,
                 table_osc)


# ---------------------------------------------------------------- plucked strings

def ks_pluck(sr, freq, dur, vel=1.0, t60=1.5, bright=0.5, seed=0, release=0.08,
             pick=0.0):
    """Karplus-Strong string. Rendered at an internal rate chosen so the loop
    length is exact for `freq`, then resampled -> accurate tuning."""
    total = dur + release
    N = int(math.floor(sr / freq - 0.5)) + 1
    sr_i = (N + 0.5) * freq
    n_i = int(math.ceil(total * sr_i)) + 4
    r = rng(seed)
    exc = r.uniform(-1, 1, N)
    passes = int(round((1 - bright) * 8))
    for _ in range(passes):
        exc = 0.5 * (exc + np.roll(exc, 1))
    if pick > 0:  # pluck position comb: removes harmonics like a real pick point
        exc = exc - np.roll(exc, max(1, int(N * pick)))
    exc -= exc.mean()
    exc /= max(np.max(np.abs(exc)), 1e-9)
    rho = 10.0 ** (-3.0 / (t60 * freq))
    z = np.zeros(n_i + 1)
    z[1:N + 1] = exc
    s = 1 + N
    while s < n_i + 1:
        e = min(s + N, n_i + 1)
        L = e - s
        z[s:e] = rho * 0.5 * (z[s - N:s - N + L] + z[s - N - 1:s - N - 1 + L])
        s = e
    y = z[1:]
    n_out = int(total * sr)
    y = np.interp(np.arange(n_out) * (sr_i / sr), np.arange(len(y)), y)
    env = ar_env(n_out, sr, 0.001, dur, release)
    return vel * y * env


def harm_pluck(sr, freq, dur, vel=1.0, k_max=10, tilt=1.2, d0=1.5, dk=2.5,
               release=0.06, sustain=0.0):
    """Additive plucked tone: higher harmonics die faster (filter-envelope feel)."""
    n = int((dur + release) * sr)
    t = secs(n, sr)
    out = np.zeros(n)
    kmax = max(1, min(k_max, int(0.45 * sr / freq)))
    for k in range(1, kmax + 1):
        a = 1.0 / k ** tilt
        env = np.exp(-t * (d0 + dk * (k - 1)))
        if sustain and k <= 2:
            env = np.maximum(env, sustain / k)
        out += a * env * np.sin(TAU * k * freq * t)
    return vel * out * ar_env(n, sr, 0.003, dur, release) / 1.6


# ---------------------------------------------------------------- winds / brass

def flute(sr, freq, dur, vel=1.0, seed=0, vib=5.2, vib_depth=0.006, breath=0.05,
          attack=0.05, release=0.14, harm=(1.0, 0.28, 0.1, 0.04)):
    n = int((dur + release) * sr)
    t = secs(n, sr)
    r = rng(seed)
    depth = vib_depth * np.clip((t - 0.18) / 0.35, 0, 1)
    f = freq * (1 + depth * np.sin(TAU * vib * t + r.uniform(0, TAU)))
    f *= 1 - 0.012 * np.exp(-t / 0.03)  # tiny scoop into the note
    ph = TAU * phase_of(f, n, sr)
    tone = sum(h * np.sin((k + 1) * ph) for k, h in enumerate(harm) if (k + 1) * freq < 0.45 * sr)
    env = ar_env(n, sr, attack, dur, release) * (0.92 + 0.08 * np.exp(-t / 0.4))
    b = fft_filter(noise(n, r), sr, lambda fr: bp(fr, freq * 1.5, min(freq * 6, 0.45 * sr), 1))
    b /= max(np.std(b), 1e-9)
    benv = ar_env(n, sr, attack * 0.5, dur, release) * (0.5 + 1.5 * np.exp(-t / 0.05))
    return vel * (tone * env + breath * b * benv * 0.3)


def brass(sr, freq, dur, vel=1.0, seed=0, bright=1.0, attack=0.035, release=0.12,
          vib_depth=0.004):
    """Brass-ish: brightness rises with the attack ("blat") then settles."""
    n = int((dur + release) * sr)
    t = secs(n, sr)
    r = rng(seed)
    b = 0.25 + 0.75 * np.clip(t / (attack * 1.6), 0, 1)
    b *= 0.72 + 0.28 * np.exp(-np.maximum(t - attack, 0) / 0.25)
    b *= (0.65 + 0.35 * vel) * bright
    b = np.clip(b, 0.05, 1.0)
    depth = vib_depth * np.clip((t - 0.2) / 0.3, 0, 1)
    f = freq * (1 + depth * np.sin(TAU * 5.5 * t + r.uniform(0, TAU)))
    f *= 1 - 0.02 * np.exp(-t / 0.02)
    ph = TAU * phase_of(f, n, sr)
    out = np.zeros(n)
    kmax = max(1, min(14, int(0.42 * sr / freq)))
    for k in range(1, kmax + 1):
        out += (1.0 / k) * b ** (0.8 * (k - 1)) * np.sin(k * ph)
    env = ar_env(n, sr, attack, dur, release)
    return vel * out * env * 0.8


# ---------------------------------------------------------------- pads

def pad(sr, freqs, dur, vel=1.0, seed=0, attack=0.6, release=1.0, cutoff=2200.0,
        voices=3, detune=9.0, slope=2):
    n = int((dur + release) * sr)
    r = rng(seed)
    out = np.zeros(n)
    for f in freqs:
        tab = harmonic_table(saw_amps(f * 1.01, sr, cutoff, slope=slope))
        for v in range(voices):
            c = 0.0 if voices == 1 else (v / (voices - 1) - 0.5) * 2 * detune
            out += table_osc(tab, f * 2 ** (c / 1200), n, sr, r.uniform())
    out /= voices * max(1, len(freqs)) ** 0.5 * 2.2
    return vel * out * ar_env(n, sr, attack, dur, release)


VOWELS = {
    "ah": [(750, 130, 1.0), (1150, 150, 0.55), (2600, 220, 0.18)],
    "oo": [(330, 90, 1.0), (800, 120, 0.35), (2300, 200, 0.06)],
    "oh": [(480, 110, 1.0), (850, 130, 0.5), (2500, 220, 0.1)],
}


def choir(sr, freqs, dur, vel=1.0, seed=0, vowel="ah", attack=0.7, release=1.2,
          voices=3, detune=10.0):
    n = int((dur + release) * sr)
    t = secs(n, sr)
    r = rng(seed)
    out = np.zeros(n)
    for f in freqs:
        tab = harmonic_table(saw_amps(f * 1.02, sr, 3500))
        for v in range(voices):
            c = 0.0 if voices == 1 else (v / (voices - 1) - 0.5) * 2 * detune
            vib = 1 + 0.0035 * np.sin(TAU * (4.6 + 0.7 * v) * t + r.uniform(0, TAU))
            out += table_osc(tab, f * 2 ** (c / 1200) * vib, n, sr, r.uniform())
    out = fft_filter(out, sr, formant_resp(VOWELS[vowel]))
    out /= max(np.std(out), 1e-9) * 6.0
    return vel * out * ar_env(n, sr, attack, dur, release)


# ---------------------------------------------------------------- bells

def bell(sr, freq, dur=1.5, vel=1.0, seed=0, kind="celesta"):
    n = int(dur * sr)
    r = rng(seed)
    if kind == "glock":
        spec = [(1, 1.0, 1.4), (2.76, 0.35, 0.5), (5.4, 0.15, 0.25), (8.93, 0.07, 0.15)]
    elif kind == "chime":
        spec = [(1, 1.0, 1.6), (2.0, 0.5, 1.0), (3.0, 0.2, 0.6), (4.16, 0.15, 0.4), (5.43, 0.08, 0.25)]
    else:  # celesta: nearly harmonic, soft
        spec = [(1, 1.0, 1.2), (2.0, 0.3, 0.6), (3.0, 0.12, 0.35), (4.07, 0.05, 0.2)]
    out = np.zeros(n)
    for ratio, amp, t60 in spec:
        f = freq * ratio
        if f < 0.45 * sr:
            out += amp * np.sin(TAU * (f * np.arange(n) / sr + r.uniform())) * exp_decay(n, sr, t60)
    out *= ramp_in(n, sr, 0.002)
    out[-int(0.02 * sr):] *= np.linspace(1, 0, int(0.02 * sr))
    return vel * out * 0.6


# ---------------------------------------------------------------- drums

def _thump(sr, n, f_hi, f_lo, sweep, t60):
    t = secs(n, sr)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / sweep)
    return np.sin(TAU * phase_of(f, n, sr)) * exp_decay(n, sr, t60)


def kick(sr, vel=1.0, seed=0, t60=0.35):
    n = int(0.45 * sr)
    r = rng(seed)
    body = _thump(sr, n, 160, 52, 0.035, t60)
    click = fft_filter(noise(n, r), sr, lambda f: bp(f, 1500, 6000)) * exp_decay(n, sr, 0.012)
    x = saturate(body * 1.3, 1.8) + 0.25 * click
    return vel * x * ramp_in(n, sr, 0.001) * 0.9


def snare(sr, vel=1.0, seed=0, t60=0.2, tone=190.0):
    n = int(0.4 * sr)
    r = rng(seed)
    t = secs(n, sr)
    body = (np.sin(TAU * tone * t) + 0.5 * np.sin(TAU * tone * 1.74 * t)) * exp_decay(n, sr, 0.09)
    nz = fft_filter(noise(n, r), sr, lambda f: bp(f, 900, 7000, 1)) * exp_decay(n, sr, t60)
    nz /= max(np.max(np.abs(nz)), 1e-9)
    return vel * (0.45 * body + 0.8 * nz) * ramp_in(n, sr, 0.001) * 0.8


def hat(sr, vel=1.0, seed=0, t60=0.05):
    n = int(max(0.1, t60 * 1.3) * sr)
    r = rng(seed)
    nz = fft_filter(noise(n, r), sr, lambda f: hp(f, 6500, 2) * lp(f, 10500, 2))
    nz /= max(np.max(np.abs(nz)), 1e-9)
    return vel * nz * exp_decay(n, sr, t60) * ramp_in(n, sr, 0.0005) * 0.5


def shaker(sr, vel=1.0, seed=0):
    n = int(0.12 * sr)
    r = rng(seed)
    nz = fft_filter(noise(n, r), sr, lambda f: bp(f, 3500, 9000, 2))
    nz /= max(np.max(np.abs(nz)), 1e-9)
    env = ramp_in(n, sr, 0.018) * exp_decay(n, sr, 0.09, int(0.018 * sr))
    return vel * nz * env * 0.4


def tambourine(sr, vel=1.0, seed=0):
    n = int(0.3 * sr)
    r = rng(seed)
    t = secs(n, sr)
    nz = fft_filter(noise(n, r), sr, lambda f: bp(f, 5000, 10000, 2))
    nz /= max(np.max(np.abs(nz)), 1e-9)
    jingle = sum(np.sin(TAU * f * t + r.uniform(0, TAU)) for f in r.uniform(5500, 9500, 6)) / 6
    env = exp_decay(n, sr, 0.22) * (1 + 0.3 * np.sin(TAU * 32 * t))
    return vel * (0.6 * nz + 0.5 * jingle) * env * ramp_in(n, sr, 0.001) * 0.45


def frame_drum(sr, vel=1.0, seed=0, f0=115.0):
    n = int(0.4 * sr)
    r = rng(seed)
    body = _thump(sr, n, f0 * 1.35, f0, 0.02, 0.3) + 0.35 * _thump(sr, n, f0 * 2.3, f0 * 2.1, 0.02, 0.12)
    skin = fft_filter(noise(n, r), sr, lambda f: bp(f, 300, 2500, 1)) * exp_decay(n, sr, 0.04)
    skin /= max(np.max(np.abs(skin)), 1e-9)
    return vel * saturate(body + 0.25 * skin, 1.4) * ramp_in(n, sr, 0.001) * 0.8


def tom(sr, vel=1.0, seed=0, f0=140.0):
    n = int(0.45 * sr)
    r = rng(seed)
    body = _thump(sr, n, f0 * 1.5, f0, 0.04, 0.35)
    skin = fft_filter(noise(n, r), sr, lambda f: bp(f, 200, 3000, 1)) * exp_decay(n, sr, 0.05)
    skin /= max(np.max(np.abs(skin)), 1e-9)
    return vel * saturate(body * 1.2 + 0.2 * skin, 1.5) * ramp_in(n, sr, 0.001) * 0.8


def taiko(sr, vel=1.0, seed=0, f0=62.0):
    n = int(1.1 * sr)
    r = rng(seed)
    body = (_thump(sr, n, f0 * 1.6, f0, 0.05, 0.9)
            + 0.5 * _thump(sr, n, f0 * 1.6 * 1.59, f0 * 1.59, 0.05, 0.5)
            + 0.3 * _thump(sr, n, f0 * 1.6 * 2.14, f0 * 2.14, 0.05, 0.3))
    slap = fft_filter(noise(n, r), sr, lambda f: bp(f, 150, 1800, 1)) * exp_decay(n, sr, 0.06)
    slap /= max(np.max(np.abs(slap)), 1e-9)
    return vel * saturate(body * 0.9 + 0.35 * slap, 2.0) * ramp_in(n, sr, 0.001) * 0.85


def crash(sr, vel=1.0, seed=0, t60=1.6):
    n = int(t60 * 1.1 * sr)
    r = rng(seed)
    t = secs(n, sr)
    nz = fft_filter(noise(n, r), sr, lambda f: hp(f, 3000, 2) * lp(f, 10000, 1))
    nz /= max(np.max(np.abs(nz)), 1e-9)
    ring = sum(np.sin(TAU * f * t + r.uniform(0, TAU)) for f in r.uniform(3000, 8000, 10)) / 10
    x = (nz + 0.4 * ring) * exp_decay(n, sr, t60) * ramp_in(n, sr, 0.002)
    x[-int(0.05 * sr):] *= np.linspace(1, 0, int(0.05 * sr))
    return vel * x * 0.35


def drip(sr, vel=1.0, seed=0, f0=1100.0):
    """Water drop 'plip': a sine that bends upward very fast."""
    n = int(0.18 * sr)
    t = secs(n, sr)
    f = f0 * (1 + 1.1 * (1 - np.exp(-t / 0.014)))
    x = np.sin(TAU * phase_of(f, n, sr)) * exp_decay(n, sr, 0.07) * ramp_in(n, sr, 0.0015)
    return vel * x * 0.6
