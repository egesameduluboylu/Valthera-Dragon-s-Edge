"""Loop-based music renderer + the five game tracks.

Every note is added into a circular buffer exactly one loop long, so tails
(release, echo, reverb) wrap back to the start and the loop is seamless by
construction. All effects on the mix are circular too.
"""
import numpy as np

import instruments as ins
from dsp import (convolve, db, echo_circular, fft_filter, hp, limit, lp, lufs_integrated,
                 midi, mtof, peak, reverb_ir, rng, shelf_hi, shelf_lo)

SR = 22050
TARGET_LUFS = -16.0
CEILING_DB = -1.5

# ---------------------------------------------------------------- theory helpers

QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10),
        "maj7": (0, 4, 7, 11), "sus4": (0, 5, 7), "dim": (0, 3, 6)}
PCS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def parse_chord(sym):
    pc = PCS[sym[0]]
    i = 1
    if i < len(sym) and sym[i] in "#b":
        pc += 1 if sym[i] == "#" else -1
        i += 1
    return pc % 12, QUAL[sym[i:]]


def place(pc, lo):
    """Lowest midi note with pitch class pc that is >= lo."""
    return lo + (pc - lo) % 12


def chord_notes(sym, lo):
    root, iv = parse_chord(sym)
    return sorted(place((root + i) % 12, lo) for i in iv)


def arp_tones(sym, lo):
    """root, fifth, octave, tenth, 12th, 15th starting from a root >= lo."""
    root, iv = parse_chord(sym)
    r = place(root, lo)
    third, fifth = iv[1], iv[2]
    return [r, r + fifth, r + 12, r + 12 + third, r + 12 + fifth, r + 24]


def parse_chords(text, beats_per_bar):
    """'G C Am-D | ...' -> [(beat, beats, sym)]; '-' splits a bar evenly."""
    out = []
    beat = 0.0
    for bar in text.replace("|", " ").split():
        parts = bar.split("-")
        each = beats_per_bar / len(parts)
        for p in parts:
            out.append((beat, each, p))
            beat += each
    return out


def parse_melody(text, beats_per_bar):
    """'B4:1 D5:1 r:2 | ...' -> [(beat, beats, midi)]; checks every bar's length."""
    out = []
    beat = 0.0
    for bi, bar in enumerate(text.split("|")):
        total = 0.0
        for tok in bar.split():
            name, length = tok.split(":")
            length = float(length)
            if name != "r":
                out.append((beat, length, midi(name)))
            beat += length
            total += length
        assert abs(total - beats_per_bar) < 1e-6, f"bar {bi + 1} has {total} beats: {bar}"
    return out


# ---------------------------------------------------------------- song buffer

class Song:
    def __init__(self, name, bpm, bpb, bars, seed):
        self.name = name
        self.bpm = bpm
        self.bpb = bpb
        self.bars = bars
        self.spb = 60.0 / bpm
        self.beats = bars * bpb
        self.L = int(round(self.beats * self.spb * SR))
        self.buses = {}
        self.r = rng(seed)
        self.seed = seed
        self._n = 0

    def sec(self, beats):
        return beats * self.spb

    def nseed(self):
        self._n += 1
        return self.seed * 1000 + self._n

    def add(self, bus, beat, audio, jitter=0.004):
        buf = self.buses.setdefault(bus, np.zeros(self.L))
        pos = int(round((beat * self.spb + self.r.uniform(-jitter, jitter)) * SR)) % self.L
        a = audio
        while len(a):
            k = min(len(a), self.L - pos)
            buf[pos:pos + k] += a[:k]
            a = a[k:]
            pos = 0

    def mix(self, spec, reverb_t60, reverb_seed, master_eq=None):
        """spec: bus -> dict(level dB, send (0..1), eq resp fn, echo (delay_beats, fb)).

        `level` is the bus's active level relative to the others (0 = the lead)."""
        dry = np.zeros(self.L)
        wet_in = np.zeros(self.L)
        for bus, buf in self.buses.items():
            s = spec[bus]
            x = buf
            if "eq" in s:
                x = fft_filter(x, SR, s["eq"], circular=True)
            x = x * db(s.get("level", 0.0) - active_db(x))
            if "echo" in s:
                d, fb = s["echo"]
                x = x + 0.55 * echo_circular(x, SR, self.sec(d), fb, 2800)
            dry += x
            wet_in += x * s.get("send", 0.2)
        ir = reverb_ir(SR, reverb_t60, reverb_seed, predelay=0.02, bright=5000)
        wet = convolve(wet_in, ir, circular=True)
        out = dry + wet
        eq = master_eq or (lambda f: hp(f, 45, 2))
        out = fft_filter(out, SR, eq, circular=True)
        return master(out)


