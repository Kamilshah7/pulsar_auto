"""
Gold audit: gold boundaries that the signals clearly contradict (the user: "your data, when clear, is the source of
truth"). Fixed criteria, each confirmed by a 2 ms read of every dev case it flags (009 + 026: 16 of 16 clear; the list
is in bench/cache/aligner2/fullread/NOTES.md). Applied unchanged to the held-out set. The gold files are never edited:
this is an overlay; aligner2/local_bench.py --audit scores against it next to the original gold.

  C1  WEAK INITIAL FRICATIVE LEFT OUT. The gold gap before a fricative-initial word (not DH) is frication throughout
      (10th percentile zcr >= 0.2 and >= -10 dB above 4 kHz): no silence, the word's own F / TH / S. The old accepted
      golds leave it out (very|first, em|fill, happen|first, a|fear, question|for; this|film and benefit|from: a 43-45 ms
      "gap" inside unbroken frication 30 dB over the floor); every reviewer-moved case includes it.
      -> word k+1 starts where word k ends.
  C2  WORD-FINAL FRICATIVE CUT WHILE STILL LOUD. Before a pause, the frication runs on after the gold end (the next
      20 ms: zcr >= 0.3 in >= 80% of the frames and >= 15 dB over the local floor throughout): please, markets and
      is|just, race, miss, ridiculous, was: 50-120 ms of /s z/ left out (reviewers keep a fricative until it dies, R7).
      -> word k ends where the frication dies: zcr < max(0.15, half its level at the gold end) or < floor + 6 dB.
"""
import copy
import json
import os

import numpy as np

from aligner2 import refine as R


def audit_clip(clip, z, arpa):
    """-> [(token index, side, old, new, reason)]"""
    S = R.Sig(z)
    toks = clip["tokens"]
    out = []
    for k in range(len(toks) - 1):
        ge, gs = toks[k]["end"], toks[k + 1]["start"]
        if gs - ge <= 0.005:
            continue
        a, b = int(round(ge / R.HOP)), int(round(gs / R.HOP))
        A, B = R.last_phone(arpa[k]), R.first_phone(arpa[k + 1])
        if R.pclass(B) == "fric" and B != "DH" and gs - ge < 0.300 and b - a >= R.MS(10):
            if np.percentile(S.zcr[a:b], 10) >= 0.2 and np.percentile(S.hi[a:b], 10) >= -10.0:
                out.append((k + 1, "start", gs, ge, "C1 weak initial fricative left out"))
                continue
        if R.pclass(A) in ("fric", "aff") and gs - ge > 0.050:
            w = slice(a, min(b, a + R.MS(20)))
            if (S.zcr[w] >= 0.3).mean() >= 0.8 and (S.Ls[w] - S.floor[w]).min() >= 15.0:
                zr = np.median(S.zcr[max(0, a - R.MS(10)):a + 1])
                i = a
                while i < b and S.zcr[i] >= max(0.15, 0.5 * zr) and S.Ls[i] >= S.floor[i] + 6.0:
                    i += 1
                out.append((k, "end", ge, i * R.HOP, "C2 final fricative cut while still loud"))
    return out


def audited(data):
    """data = local_bench.clip_inputs(...) -> (clips with the audit applied, [corrections])"""
    clips, log = [], []
    for c, z, ar, coarse, lx in data:
        cc = copy.deepcopy(c)
        for j, side, old, new, why in audit_clip(c, z, ar):
            cc["tokens"][j][side] = new
            log.append({"set": c["set"], "clip": int(c["clip"]), "token": j, "text": c["tokens"][j]["text"],
                        "side": side, "gold": round(old, 4), "audited": round(new, 4), "reason": why})
        clips.append(cc)
    return clips, log


if __name__ == "__main__":
    from aligner2.local_bench import clip_inputs
    for sets in (("009", "026"), ("049",)):
        _, log = audited(clip_inputs(sets))
        for r in log:
            print(f"{r['set']}-{r['clip']:02d} {r['token']:>3} {r['text']:<12} {r['side']:5} {r['gold']:8.3f} -> "
                  f"{r['audited']:8.3f} ({(r['audited'] - r['gold']) * 1000:+5.0f} ms)  {r['reason']}")
