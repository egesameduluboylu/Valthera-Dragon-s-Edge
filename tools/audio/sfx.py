"""All sound effects. Each function takes a seeded Generator and returns mono float audio
at SR. generate.py then EQs, loudness-matches and limits them."""
import numpy as np

import instruments as ins
from dsp import (TAU, ar_env, bp, convolve, curve, exp_decay, expcurve, fft_filter, hp, hz,
                 lp, noise, partials, peak, phase_of, ramp_in, reverb_ir, saturate, secs,
                 sine, svf)

SR = 44100


# ---------------------------------------------------------------- building blocks

def N(dur):
    return int(dur * SR)


def place(buf, t, x, gain=1.0):
    i = int(t * SR)
    k = min(len(x), len(buf) - i)
    if k > 0:
        buf[i:i + k] += gain * x[:k]
    return buf


def room(x, t60=0.5, mix=0.25, seed=1, bright=7000):
    ir = reverb_ir(SR, t60, seed, predelay=0.006, bright=bright)
    wet = convolve(x, ir)[:len(x)]
    return x + mix * wet


def thump(dur, f_hi, f_lo, sweep, t60, drive=1.6):
    n = N(dur)
    t = secs(n, SR)
    f = f_lo + (f_hi - f_lo) * np.exp(-t / sweep)
    x = np.sin(TAU * phase_of(f, n, SR)) * exp_decay(n, SR, t60) * ramp_in(n, SR, 0.0008)
    return saturate(x * 1.2, drive)


def burst(r, dur, lo, hi, t60, attack=0.0008, order=2):
    n = N(dur)
    x = fft_filter(noise(n, r), SR, lambda f: bp(f, lo, hi, order))
    x /= max(np.max(np.abs(x)), 1e-9)
    return x * exp_decay(n, SR, t60) * ramp_in(n, SR, attack)


def whoosh(r, dur, f_pts, a_pts, q=1.2, mode="bp"):
    """Noise through a moving filter. f_pts/a_pts: [(0..1, value)]."""
    n = N(dur)
    fc = expcurve(n, f_pts)
    amp = curve(n, a_pts)
    x = svf(noise(n, r), SR, fc, q, mode)
    x /= max(np.max(np.abs(x)), 1e-9)
    return x * amp


def metal(r, dur, f0, spec, attack=0.0005):
    """spec: [(ratio, amp, t60)] inharmonic partials."""
    n = N(dur)
    return partials(f0, n, SR, spec, r) * ramp_in(n, SR, attack)


def clink(r, dur, f0):
    """One small gold coin: bright inharmonic ring + tick."""
    spec = [(1.0, 1.0, 0.35), (2.41, 0.6, 0.22), (3.87, 0.4, 0.15), (5.62, 0.25, 0.09),
            (1.012, 0.7, 0.3)]
    x = metal(r, dur, f0, spec)
    x += 0.5 * burst(r, dur, 3000, 12000, 0.008)
    return x


def sparkle(r, dur, count, t0, t1, fmin, fmax, rise=True, t60=0.12, amp=0.5):
    n = N(dur)
    out = np.zeros(n)
    times = np.sort(r.uniform(t0, t1, count))
    for j, tt in enumerate(times):
        if rise:
            frac = (tt - t0) / max(t1 - t0, 1e-6)
            f = fmin * (fmax / fmin) ** (0.7 * frac + 0.3 * r.uniform())
        else:
            f = r.uniform(fmin, fmax)
        m = N(min(0.25, dur - tt))
        if m <= 10:
            continue
        ping = (np.sin(TAU * f * secs(m, SR)) + 0.3 * np.sin(TAU * f * 2.01 * secs(m, SR)))
        ping *= exp_decay(m, SR, t60) * ramp_in(m, SR, 0.001)
        place(out, tt, ping, amp * r.uniform(0.5, 1.0))
    return out


def chime(dur, f, t60=0.8, amp=1.0, kind="chime"):
    x = ins.bell(SR, f, dur, amp, seed=int(f), kind=kind)
    return x


def bubble(dur, f0, rise=1.8, t60=0.06, tau=0.02):
    n = N(dur)
    t = secs(n, SR)
    f = f0 * (1 + (rise - 1) * (1 - np.exp(-t / tau)))
    return np.sin(TAU * phase_of(f, n, SR)) * exp_decay(n, SR, t60) * ramp_in(n, SR, 0.002)


def tone(dur, f, harm=(1.0,), vib=0.0, vib_rate=6.0):
    n = N(dur)
    t = secs(n, SR)
    fr = np.broadcast_to(np.asarray(f, float), (n,)) * (1 + vib * np.sin(TAU * vib_rate * t))
    ph = TAU * phase_of(fr, n, SR)
    return sum(a * np.sin((k + 1) * ph) for k, a in enumerate(harm))