def active_db(x, block=0.2):
    """RMS level of the blocks where the part is actually playing (within 30 dB of its peak block)."""
    b = int(block * SR)
    nb = len(x) // b
    ms = np.mean(x[:nb * b].reshape(nb, b) ** 2, axis=1)
    ms = ms[ms > ms.max() * 1e-3]
    return 10 * np.log10(np.mean(ms) + 1e-20)


def master(x):
    x = x - np.mean(x)
    for _ in range(3):
        g = TARGET_LUFS - lufs_integrated(x, SR, circular=True)
        x = x * db(g)
        x = limit(x, SR, CEILING_DB, circular=True)
    return x


# ---------------------------------------------------------------- shared parts

def play_melody(song, bus, mel, voice, legato=0.92, octave=0, vel=0.8, **kw):
    for beat, length, m in parse_melody(mel, song.bpb):
        dur = song.sec(length) * legato
        f = mtof(m + 12 * octave)
        # accent the downbeats a little
        v = vel * (1.0 if beat % song.bpb == 0 else 0.9)
        song.add(bus, beat, voice(SR, f, dur, v, seed=song.nseed(), **kw))


def play_pad(song, bus, chords, lo, vel=0.4, kind="pad", **kw):
    for beat, length, sym in chords:
        fs = [mtof(m) for m in chord_notes(sym, lo)]
        dur = song.sec(length)
        if kind == "pad":
            a = ins.pad(SR, fs, dur, vel, seed=song.nseed(), **kw)
        else:
            a = ins.choir(SR, fs, dur, vel, seed=song.nseed(), **kw)
        song.add(bus, beat, a, jitter=0)


def perc_bank(fn, count, seed, **kw):
    return [fn(SR, 1.0, seed=seed + i, **kw) for i in range(count)]


def hit(song, bus, beat, bank, vel, idx=None):
    b = bank[song.r.integers(len(bank))] if idx is None else bank[idx % len(bank)]
    song.add(bus, beat, b * vel, jitter=0.003)


# ================================================================= TOWN

