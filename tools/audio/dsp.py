"""Small numpy DSP toolkit for the Valthera audio generator.

Everything here is deterministic: randomness always comes from a seeded
numpy Generator passed in by the caller.
"""
import math
import wave

import numpy as np

TAU = 2.0 * np.pi


# ---------------------------------------------------------------- basics

def rng(seed):
    return np.random.default_rng(seed)


def db(x):
    return 10.0 ** (x / 20.0)


def to_db(x):
    return 20.0 * math.log10(max(float(x), 1e-12))


def secs(n, sr):
    return np.arange(n) / sr


def nsamp(dur, sr):
    return max(1, int(round(dur * sr)))


_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    """'C4' -> 60, 'F#3', 'Bb5'."""
    name = name.strip()
    pc = _PC[name[0].upper()]
    i = 1
    while i < len(name) and name[i] in "#b":
        pc += 1 if name[i] == "#" else -1
        i += 1
    octave = int(name[i:])
    return 12 * (octave + 1) + pc


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def hz(name):
    return mtof(midi(name))


# ---------------------------------------------------------------- envelopes

def exp_decay(n, sr, t60, start=0):
    """Amplitude falling 60 dB over t60 seconds, flat before `start` samples."""
    t = np.maximum(np.arange(n) - start, 0) / sr
    return 10.0 ** (-3.0 * t / max(t60, 1e-4))


def ramp_in(n, sr, attack, curve="sine"):
    a = max(1, int(attack * sr))
    e = np.ones(n)
    k = min(a, n)
    x = np.arange(k) / a
    e[:k] = np.sin(0.5 * np.pi * x) ** 2 if curve == "sine" else x
    return e


def ar_env(n, sr, attack, hold, release):
    """Attack, hold until `hold` seconds, then cosine release over `release`."""
    e = ramp_in(n, sr, attack)
    hs = int(hold * sr)
    rs = max(1, int(release * sr))
    if hs < n:
        k = np.arange(n - hs)
        tail = np.where(k < rs, 0.5 * (1 + np.cos(np.pi * np.minimum(k, rs) / rs)), 0.0)
        e[hs:] *= tail
    return e


def fade(x, sr, fin=0.002, fout=0.02):
    y = x.copy()
    a = min(len(y), max(1, int(fin * sr)))
    b = min(len(y), max(1, int(fout * sr)))
    y[:a] *= np.sin(0.5 * np.pi * np.arange(a) / a) ** 2
    y[len(y) - b:] *= np.cos(0.5 * np.pi * np.arange(1, b + 1) / b) ** 2
    return y


def curve(n, points):
    """Piecewise-linear control curve. points = [(pos 0..1, value), ...]."""
    xs = np.array([p[0] for p in points], float)
    ys = np.array([p[1] for p in points], float)
    return np.interp(np.linspace(0, 1, n), xs, ys)


def expcurve(n, points):
    """Like curve() but interpolates in log space (good for frequencies)."""
    return np.exp(curve(n, [(p, math.log(v)) for p, v in points]))


# ---------------------------------------------------------------- oscillators

def phase_of(freq, n, sr, phase0=0.0):
    """Phase in cycles for a constant or per-sample frequency."""
    if np.ndim(freq) == 0:
        return phase0 + float(freq) * np.arange(n) / sr
    f = np.asarray(freq, float)[:n]
    return phase0 + np.concatenate(([0.0], np.cumsum(f)[:-1])) / sr


def sine(freq, n, sr, phase0=0.0):
    return np.sin(TAU * phase_of(freq, n, sr, phase0))


def harmonic_table(amps, size=4096, phases=None):
    k = np.arange(1, len(amps) + 1)
    x = np.arange(size) / size
    tab = np.zeros(size)
    for i, a in enumerate(amps):
        if a:
            ph = 0.0 if phases is None else phases[i]
            tab += a * np.sin(TAU * (k[i] * x + ph))
    return tab


def table_osc(tab, freq, n, sr, phase0=0.0):
    size = len(tab)
    ph = phase_of(freq, n, sr, phase0) % 1.0
    idx = ph * size
    i0 = idx.astype(np.int64) % size
    frac = idx - np.floor(idx)
    return tab[i0] * (1 - frac) + tab[(i0 + 1) % size] * frac


def saw_amps(fmax, sr, cutoff=None, limit=64, slope=2):
    kmax = max(1, min(limit, int(0.45 * sr / max(fmax, 1.0))))
    k = np.arange(1, kmax + 1)
    a = 1.0 / k
    if cutoff:
        a = a / np.sqrt(1 + (k * fmax / cutoff) ** (2 * slope))
    return a


def square_amps(fmax, sr, cutoff=None, limit=64):
    a = saw_amps(fmax, sr, cutoff, limit)
    a[1::2] = 0.0
    return a


