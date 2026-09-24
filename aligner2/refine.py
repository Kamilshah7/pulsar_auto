"""
aligner2 boundary rules: moves each word boundary from the coarse aligner (v16) onto the acoustic landmark
that human reviewers use for that kind of junction. No training, no fitted parameters: every rule is a
phonetic definition read from the boundary-by-boundary study in bench/cache/aligner2/fullread/NOTES.md
(sets 009 and 026; 'H' = a boundary a reviewer moved by hand).

The junction kind comes from the last phone of word k (A) and the first phone of word k+1 (B), in ARPAbet.
Positions are found in the signals on the 2 ms grid (aligner2/signals.py). Levels are always taken
RELATIVE to the recording (the two phones' own steady states, the local background), never absolute.

Continuous joins (no pause between the words):
  J1 released stop  -> vowel-initial word: the release belongs to word k; cut at the VOICING ONSET of B =
     halfway up the loudness rise into the vowel            (good|a-, and|if, write|about, book|is: H)
  J2 vowel/sonorant -> voiced stop/affricate (B D G JH): cut at the BURST ONSET; the voice bar belongs to
     word k                                                  (they've|been, they've|done, cutting|jerome: H)
  J3 vowel/sonorant -> voiceless stop/affricate (P T K CH): word k ends at its decay KNEE (end of voicing),
     word k+1 starts at its BURST ONSET; the silent closure is left unassigned (you're|preseason: H)
  J4 sonorant -> fricative: frication crossover = halfway through the sonorant->fricative change
     (compromise between the 009 reviewer's frication onset and the 026 reviewer's plateau start)
  J5 fricative -> sonorant: CROSSFADE MIDPOINT (situations|and, drive|so, his|ability, next|one: H); a vowel-
     initial word with a glottal attack is cut at the attack (is|at)
  J6 fricative -> fricative: the loudness minimum between them (is|they've, teens|the, was|the)
  J7 vowel -> nasal: END of the nasal-onset transition (think|more, my|mother: H)
  J8 nasal -> vowel-initial word: the glottal attack when there is one (leading|up: H, woman|i), else the
     middle of the nasal-release ramp (thing|about: H)
  J9 vowel -> glide/liquid: the constriction maximum (loudness / high-band minimum; the|real: H, R4)
  J10 everything else: the midpoint of the joint spectral change between the two phones' steady states
Pause edges (a silence between the words):
  P1 word end: where its decay reaches the local background + 6 dB (walk.end, howard.end, first.end: H);
     releases and aspiration are kept (R2); an event after a dip toward the background (breath, click, hum,
     laugh) is not the word's (R3)
  P2 word start: where the rise into the word leaves the background + 6 dB, skipping separate events
     before it (R3); a stop-initial word starts at its burst onset (R8)
"""
import numpy as np

HOP = 0.002
MS = lambda ms: int(round(ms / 1000 / HOP))
VOWELS = set("AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW".split())
CLASS = {**{p: "V" for p in VOWELS}, **{p: "stop" for p in ("P", "B", "T", "D", "K", "G")},
         **{p: "aff" for p in ("CH", "JH")}, **{p: "fric" for p in ("F", "V", "TH", "DH", "S", "Z", "SH", "ZH")},
         "HH": "h", **{p: "nas" for p in ("M", "N", "NG")}, "L": "liq", "R": "liq", "W": "gl", "Y": "gl"}
VOICELESS = {"P", "T", "K", "CH", "F", "TH", "S", "SH", "HH"}
SONORANT = {"V", "nas", "liq", "gl"}
BG_DB = 6.0                                   # pause edges: background + 6 dB (read from the H pause ends)
RISE_DB = 4.0                                 # a clear loudness rise: >= 4 dB per 12 ms
J0_DB, J0_MS = 8, 40
RULES = {"J1", "J4", "J5", "J8", "P1", "P2", "E1", "E2", "F1"}                    # enabled rules (aligner2/local_bench.py --rules for ablations)