def town():
    s = Song("town", 96, 4, 16, seed=11)
    chords = parse_chords("G C D G | Em C Am-D G | C G Am Em | C G Am D", 4)
    mel = ("B4:1 D5:1 G5:1.5 F#5:.5 | E5:1 G5:1 E5:1 C5:1 | D5:1.5 E5:.5 F#5:1 A5:1 | G5:2 D5:1 B4:1 |"
           "E5:1 G5:1 B5:1.5 A5:.5 | G5:1 E5:1 C5:1 E5:1 | E5:1 C5:1 D5:1 F#5:1 | G5:3 r:1 |"
           "E5:1.5 F#5:.5 G5:1 E5:1 | D5:1 B4:1 D5:1 G5:1 | C6:1.5 B5:.5 A5:1 E5:1 | G5:1.5 F#5:.5 E5:2 |"
           "E5:1 G5:1 C6:1 B5:1 | A5:1 G5:1 D5:1 B4:1 | C5:1 E5:1 A5:1 G5:1 | F#5:1.5 E5:.5 D5:1 A4:1")
    play_melody(s, "flute", mel, ins.flute, legato=0.9, vel=0.8, breath=0.06)

    # lute: finger-picked eighth-note arpeggios
    pat_a = [0, 2, 3, 2, 1, 2, 3, 2]
    pat_b = [0, 2, 3, 4, 1, 3, 2, 3]
    for beat, length, sym in chords:
        tones = arp_tones(sym, 43 + 5)  # root from C3 upward
        steps = int(length * 2)
        pat = pat_a if beat < 32 else pat_b
        for i in range(steps):
            b = beat + i * 0.5
            m = tones[pat[(int(b * 2)) % 8]]
            v = 0.55 if i % 4 == 0 else 0.4
            s.add("lute", b, ins.ks_pluck(SR, mtof(m), s.sec(0.9), v, t60=1.1, bright=0.55,
                                          seed=s.nseed(), release=0.1, pick=0.18))
    # soft plucked bass on 1 and 3
    for beat, length, sym in chords:
        root, iv = parse_chord(sym)
        r = place(root, 40)
        s.add("bass", beat, ins.harm_pluck(SR, mtof(r), s.sec(min(length, 2) * 0.9), 0.8,
                                           k_max=6, tilt=1.4, d0=1.2, dk=2.0, sustain=0.25))
        if length >= 4:
            s.add("bass", beat + 2, ins.harm_pluck(SR, mtof(r + iv[2]), s.sec(1.8), 0.65,
                                                   k_max=6, tilt=1.4, d0=1.2, dk=2.0, sustain=0.25))
    # warm pad, fuller in the second half
    for beat, length, sym in chords:
        v = 0.22 if beat < 32 else 0.34
        play_pad(s, "pad", [(beat, length, sym)], 55, vel=v, attack=0.5, release=0.9,
                 cutoff=1600)
    # percussion: frame drum, tambourine on 2 & 4, soft shaker eighths
    fd = perc_bank(ins.frame_drum, 3, 500)
    tb = perc_bank(ins.tambourine, 3, 510)
    sh = perc_bank(ins.shaker, 4, 520)
    for bar in range(16):
        b0 = bar * 4
        hit(s, "perc", b0, fd, 0.8)
        hit(s, "perc", b0 + 2, fd, 0.55)
        if bar % 2 == 1:
            hit(s, "perc", b0 + 3.5, fd, 0.35)
        hit(s, "perc", b0 + 1, tb, 0.45)
        hit(s, "perc", b0 + 3, tb, 0.45)
        for i in range(8):
            hit(s, "perc", b0 + i * 0.5, sh, 0.35 if i % 2 else 0.2)
    # a little glockenspiel sparkle at phrase ends
    for beat, m in ((28, "B6"), (29, "D7"), (60, "A6"), (61, "F#6")):
        s.add("bell", beat, ins.bell(SR, mtof(midi(m)), 1.2, 0.35, seed=s.nseed(), kind="glock"))

    spec = {
        "flute": dict(level=0, send=0.25),
        "lute": dict(level=-9, send=0.2, eq=lambda f: peak(f, 2500, 2, 1) * hp(f, 120)),
        "bass": dict(level=-9, send=0.08),
        "pad": dict(level=-14, send=0.35, eq=lambda f: hp(f, 150)),
        "perc": dict(level=-13, send=0.15),
        "bell": dict(level=-14, send=0.4),
    }
    return s, s.mix(spec, 1.6, 101)


# ================================================================= DUNGEON