def wood_tap(r, dur, f0=900, t60=0.05):
    spec = [(1.0, 1.0, t60), (1.83, 0.5, t60 * 0.7), (3.1, 0.3, t60 * 0.5)]
    x = metal(r, dur, f0, spec, attack=0.0008)
    x += 0.6 * burst(r, dur, 600, 4000, 0.012)
    return x


def arp(notes, step, note_dur, total, voice="bell", amp=1.0, kind="glock"):
    out = np.zeros(N(total))
    for i, name in enumerate(notes):
        f = hz(name)
        if voice == "bell":
            x = ins.bell(SR, f, note_dur, amp, seed=i, kind=kind)
        else:
            x = ins.brass(SR, f, note_dur * 0.8, amp, seed=i)
        place(out, i * step, x)
    return out


# ---------------------------------------------------------------- UI

def ui_click(r):
    x = wood_tap(r, 0.12, 1100, 0.045)
    return x


def ui_open(r):
    d = 0.34
    x = whoosh(r, d, [(0, 700), (0.7, 2600), (1, 3000)], [(0, 0), (0.55, 1), (0.85, 0.5), (1, 0)], q=0.9)
    place(x, 0.22, wood_tap(r, 0.12, 700, 0.05), 0.5)
    return x


def ui_close(r):
    d = 0.3
    x = whoosh(r, d, [(0, 2800), (0.7, 800), (1, 600)], [(0, 0), (0.3, 1), (0.7, 0.45), (1, 0)], q=0.9)
    place(x, 0.19, wood_tap(r, 0.11, 520, 0.05), 0.65)
    return x


# ---------------------------------------------------------------- economy

def coin(r):
    d = 0.5
    x = np.zeros(N(d))
    place(x, 0.0, clink(r, 0.45, 2350), 1.0)
    place(x, 0.055, clink(r, 0.4, 2710), 0.7)
    place(x, 0.11, clink(r, 0.35, 2520), 0.45)
    return room(x, 0.3, 0.15)


def buy(r):
    d = 0.9
    x = np.zeros(N(d))
    for t, f, g in ((0.0, 2350, 0.8), (0.04, 2710, 0.6), (0.085, 2520, 0.5), (0.12, 2890, 0.35)):
        place(x, t, clink(r, 0.4, f), g)
    # register "ka-ching": two bright bells
    place(x, 0.16, chime(0.7, hz("E6")), 0.7)
    place(x, 0.24, chime(0.65, hz("A6")), 0.8)
    return room(x, 0.5, 0.2)


def equip(r):
    d = 0.45
    x = np.zeros(N(d))
    # leather flap / creak
    place(x, 0.0, whoosh(r, 0.1, [(0, 500), (1, 1400)], [(0, 0), (0.3, 1), (1, 0)], q=1.5), 0.55)
    place(x, 0.0, thump(0.15, 260, 140, 0.02, 0.08), 0.45)
    # metal clank + clink
    spec = [(1.0, 1.0, 0.22), (1.47, 0.7, 0.15), (2.09, 0.5, 0.12), (2.83, 0.4, 0.08), (4.1, 0.2, 0.05)]
    place(x, 0.07, metal(r, 0.35, 620, spec), 0.8)
    place(x, 0.07, burst(r, 0.05, 1500, 8000, 0.015), 0.5)
    place(x, 0.15, metal(r, 0.28, 1340, spec), 0.35)
    return room(x, 0.35, 0.15)


def upgrade(r):
    d = 1.05
    x = np.zeros(N(d))
    anvil = [(1.0, 1.0, 0.7), (2.71, 0.7, 0.5), (3.9, 0.45, 0.4), (5.3, 0.3, 0.25), (1.005, 0.6, 0.6)]
    place(x, 0.0, metal(r, 0.9, 1080, anvil), 0.8)
    place(x, 0.0, thump(0.2, 220, 120, 0.015, 0.1), 0.7)
    place(x, 0.0, burst(r, 0.08, 1200, 9000, 0.02), 0.9)
    place(x, 0.12, sparkle(r, 0.85, 14, 0.0, 0.6, 2600, 6500, t60=0.18, amp=0.35))
    place(x, 0.3, chime(0.7, hz("E7"), kind="glock"), 0.25)
    return room(x, 0.6, 0.2)


def salvage(r):
    d = 0.85
    x = np.zeros(N(d))
    # crunch: dense cluster of short gritty grains
    for i in range(26):
        t = 0.3 * (i / 26) ** 1.3 + r.uniform(0, 0.012)
        g = burst(r, 0.03, r.uniform(500, 1200), r.uniform(2500, 6000), r.uniform(0.01, 0.03))
        place(x, t, g, r.uniform(0.35, 0.8) * (1 - 0.6 * i / 26))
    place(x, 0.0, thump(0.2, 180, 90, 0.02, 0.12), 0.6)
    place(x, 0.1, burst(r, 0.15, 200, 1200, 0.1), 0.5)
    for t, f, g in ((0.36, 2350, 0.7), (0.41, 2710, 0.55), (0.47, 2520, 0.45), (0.55, 2890, 0.3)):
        place(x, t, clink(r, 0.3, f), g)
    return room(x, 0.35, 0.12)


