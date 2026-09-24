"""
Render every clip's full signal set as text, for reading end to end.

10 ms per character; per signal 0..9 = the clip's 1st..99th percentile (probabilities: 0..1 linear).
Blocks of 2 s (200 chars). Rows: time ruler, gold words ('|' = gold start, words written from their
start, ']' = gold end where a gap follows), system tokens ('[' start, ']' end, 'X' both), err (system -
gold at each gold boundary, in 10 ms steps, 9 = 90+ ms), then the 15 signals.

    python -m aligner2.render_full bench/prov_runs/aligner2_v16.json   -> bench/cache/aligner2/fullread/*.txt
"""
import json
import os
import sys

import numpy as np

from aligner2.benchmark import load_sets
from aligner2.signals import CACHE, HOP, compute

STEP = 5                     # 5 x 2 ms = 10 ms per char
BLOCK = 200                  # chars per block (2 s)
SIGS = ["loudness", "periodicity", "log_f0", "flatness", "centroid", "mfcc_change", "formant_vel", "ssl_change",
        "glottal", "transient", "flux", "ctc_wordsep", "ctc_blank", "ctc_change", "speech_prob"]
PROB = {"ctc_wordsep", "ctc_blank", "speech_prob", "periodicity"}


def quant(x, name):
    if name in PROB:
        return np.clip((x * 9.999).astype(int), 0, 9)
    lo, hi = np.percentile(x, 1), np.percentile(x, 99)
    return np.clip(((x - lo) / (hi - lo + 1e-12) * 9.999).astype(int), 0, 9)


def main(run_json):
    R = json.load(open(run_json))
    sysp = R["grid_preds"][0] if R.get("grid_preds") else R["preds"]
    out_dir = os.path.join(CACHE, "fullread"); os.makedirs(out_dir, exist_ok=True)
    for c in load_sets():
        z = compute(c["wav"]); T = len(z["t"])
        n = T // STEP
        rows = {}
        for s in SIGS:
            x = z[s].astype(float)[: n * STEP].reshape(n, STEP).mean(1)
            rows[s] = "".join(str(v) for v in quant(x, s))
        gold = [" "] * n; syst = [" "] * n; err = [" "] * n
        toks = c["tokens"]; sp = sysp[f"{c['set']}|{c['clip']}"]
        for j, t in enumerate(toks):
            a, b = int(t["start"] / (HOP * STEP)), int(t["end"] / (HOP * STEP))
            if 0 <= a < n:
                txt = "|" + t["text"]
                for i, ch in enumerate(txt[: max(1, b - a)]):
                    if a + i < n:
                        gold[a + i] = ch
            nxt = toks[j + 1]["start"] if j + 1 < len(toks) else None
            if 0 <= b < n and (nxt is None or nxt - t["end"] > 0.005):
                gold[b] = "]"                                   # end shown only where a gap follows
            for side, pos in (("start", a), ("end", b)):          # error magnitude at the gold position, 10 ms/step
                if 0 <= pos < n:
                    e = min(9, int(abs(sp[j][side] - t[side]) * 100))
                    err[pos] = str(max(e, int(err[pos]) if err[pos] != " " else 0))
        for t in sp:
            a, b = int(t["start"] / (HOP * STEP)), int(t["end"] / (HOP * STEP))
            if 0 <= a < n:
                syst[a] = "[" if syst[a] == " " else "X"
            if 0 <= b < n:
                syst[b] = "]" if syst[b] == " " else "X"
        gold, syst, err = "".join(gold), "".join(syst), "".join(err)
        lines = [f"### {c['set']}-{c['clip']}  {T * HOP:.2f}s  ({len(c['tokens'])} tokens)  10 ms/char, signals 0-9 = clip 1st-99th pct"]
        for b0 in range(0, n, BLOCK):
            b1 = min(n, b0 + BLOCK)
            ruler = "".join("'" if (i % 10 == 0 and i % 100) else ("^" if i % 100 == 0 else " ") for i in range(b0, b1))
            lines.append(f"t={b0 / 100:6.2f}s  {ruler}")
            lines.append(f"{'gold':<14}{gold[b0:b1]}")
            lines.append(f"{'system':<14}{syst[b0:b1]}")
            lines.append(f"{'err x10ms':<14}{err[b0:b1]}")
            for s in SIGS:
                lines.append(f"{s:<14}{rows[s][b0:b1]}")
            lines.append("")
        open(os.path.join(out_dir, f"{c['set']}_{int(c['clip']):02d}.txt"), "w", encoding="utf-8").write("\n".join(lines))
        print(c["set"], c["clip"], n, "chars/row", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