def dungeon():
    s = Song("dungeon", 80, 4, 12, seed=22)
    chords = parse_chords("Dm Bb Gm A | Dm Bb Gm A | Dm C Bb A", 4)
    # low drone D + A, long overlapping notes (wrap around seamlessly)
    for k in range(3):
        s.add("drone", k * 16, ins.pad(SR, [mtof(midi("D2")), mtof(midi("A2")), mtof(midi("D3"))],
                                       s.sec(16), 0.9, seed=s.nseed(), attack=3.0, release=4.0,
                                       cutoff=500, voices=3, detune=6), jitter=0)
    # sparse harp plucks with echo
    shapes = [[(0, 2), (1.5, 4), (3, 3)], [(0, 2), (1, 3), (2.5, 4)], [(0, 1), (2, 4), (3.5, 3)]]
    for i, (beat, length, sym) in enumerate(chords):
        tones = arp_tones(sym, 50)
        for off, idx in shapes[i % 3]:
            s.add("harp", beat + off, ins.ks_pluck(SR, mtof(tones[idx]), s.sec(2.5), 0.5, t60=2.2,
                                                   bright=0.4, seed=s.nseed(), release=0.3))
        # low bass pluck on the downbeat
        s.add("harp", beat, ins.ks_pluck(SR, mtof(tones[0] - 12), s.sec(3.5), 0.55, t60=3.0,
                                         bright=0.3, seed=s.nseed(), release=0.3))
    mel = ("r:4 | r:4 | r:4 | r:4 |"
           "A4:2 D5:1 F5:1 | E5:3 D5:1 | D5:2 Bb4:1 G4:1 | C#5:2 A4:2 |"
           "F5:2 E5:1 D5:1 | E5:2 G5:1 E5:1 | D5:3 C5:.5 Bb4:.5 | A4:4")
    play_melody(s, "flute", mel, ins.flute, legato=0.95, vel=0.6, vib=4.5, vib_depth=0.005,
                breath=0.12, attack=0.09, release=0.3)
    # choir "oo" behind the melody
    play_pad(s, "choir", chords[4:], 57, vel=0.5, kind="choir", vowel="oo", attack=1.2,
             release=1.5)
    # water drips at irregular (but fixed) spots
    dr = rng(2222)
    for bar in range(12):
        for _ in range(1 + int(dr.integers(0, 2))):
            b = bar * 4 + int(dr.integers(0, 16)) * 0.25
            f0 = float(dr.choice([880, 1046, 1174, 1318, 1568]))
            s.add("drip", b, ins.drip(SR, float(dr.uniform(0.5, 0.9)), f0=f0))
    # distant heartbeat drum
    tb = perc_bank(ins.taiko, 2, 600, f0=55)
    for bar in range(0, 12, 2):
        hit(s, "boom", bar * 4, tb, 0.6)
        hit(s, "boom", bar * 4 + 0.75, tb, 0.35)

    spec = {
        "drone": dict(level=-9, send=0.2, eq=lambda f: hp(f, 60) * peak(f, 220, 3, 1)),
        "harp": dict(level=-5, send=0.45, echo=(0.75, 0.38), eq=lambda f: hp(f, 90)),
        "flute": dict(level=-3, send=0.45),
        "choir": dict(level=-12, send=0.5),
        "drip": dict(level=-13, send=0.8),
        "boom": dict(level=-11, send=0.35, eq=lambda f: lp(f, 900) * hp(f, 45)),
    }
    return s, s.mix(spec, 3.4, 202)


# ================================================================= BATTLE

def _drum_kit(seed, taiko_f0=None):
    k = dict(
        kick=perc_bank(ins.kick, 3, seed),
        snare=perc_bank(ins.snare, 4, seed + 10),
        hat=perc_bank(ins.hat, 4, seed + 20),
        ohat=perc_bank(ins.hat, 2, seed + 30, t60=0.25),
        tom_hi=perc_bank(ins.tom, 2, seed + 40, f0=180),
        tom_lo=perc_bank(ins.tom, 2, seed + 50, f0=120),
        crash=perc_bank(ins.crash, 1, seed + 60),
    )
    if taiko_f0:
        k["taiko"] = perc_bank(ins.taiko, 3, seed + 70, f0=taiko_f0)
    return k