def level_up(r):
    d = 1.2
    x = np.zeros(N(d))
    notes = ["C5", "E5", "G5", "C6", "E6"]
    for i, name in enumerate(notes):
        f = hz(name)
        t = i * 0.075
        place(x, t, ins.brass(SR, f, 0.09, 0.55, seed=i, bright=0.8, attack=0.01, release=0.05), 0.6)
        place(x, t, ins.bell(SR, f * 2, 0.4, 0.5, seed=i, kind="glock"), 0.5)
    # held bright chord
    t0 = 0.4
    for i, name in enumerate(["C5", "E5", "G5", "C6"]):
        place(x, t0, ins.brass(SR, hz(name), 0.55, 0.5, seed=10 + i, bright=0.85, release=0.2), 0.45)
    place(x, t0, ins.bell(SR, hz("C7"), 0.8, 0.6, seed=20, kind="chime"), 0.4)
    place(x, 0.35, sparkle(r, 0.85, 16, 0.0, 0.6, 3000, 7000, t60=0.15, amp=0.25))
    x *= ar_env(len(x), SR, 0.001, 1.08, 0.12)
    return room(x, 0.9, 0.3)


def star(r):
    d = 0.6
    x = np.zeros(N(d))
    place(x, 0.0, ins.bell(SR, hz("E7"), 0.6, 1.0, seed=3, kind="glock"), 0.8)
    place(x, 0.0, ins.bell(SR, hz("E7") * 1.004, 0.6, 1.0, seed=4, kind="glock"), 0.4)
    place(x, 0.0, sparkle(r, 0.4, 6, 0.0, 0.12, 4500, 8000, t60=0.08, amp=0.3))
    place(x, 0.0, burst(r, 0.03, 5000, 14000, 0.01), 0.2)
    return room(x, 0.6, 0.25)


# ---------------------------------------------------------------- world

def creak(r, dur, f_pts, body=(380, 820, 1650, 2900), amp_pts=None, jitter=0.25):
    """Stick-slip friction: an irregular impulse train through wooden resonances."""
    n = N(dur)
    rate = expcurve(n, f_pts)
    imp = np.zeros(n)
    ph = 0.0
    for i in range(n):
        ph += rate[i] / SR * (1 + jitter * (r.random() - 0.5))
        if ph >= 1.0:
            ph -= 1.0
            imp[i] = 1.0 + 0.5 * r.random()
    y = np.zeros(n)
    for j, f in enumerate(body):
        y += svf(imp, SR, f, q=12 + 4 * j, mode="bp") / (1 + 0.4 * j)
    y /= max(np.max(np.abs(y)), 1e-9)
    if amp_pts:
        y *= curve(n, amp_pts)
    return y


def door_open(r):
    d = 1.2
    x = np.zeros(N(d))
    c = creak(r, 0.95, [(0, 18), (0.3, 55), (0.6, 95), (0.85, 60), (1, 30)],
              amp_pts=[(0, 0), (0.08, 0.7), (0.5, 1), (0.85, 0.8), (1, 0)])
    place(x, 0.05, c, 0.8)
    place(x, 0.0, thump(0.25, 240, 140, 0.02, 0.12), 0.45)  # latch release
    place(x, 0.0, burst(r, 0.05, 800, 5000, 0.02), 0.4)
    place(x, 0.1, whoosh(r, 1.0, [(0, 250), (1, 600)], [(0, 0), (0.4, 0.3), (1, 0)], q=0.7), 0.4)
    place(x, 0.95, thump(0.22, 200, 125, 0.02, 0.12), 0.5)  # settles
    place(x, 0.95, burst(r, 0.12, 250, 1600, 0.08), 0.3)
    return room(x, 0.7, 0.2, bright=4000)


def chest_open(r):
    d = 1.05
    x = np.zeros(N(d))
    c = creak(r, 0.28, [(0, 45), (0.5, 110), (1, 70)], body=(520, 1150, 2400),
              amp_pts=[(0, 0), (0.1, 0.8), (0.8, 1), (1, 0)])
    place(x, 0.0, c, 0.55)
    place(x, 0.27, thump(0.2, 200, 120, 0.02, 0.1), 0.8)
    place(x, 0.27, wood_tap(r, 0.12, 480, 0.06), 0.6)
    place(x, 0.33, arp(["E6", "G#6", "B6", "E7"], 0.06, 0.6, 0.72, amp=0.8), 0.45)
    place(x, 0.33, sparkle(r, 0.7, 14, 0.05, 0.5, 3000, 8000, t60=0.15, amp=0.3))
    return room(x, 0.6, 0.25)


# ---------------------------------------------------------------- support / items

