"""
aligner2 segmenter: token start/end times from the signals. No word-, sound- or recording-specific rules.

Every boundary is found the same way: where the audio stops sounding like one side and starts sounding
like the other. Per boundary, the templates come from the audio itself:
    A  word 1's last letter   (signal vectors weighted by the CTC posterior of that letter)
    B  word 2's first letter  (same, for word 2's first letter)
    S  silence                (the silent run, when there is a pause)
Frame vectors: the level signals (loudness, periodicity, flatness, centroid, log_f0, glottal) and the
13 MFCCs behind mfcc_change, whitened per clip. A change point minimises the summed squared distance of
the frames before it to one template and after it to the other.

Continuous join: one change A -> B, searched between the two letters' posterior peaks; combined with the
lexical prior as posterior = prior * exp(-lam * normalised cost), cut = posterior median.
Pause: between the two letters, the local background is the quietest loudness there; frames within
theta_db of it (and that the lexical stage puts between the words, P(between) > 0.5) are silent. A silent
run >= min_pause is a pause: token k ends where it starts, token k+1 starts where it ends.
(Read from the raw dump: people put pause edges ~13-15 dB above the LOCAL background.)
Clip edges: the same threshold against the quietest level before the first / after the last token.

Pause models compared (pause_model): 'word_ref' -- quieter than the two WORDS by theta_db (read from the
traces: people count breath and room noise inside a pause as pause), 'local_min' -- within theta_db of the
quietest level, 'gmm' -- v2's unsupervised 2-cluster silence.
snap_ms: after the continuous split, move the cut to the sharpest joint change (whitened left/right
contrast, 6/10/20 ms) within +-snap_ms -- the traces show the cut is where word 2's sound switches on.
unit: 'letter' (HuBERT CTC letters) or 'phone' (xlsr-53 espeak phonemes; the transcript phonemized with
espeak) -- which lexical view gives the priors, P(between) and the edge templates.
cont_model: 'edge' (templates from the edge letters' posteriors) or 'class' -- read from the raw data:
the cut is the acoustic landmark between the two sounds' manner classes (closure, release, frication
on/offset...), so the split uses per-recording manner-class templates (vowel/stop/fricative/nasal/liquid/
glide, from the phoneme model's class posteriors) within +-radius_ms of the lexical median. Same-class
joins (vowel>vowel...) have no landmark and keep the edge templates.
cont_model 'sonority' (read from the ear-judged joins: the cut people accept is the amplitude landmark
of the sonority change): rising sonority -> steepest loudness rise, falling -> steepest fall (or the
quietest point, fall_mode='min'), obstruent>obstruent -> quietest point; sonorant>sonorant has no
landmark and keeps the edge templates. Searched within +-radius_ms of the lexical median, combined with
the lexical prior as argmax(log prior + lam * landmark strength).
charsiu (aligner2/fc_align.py, frame-classification phone model, 10 ms): cont_model='fc' uses its word
edges directly; center='fc' centres the landmark / class searches on them (prior = 10 ms Gaussian);
pause_model='fc' takes pauses from its [SIL] segments (>= min_pause).
onset_ms / offset_ms: refine pause edges to the steepest loudness rise (speech onset) near the silence end /
steepest fall near its start, within +-onset_ms / +-offset_ms (read from the raw dump: gold pause starts sit
on the steepest rise, 79% within 10 ms).
ref_mode 'word': the pause test compares against the loudness of the words' bodies (not their edge sounds,
which can be weak fricatives). anchor_ms / clip_anchor_ms: word start = steepest loudness rise within
anchor_ms before its first letter, word end = steepest fall within anchor_ms after its last letter (read
from the pause outliers: breath, clicks and untranscribed fillers inside pauses were taken as word edges).
unit 'letter4': the letter view averaged over HuBERT run on the audio shifted by 0/5/10/15 ms (frame-phase
ensemble: 5 ms effective resolution, frame-grid jitter averaged out).
Global parameters (leave-one-set-out in aligner2/run_bench.py): lam, pause_model, theta_db, min_pause,
snap_ms, unit, cont_model, radius_ms, fall_mode, center, onset_ms, offset_ms, ref_mode, anchor_ms, clip_anchor_ms.
"""
import numpy as np