def battle():
    s = Song("battle", 132, 4, 24, seed=33)
    chords = parse_chords("Am F G Am | Am F G E | Dm Am F E | Dm Am F-G E | F G Em Am | F G E E", 4)
    mel = ("E5:1.5 A5:.5 B5:1 C6:1 | C6:1.5 B5:.5 A5:1 F5:1 | G5:1.5 A5:.5 B5:1 D6:1 | C6:1.5 B5:.5 A5:2 |"
           "E5:1.5 A5:.5 B5:1 C6:1 | D6:1.5 C6:.5 A5:1 F5:1 | G5:1 B5:1 D6:1 B5:1 | G#5:2 B5:2 |"
           "F5:1 E5:1 D5:1 A5:1 | C6:2 B5:1 A5:1 | A5:1 G5:1 F5:1 C5:1 | E5:2 G#5:1 B5:1 |"
           "D6:1 C6:1 A5:1 F5:1 | E5:1.5 A5:.5 C6:2 | C6:1 A5:1 B5:1 D6:1 | E6:2 D6:.5 C6:.5 B5:1 |"
           "r:4 | r:4 | r:4 | r:4 |"
           "A5:4 | B5:4 | G#5:2 B5:2 | E6:2 D6:1 B5:1")
    play_melody(s, "lead", mel, ins.brass, legato=0.88, octave=-1, vel=0.85)
    play_melody(s, "lead2", mel, ins.flute, legato=0.85, vel=0.5, breath=0.03)
    counter = "r:4 | " * 16 + "A4:2 C5:2 | B4:2 D5:2 | B4:2 G4:2 | A4:4 | " + "r:4 | r:4 | r:4 | r:4"
    play_melody(s, "lead", counter, ins.brass, legato=0.95, vel=0.6, bright=0.6, attack=0.08)

    # driving eighth-note bass
    bass_pat = [0, 0, 12, 0, 0, 0, 12, 7]
    for beat, length, sym in chords:
        root, iv = parse_chord(sym)
        r = place(root, 33)
        for i in range(int(length * 2)):
            b = beat + i * 0.5
            m = r + bass_pat[int(b * 2) % 8]
            v = 0.9 if i % 2 == 0 else 0.7
            s.add("bass", b, ins.harm_pluck(SR, mtof(m), s.sec(0.42), v, k_max=12, tilt=1.1,
                                            d0=3.0, dk=4.0, sustain=0.35, release=0.03))
    # pluck ostinato
    ost = [0, 2, 3, 2, 4, 2, 3, 1]
    for beat, length, sym in chords:
        tones = arp_tones(sym, 52)
        for i in range(int(length * 2)):
            b = beat + i * 0.5
            s.add("pluck", b, ins.ks_pluck(SR, mtof(tones[ost[int(b * 2) % 8]]), s.sec(0.35),
                                           0.45 if i % 2 == 0 else 0.35, t60=0.7, bright=0.6,
                                           seed=s.nseed(), release=0.05))
    # strings pad
    for beat, length, sym in chords:
        v = 0.25 if beat < 32 else 0.33
        play_pad(s, "pad", [(beat, length, sym)], 57, vel=v, attack=0.25, release=0.5,
                 cutoff=2400)

    kit = _drum_kit(700)
    for bar in range(24):
        b0 = bar * 4
        quiet = 16 <= bar < 20
        if bar in (0, 8, 20):
            hit(s, "drums", b0, kit["crash"], 0.7)
        hit(s, "drums", b0, kit["kick"], 1.0)
        if not quiet:
            hit(s, "drums", b0 + 1.5, kit["kick"], 0.6)
            hit(s, "drums", b0 + 2, kit["kick"], 0.9)
        hit(s, "drums", b0 + 1, kit["snare"], 0.8 if not quiet else 0.5)
        hit(s, "drums", b0 + 3, kit["snare"], 0.85 if not quiet else 0.5)
        for i in range(8):
            if not quiet or i % 2 == 1:
                hit(s, "drums", b0 + i * 0.5, kit["hat"], 0.5 if i % 2 else 0.3)
        if quiet:
            hit(s, "drums", b0 + 2, kit["tom_lo"], 0.6)
            hit(s, "drums", b0 + 2.75, kit["tom_lo"], 0.4)
        if bar % 8 == 7:  # fill into the next section
            for j, (o, drum) in enumerate(((3, "tom_hi"), (3.25, "tom_hi"), (3.5, "tom_lo"),
                                           (3.75, "tom_lo"))):
                hit(s, "drums", b0 + o, kit[drum], 0.7)
        if bar == 23:
            for i in range(8):
                hit(s, "drums", b0 + 2 + i * 0.25, kit["snare"], 0.3 + 0.07 * i)

    spec = {
        "lead": dict(level=0, send=0.2, eq=lambda f: lp(f, 5000, 1)),
        "lead2": dict(level=-10, send=0.25),
        "bass": dict(level=-6, send=0.05, eq=lambda f: hp(f, 50) * lp(f, 3000, 1)),
        "pluck": dict(level=-12, send=0.2, eq=lambda f: hp(f, 150)),
        "pad": dict(level=-13, send=0.3, eq=lambda f: hp(f, 180)),
        "drums": dict(level=-5, send=0.12, eq=lambda f: shelf_hi(f, 6000, -3)),
    }
    return s, s.mix(spec, 1.3, 303)


# ================================================================= BOSS