def potion(r):
    d = 0.95
    x = np.zeros(N(d))
    for i, (t, f) in enumerate(((0.0, 260), (0.12, 300), (0.24, 280))):
        g = bubble(0.12, f, rise=2.2, t60=0.08, tau=0.03)
        g = saturate(g * 1.3, 1.3)
        place(x, t, g, 0.85)
        place(x, t, burst(r, 0.06, 300, 1500, 0.04), 0.15)
    for i in range(16):
        t = 0.38 + r.uniform(0, 0.45)
        place(x, t, bubble(0.08, r.uniform(700, 1800), rise=1.9, t60=0.05, tau=0.012), 0.35)
    place(x, 0.4, arp(["C6", "E6", "G6"], 0.07, 0.5, 0.55, amp=0.6), 0.3)
    return room(x, 0.5, 0.18)


def heal(r):
    d = 1.0
    n = N(d)
    t = secs(n, SR)
    x = np.zeros(n)
    for i, name in enumerate(["C5", "G5", "E6", "C7"]):
        f = hz(name)
        glide = f * (0.94 + 0.06 * np.clip(t / 0.4, 0, 1))
        trem = 0.8 + 0.2 * np.sin(TAU * (7 + i) * t)
        env = ar_env(n, SR, 0.15 + 0.1 * i, 0.55, 0.4)
        x += 0.35 * np.sin(TAU * phase_of(glide, n, SR)) * trem * env
    x += 0.6 * arp(["C6", "E6", "G6", "C7", "E7"], 0.1, 0.5, d, amp=0.5, kind="celesta")
    sh = fft_filter(noise(n, r), SR, lambda f: bp(f, 5000, 12000))
    sh /= np.max(np.abs(sh))
    x += 0.08 * sh * curve(n, [(0, 0), (0.4, 1), (1, 0)])
    return room(x, 0.9, 0.3)


def shield(r):
    d = 0.9
    n = N(d)
    t = secs(n, SR)
    x = np.zeros(n)
    # rising bubble "vwum"
    f = 180 + 260 * (1 - np.exp(-t / 0.12))
    env = ar_env(n, SR, 0.04, 0.3, 0.5)
    x += 0.6 * np.sin(TAU * phase_of(f, n, SR) + 2.0 * np.sin(TAU * phase_of(f * 2, n, SR))) * env
    # metallic shimmer: detuned pairs beating
    for base in (1190, 1760, 2630, 3480):
        for dt in (0, 5.5):
            x += 0.12 * np.sin(TAU * (base + dt) * t) * ar_env(n, SR, 0.08, 0.4, 0.45)
    x += 0.2 * whoosh(r, d, [(0, 1500), (0.5, 5000), (1, 3000)], [(0, 0), (0.25, 1), (1, 0)], q=2)
    return room(x, 0.6, 0.25)


# ---------------------------------------------------------------- combat

def hit(r):
    d = 0.3
    x = np.zeros(N(d))
    place(x, 0.0, thump(0.25, 260, 115, 0.015, 0.15, drive=3.0), 0.7)
    place(x, 0.0, thump(0.15, 520, 330, 0.01, 0.08, drive=2.0), 0.45)  # punch you can hear on a phone
    place(x, 0.0, burst(r, 0.2, 300, 2800, 0.09), 0.9)  # meaty smack
    place(x, 0.0, burst(r, 0.04, 1500, 7000, 0.012), 0.35)
    x = fft_filter(x, SR, lambda f: peak(f, 450, 4, 1.2))
    return saturate(x * 1.3, 1.6)


def crit(r):
    d = 0.65
    x = np.zeros(N(d))
    place(x, 0.0, thump(0.4, 280, 95, 0.03, 0.22, drive=3.0), 0.8)
    place(x, 0.0, thump(0.15, 560, 300, 0.012, 0.08, drive=2.0), 0.5)
    place(x, 0.0, burst(r, 0.2, 280, 3000, 0.09), 1.0)
    place(x, 0.0, burst(r, 0.06, 2000, 9000, 0.02), 0.45)
    ring = [(1.0, 1.0, 0.45), (2.32, 0.6, 0.35), (3.61, 0.35, 0.25), (1.003, 0.8, 0.4)]
    place(x, 0.005, metal(r, 0.6, 1260, ring), 0.35)
    place(x, 0.0, whoosh(r, 0.25, [(0, 5000), (1, 2500)], [(0, 1), (1, 0)], q=1.0), 0.25)
    x = fft_filter(x, SR, lambda f: peak(f, 420, 4, 1.2))
    return room(saturate(x * 1.3, 1.8), 0.4, 0.12)


def miss(r):
    return whoosh(r, 0.35, [(0, 700), (0.45, 3200), (1, 1300)],
                  [(0, 0), (0.4, 1), (0.6, 0.6), (1, 0)], q=1.4)


