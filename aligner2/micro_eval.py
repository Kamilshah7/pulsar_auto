"""
Shared harness for the micro-adjustment experiments (2026-09-27; the user: "test more approaches, plan first"): any
function that changes the rule stage's cuts is scored like aligner2/verify.py (gold MAE all / H per set, ear accepted /
rejected / distance / manual) PLUS a per-move test -- of the cuts it moved, how many went closer to the gold boundary /
to an accepted ear cut and how many further (a coin flip is 50 / 50). Choices on 009 + 026 (ear 026); 049 held out
(reject only); old14 a check.
"""
import collections
import json

import numpy as np

from aligner2.benchmark import load_sets
from aligner2.fc_nudge_eval import BASE, base_preds, line, score
from aligner2.verify import SETS, ear_items

VOWELS = set("AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW".split())


def pclass(p):
    return ("V" if p in VOWELS else "stop" if p in ("P", "B", "T", "D", "K", "G") else
            "fric" if p in ("F", "V", "TH", "DH", "S", "Z", "SH", "ZH", "HH", "CH", "JH") else
            "nas" if p in ("M", "N", "NG") else "liq" if p in ("L", "R") else "gl" if p in ("W", "Y") else "?")


def junction_type(arpa, k):
    a, b = (arpa[k] or "").split(), (arpa[k + 1] or "").split()
    return f"{pclass(a[-1])}>{pclass(b[0])}" if a and b else None


def continuous(p, k):
    """the rule stage leaves a 2 ms gap between touching words (82 % of gold-continuous junctions: 1-5 ms)"""
    return -0.001 <= p[k + 1]["start"] - p[k]["end"] <= 0.005


def move(p, k, t):
    """put junction k's cut (midpoint) at t, keeping its gap"""
    d = t - (p[k]["end"] + p[k + 1]["start"]) / 2
    p[k]["end"] += d; p[k + 1]["start"] += d


def setup():
    clips = load_sets(SETS)
    base, arpa = base_preds(clips)
    return clips, base, arpa, ear_items()


def per_move(clips, base, P, J):
    """{set: {test: [closer, further]}} over the junctions P moved (>= 1 ms). Tests: 'H' = the gold boundary where the
    user moved it by hand (the unmoved gold is older aligner output), 'hand' = the user's own cut in the ear review,
    'ear' = the nearest cut the user accepted by ear (often our own earlier cut: favours not moving)"""
    out = {s: {"H": [0, 0], "hand": [0, 0], "ear": [0, 0]} for s in SETS}

    def add(s, test, da, db):
        if abs(da - db) >= 0.001:
            out[s][test][0 if db < da else 1] += 1

    for c in clips:
        k = f"{c['set']}|{c['clip']}"; toks = c["tokens"]
        for j in range(len(toks) - 1):
            a = (base[k][j]["end"] + base[k][j + 1]["start"]) / 2; b = (P[k][j]["end"] + P[k][j + 1]["start"]) / 2
            if abs(a - b) < 0.001:
                continue
            if toks[j]["end_human"] or toks[j + 1]["start_human"]:
                g = (toks[j]["end"] + toks[j + 1]["start"]) / 2
                add(c["set"], "H", abs(a - g), abs(b - g))
            it = J.get(f"{c['set']}-{int(c['clip'])}-{j}")
            if it and it["man"]:
                m = float(np.median(it["man"])); add(c["set"], "hand", abs(a - m), abs(b - m))
            if it and it["acc"]:
                add(c["set"], "ear", min(abs(a - x) for x in it["acc"]), min(abs(b - x) for x in it["acc"]))
    return out


def report(tag, clips, base, P, J, sA=None):
    sA = sA or score(base, clips, J)
    m = per_move(clips, base, P, J)
    tot = {t: [sum(m[s][t][i] for s in SETS) for i in (0, 1)] for t in ("H", "hand", "ear")}
    mv = " | ".join(f"{s} " + " ".join(f"{t} {m[s][t][0]}/{m[s][t][1]}" for t in ("H", "hand", "ear") if sum(m[s][t]))
                    for s in SETS)
    print(line(tag, sA, score(P, clips, J)), flush=True)
    print(f"{'':24} moves closer/further: {mv}", flush=True)
    print(f"{'':24} share of moves that go closer, all sets: " + ", ".join(
        f"{t} {tot[t][0] / max(1, sum(tot[t])):.0%} (n={sum(tot[t])})" for t in ("H", "hand", "ear")), flush=True)
    return m