from aligner2 import lexical
from aligner2.signals import HOP

LEVEL = ["loudness", "periodicity", "flatness", "centroid", "log_f0", "glottal"]
SUPPORT = 1e-4                                   # prior support: density >= SUPPORT * its max
GAP = 0.001                                      # continuous cut: end = cut - GAP/2, start = cut + GAP/2
PAD = int(0.020 / HOP)                           # search 20 ms beyond the template peaks


def _z(x):
    return (x - x.mean(0)) / (x.std(0) + 1e-9)


def frame_vectors(z):
    X = np.column_stack([_z(z[n].astype(float)) for n in LEVEL] + [z["mfcc"].astype(float)])
    cov = np.cov(X[::2].T) + 1e-6 * np.eye(X.shape[1])
    return X @ np.linalg.cholesky(np.linalg.inv(cov))


def _runs(mask):
    d = np.diff(np.r_[0, mask.astype(int), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def _gmm_silence(z):
    """v2's silence model: 2-component mixture on (loudness, periodicity, flatness), quieter component"""
    from sklearn.mixture import GaussianMixture
    X = np.c_[z["loudness"], z["periodicity"], z["flatness"]].astype(float)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    g = GaussianMixture(2, covariance_type="full", random_state=0).fit(Xs[::3])
    return g.predict_proba(Xs)[:, int(np.argmin(g.means_[:, 0]))]


def _template(Y, w):
    w = np.asarray(w, float)
    if w.sum() < 1e-6:
        return None
    return (Y * w[:, None]).sum(0) / w.sum()


def change_cost(Y, a, b, mu1, mu2):
    """cost[i] for a change at a + i (frames [a, a+i) -> mu1, [a+i, b) -> mu2), i = 0 .. b-a"""
    d1 = ((Y[a:b] - mu1) ** 2).sum(1); d2 = ((Y[a:b] - mu2) ** 2).sum(1)
    c1 = np.r_[0, np.cumsum(d1)]; c2 = np.r_[0, np.cumsum(d2)]
    return c1 + (c2[-1] - c2)


def contrast(Y, scales=(3, 5, 10)):
    """joint left/right change of the whitened frame vectors at 6/10/20 ms scales (each z-scored)"""
    T = len(Y); cs = np.vstack([np.zeros((1, Y.shape[1])), np.cumsum(Y, 0)])
    k = np.arange(T); out = np.zeros(T)
    for w in scales:
        a = np.clip(k - w, 0, T); b = np.clip(k + w, 0, T)
        L = (cs[k] - cs[a]) / np.maximum(k - a, 1)[:, None]; R = (cs[b] - cs[k]) / np.maximum(b - k, 1)[:, None]
        d = ((L - R) ** 2).sum(1); out += (d - d.mean()) / (d.std() + 1e-9)
    return out


class Lexical:
    """one lexical view of the clip (letters from HuBERT, or phones from the xlsr-53 espeak model).
    logp may be a list of (logp, frame_offset) -- the frame-phase ensemble: each shifted copy gets its own
    forward-backward, and the boundary densities / posteriors are averaged on the 2 ms grid."""

    def __init__(self, Y, T, logp, texts, device, units=None, sep=lexical.SEP, wild_from=lexical.SEP + 1):
        views = logp if isinstance(logp, list) else [(logp, lexical.FRAME_OFF)]
        outs = [lexical.boundary_priors(lp, texts, T, HOP, device, units, sep, wild_from, off) for lp, off in views]
        avg = lambda i: [np.mean([o[i][k] for o in outs], 0) for k in range(len(outs[0][i]))]
        self.priors = [p / p.sum() for p in avg(0)]
        self.first_start = np.mean([o[1] for o in outs], 0); self.last_end = np.mean([o[2] for o in outs], 0)
        self.between = avg(4)
        self.edge = {kind: [np.mean([o[5][kind][k] for o in outs], 0) for k in range(len(texts))] for kind in ("first", "last")}
        self.ab = [(np.mean([o[6][k][0] for o in outs], 0), np.mean([o[6][k][1] for o in outs], 0)) for k in range(len(texts) - 1)]
        # edge templates: signal vectors weighted by the edge unit's posterior, limited to +-60 ms of its peak
        self.peak_first, self.peak_last, self.mu_first, self.mu_last = [], [], [], []
        for k in range(len(texts)):
            for kind, lst_p, lst_m in (("first", self.peak_first, self.mu_first), ("last", self.peak_last, self.mu_last)):
                w = self.edge[kind][k]
                pk = int(np.argmax(w)); lo, hi = max(0, pk - 30), min(T, pk + 31)
                ww = np.zeros(T); ww[lo:hi] = w[lo:hi]
                lst_p.append(pk); lst_m.append(_template(Y, ww))


class Prepared:
    """everything parameter-independent for one clip: z = signals.features(...) output;
    phone_units = per-token phone ids (aligner2/phones.py) when the phoneme posteriors are available"""

    def __init__(self, z, texts, device=None, phone_units=None, phone_strs=None, fc_ids=None):
        self.T = len(z["t"])
        self.Y = frame_vectors(z)
        self.C = contrast(self.Y)
        self.loud = z["loudness"].astype(float)
        self.loud_z = (self.loud - self.loud.mean()) / (self.loud.std() + 1e-9)
        # noise-robust pause cues (align(pause_floor_db=..., pause_vad=...)): the local background = the minimum of the
        # 50 ms-smoothed loudness within +-1 s; pyannote's speech probability
        sm = np.convolve(self.loud, np.ones(25) / 25, "same")
        pad = np.pad(sm, 500, mode="edge")
        self.floor = np.lib.stride_tricks.sliding_window_view(pad, 1001).min(axis=1)[:self.T]
        self.vad = z["speech_prob"].astype(float) if "speech_prob" in z else None
        self.slope = _slope(self.loud)
        self.gmm_runs = _runs(_gmm_silence(z) > 0.5)
        self.lex = {"letter": Lexical(self.Y, self.T, z["ctc_logp"], texts, device)}
        shifted = [(z[f"ctc_logp_s{sh}"], lexical.FRAME_OFF + sh / 16000) for sh in (80, 160, 240) if f"ctc_logp_s{sh}" in z]
        if shifted:
            self.lex["letter4"] = Lexical(self.Y, self.T, [(z["ctc_logp"], lexical.FRAME_OFF)] + shifted, texts, device)
        if phone_units is not None and "phone_logp" in z:
            self.lex["phone"] = Lexical(self.Y, self.T, z["phone_logp"], texts, device, phone_units, sep=None, wild_from=4)
        self.fc = None
        if fc_ids is not None and "fc_logp" in z:          # charsiu frame-classification forced alignment
            from aligner2 import fc_align
            self.fc = fc_align.word_times(z["fc_logp"].astype(float), fc_ids)
        self.class_mu, self.edge_class = {}, None
        if phone_strs is not None and "phone_logp" in z:
            self._class_templates(z, phone_strs)

    def _class_templates(self, z, phone_strs):
        """per-recording manner-class templates: frame vectors weighted by P(class)^4 (class posterior =
        sum of the phoneme model's posteriors over that class's phones), plus each token's edge classes"""
        from aligner2 import phones
        P = np.exp(z["phone_logp"].astype(float))
        CP = P @ phones.class_matrix().T                         # (T20, classes)
        tf = np.arange(len(CP)) * 0.020 + 0.0125
        grid = np.arange(self.T) * HOP
        for ci, c in enumerate(phones.CLASSES):
            w = np.interp(grid, tf, CP[:, ci]) ** 4
            if w.sum() > 5:
                self.class_mu[c] = _template(self.Y, w)
        self.edge_class = [(phones.manner(s.split()[0]) if s.split() else None,
                            phones.manner(s.split()[-1]) if s.split() else None) for s in phone_strs]

    def use(self, unit):
        L = self.lex[unit]
        for n in ("priors", "first_start", "last_end", "between", "edge", "peak_first", "peak_last", "mu_first", "mu_last", "ab"):
            setattr(self, n, getattr(L, n))


def _split(prep, a, b, mu1, mu2):
    """best change point in [a, b] between templates mu1 -> mu2 (frame index)"""
    a, b = max(0, a), min(prep.T, b)
    if b - a < 2 or mu1 is None or mu2 is None:
        return (a + b) // 2
    return a + int(np.argmin(change_cost(prep.Y, a, b, mu1, mu2)))


def _silent_run(prep, a, b, theta_db, between=None):
    """longest run in [a, b) within theta_db of the quietest loudness there (and, if given, where
    P(between words) > 0.5); returns (start, end) frame indices or None"""
    a, b = max(0, a), min(prep.T, b)
    if b - a < 2:
        return None
    L = prep.loud[a:b]
    quiet = L < L.min() + theta_db
    if between is not None:
        quiet &= between[a:b] > 0.5
    runs = _runs(quiet)
    if not runs:
        return None
    r0, r1 = max(runs, key=lambda r: r[1] - r[0])
    return a + r0, a + r1


def _word_quiet_run(prep, k, delta_db, ref_mode="edge", floor_db=None, vad=None, floor_vad=None):
    """pause candidate for boundary k: the longest run between the two words' letter peaks that the
    lexical stage puts in neither word (P(between) > 0.5) and that is >= delta_db quieter than the
    quieter of the two words (loudness around their edge-letter peaks). Breath and room noise count
    as pause; weak word sounds keep their letters' posterior and stay out."""
    pa, pb = prep.peak_last[k], prep.peak_first[k + 1]
    a, b = max(0, min(pa, pb)), min(prep.T, max(pa, pb) + 1)
    if b - a < 2:
        return None
    w = int(0.030 / HOP)
    if ref_mode == "word":       # loudness of the words' bodies (90th pct between their first and last letters)
        f1, l2 = prep.peak_first[k], prep.peak_last[k + 1]
        body = lambda x, y: np.percentile(prep.loud[max(0, min(x, y) - w):max(x, y) + w + 1], 90)
        ref = min(body(f1, pa), body(pb, l2))
    else:
        ref = min(np.max(prep.loud[max(0, pa - w):pa + w + 1]), np.max(prep.loud[max(0, pb - w):pb + w + 1]))
    quiet = prep.loud[a:b] < ref - delta_db
    if floor_db is not None:                  # noise-robust: at the local background (a noisy pause is not
        at_floor = prep.loud[a:b] < prep.floor[a:b] + floor_db    # delta_db under the words, but it is at the floor)
        if floor_vad is not None and prep.vad is not None:     # ... and the speech detector agrees (weak consonants
            at_floor &= prep.vad[a:b] < floor_vad               # near a noisy floor are still speech)
        quiet |= at_floor
    if vad is not None and prep.vad is not None:   # noise-robust: the neural speech detector says non-speech
        quiet |= prep.vad[a:b] < vad
    quiet &= prep.between[k][a:b] > 0.5
    runs = _runs(quiet)
    if not runs:
        return None
    r0, r1 = max(runs, key=lambda r: r[1] - r[0])
    return a + r0, a + r1


SONORITY = {"stop": 1, "affric": 2, "fric": 3, "nasal": 4, "liquid": 5, "glide": 6, "vowel": 7}   # standard hierarchy


def _slope(x, w=3):
    """12 ms centred loudness slope (dB), z-scored per clip"""
    d = np.zeros_like(x); d[w:-w] = x[2 * w:] - x[:-2 * w]
    return (d - d.mean()) / (d.std() + 1e-9)


def align(prep, lam=1.0, pause_model="word_ref", theta_db=12.0, min_pause=0.1, snap_ms=0, unit="letter",
          cont_model="edge", radius_ms=40, fall_mode="fall", center="lexical", onset_ms=0, offset_ms=0,
          ref_mode="edge", anchor_ms=0, clip_anchor_ms=0, pause_floor_db=None, pause_vad=None, pause_floor_vad=None):
    prep.use(unit)
    T, n = prep.T, len(prep.priors) + 1
    ends, starts = [None] * n, [None] * n
    for k, pr in enumerate(prep.priors):
        sup = np.where(pr >= SUPPORT * pr.max())[0]
        lo, hi = sup[0], sup[-1] + 1
        pa, pb = prep.peak_last[k], prep.peak_first[k + 1]
        muA, muB = prep.mu_last[k], prep.mu_first[k + 1]
        fc_ok = prep.fc is not None and prep.fc[1][k] is not None and prep.fc[0][k + 1] is not None
        if pause_model == "fc" and fc_ok:
            sil = prep.fc[2][k]
            run = (int(sil[0] / HOP), int(sil[1] / HOP)) if sil else None
        elif pause_model == "word_ref":
            run = _word_quiet_run(prep, k, theta_db, ref_mode, pause_floor_db, pause_vad, pause_floor_vad)
        elif pause_model == "gmm":
            run = None
            for a0, b0 in prep.gmm_runs:
                if a0 < max(pa, pb) + PAD and b0 > min(pa, pb) - PAD and prep.between[k][a0:b0].mean() > 0.5:
                    if run is None or b0 - a0 > run[1] - run[0]:
                        run = (a0, b0)
        else:
            run = _silent_run(prep, min(pa, pb) - PAD, max(pa, pb) + PAD, theta_db, prep.between[k])
        if run and (run[1] - run[0]) * HOP >= min_pause:
            e_, s_ = run
            if anchor_ms:                    # anchor on the words' own letters: skips breath / clicks in the pause
                w = int(anchor_ms / 1000 / HOP); pad = int(0.010 / HOP)
                a0, b0 = max(e_, pb - w), min(T, pb + pad)
                if b0 > a0:
                    s_ = a0 + int(np.argmax(prep.slope[a0:b0]))
                a0, b0 = max(0, pa - pad), min(s_, pa + w)
                if b0 > a0:
                    e_ = a0 + int(np.argmin(prep.slope[a0:b0]))
            elif onset_ms:                     # speech onset landmark: steepest loudness rise near the silence end
                w = int(onset_ms / 1000 / HOP); a0, b0 = max(e_ + 1, s_ - w), min(T, s_ + w + 1)
                if b0 > a0:
                    s_ = a0 + int(np.argmax(prep.slope[a0:b0]))
            if offset_ms:                    # speech offset landmark: steepest loudness fall near the silence start
                w = int(offset_ms / 1000 / HOP); a0, b0 = max(0, e_ - w), min(s_ - 1, e_ + w + 1)
                if b0 > a0:
                    e_ = a0 + int(np.argmin(prep.slope[a0:b0]))
            ends[k], starts[k + 1] = e_ * HOP, max(s_, e_ + 1) * HOP
            continue
        a, b = min(pa, pb) - PAD, max(pa, pb) + PAD
        a, b = max(a, lo), min(b, hi)
        if cont_model == "fc" and fc_ok:                   # charsiu's word edge directly
            t = int(round((prep.fc[1][k] + prep.fc[0][k + 1]) / 2 / HOP))
            ends[k], starts[k + 1] = t * HOP - GAP / 2, t * HOP + GAP / 2
            continue
        if center == "fc" and fc_ok:                       # centre landmark searches on charsiu instead of CTC
            c0 = int(round((prep.fc[1][k] + prep.fc[0][k + 1]) / 2 / HOP))
            pr = np.exp(-0.5 * ((np.arange(T) - c0) * HOP / 0.010) ** 2) + 1e-12
            pr = pr / pr.sum()
        if cont_model == "sonority" and prep.edge_class is not None:
            cA, cB = prep.edge_class[k][1], prep.edge_class[k + 1][0]
            if cA in SONORITY and cB in SONORITY and not (SONORITY[cA] >= 5 and SONORITY[cB] >= 5):
                cdf = np.cumsum(pr); m = int(np.searchsorted(cdf / cdf[-1], 0.5)); r = int(radius_ms / 1000 / HOP)
                a0, b0 = max(0, m - r), min(T, m + r + 1)
                if SONORITY[cB] > SONORITY[cA]:
                    ev = prep.slope[a0:b0]                          # release into a more sonorous sound: rise
                elif SONORITY[cB] < SONORITY[cA] and fall_mode == "fall":
                    ev = -prep.slope[a0:b0]                         # closure / constriction onset: fall
                else:
                    ev = -prep.loud_z[a0:b0]                        # between obstruents (or fall_mode=min): quietest point
                t = a0 + int(np.argmax(np.log(pr[a0:b0] + 1e-12) + lam * ev))
                ends[k], starts[k + 1] = t * HOP - GAP / 2, t * HOP + GAP / 2
                continue
        if cont_model == "class" and prep.edge_class is not None:
            cA, cB = prep.edge_class[k][1], prep.edge_class[k + 1][0]
            if cA and cB and cA != cB and cA in prep.class_mu and cB in prep.class_mu:
                # the speaker's own class templates; search around the lexical prior's median
                cdf = np.cumsum(pr); m = int(np.searchsorted(cdf / cdf[-1], 0.5)); r = int(radius_ms / 1000 / HOP)
                a, b = max(0, m - r), min(T, m + r + 1)
                muA, muB = prep.class_mu[cA], prep.class_mu[cB]
        if b - a < 2 or muA is None or muB is None:
            cdf = np.cumsum(pr); t = int(np.searchsorted(cdf / cdf[-1], 0.5))
        else:
            cost = change_cost(prep.Y, a, b, muA, muB)[:-1]
            cost = (cost - cost.min()) / (cost.std() + 1e-9)
            logpost = np.log(pr[a:b]) - lam * cost
            post = np.exp(logpost - logpost.max()); cdf = np.cumsum(post)
            t = a + int(np.searchsorted(cdf / cdf[-1], 0.5))
        if snap_ms:                                   # lock onto the sharpest joint change nearby
            w = int(snap_ms / 1000 / HOP)
            s0, s1 = max(0, t - w), min(T, t + w + 1)
            t = s0 + int(np.argmax(prep.C[s0:s1]))
        ends[k], starts[k + 1] = t * HOP - GAP / 2, t * HOP + GAP / 2
    # clip edges: the first token starts after the quiet run before its first letter; the last token
    # ends before the quiet run after its last letter (same local-background threshold)
    f0 = prep.peak_first[0]
    l1 = prep.peak_last[-1]
    if clip_anchor_ms:                   # same letter-anchored landmarks at the clip edges
        w = int(clip_anchor_ms / 1000 / HOP); pad = int(0.010 / HOP)
        a0, b0 = max(0, f0 - w), min(T, f0 + pad)
        starts[0] = (a0 + int(np.argmax(prep.slope[a0:b0]))) * HOP if b0 > a0 else 0.0
        a0, b0 = max(0, l1 - pad), min(T, l1 + w)
        ends[-1] = (a0 + int(np.argmin(prep.slope[a0:b0]))) * HOP if b0 > a0 else (T - 1) * HOP
    else:
        run = _silent_run(prep, 0, f0, theta_db)
        starts[0] = run[1] * HOP if run and run[1] < f0 else 0.0
        run = _silent_run(prep, l1, T, theta_db)
        ends[-1] = run[0] * HOP if run and run[0] > l1 else (T - 1) * HOP
    out = []
    for k in range(n):
        s, e = starts[k], ends[k]
        if e <= s:
            e = s + 0.010
        out.append({"start": float(s), "end": float(e)})
    return out


# ── two passes: properly spoken words first, soft tokens fill the gaps (the user's rule) ──────────
FILLERS = {"uh", "um", "uhm", "umm", "uhh", "hmm", "hm", "mm", "mmm", "mhm", "ah", "er", "erm", "eh"}


def is_soft(tok, cutoffs=False):
    """fillers, '(())' / '((...))' (unintelligible / uncertain), optionally cut-offs 'x-'"""
    t = tok.strip().lower()
    if t.startswith("((") and t.endswith("))"):
        return True
    if t.strip(".,!?") in FILLERS:
        return True
    return cutoffs and t.endswith("-")


def align_two_pass(preps, texts, soft="off", **params):
    """preps: {"full": Prepared(all tokens), "anchors": Prepared(non-soft tokens), "anchors+cut": ...}.
    Pass 1 aligns only the properly spoken words. Pass 2, per stretch of soft tokens between real words A and
    B: speech islands (speech bounded by word-referenced silences >= min_pause) from A's last-letter peak to
    B's first-letter peak (peaks searched inside each word's own span). A's island holds A's peak, B's island
    holds B's; the islands strictly between them are the soft tokens (A ends where its island ends, B starts
    where its island starts). No island between -> the soft tokens are fused to A's tail or B's head and
    split off where that word's own letters finish / start (P(A finished) / P(B started) medians).
    Several soft tokens split their span at silences inside it, else evenly. Clip-edge stretches: the open
    side is the first / last speech in the clip."""
    if soft == "off" or soft not in preps:
        return align(preps["full"], **params)
    if soft.startswith("wild"):                            # soft tokens aligned as wildcards in their slots
        return align(preps[soft], **params)
    cut = soft == "anchors+cut"
    anchors = [i for i, t in enumerate(texts) if not is_soft(t, cut)]
    if not anchors or len(anchors) == len(texts):
        return align(preps["full"], **params)
    sub = preps[soft]
    A = align(sub, **params)                               # also leaves sub.use(unit) active
    theta = params.get("theta_db", 20.0); min_pause = params.get("min_pause", 0.03)
    T, loud = sub.T, sub.loud
    out = [None] * len(texts)
    for j, i in enumerate(anchors):
        out[i] = dict(A[j])
    fr = lambda t: int(np.clip(round(t / HOP), 0, T - 1))
    med = lambda cdf: int(np.searchsorted(cdf, 0.5))

    def body(i):                                            # loudness of a word's body (90th percentile)
        a, b = fr(out[i]["start"]), fr(out[i]["end"])
        return np.percentile(loud[a:max(b, a + 1)], 90)

    groups, i = [], 0                                      # maximal runs of soft tokens
    while i < len(texts):
        if out[i] is None:
            j = i
            while j < len(texts) and out[j] is None:
                j += 1
            groups.append((i, j)); i = j
        else:
            i += 1
    for g0, g1 in groups:
        left, right, n_soft = g0 - 1, g1, g1 - g0
        kl = anchors.index(left) if left >= 0 else None
        kr = anchors.index(right) if right < len(texts) else None
        # the real words' own letter peaks, searched only inside their pass-1 spans
        def peak(kind, k, i):
            a, b = fr(out[i]["start"]), max(fr(out[i]["end"]), fr(out[i]["start"]) + 1)
            w = sub.edge[kind][k][a:b]
            return a + int(np.argmax(w)) if len(w) else a
        pa = peak("last", kl, left) if kl is not None else 0
        pb = peak("first", kr, right) if kr is not None else T - 1
        ra, rb = min(pa, pb), max(pa, pb) + 1
        ref = min(body(x) for x in (left, right) if 0 <= x < len(texts))
        speech = loud[ra:rb] >= ref - theta
        # speech islands: speech runs, merging gaps shorter than min_pause
        isl = [[ra + a, ra + b] for a, b in _runs(speech)]
        merged = []
        for a, b in isl:
            if merged and (a - merged[-1][1]) * HOP < min_pause:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        # A's island holds A's last-letter peak, B's island holds B's first-letter peak
        ia = next((m for m, (a, b) in enumerate(merged) if a <= pa < b + 1), 0) if kl is not None else -1
        ib = next((m for m, (a, b) in enumerate(merged) if a <= pb < b + 1), len(merged) - 1) if kr is not None else len(merged)
        between = merged[ia + 1:ib] if merged else []
        if kl is not None and kr is not None:
            cA, cB = sub.ab[kl]
            a_let, b_let = int(np.clip(med(cA), ra, rb)), int(np.clip(med(cB), ra, rb))
        else:
            a_let, b_let = ra, rb
        if between:                                   # the soft tokens are the islands between the words
            s_start, s_end = between[0][0], between[-1][1]
            a_end = merged[ia][1] if 0 <= ia < len(merged) else s_start
            b_start = merged[ib][0] if 0 <= ib < len(merged) else s_end
        else:                                         # fused to A's tail or B's head: split at the letters
            tail = (merged[ia][1] - a_let) if 0 <= ia < len(merged) else -1
            head = (b_let - merged[ib][0]) if 0 <= ib < len(merged) else -1
            if kl is None or (kr is not None and head >= tail):
                s0_ = merged[ib][0] if 0 <= ib < len(merged) else ra
                s_start, s_end, b_start = s0_, max(b_let, s0_ + n_soft), max(b_let, s0_ + n_soft)
                a_end = merged[ia][1] if 0 <= ia < len(merged) else s_start
            else:
                e0_ = merged[ia][1] if 0 <= ia < len(merged) else rb
                s_start, s_end, a_end = min(a_let, e0_ - n_soft), e0_, min(a_let, e0_ - n_soft)
                b_start = merged[ib][0] if 0 <= ib < len(merged) else s_end
        if kl is None:
            a_end = s_start
        if kr is None:
            b_start = s_end
        a_end, s_start = min(a_end, s_start), max(a_end, s_start)
        s_end, b_start = min(s_end, b_start), max(s_end, b_start)
        s_end = max(s_end, s_start + n_soft)
        if left >= 0:
            out[left]["end"] = a_end * HOP
        if right < len(texts):
            out[right]["start"] = b_start * HOP
        inner = [(a, b) for a, b in _runs(~(loud[s_start:s_end] >= ref - theta)) if (b - a) * HOP >= min_pause]             if s_end > s_start + 1 else []
        if n_soft > 1 and len(inner) >= n_soft - 1:
            cuts = sorted(sorted(inner, key=lambda r: r[0] - r[1])[:n_soft - 1])
            bounds = [(s_start, s_start + cuts[0][0])] +                      [(s_start + cuts[m][1], s_start + cuts[m + 1][0]) for m in range(n_soft - 2)] +                      [(s_start + cuts[-1][1], s_end)]
        else:
            edges = np.linspace(s_start, s_end, n_soft + 1).astype(int)
            bounds = [(edges[m], edges[m + 1]) for m in range(n_soft)]
        for m, (a, b) in enumerate(bounds):
            out[g0 + m] = {"start": float(a * HOP), "end": float(max(b, a + 1) * HOP)}
    for k in range(len(out)):
        if out[k]["end"] <= out[k]["start"]:
            out[k]["end"] = out[k]["start"] + 0.010
    return out