def combo(r):
    d = 0.85
    x = np.zeros(N(d))
    place(x, 0.0, hit(r) * 0.8)
    place(x, 0.06, arp(["E6", "G#6", "B6", "E7"], 0.055, 0.5, 0.65, amp=0.9), 0.55)
    place(x, 0.06, arp(["E5", "G#5", "B5", "E6"], 0.055, 0.3, 0.6, voice="brass", amp=0.6), 0.35)
    place(x, 0.2, sparkle(r, 0.6, 12, 0.0, 0.4, 3500, 8000, t60=0.12, amp=0.3))
    return room(x, 0.5, 0.2)


def slash(r):
    d = 0.38
    x = whoosh(r, d, [(0, 1200), (0.35, 5200), (1, 1800)], [(0, 0), (0.3, 1), (0.55, 0.5), (1, 0)], q=2.0)
    ring = [(1.0, 1.0, 0.25), (1.52, 0.6, 0.2), (2.23, 0.4, 0.12)]
    place(x, 0.08, metal(r, 0.28, 3150, ring, attack=0.01), 0.18)
    low = whoosh(r, d, [(0, 400), (0.35, 1200), (1, 500)], [(0, 0), (0.3, 1), (1, 0)], q=1.0)
    return x + 0.5 * low


def stab(r):
    d = 0.26
    x = whoosh(r, 0.12, [(0, 1800), (1, 5500)], [(0, 0), (0.6, 1), (1, 0)], q=2.0)
    x = np.concatenate((x, np.zeros(N(d) - len(x))))
    place(x, 0.09, thump(0.16, 320, 170, 0.01, 0.07, drive=2.0), 0.8)
    place(x, 0.09, burst(r, 0.06, 400, 3000, 0.03), 0.6)
    place(x, 0.09, metal(r, 0.12, 4200, [(1, 1, 0.06), (1.7, 0.5, 0.04)]), 0.15)
    return x


def magic_fire(r):
    d = 0.95
    n = N(d)
    x = whoosh(r, d, [(0, 250), (0.25, 2600), (0.6, 1200), (1, 500)],
               [(0, 0), (0.18, 1), (0.5, 0.7), (1, 0)], q=0.8, mode="lp")
    x += 0.5 * whoosh(r, d, [(0, 150), (0.3, 500), (1, 250)], [(0, 0), (0.2, 1), (1, 0)], q=1.5)
    # roar body with a little flutter
    t = secs(n, SR)
    x *= 1 + 0.25 * np.sin(TAU * 13 * t)
    place(x, 0.0, thump(0.35, 140, 70, 0.08, 0.3), 0.55)
    for i in range(22):  # crackles
        tt = r.uniform(0.1, 0.85)
        place(x, tt, burst(r, 0.01, 2000, 9000, 0.004), r.uniform(0.1, 0.35))
    return room(saturate(x, 1.4), 0.5, 0.15)


def magic_ice(r):
    d = 0.95
    x = np.zeros(N(d))
    place(x, 0.0, burst(r, 0.08, 2500, 12000, 0.03), 0.6)  # crack
    place(x, 0.0, thump(0.12, 400, 250, 0.01, 0.05), 0.3)
    for i in range(30):  # crystal pings, dense at first
        tt = 0.7 * r.random() ** 1.8
        f = r.uniform(2400, 7500)
        spec = [(1, 1, 0.12), (2.76, 0.4, 0.06)]
        place(x, tt, metal(r, 0.2, f, spec), r.uniform(0.15, 0.45))
    x += 0.35 * whoosh(r, d, [(0, 6000), (1, 1500)], [(0, 0.8), (0.3, 1), (1, 0)], q=3.0)
    for f in (2093, 2637, 3136):  # glassy shimmer
        n = N(d)
        x += 0.07 * np.sin(TAU * f * secs(n, SR)) * ar_env(n, SR, 0.05, 0.4, 0.45)
    return room(x, 0.8, 0.3, bright=9000)