def tri_amps(fmax, sr, limit=32):
    kmax = max(1, min(limit, int(0.45 * sr / max(fmax, 1.0))))
    k = np.arange(1, kmax + 1)
    a = np.where(k % 2 == 1, 1.0 / k ** 2, 0.0)
    a[2::4] *= -1
    return a


def partials(freq, n, sr, spec, phase_rand=None):
    """Additive inharmonic partials: spec = [(ratio, amp, t60), ...]."""
    out = np.zeros(n)
    for j, (ratio, amp, t60) in enumerate(spec):
        f = freq * ratio
        if f >= 0.47 * sr:
            continue
        ph = 0.0 if phase_rand is None else phase_rand.uniform()
        out += amp * np.sin(TAU * (f * np.arange(n) / sr + ph)) * exp_decay(n, sr, t60)
    return out


# ---------------------------------------------------------------- filters

def _f_axis(m, sr):
    f = np.fft.rfftfreq(m, 1.0 / sr)
    f[0] = 1e-3
    return f


def lp(f, fc, order=2):
    return 1.0 / np.sqrt(1 + (f / fc) ** (2 * order))


def hp(f, fc, order=2):
    return 1.0 / np.sqrt(1 + (fc / f) ** (2 * order))


def bp(f, lo, hi, order=2):
    return lp(f, hi, order) * hp(f, lo, order)


def peak(f, f0, gain_db, q=1.0):
    g = db(gain_db)
    bw = f0 / q
    return 1 + (g - 1) / (1 + ((f - f0) / bw) ** 2)


def shelf_hi(f, f0, gain_db):
    g = db(gain_db)
    w = f ** 2 / (f ** 2 + f0 ** 2)
    return 1 + (g - 1) * w


def shelf_lo(f, f0, gain_db):
    g = db(gain_db)
    w = f0 ** 2 / (f ** 2 + f0 ** 2)
    return 1 + (g - 1) * w


def fft_filter(x, sr, resp, circular=False, pad=0.25):
    """Zero-phase static filter. resp(f) -> magnitude array.

    circular=True treats x as one period of a loop (used for music)."""
    n = len(x)
    m = n if circular else n + int(pad * sr)
    X = np.fft.rfft(x, m)
    y = np.fft.irfft(X * resp(_f_axis(m, sr)), m)
    return y[:n]


def svf(x, sr, fc, q=0.707, mode="lp"):
    """Time-varying state variable filter (TPT form). fc: scalar or array."""
    n = len(x)
    fc = np.clip(np.broadcast_to(np.asarray(fc, float), (n,)), 10.0, sr * 0.45)
    g = np.tan(np.pi * fc / sr)
    k = 1.0 / q
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    xs = x.tolist()
    A1, A2, A3 = a1.tolist(), a2.tolist(), a3.tolist()
    out = [0.0] * n
    s1 = s2 = 0.0
    m = {"lp": 0, "bp": 1, "hp": 2}[mode]
    for i in range(n):
        v3 = xs[i] - s2
        v1 = A1[i] * s1 + A2[i] * v3
        v2 = s2 + A2[i] * s1 + A3[i] * v3
        s1 = 2 * v1 - s1
        s2 = 2 * v2 - s2
        if m == 0:
            out[i] = v2
        elif m == 1:
            out[i] = v1
        else:
            out[i] = xs[i] - k * v1 - v2
    return np.array(out)


def onepole_lp(x, sr, fc):
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, float), (n,))
    a = (1 - np.exp(-TAU * fc / sr)).tolist()
    xs = x.tolist()
    y = 0.0
    out = [0.0] * n
    for i in range(n):
        y += a[i] * (xs[i] - y)
        out[i] = y
    return np.array(out)


def noise(n, r):
    return r.standard_normal(n)


def band_noise(n, sr, r, lo, hi, order=2):
    return fft_filter(noise(n, r), sr, lambda f: bp(f, lo, hi, order))


def formant_resp(formants):
    """formants = [(freq, bandwidth, gain), ...] -> resp(f)."""
    def resp(f):
        h = np.full_like(f, 0.02)
        for fr, bw, g in formants:
            h = h + g / (1 + ((f - fr) / (bw / 2)) ** 2)
        return h
    return resp


# ---------------------------------------------------------------- effects