def boss():
    s = Song("boss", 140, 4, 24, seed=44)
    chords = parse_chords("Dm Dm Bb A | Dm Dm Gm A | Bb C Dm Dm | Bb C A A | Gm A Dm Bb | Gm Eb A A", 4)
    mel = ("D4:1.5 D4:.5 F4:1 A4:1 | Bb4:1.5 A4:.5 G#4:1 A4:1 | D5:2 C5:1 Bb4:1 | A4:2 C#5:1 E5:1 |"
           "D4:1.5 D4:.5 F4:1 A4:1 | Bb4:1.5 A4:.5 G#4:1 A4:1 | G4:1.5 F4:.5 E4:1 D4:1 | C#4:2 E4:2 |"
           "F4:2 D4:1 F4:1 | G4:2 E4:1 G4:1 | A4:3 F4:1 | D5:2 A4:2 |"
           "Bb4:2 A4:1 G4:1 | G4:2 C5:2 | A4:2 C#5:2 | E5:2 D5:.5 C#5:.5 A4:1 |"
           "G3:2 Bb3:1 D4:1 | C#4:2 E4:1 A4:1 | D4:4 | F4:2 D4:2 |"
           "G4:2 Bb4:2 | Bb4:2 Eb5:2 | C#5:2 E5:2 | A5:2 G5:1 E5:1")
    play_melody(s, "brass", mel, ins.brass, legato=0.9, vel=0.9, bright=0.9)
    # octave-down doubling where it stays above D3
    low = []
    for beat, length, m in parse_melody(mel, 4):
        if m - 12 >= midi("D3"):
            low.append((beat, length, m - 12))
    for beat, length, m in low:
        s.add("brass_lo", beat, ins.brass(SR, mtof(m), s.sec(length) * 0.9, 0.75,
                                          seed=s.nseed(), bright=0.6))
    # high strings shine in the second and last sections
    hi_bars = [(8, 16), (20, 24)]
    for beat, length, m in parse_melody(mel, 4):
        if any(a * 4 <= beat < b * 4 for a, b in hi_bars):
            s.add("strings", beat, ins.pad(SR, [mtof(m + 12)], s.sec(length) * 0.95, 0.9,
                                           seed=s.nseed(), attack=0.06, release=0.25,
                                           cutoff=3500, voices=3, detune=7))
    # ominous choir on every chord
    for beat, length, sym in chords:
        v = 0.55 if 64 <= beat < 80 else 0.4
        play_pad(s, "choir", [(beat, length, sym)], 50, vel=v, kind="choir", vowel="ah",
                 attack=0.4, release=0.8)
    # gallop bass
    for beat, length, sym in chords:
        root, _ = parse_chord(sym)
        r = place(root, 38)
        for q in range(int(length)):
            for o, v in ((0, 1.0), (0.5, 0.7), (0.75, 0.75)):
                s.add("bass", beat + q + o, ins.harm_pluck(SR, mtof(r), s.sec(0.22), v, k_max=12,
                                                           tilt=1.0, d0=4.0, dk=5.0, sustain=0.3,
                                                           release=0.03))
    kit = _drum_kit(800, taiko_f0=58)
    for bar in range(24):
        b0 = bar * 4
        breakdown = 16 <= bar < 20
        if bar in (0, 8, 20):
            hit(s, "drums", b0, kit["crash"], 0.8)
        hit(s, "drums", b0, kit["taiko"], 1.0)
        hit(s, "drums", b0 + 2, kit["taiko"], 0.9)
        if breakdown:
            hit(s, "drums", b0 + 3.5, kit["taiko"], 0.6)
            hit(s, "drums", b0 + 3, kit["tom_lo"], 0.6)
            continue
        hit(s, "drums", b0 + 1.5, kit["taiko"], 0.55)
        hit(s, "drums", b0 + 3.5, kit["taiko"], 0.5)
        for kb in (0, 0.75, 2, 2.5):
            hit(s, "drums", b0 + kb, kit["kick"], 0.8)
        hit(s, "drums", b0 + 1, kit["snare"], 0.9)
        hit(s, "drums", b0 + 3, kit["snare"], 0.95)
        for i in range(8):
            hit(s, "drums", b0 + i * 0.5, kit["hat"], 0.5 if i % 2 else 0.35)
        if bar % 4 == 3:
            for i, drum in enumerate(("tom_hi", "tom_hi", "tom_lo", "tom_lo")):
                hit(s, "drums", b0 + 3 + i * 0.25, kit[drum], 0.75)

    spec = {
        "brass": dict(level=0, send=0.25, eq=lambda f: lp(f, 4500, 1)),
        "brass_lo": dict(level=-6, send=0.2, eq=lambda f: lp(f, 3000, 1)),
        "strings": dict(level=-10, send=0.35),
        "choir": dict(level=-8, send=0.45, eq=lambda f: hp(f, 120)),
        "bass": dict(level=-6, send=0.05, eq=lambda f: hp(f, 45) * lp(f, 2500, 1)),
        "drums": dict(level=-4, send=0.18, eq=lambda f: shelf_hi(f, 6000, -3)),
    }
    return s, s.mix(spec, 2.0, 404)


