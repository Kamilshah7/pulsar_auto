"""
Coarse word placement from a pretrained FRAME-CLASSIFICATION phone model (charsiu/en_w2v2_fc_10ms):
unlike CTC models it was trained to label every 10 ms frame with its phone, so its phone edges sit on
the real boundaries instead of on arbitrary spikes. Used as-is (no training).

Transcript -> ARPAbet (g2p_en: CMUdict + its own letter-to-sound fallback), stress removed. Viterbi
forced alignment over the 10 ms frames: every phone >= 1 frame, optional [SIL] before/between/after
words; '(())' and one-letter cut-offs are a wildcard phone (best non-silence phone per frame).
Output per token: (start, end) in seconds, and whether a silence separates it from the next token.
"""
import re

import numpy as np

FRAME, FRAME_OFF = 0.010, 0.0125          # conv strides 5*2*2*2*2*2*1 = 160 samples; receptive field 400
VOCAB = {"[SIL]": 0, "NG": 1, "F": 2, "M": 3, "AE": 4, "R": 5, "UW": 6, "N": 7, "IY": 8, "AW": 9, "V": 10, "UH": 11,
         "OW": 12, "AA": 13, "ER": 14, "HH": 15, "Z": 16, "K": 17, "CH": 18, "W": 19, "EY": 20, "ZH": 21, "T": 22,
         "EH": 23, "Y": 24, "AH": 25, "B": 26, "P": 27, "TH": 28, "DH": 29, "AO": 30, "G": 31, "L": 32, "JH": 33,
         "OY": 34, "SH": 35, "D": 36, "AY": 37, "S": 38, "IH": 39}
SIL, WILD = 0, -1
_G2P = None


def token_phones(tokens):
    """per token: list of ARPAbet ids (WILD for unknown), plus the phone strings"""
    global _G2P
    if _G2P is None:
        from g2p_en import G2p
        _G2P = G2p()
    ids, strs = [], []
    for tok in tokens:
        w = re.sub(r"^\(\((.*)\)\)$", r"\1", tok.strip())
        cut = w.endswith("-"); w = w.rstrip("-")
        letters = re.sub(r"[^A-Za-z]", "", w)
        if not re.search(r"[A-Za-z0-9]", w) or (cut and len(letters) <= 1):
            ids.append([WILD]); strs.append("*"); continue
        ph = [re.sub(r"\d", "", p) for p in _G2P(w) if p.strip() and re.sub(r"\d", "", p) in VOCAB]
        ids.append([VOCAB[p] for p in ph] or [WILD]); strs.append(" ".join(ph) or "*")
    return ids, strs


def viterbi(logp, token_ids):
    """logp (T, 42) log posteriors. States: [SIL] w1p1 .. w1pn [SIL] w2p1 .. [SIL]; SIL states optional.
    Returns per token (first_frame, last_frame) and per gap (sil_first, sil_last) or None."""
    T = logp.shape[0]
    best_speech = np.max(logp[:, 1:40], axis=1)
    states, kind, owner = [], [], []                 # kind: 0 = SIL, 1 = phone
    for k, ph in enumerate(token_ids):
        states.append(SIL); kind.append(0); owner.append(k - 1)          # silence before token k
        for p in ph:
            states.append(p); kind.append(1); owner.append(k)
    states.append(SIL); kind.append(0); owner.append(len(token_ids) - 1)
    S = len(states); kind = np.array(kind)
    em = np.empty((T, S))
    for s, p in enumerate(states):
        em[:, s] = best_speech if p == WILD else logp[:, p]
    # transitions: stay, +1; from a phone to the next phone skipping the optional SIL (+2 when s+1 is SIL)
    NEG = -1e18
    delta = np.full(S, NEG); delta[0] = em[0, 0]; delta[1] = em[0, 1]
    back = np.zeros((T, S), dtype=np.int32)
    skip_ok = np.zeros(S, bool)
    skip_ok[2:] = (kind[1:-1] == 0) & (kind[2:] == 1)                     # s-2 -> s over an optional SIL
    idx = np.arange(S)
    for t in range(1, T):
        stay = delta
        step = np.r_[NEG, delta[:-1]]
        jump = np.where(skip_ok, np.r_[NEG, NEG, delta[:-2]], NEG)
        cand = np.stack([stay, step, jump])
        arg = np.argmax(cand, 0)
        delta = cand[arg, idx] + em[t]
        back[t] = idx - arg
    s = S - 1 if delta[S - 1] >= delta[S - 2] else S - 2
    path = np.empty(T, dtype=np.int32)
    for t in range(T - 1, -1, -1):
        path[t] = s; s = back[t, s]
    n = len(token_ids)
    first, last = [None] * n, [None] * n
    gaps = [None] * (n + 1)
    for t, s in enumerate(path):
        o = owner[s]
        if kind[s] == 1:
            first[o] = t if first[o] is None else first[o]; last[o] = t
        else:
            g = o + 1                                                  # silence before token o+1
            gaps[g] = (t, t) if gaps[g] is None else (gaps[g][0], t)
    return first, last, gaps


def word_times(logp, token_ids):
    """per token (start, end) seconds and, per boundary k, the silence (start, end) between k and k+1"""
    first, last, gaps = viterbi(logp, token_ids)
    edge = lambda f: f * FRAME + FRAME_OFF - FRAME / 2                  # frame f spans centre +- 5 ms
    starts = [edge(f) if f is not None else None for f in first]
    ends = [edge(l + 1) if l is not None else None for l in last]
    sil = [(edge(g[0]), edge(g[1] + 1)) if g else None for g in gaps[1:-1]]
    return starts, ends, sil