def reverb_ir(sr, t60, seed, predelay=0.012, bright=6000.0, length=None):
    r = rng(seed)
    n = int((length or t60 * 1.05) * sr)
    t = np.arange(n) / sr
    base = noise(n, r)
    lo = fft_filter(base, sr, lambda f: lp(f, 700, 2))
    hi = fft_filter(base, sr, lambda f: hp(f, 700, 2) * lp(f, bright, 1))
    ir = lo * 10 ** (-3 * t / t60) + hi * 10 ** (-3 * t / (t60 * 0.6))
    ir *= ramp_in(n, sr, 0.03)
    # a few early reflections
    for d, g in ((0.011, 0.5), (0.019, -0.35), (0.027, 0.3), (0.041, -0.2)):
        i = int(d * sr)
        if i < n:
            ir[i] += g * 6.0 / math.sqrt(sr * t60 / 10.0)
    ir /= math.sqrt(np.sum(ir ** 2))
    pd = int(predelay * sr)
    return np.concatenate((np.zeros(pd), ir))


def convolve(x, ir, circular=False):
    if circular:
        n = len(x)
        h = np.zeros(n)
        k = min(n, len(ir))
        h[:k] = ir[:k]
        return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(h), n)
    m = len(x) + len(ir)
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)


def echo_circular(x, sr, delay, feedback, damp=3000.0):
    """Infinite feedback delay line evaluated exactly on a loop (circular)."""
    n = len(x)
    f = _f_axis(n, sr)
    w = TAU * f * delay
    H = 1.0 / (1.0 - feedback * lp(f, damp, 1) * np.exp(-1j * w)) - 1.0
    return np.fft.irfft(np.fft.rfft(x) * H, n)


def saturate(x, drive=1.5):
    return np.tanh(drive * x) / np.tanh(drive)


# ---------------------------------------------------------------- loudness

def k_weight(x, sr, circular=False):
    return fft_filter(x, sr, lambda f: shelf_hi(f, 1500, 4.0) * hp(f, 38, 2),
                      circular=circular, pad=0.05)


def lufs_integrated(x, sr, circular=False):
    y = k_weight(x, sr, circular)
    blk, hop = int(0.4 * sr), int(0.1 * sr)
    if circular:
        y = np.concatenate((y, y[:blk]))
    ms = []
    for s in range(0, max(1, len(y) - blk + 1), hop):
        ms.append(np.mean(y[s:s + blk] ** 2))
    ms = np.array(ms) + 1e-20
    l = -0.691 + 10 * np.log10(ms)
    ms = ms[l > -70]
    rel = -0.691 + 10 * np.log10(np.mean(ms)) - 10
    ms = ms[(-0.691 + 10 * np.log10(ms)) > rel]
    return -0.691 + 10 * np.log10(np.mean(ms))


def lufs_max_short(x, sr, win=0.2, phone=False):
    """Max loudness over sliding `win` windows (short sounds count as padded).

    phone=True also high-passes at 180 Hz, roughly what a phone speaker can play."""
    y = k_weight(x, sr)
    if phone:
        y = fft_filter(y, sr, lambda f: hp(f, 180, 2), pad=0.05)
    w = int(win * sr)
    if len(y) < w:
        y = np.concatenate((y, np.zeros(w - len(y))))
    c = np.concatenate(([0.0], np.cumsum(y ** 2)))
    ms = (c[w:] - c[:-w]) / w
    return -0.691 + 10 * np.log10(np.max(ms) + 1e-20)


# ---------------------------------------------------------------- limiter

def limit(x, sr, ceiling_db=-1.0, circular=False, block=0.0015, radius=4):
    """Look-ahead block limiter that never lets |x| exceed the ceiling."""
    thr = db(ceiling_db)
    b = max(8, int(block * sr))
    n = len(x)
    nb = int(math.ceil(n / b))
    pad = np.zeros(nb * b)
    pad[:n] = np.abs(x)
    pk = pad.reshape(nb, b).max(axis=1)
    g = np.minimum(1.0, thr / np.maximum(pk, 1e-12))
    # min filter then equal-width moving average -> gain at a peak <= needed
    k = 2 * radius + 1
    if circular:
        ext = np.concatenate((g[-radius:], g, g[:radius]))
    else:
        ext = np.concatenate((np.ones(radius), g, np.ones(radius)))
    gm = np.min(np.lib.stride_tricks.sliding_window_view(ext, k), axis=1)
    if circular:
        ext = np.concatenate((gm[-radius:], gm, gm[:radius]))
    else:
        ext = np.concatenate((np.ones(radius), gm, np.ones(radius)))
    ga = np.convolve(ext, np.ones(k) / k, mode="valid")
    centers = (np.arange(nb) + 0.5) * b
    gs = np.interp(np.arange(n), centers, ga)
    y = x * gs
    # tiny safety for interpolation overshoot
    m = np.max(np.abs(y))
    if m > thr:
        y *= thr / m
    return y


def peak_db(x):
    return to_db(np.max(np.abs(x)))


# ---------------------------------------------------------------- io

def write_wav(path, x, sr):
    y = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(y.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        data = w.readframes(w.getnframes())
    assert sw == 2, "expected 16-bit"
    x = np.frombuffer(data, "<i2").astype(float) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr, ch, sw