def magic_lightning(r):
    d = 0.85
    n = N(d)
    t = secs(n, SR)
    x = np.zeros(n)
    # crackling electric noise with random gating
    nz = fft_filter(noise(n, r), SR, lambda f: bp(f, 700, 9000, 1))
    gate = np.repeat(r.random(n // 220 + 1) > 0.45, 220)[:n].astype(float)
    gate = fft_filter(gate, SR, lambda f: lp(f, 300))
    x += 0.5 * nz / np.max(np.abs(nz)) * gate * curve(n, [(0, 1), (0.5, 0.6), (1, 0)])
    # buzzy descending zap
    f = expcurve(n, [(0, 1800), (0.25, 400), (1, 90)])
    zap = np.sign(np.sin(TAU * phase_of(f, n, SR))) * 0.5 + 0.5 * np.sin(TAU * phase_of(f * 1.5, n, SR))
    zap = fft_filter(zap, SR, lambda fr: lp(fr, 4000, 2))
    x += 0.35 * zap * curve(n, [(0, 0), (0.02, 1), (0.4, 0.5), (1, 0)])
    place(x, 0.0, burst(r, 0.05, 2000, 14000, 0.015), 0.9)  # crack
    place(x, 0.02, thump(0.5, 110, 60, 0.05, 0.4), 0.5)  # thunder body
    place(x, 0.03, burst(r, 0.6, 100, 900, 0.45, attack=0.03), 0.4)
    return room(x, 0.7, 0.2)


def magic_shadow(r):
    d = 1.0
    n = N(d)
    t = secs(n, SR)
    x = whoosh(r, d, [(0, 300), (0.55, 900), (1, 250)], [(0, 0), (0.55, 1), (0.8, 0.5), (1, 0)], q=2.0)
    env = curve(n, [(0, 0), (0.5, 1), (0.8, 0.6), (1, 0)])
    for f0, g in ((147, 0.25), (155.5, 0.25), (233, 0.25), (277, 0.2)):
        f = f0 * (1.06 - 0.12 * t)
        x += g * np.sin(TAU * phase_of(f, n, SR) + 1.5 * np.sin(TAU * phase_of(f * 2, n, SR))) * env
    # whispery formant noise
    w = fft_filter(noise(n, r), SR, lambda f: 1.0 / (1 + ((f - 600) / 150) ** 2) + 0.6 / (1 + ((f - 1700) / 250) ** 2))
    x += 0.25 * w / np.max(np.abs(w)) * env
    return room(x, 1.0, 0.3, bright=3500)


def poison(r):
    d = 0.9
    n = N(d)
    x = np.zeros(n)
    hiss = fft_filter(noise(n, r), SR, lambda f: bp(f, 3000, 10000))
    x += 0.35 * hiss / np.max(np.abs(hiss)) * curve(n, [(0, 0), (0.1, 1), (0.6, 0.6), (1, 0)])
    for i in range(22):
        tt = r.uniform(0.0, 0.7)
        f = r.uniform(350, 1100)
        b = bubble(0.1, f, rise=1.7, t60=0.06, tau=0.015)
        b *= 1 + 0.3 * np.sin(TAU * 30 * secs(len(b), SR))
        place(x, tt, b, r.uniform(0.3, 0.7))
    # sickly wobble tone
    t = secs(n, SR)
    f = 330 * (1 + 0.03 * np.sin(TAU * 5 * t)) * (1 - 0.15 * t)
    x += 0.15 * np.sin(TAU * phase_of(f, n, SR)) * curve(n, [(0, 0), (0.2, 1), (1, 0)])
    return room(x, 0.5, 0.15)


def smoke(r):
    d = 0.7
    n = N(d)
    x = whoosh(r, d, [(0, 2500), (0.2, 1500), (1, 300)], [(0, 0), (0.03, 1), (0.3, 0.5), (1, 0)],
               q=0.6, mode="lp")
    place(x, 0.0, thump(0.25, 160, 90, 0.03, 0.15), 0.5)
    place(x, 0.0, burst(r, 0.05, 600, 4000, 0.03), 0.4)
    return room(x, 0.5, 0.2)


def enemy_attack(r):
    d = 0.6
    n = N(d)
    t = secs(n, SR)
    # rough growl: low buzzy tone with jittery pitch and amplitude roughness
    f = expcurve(n, [(0, 85), (0.3, 120), (1, 70)]) * (1 + 0.04 * fft_filter(noise(n, r), SR, lambda fr: lp(fr, 30)))
    ph = TAU * phase_of(f, n, SR)
    src = sum(np.sin(k * ph) / k for k in range(1, 30))
    src *= 1 + 0.5 * np.sin(TAU * 31 * t)
    src += 0.5 * noise(n, r)
    # "rrah" vowel formants
    y = fft_filter(src, SR, lambda fr: 1.0 / (1 + ((fr - 520) / 110) ** 2) + 0.7 / (1 + ((fr - 1050) / 160) ** 2)
                   + 0.2 / (1 + ((fr - 2400) / 300) ** 2) + 0.05 * lp(fr, 200))
    y /= np.max(np.abs(y))
    y *= curve(n, [(0, 0), (0.08, 1), (0.55, 0.8), (1, 0)])
    y = saturate(y * 1.5, 1.5)
    y += 0.4 * whoosh(r, d, [(0, 600), (0.5, 2000), (1, 800)], [(0, 0), (0.5, 1), (1, 0)], q=1.0)
    return room(y, 0.4, 0.12)


def enemy_death(r):
    d = 0.95
    n = N(d)
    x = smoke(r)[:n] * 0.8
    x = np.concatenate((x, np.zeros(n - len(x))))
    t = secs(n, SR)
    f = expcurve(n, [(0, 720), (1, 140)])
    tri = sum(((-1) ** k) * np.sin((2 * k + 1) * TAU * phase_of(f * (1 + 0.02 * np.sin(TAU * 9 * t)), n, SR))
              / (2 * k + 1) ** 2 for k in range(5))
    x += 0.55 * tri * ar_env(n, SR, 0.03, 0.6, 0.3)
    return room(x, 0.5, 0.2)


def player_hurt(r):
    d = 0.35
    x = np.zeros(N(d))
    place(x, 0.0, thump(0.3, 230, 105, 0.02, 0.12, drive=3.0), 0.75)
    place(x, 0.0, burst(r, 0.12, 250, 1600, 0.06), 0.8)
    bonk = tone(0.22, expcurve(N(0.22), [(0, 330), (1, 210)]), harm=(1.0, 0.3, 0.15))
    bonk *= exp_decay(len(bonk), SR, 0.18) * ramp_in(len(bonk), SR, 0.002)
    place(x, 0.01, bonk, 0.7)
    x = fft_filter(x, SR, lambda f: peak(f, 380, 4, 1.0) * lp(f, 5000, 1))
    return saturate(x * 1.2, 1.5)


def boss_phase(r):
    d = 1.2
    n = N(d)
    t = secs(n, SR)
    x = np.zeros(n)
    place(x, 0.0, thump(1.0, 140, 55, 0.08, 0.8, drive=3.0), 0.8)
    place(x, 0.0, thump(0.3, 330, 180, 0.03, 0.2, drive=2.0), 0.45)
    place(x, 0.0, burst(r, 0.3, 150, 2000, 0.3, attack=0.002), 0.8)
    rumble = fft_filter(noise(n, r), SR, lambda f: bp(f, 50, 400, 2))
    rumble /= np.max(np.abs(rumble))
    x += 0.45 * rumble * curve(n, [(0, 0), (0.08, 1), (0.7, 0.7), (1, 0)]) * (1 + 0.3 * np.sin(TAU * 11 * t))
    # ominous chord: D minor with the flat second on top (D, F, A, Eb)
    for i, name in enumerate(["D3", "F3", "A3", "Eb4", "D4"]):
        place(x, 0.12, ins.choir(SR, [hz(name)], 0.7, 0.6, seed=70 + i, vowel="ah", attack=0.12,
                                  release=0.35)[:N(1.08)], 0.55)
        place(x, 0.12, ins.brass(SR, hz(name), 0.7, 0.5, seed=80 + i, bright=0.5, attack=0.08,
                                  release=0.3)[:N(1.08)], 0.4)
    x = fft_filter(x, SR, lambda f: peak(f, 280, 4, 1.0))
    x *= ar_env(n, SR, 0.001, 1.05, 0.15)
    return room(saturate(x, 1.3), 1.2, 0.3, bright=4000)


def victory(r):
    d = 1.5
    x = np.zeros(N(d))
    # triplet pickup then long chord: G4 G4 G4 | C5 ... E5 G5
    seq = [("G4", 0.0, 0.1), ("G4", 0.11, 0.1), ("G4", 0.22, 0.1), ("C5", 0.33, 0.3),
           ("E5", 0.66, 0.14), ("G5", 0.82, 0.55)]
    for i, (name, t, dur) in enumerate(seq):
        place(x, t, ins.brass(SR, hz(name), dur, 0.9, seed=i, bright=0.95, attack=0.02, release=0.12), 0.7)
    for i, name in enumerate(["C4", "E4", "G4", "C5"]):
        place(x, 0.82, ins.brass(SR, hz(name), 0.55, 0.7, seed=20 + i, bright=0.7, attack=0.03,
                                  release=0.12), 0.35)
    place(x, 0.33, thump(0.4, 140, 98, 0.03, 0.35), 0.35)   # timpani-ish
    place(x, 0.82, thump(0.5, 140, 98, 0.03, 0.45), 0.45)
    place(x, 0.82, ins.crash(SR, 0.8, seed=5, t60=0.8)[:N(0.66)], 0.6)
    place(x, 0.85, sparkle(r, 0.6, 12, 0.0, 0.45, 3000, 8000, t60=0.12, amp=0.25))
    x *= ar_env(len(x), SR, 0.001, 1.38, 0.12)
    return room(x, 1.0, 0.25)


def defeat(r):
    d = 1.5
    x = np.zeros(N(d))
    seq = [("G4", 0.0, 0.28), ("F#4", 0.3, 0.28), ("F4", 0.6, 0.28), ("E4", 0.9, 0.5)]
    for i, (name, t, dur) in enumerate(seq):
        v = ins.brass(SR, hz(name), dur, 0.7, seed=i, bright=0.45, attack=0.05, release=0.12,
                      vib_depth=0.01 if i == 3 else 0.004)
        place(x, t, v, 0.7)
        place(x, t, ins.flute(SR, hz(name) * 2, dur, 0.4, seed=10 + i, release=0.12), 0.25)
    # soft minor pad underneath: C minor
    place(x, 0.0, ins.pad(SR, [hz("C3"), hz("Eb3"), hz("G3")], 1.2, 0.8, seed=30, attack=0.3,
                          release=0.25, cutoff=1200), 0.45)
    x *= ar_env(len(x), SR, 0.001, 1.38, 0.12)
    return room(x, 0.9, 0.25, bright=4000)


def summon(r):
    d = 1.2
    n = N(d)
    t = secs(n, SR)
    x = np.zeros(n)
    env = curve(n, [(0, 0), (0.8, 1), (0.9, 0.7), (1, 0)])
    for f0, g in ((196, 0.3), (207.6, 0.25), (277, 0.2), (293.7, 0.15), (392, 0.1)):
        f = f0 * 2 ** (1.4 * t / d)
        x += g * np.sin(TAU * phase_of(f, n, SR) + 0.8 * np.sin(TAU * phase_of(f * 3.01, n, SR))) * env
    x += 0.35 * whoosh(r, d, [(0, 300), (0.85, 4000), (1, 2500)], [(0, 0), (0.85, 1), (1, 0)], q=2.5)
    place(x, 0.95, ins.bell(SR, hz("A6"), 0.25, 0.8, seed=9, kind="glock"), 0.35)
    place(x, 0.95, burst(r, 0.2, 3000, 10000, 0.1), 0.25)
    x *= ar_env(n, SR, 0.001, 1.1, 0.1)
    return room(x, 0.9, 0.3)


def stun(r):
    d = 0.95
    x = np.zeros(N(d))
    for i, t in enumerate((0.0, 0.16, 0.42, 0.58)):
        m = N(0.12)
        tt = secs(m, SR)
        base = 2600 if i % 2 == 0 else 3000
        f = base * (1 + 0.45 * np.clip(tt / 0.06, 0, 1)) * (1 + 0.03 * np.sin(TAU * 40 * tt))
        tw = np.sin(TAU * phase_of(f, m, SR)) * ar_env(m, SR, 0.005, 0.07, 0.04)
        place(x, t, tw, 0.6)
    # little wobbly "dizzy" slide underneath
    n = N(d)
    t = secs(n, SR)
    f = 900 * (1 + 0.12 * np.sin(TAU * 3.5 * t))
    x += 0.12 * np.sin(TAU * phase_of(f, n, SR)) * ar_env(n, SR, 0.05, 0.75, 0.2)
    return room(x, 0.4, 0.15)


def status_bad(r):
    d = 0.8
    n = N(d)
    t = secs(n, SR)
    f = expcurve(n, [(0, 330), (1, 150)]) * (1 + 0.06 * np.sin(TAU * 7 * t))
    ph = TAU * phase_of(f, n, SR)
    x = sum(np.sin((2 * k + 1) * ph) / (2 * k + 1) for k in range(6))
    x = fft_filter(x, SR, lambda fr: lp(fr, 1800, 2))
    x += 0.5 * np.sin(TAU * phase_of(f * 0.5 * 1.01, n, SR))
    x *= ar_env(n, SR, 0.02, 0.6, 0.2)
    x += 0.15 * whoosh(r, d, [(0, 1200), (1, 300)], [(0, 1), (1, 0)], q=1.0)
    return room(x, 0.5, 0.15, bright=3500)


# name -> (function, seed, loudness trim dB)
SFX = {
    "ui_click": (ui_click, 1, -6), "ui_open": (ui_open, 2, -5), "ui_close": (ui_close, 3, -5),
    "coin": (coin, 4, -3), "buy": (buy, 5, -2), "equip": (equip, 6, -2), "upgrade": (upgrade, 7, 0),
    "salvage": (salvage, 8, -1), "level_up": (level_up, 9, 0), "star": (star, 10, -3),
    "door_open": (door_open, 11, -1), "chest_open": (chest_open, 12, -1), "potion": (potion, 13, -1),
    "heal": (heal, 14, -2), "shield": (shield, 15, -1), "hit": (hit, 16, 0), "crit": (crit, 17, 1),
    "miss": (miss, 18, -2), "combo": (combo, 19, 0), "slash": (slash, 20, -1), "magic_fire": (magic_fire, 21, 0),
    "magic_ice": (magic_ice, 22, 0), "magic_lightning": (magic_lightning, 23, 0),
    "magic_shadow": (magic_shadow, 24, 0), "poison": (poison, 25, -1), "stab": (stab, 26, -1),
    "smoke": (smoke, 27, -1), "enemy_attack": (enemy_attack, 28, 0), "enemy_death": (enemy_death, 29, -1),
    "player_hurt": (player_hurt, 30, 0), "boss_phase": (boss_phase, 31, 1), "victory": (victory, 32, 0),
    "defeat": (defeat, 33, -1), "summon": (summon, 34, 0), "stun": (stun, 35, -2),
    "status_bad": (status_bad, 36, -1),
}