# ================================================================= ENDING

def ending():
    s = Song("ending", 80, 3, 16, seed=55)
    chords = parse_chords("G D Em C | G C Am D | Em C G D | C D G D", 3)
    mel = ("B4:1 D5:1 G5:1 | F#5:2 E5:1 | E5:1 G5:1 B5:1 | A5:2 G5:1 |"
           "G5:1 D5:1 B4:1 | C5:1 E5:1 G5:1 | A5:1.5 G5:.5 E5:1 | F#5:3 |"
           "E5:1 G5:1 B5:1 | C6:2 B5:1 | B5:1 A5:1 G5:1 | A5:3 |"
           "G5:1 E5:1 C5:1 | D5:1 F#5:1 A5:1 | G5:3 | F#5:1 E5:1 D5:1")
    play_melody(s, "flute", mel, ins.flute, legato=0.95, vel=0.75, vib=4.8, breath=0.05,
                attack=0.07, release=0.25)
    # second half: strings answer a sixth/octave below
    harm = ("r:3 | r:3 | r:3 | r:3 | r:3 | r:3 | r:3 | r:3 |"
            "G4:3 | E4:3 | D4:3 | F#4:3 | E4:3 | F#4:3 | B4:3 | A4:3")
    for beat, length, m in parse_melody(harm, 3):
        s.add("strings", beat, ins.pad(SR, [mtof(m)], s.sec(length), 0.8, seed=s.nseed(),
                                       attack=0.35, release=0.7, cutoff=2200))
    # harp arpeggios up and down
    pat = [0, 1, 2, 3, 2, 1]
    for beat, length, sym in chords:
        tones = arp_tones(sym, 43)
        for i in range(6):
            b = beat + i * 0.5
            s.add("harp", b, ins.ks_pluck(SR, mtof(tones[pat[i]]), s.sec(1.8),
                                          0.5 if i == 0 else 0.38, t60=2.0, bright=0.45,
                                          seed=s.nseed(), release=0.25, pick=0.13))
    # warm pad + soft bass
    play_pad(s, "pad", chords, 55, vel=0.3, attack=0.9, release=1.2, cutoff=1400)
    for beat, length, sym in chords:
        root, _ = parse_chord(sym)
        s.add("bass", beat, ins.harm_pluck(SR, mtof(place(root, 40)), s.sec(length) * 0.95, 0.7,
                                           k_max=5, tilt=1.5, d0=0.8, dk=1.5, sustain=0.35,
                                           release=0.4))
    # celesta sparkle every other bar on the chord top
    for i, (beat, length, sym) in enumerate(chords):
        if i % 2 == 1:
            top = chord_notes(sym, 79)[-1]
            s.add("bell", beat + 1, ins.bell(SR, mtof(top), 1.8, 0.4, seed=s.nseed()))
    fd = perc_bank(ins.frame_drum, 2, 900, f0=95)
    for bar in range(8, 16):
        hit(s, "perc", bar * 3, fd, 0.45)

    spec = {
        "flute": dict(level=0, send=0.35),
        "strings": dict(level=-8, send=0.4, eq=lambda f: hp(f, 150)),
        "harp": dict(level=-8, send=0.35, eq=lambda f: hp(f, 110)),
        "pad": dict(level=-13, send=0.45, eq=lambda f: hp(f, 150)),
        "bass": dict(level=-11, send=0.15),
        "bell": dict(level=-15, send=0.5),
        "perc": dict(level=-17, send=0.3, eq=lambda f: lp(f, 1500)),
    }
    return s, s.mix(spec, 2.6, 505)


TRACKS = {"town": town, "dungeon": dungeon, "battle": battle, "boss": boss, "ending": ending}