def first_phone(arpa):
    ph = (arpa or "").split()
    return ph[0] if ph and ph[0] != "*" else None


def last_phone(arpa):
    ph = (arpa or "").split()
    return ph[-1] if ph and ph[-1] != "*" else None


def pclass(ph):
    return CLASS.get(ph, "?") if ph else "?"


def _runs(mask):
    d = np.diff(np.r_[0, mask.astype(int), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _box(x, n):
    if n <= 1:
        return x.astype(float)
    return np.convolve(x.astype(float), np.ones(n) / n, "same")


class Sig:
    """the clip's signals on the 2 ms grid, plus smoothed loudness and the local background level"""

    def __init__(self, z):
        self.T = len(z["loudness"])
        self.L = z["loudness"].astype(float)
        self.Ls = _box(self.L, 5)                                  # 10 ms
        L50 = _box(self.L, 25)                                     # 50 ms
        w = MS(1000)
        # local floor: the quietest 50 ms level within +-1 s (running minimum, computed in blocks)
        self.floor = np.array([L50[max(0, i - w): i + w + 1].min() for i in range(0, self.T, 25)])
        self.floor = np.repeat(self.floor, 25)[:self.T]
        for n in ("periodicity", "zcr", "centroid", "high_ratio", "low_ratio", "transient", "glottal",
                  "mfcc_change", "ctc_blank", "ctc_wordsep"):
            setattr(self, n, z[n].astype(float))
        self.per, self.cent, self.hi, self.lo, self.trn = (self.periodicity, self.centroid, self.high_ratio,
                                                            self.low_ratio, self.transient)
        self.slope = np.zeros(self.T); self.slope[3:-3] = self.Ls[6:] - self.Ls[:-6]     # 12 ms loudness slope

    def clip(self, i):
        return int(min(max(i, 0), self.T - 1))


# ── landmark detectors (indices on the 2 ms grid) ────────────────────────────────────────────────────────
def burst_onset(S, a, b, prefer="last", closure_db=6.0):
    """stop release in [a, b): a >2 kHz transient (>= 3 dB) that follows a CLOSURE -- the 16 ms before it at
    least closure_db quieter than the 16 ms after it (glottal pulses in creaky voice have no closure).
    Returns the burst onset: the first frame >= 25% of the transient peak within 10 ms before it."""
    a, b = S.clip(a), S.clip(b)
    if b - a < 2:
        return None
    cands = []
    i = a
    while i < b:
        if S.trn[i] >= 3.0:
            j = i
            while j + 1 < b and S.trn[j + 1] >= 1.5:
                j += 1
            pk = i + int(np.argmax(S.trn[i:j + 1]))
            before = np.median(S.Ls[max(0, pk - MS(18)):max(1, pk - MS(2))])
            after = S.Ls[pk:min(S.T, pk + MS(16))].max()
            if after - before >= closure_db:
                lo = max(0, pk - MS(10))
                on = next((q for q in range(lo, pk + 1) if S.trn[q] >= max(2.0, 0.25 * S.trn[pk])), pk)
                cands.append((on, S.trn[pk]))
            i = j + 1
        else:
            i += 1
    if not cands:
        return None
    if prefer == "last":
        return cands[-1][0]
    if prefer == "first":
        return cands[0][0]
    return max(cands, key=lambda c: c[1])[0]


def after_burst(S, pb):
    """first frame after a burst onset where the burst's own loudness rise is over"""
    i = pb
    while i < min(S.T - 1, pb + MS(20)) and S.slope[i] >= RISE_DB / 2:
        i += 1
    return max(i, pb + MS(4))


def voicing_onset(S, pb, lim):
    """after a release at pb: where the spectrum is halfway from the release (its first 6 ms) to the vowel
    (the most periodic 10 ms within 10-60 ms after the release) -- low-band share, centroid, zcr, periodicity"""
    a, b = S.clip(pb + MS(10)), S.clip(min(lim, pb + MS(60)))
    if b - a < MS(10):
        return None
    pm = _box(S.per[a:b], MS(10))
    v0 = a + int(np.argmax(pm)) - MS(5)
    ra, rb = (pb, pb + MS(6)), (max(pb + MS(8), v0), max(pb + MS(8), v0) + MS(10))
    p = progress(S, pb, rb[0], ra, rb, feats=("lo", "cent", "zcr", "per"))
    i = crossing(p, 0.5)
    return pb + i if i is not None else None


def first_rise(S, a, b, min_db=3.0):
    """halfway up the FIRST loudness rise of >= min_db in [a, b): from the minimum before it to the maximum
    within 20 ms after it"""
    a, b = S.clip(a), S.clip(b)
    if b - a < 3:
        return None
    sl = S.slope[a:b]
    if sl.max() < RISE_DB:
        return None
    k = a + int(np.argmax(sl >= RISE_DB))                     # first frame of a clear rise
    while k + 1 < b and S.slope[k + 1] > S.slope[k]:
        k += 1                                                # its steepest point
    i0 = max(a, k - MS(16)); i0 = i0 + int(np.argmin(S.Ls[i0:k + 1]))
    top = S.Ls[k:min(S.T, k + MS(20))].max()
    if top - S.Ls[i0] < min_db:
        return None
    half = (S.Ls[i0] + top) / 2
    for i in range(i0, min(S.T, k + MS(20))):
        if S.Ls[i] >= half:
            return i
    return k


def rise_mid(S, a, b):
    """halfway up the steepest loudness rise in [a, b): between the minimum before it and the top after it"""
    a, b = S.clip(a), S.clip(b)
    if b - a < 3:
        return None
    k = a + int(np.argmax(S.slope[a:b]))
    lo_i = max(a - MS(10), k - MS(20)); hi_i = min(S.T, k + MS(20))
    bot = S.Ls[lo_i:k + 1].min(); top = S.Ls[k:hi_i].max()
    half = (bot + top) / 2
    i0 = lo_i + int(np.argmin(S.Ls[lo_i:k + 1]))
    for i in range(i0, hi_i):
        if S.Ls[i] >= half:
            return i
    return k


def fall_knee(S, a, b):
    """end of a steep decay in [a, b): after the steepest fall, the first frame where the loudness has come
    down 90% of the way from the level before the fall to the level at the end of the window"""
    a, b = S.clip(a), S.clip(b)
    if b - a < 3:
        return None
    k = a + int(np.argmin(S.slope[a:b]))
    top = S.Ls[max(0, k - MS(12)):k + 1].max(); bot = S.Ls[k:b].min()
    lvl = top - 0.9 * (top - bot)
    for i in range(k, b):
        if S.Ls[i] <= lvl:
            return i
    return k


def loud_min(S, a, b):
    a, b = S.clip(a), S.clip(b)
    if b - a < 1:
        return None
    return a + int(np.argmin(S.Ls[a:b]))


def glottal_attack(S, a, b, depth_db=3.0):
    """a vowel-initial word's glottal attack in [a, b): a loudness dip of >= depth_db below both sides
    followed by a rise with a transient or glottal-pulse crest; returns the rise onset (dip bottom)"""
    a, b = S.clip(a), S.clip(b)
    if b - a < 4:
        return None
    i = a + int(np.argmin(S.Ls[a:b]))
    left = S.Ls[max(0, i - MS(20)):i + 1].max(); right = S.Ls[i:min(S.T, i + MS(20))].max()
    if min(left, right) - S.Ls[i] < depth_db:
        return None
    return i


FEATS = ("Ls", "lo", "hi", "cent", "zcr", "per")
SCALE = {"Ls": 6.0, "lo": 3.0, "hi": 8.0, "cent": 0.5, "zcr": 0.12, "per": 0.2}   # a clear change of each


def _arr(S, f):
    return S.Ls if f == "Ls" else {"lo": S.lo, "hi": S.hi, "cent": S.cent, "zcr": S.zcr, "per": S.per}[f]


def progress(S, a, b, ra, rb, feats=FEATS):
    """joint progress (0 = phone A's steady state, 1 = phone B's) over [a, b); ra / rb are (i0, i1) reference
    windows. Features that differ clearly between the two references are averaged, weighted by contrast."""
    num = np.zeros(b - a); den = 0.0
    for f in feats:
        x = _box(_arr(S, f)[max(0, a - 3):b + 3], 3)[a - max(0, a - 3):][:b - a]
        xa = np.median(_arr(S, f)[ra[0]:ra[1]]); xb = np.median(_arr(S, f)[rb[0]:rb[1]])
        c = abs(xb - xa) / SCALE[f]
        if c < 1.0:
            continue
        num += c * np.clip((x - xa) / (xb - xa), -0.5, 1.5); den += c
    return num / den if den else None


def crossing(p, q):
    """first index where p reaches q and stays >= q for 3 frames (scanning from its last minimum below q)"""
    if p is None:
        return None
    below = np.where(p < q)[0]
    start = below[0] if len(below) else 0
    for i in range(start, len(p) - 2):
        if p[i] >= q and p[i + 1] >= q and p[i + 2] >= q:
            return i
    return None


# ── class prototypes: the most typical 10 ms of a phone class inside a range ─────────────────────────────
def pick_ref(S, cls, a, b, voiceless=False):
    """start index of the 10 ms window in [a, b) that looks most like `cls` (a pclass name)"""
    a, b = S.clip(a), S.clip(b)
    w = MS(10)
    if b - a <= w:
        return None
    sm = lambda x: _box(x[a:b], w)
    if cls == "V":
        score = sm(S.per) + sm(S.Ls) / 20.0
    elif cls in ("fric", "aff", "h"):
        score = sm(S.zcr) if voiceless else sm(S.hi) / 10.0 + sm(S.zcr)
    elif cls == "nas":
        score = sm(S.per) + sm(S.lo) / 3.0 - sm(S.cent)
    elif cls in ("liq", "gl"):
        score = sm(S.per) - sm(S.hi) / 20.0 - sm(S.Ls) / 20.0
    elif cls == "stop":
        score = -sm(S.Ls)
    else:
        return None
    i = int(np.argmax(score[w // 2:len(score) - w // 2])) + w // 2     # the window's centre
    return a + i - w // 2


def transition(S, clsA, clsB, a, cut, b, q, feats=None, vlA=False, vlB=False):
    """frame where the joint change from phone A's most typical 10 ms (in [a, cut + 10 ms]) to phone B's (in
    [cut - 10 ms, b]) has progressed a fraction q"""
    ia = pick_ref(S, clsA, a, cut + MS(10), vlA)
    ib = pick_ref(S, clsB, cut - MS(10), b, vlB)
    if ia is None or ib is None or ib - ia < MS(22):
        return None
    lo_, hi_ = ia + MS(10), ib
    p = progress(S, lo_, hi_, (ia, ia + MS(10)), (ib, ib + MS(10)), feats or FEATS)
    i = crossing(p, q)
    return lo_ + i if i is not None else None


# ── lexical region: the boundary lies between word k's last-letter peak and word k+1's first-letter peak ──
def lexical_peaks(z, texts):
    """HuBERT CTC letters (4 frame phases averaged, aligner2/lexical.py): per token the 2 ms-grid index of its
    first / last letter's posterior peak. Read on 009 + 026: 97% of the gold joins lie between word k's
    last-letter peak and word k+1's first-letter peak (+-10 ms), 99% within +-20 ms."""
    from aligner2 import lexical
    T = len(z["loudness"])
    views = [(z["ctc_logp"], lexical.FRAME_OFF)]
    views += [(z[f"ctc_logp_s{sh}"], lexical.FRAME_OFF + sh / 16000) for sh in (80, 160, 240) if f"ctc_logp_s{sh}" in z]
    outs = [lexical.boundary_priors(lp.astype(float), texts, T, HOP, None, frame_off=off) for lp, off in views]
    n = len(texts)
    first = [int(np.argmax(np.mean([o[5]["first"][k] for o in outs], 0))) for k in range(n)]
    last = [int(np.argmax(np.mean([o[5]["last"][k] for o in outs], 0))) for k in range(n)]
    return {"first": first, "last": last}


# ── the rules ────────────────────────────────────────────────────────────────────────────────────────────
class Clip:
    def __init__(self, z, texts, arpa, coarse, lex=None):
        self.S = Sig(z)
        self.lex = lex if lex is not None else lexical_peaks(z, texts)
        self.texts, self.arpa = texts, arpa
        self.n = len(texts)
        self.e = [c["end"] for c in coarse]
        self.s = [c["start"] for c in coarse]
        self.trace = {}

    def idx(self, t):
        return self.S.clip(int(round(t / HOP)))

    def refs(self, cut, lo_lim, hi_lim):
        """reference windows for phone A (before the cut) and phone B (after it)"""
        ra = (max(lo_lim, cut - MS(35)), max(lo_lim + 1, cut - MS(15)))
        rb = (min(hi_lim - 1, cut + MS(15)), min(hi_lim, cut + MS(35)))
        return ra, rb

    def join(self, k):
        """continuous join k|k+1 -> (end_k, start_k+1) in seconds"""
        S = self.S
        cut = self.idx((self.e[k] + self.s[k + 1]) / 2)
        lo_lim = self.idx(self.s[k]) + MS(10)                       # stay inside the two words
        hi_lim = self.idx(self.e[k + 1]) - MS(10)
        pa, pb = self.lex["last"][k], self.lex["first"][k + 1]      # the lexical region
        a, b = max(lo_lim, min(pa, cut) - MS(10)), min(hi_lim, max(pb, cut) + MS(10))
        if b - a < MS(10):
            return None
        A, B = last_phone(self.arpa[k]), first_phone(self.arpa[k + 1])
        cA, cB = pclass(A), pclass(B)
        ra, rb = self.refs(cut, lo_lim, hi_lim)
        t = None
        if cA not in ("stop", "aff") and cB not in ("stop", "aff") and "J0" in RULES:   # J0: a missed pause
            quiet = S.Ls[a:b] <= S.floor[a:b] + J0_DB
            runs = [(a + r0, a + r1) for r0, r1 in _runs(quiet) if r1 - r0 >= MS(J0_MS)]
            if runs:
                r0, r1 = max(runs, key=lambda r: r[1] - r[0])
                self.note(k, "J0 silence", end=r0, start=r1)
                return r0, r1
        if cA == "stop" and cB == "V" and "J1" in RULES:                         # J1
            bu = burst_onset(S, a, b, prefer="max")
            if bu is not None:                            # released: voicing onset after the release
                t = voicing_onset(S, bu, hi_lim)
                self.note(k, "J1 burst", burst=bu, voice=t)
            else:                                         # glottal / elided stop: re-onset after the dip
                m = glottal_attack(S, a, b)
                t = first_rise(S, m, min(hi_lim, m + MS(30))) if m is not None else None
                self.note(k, "J1 dip", dip=m, rise=t)
        if cA in ("V", "nas") and cB == "fric" and "J4" in RULES:                 # J4
            for name, q, feats in (("onset", 0.2, ("zcr", "hi")), ("loud-fall", 0.5, ("Ls",)), ("joint", 0.2, None)):
                t = transition(S, cA, cB, a, cut, b, q, feats)
                if t is not None:
                    self.note(k, f"J4 {name}", cut=t)
                    break
        if cA == "fric" and cB == "V" and "J5" in RULES:                          # J5
            for name, q, feats in (("crossfade", 0.5, ("zcr", "hi")), ("joint", 0.5, None)):
                t = transition(S, cA, cB, a, cut, b, q, feats)
                if t is not None:
                    self.note(k, f"J5 {name}", cut=t)
                    break
        if cA == "nas" and cB == "V" and "J8" in RULES:                           # J8
            for name, q, feats in (("release", 0.5, ("lo", "cent")), ("joint", 0.5, None)):
                t = transition(S, cA, cB, a, cut, b, q, feats)
                if t is not None:
                    self.note(k, f"J8 {name}", cut=t)
                    break
        return (t, t) if t is not None else None

    def note(self, k, rule, **marks):
        self.trace[k] = rule + " " + " ".join(f"{n}={v * HOP:.3f}" if v is not None else f"{n}=-" for n, v in marks.items())

    def background(self, i0, i1):
        """the quiet level of a pause [i0, i1): 10th percentile of the 10 ms loudness (the quietest 25 ms if short)"""
        S = self.S
        i0, i1 = S.clip(i0), S.clip(i1)
        if i1 - i0 >= MS(40):
            return float(np.percentile(S.Ls[i0:i1], 10))
        c = (i0 + i1) // 2
        return float(S.Ls[S.clip(c - MS(12)):S.clip(c + MS(13)) + 1].min())

    def pause_end(self, k, nxt):
        """P1 (word k before a pause): the coarse end is kept unless
          (a) after word k's last letter a SEPARATE EVENT starts: the loudness drops >= 8 dB from the word and
              rises >= 6 dB out of that trough for >= 30 ms (breath, hum, laugh, hiss; R3) -> end where the decay
              reaches the trough (+3 dB). A final stop's release burst is not an event (R2).
          (b) the word ends in a stop and its release burst lies after the coarse end (a silent closure between)
              -> end where the release has decayed back to the residual level + BG_DB (R2);
          (c) F1: the word ends in a fricative that is still sounding at the coarse end -> end where the
              frication dies (zcr under half its value, or the local floor + 6 dB; R7; 8 H pause ends: 8 ms
              MAE vs 38 ms for the coarse end -- the accepted old golds cut fricatives earlier)."""
        S = self.S
        i_end, i_nxt = self.idx(self.e[k]), self.idx(nxt)
        lim = S.clip(i_nxt - MS(10))
        stop_final = pclass(last_phone(self.arpa[k])) == "stop"
        fric_final = pclass(last_phone(self.arpa[k])) in ("fric", "aff")
        lo = max(self.lex["last"][k], self.idx(self.s[k]) + MS(20))
        if i_end - lo >= MS(30) and last_phone(self.arpa[k]):              # not for '(())' / wildcards                                             # (a) separate event
            M = m = S.Ls[lo]; ti = lo
            for i in range(lo, i_end + 1):
                x = S.Ls[i]
                if x >= M:
                    M = m = x; ti = i
                elif x < m:
                    m = x; ti = i
                elif x - m >= 6.0 and M - m >= 8.0:
                    # a real gap: the trough stays within 3 dB of its bottom for >= 16 ms (not a creak pulse);
                    # a real event: >= 6 dB above it for 30 ms, starting >= 30 ms before the coarse end
                    t0 = ti
                    while t0 > lo and S.Ls[t0 - 1] <= m + 6.0:
                        t0 -= 1
                    t1 = ti
                    while t1 < i and S.Ls[t1 + 1] <= m + 6.0:
                        t1 += 1
                    above = S.Ls[i:i + MS(30)] >= m + 6.0
                    ev = slice(i, i_end + 1)
                    body = S.Ls[self.idx(self.s[k]):t0 + 1].max() if t0 > self.idx(self.s[k]) else -1e9
                    ok = (t1 - t0 >= MS(16) and i + MS(30) <= i_end and above.all()
                          and m <= S.floor[ti] + 30.0                     # a real gap, not a dip inside speech
                          and body >= S.Ls[ev].max() - 15.0)             # the word's nucleus is before the gap
                    if ok and stop_final and burst_onset(S, ti, i + MS(4)) is not None:
                        ok = False                                        # the final stop's release (R2)
                    if ok and (fric_final or stop_final) and np.median(S.zcr[i:i + MS(40)]) >= 0.25:
                        ok = False                                        # the final fricative / affricated release
                    if ok:
                        self.note(k, "P1 event", end=t0, trough=ti)
                        return t0
                    m = x; ti = i                                  # keep the word's level M, look for a new trough
        if fric_final and "F1" in RULES:                                       # (c) the final fricative runs on
            ref = slice(max(0, i_end - MS(20)), i_end)
            zr = float(np.median(S.zcr[ref]))
            if zr >= 0.25:
                j = i_end
                while j < min(lim, i_end + MS(200)) and S.zcr[j] >= max(0.15, 0.5 * zr) and S.Ls[j] >= S.floor[j] + 6.0:
                    j += 1
                if j > i_end:
                    self.note(k, "P1 fricative", end=j)
                    return j
        if stop_final:                                                         # (b) release after the coarse end
            bu = burst_onset(S, i_end, min(lim, i_end + MS(60)), prefer="first")
            wpk = S.Ls[self.idx(self.s[k]):i_end + 1].max()
            if bu is not None and S.Ls[bu:bu + MS(20)].max() >= wpk - 30.0:   # an audible release
                resid = S.Ls[bu:min(lim, bu + MS(200))].min()
                j = bu + MS(6)
                while j < min(lim, bu + MS(80)) and S.Ls[j] >= resid + BG_DB:
                    j += 1
                self.note(k, "P1 release", end=j, burst=bu)
                return j
        return None

    def pause_start(self, k, prv):
        """P2 (word k after a pause): the coarse start is kept unless, between it and word k's first letter, a
        SEPARATE EVENT precedes the word across a real gap (the mirror of P1a: breath, click, hum; R3) -> the
        word starts where it rises out of the gap."""
        S = self.S
        i_st, i_prv = self.idx(self.s[k]), self.idx(prv)
        hi = min(self.lex["first"][k], self.idx(self.e[k]) - MS(20))
        cls0 = pclass(first_phone(self.arpa[k]))
        if hi - i_st < MS(30) or not first_phone(self.arpa[k]):          # not for '(())' / wildcards
            return None
        M = m = S.Ls[hi]; ti = hi
        for i in range(hi, i_st - 1, -1):
            x = S.Ls[i]
            if x >= M:
                M = m = x; ti = i
            elif x < m:
                m = x; ti = i
            elif x - m >= 6.0 and M - m >= 8.0:
                t1 = ti
                while t1 < hi and S.Ls[t1 + 1] <= m + 6.0:
                    t1 += 1
                t0 = ti
                while t0 > i and S.Ls[t0 - 1] <= m + 6.0:
                    t0 -= 1
                below = S.Ls[max(0, i - MS(30)):i + 1] >= m + 6.0
                ev = slice(i_st, i + 1)
                body = S.Ls[t1:self.idx(self.e[k]) + 1].max()
                ok = (t1 - t0 >= MS(16) and i - MS(30) >= i_st and below.all()
                      and m <= S.floor[ti] + 30.0 and body >= S.Ls[ev].max() - 15.0)
                if ok and cls0 in ("fric", "aff", "h") and np.median(S.zcr[max(0, i - MS(40)):i + 1]) >= 0.25:
                    ok = False                                # the word's own initial fricative
                if ok:
                    self.trace[k - 1] = self.trace.get(k - 1, "") + f" | P2 event start={t1 * HOP:.3f}"
                    return t1
                m = x; ti = i
        return None

    def _trough_before(self, hi):
        """scanning back from hi: the deepest real gap before the word -- a stretch >= 8 dB under the word,
        within 30 dB of the local floor, >= 16 ms wide (6 dB band). Returns (trough index, level) or None."""
        S = self.S
        M = S.Ls[hi]; m = M; ti = hi
        for i in range(hi, -1, -1):
            x = S.Ls[i]
            if x > M and ti == hi:
                M = m = x
            if x < m:
                m = x; ti = i
            if (x - m >= 6.0 or i == 0) and M - m >= 8.0 and m <= S.floor[ti] + 30.0:
                t0 = t1 = ti
                while t0 > 0 and S.Ls[t0 - 1] <= m + 6.0:
                    t0 -= 1
                while t1 < hi and S.Ls[t1 + 1] <= m + 6.0:
                    t1 += 1
                if t1 - t0 >= MS(16):
                    return ti, m
        return None

    def clip_start(self):
        """E1: the first word starts where it rises out of the last real gap before its first letter (level:
        trough + 6 dB, but at most 35 dB under the word's first peak); with no gap (the clip cuts into running
        speech) it starts at the clip start"""
        S = self.S
        hi = min(self.lex["first"][0], self.idx(self.e[0]) - MS(20))
        if hi < MS(10):
            return None
        g = self._trough_before(hi)
        if g is None:
            if np.median(S.Ls[MS(10):MS(30)]) >= S.floor[0] + 15.0:
                self.trace[-1] = "E1 running speech at the clip start"
                return 0
            return None
        ti, m = g
        top = S.Ls[ti:self.idx(self.e[0]) + 1].max()               # the first word's own peak
        lvl = max(m + 6.0, top - 35.0)
        on = next((i for i in range(ti, hi + 1) if S.Ls[i] >= lvl), None)
        self.trace[-1] = f"E1 gap start={on * HOP:.3f}" if on is not None else "E1 -"
        return on

    def clip_end(self):
        """E2: the last word: the P1 checks against the clip end; if the clip cuts off running speech (no drop
        after the last letter) it ends at the clip end"""
        S = self.S
        n = self.n - 1
        lo = max(self.lex["last"][n], self.idx(self.s[n]) + MS(20))
        tail = S.Ls[lo:]
        if len(tail) and tail.min() >= tail.max() - 8.0 and np.median(S.Ls[S.T - MS(30):S.T - MS(10)]) >= S.floor[-1] + 15.0:
            self.trace[n] = "E2 running speech at the clip end"
            return S.T - 1
        return self.pause_end(n, (S.T - 1) * HOP + MS(10) * HOP)

    def run(self):
        e, s = list(self.e), list(self.s)
        for k in range(self.n - 1):
            if self.s[k + 1] - self.e[k] <= 0.005:
                r = self.join(k)
                if r is not None:
                    t0, t1 = r
                    if t1 > t0:                                   # J0: a pause inside the join
                        e[k], s[k + 1] = t0 * HOP, t1 * HOP
                    else:
                        e[k], s[k + 1] = t0 * HOP - 0.001, t1 * HOP + 0.001
            else:
                r = self.pause_end(k, self.s[k + 1]) if "P1" in RULES else None
                if r is not None:
                    e[k] = r * HOP
                r = self.pause_start(k + 1, self.e[k]) if "P2" in RULES else None
                if r is not None:
                    s[k + 1] = r * HOP
        if "E1" in RULES:
            r = self.clip_start()
            if r is not None:
                s[0] = r * HOP
        if "E2" in RULES:
            r = self.clip_end()
            if r is not None:
                e[-1] = r * HOP
        out = []
        for k in range(self.n):
            st, en = s[k], e[k]
            if en <= st:
                en = st + 0.010
            out.append({"start": float(st), "end": float(en)})
        return out


def refine(z, texts, arpa, coarse, trace=None, lex=None):
    """z: signals dict (aligner2/signals.py), texts: tokens, arpa: per-token ARPAbet strings, coarse: v16
    [{start, end}] -> refined [{start, end}]; trace: optional dict filled with {boundary k: rule + landmarks};
    lex: precomputed lexical_peaks(z, texts)"""
    c = Clip(z, texts, arpa, coarse, lex)
    out = c.run()
    if trace is not None:
        trace.update(c.trace)
    return out
