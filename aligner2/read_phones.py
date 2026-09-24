"""
Read the phoneme posteriors around every continuous gold boundary.

For boundary k: w1's last phone p1 and w2's first phone p2 (espeak phones from the engine's run output).
On the 2 ms grid around the gold cut, P(p1) and P(p2) from the xlsr-53 phoneme model (blank excluded,
renormalised over real phones), plus where each crosses 0.5 of its own local peak, and where
P(p2) - P(p1) changes sign. Grouped by manner class of p1 > p2 (IPA manner, general phonetics).

    python -m aligner2.read_phones bench/prov_runs/aligner2_v6.json
"""
import collections
import json
import sys

import numpy as np

from aligner2.benchmark import CONT_MAX_GAP_MS, load_sets
from aligner2.phones import vocab
from aligner2.signals import HOP, compute

VOWELS = set("aeiouæɐɑɒɔəɚɛɜɝɞɤɨɪɯɵʉʊʌʏøœɶy")
MANNER = [("stop", set("pbtdkgʔ")), ("affric", {"tʃ", "dʒ"}), ("fric", set("fvθðszʃʒhç")), ("nasal", set("mnŋ")),
          ("liquid", set("lɹɾɫ")), ("glide", set("wj"))]


def manner(ph):
    if not ph or ph == "*":
        return "?"
    base = ph.replace("ː", "").replace("ˈ", "").replace("ˌ", "")
    if base in {"tʃ", "dʒ"}:
        return "affric"
    if base[0] in VOWELS:
        return "vowel"
    for name, S in MANNER:
        if base[0] in S:
            return name
    return "other"


def main(run_json):
    R = json.load(open(run_json))
    V = vocab()
    rows = []
    for c in load_sets():
        ph = R["phones"].get(f"{c['set']}|{c['clip']}")
        if not ph:
            continue
        z = compute(c["wav"])
        if "phone_logp" not in z:
            continue
        P = np.exp(z["phone_logp"].astype(float)); P = P[:, 4:] / P[:, 4:].sum(1, keepdims=True)   # real phones only
        tf = np.arange(len(P)) * 0.020 + 0.0125
        g = c["tokens"]
        for j in range(len(g) - 1):
            if (g[j + 1]["start"] - g[j]["end"]) * 1000 > CONT_MAX_GAP_MS:
                continue
            p1s, p2s = ph[j].split(), ph[j + 1].split()
            if not p1s or not p2s or p1s[-1] not in V or p2s[0] not in V:
                continue
            i1, i2 = V[p1s[-1]] - 4, V[p2s[0]] - 4
            cut = (g[j]["end"] + g[j + 1]["start"]) / 2
            grid = cut + np.arange(-60, 61, 2) / 1000
            a = np.interp(grid, tf, P[:, i1]); b = np.interp(grid, tf, P[:, i2])
            d = b - a
            # where does p2 overtake p1 (closest sign change to the cut)?
            sc = np.where(np.diff(np.sign(d)) > 0)[0]
            cross = (grid[sc[np.argmin(np.abs(sc - 30))]] - cut) * 1000 if len(sc) else np.nan
            rows.append({"cls": f"{manner(p1s[-1])}>{manner(p2s[0])}", "p": f"{p1s[-1]}>{p2s[0]}", "a": a, "b": b,
                         "cross": cross, "human": g[j]["end_human"] or g[j + 1]["start_human"]})
    print(f"{len(rows)} continuous boundaries with phone posteriors\n")
    cols = list(range(0, 61, 3))
    print("MEAN P(w1 last phone) / P(w2 first phone) around the gold cut (ms):")
    print(f"{'':<22}" + "".join(f"{(c - 30) * 2:>6}" for c in cols))
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r["cls"]].append(r)
    for cls, G in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
        A = np.mean([r["a"] for r in G], 0); B = np.mean([r["b"] for r in G], 0)
        cr = np.array([r["cross"] for r in G]); cr = cr[~np.isnan(cr)]
        print(f"{cls:<16}n={len(G):<4}  crossover med {np.median(cr):+5.0f} ms  IQR [{np.percentile(cr, 25):+4.0f},{np.percentile(cr, 75):+4.0f}]"
              f"  |x|<=5 {np.mean(np.abs(cr) <= 5) * 100:3.0f}%  <=10 {np.mean(np.abs(cr) <= 10) * 100:3.0f}%")
        print(f"   {'P(w1 last)':<19}" + "".join(f"{A[c]:>6.2f}" for c in cols))
        print(f"   {'P(w2 first)':<19}" + "".join(f"{B[c]:>6.2f}" for c in cols))
    cr = np.array([r["cross"] for r in rows]); cr = cr[~np.isnan(cr)]
    print(f"\nALL: crossover found {len(cr)}/{len(rows)}; median {np.median(cr):+.0f} ms, IQR [{np.percentile(cr, 25):+.0f},{np.percentile(cr, 75):+.0f}],"
          f" |x|<=5 {np.mean(np.abs(cr) <= 5) * 100:.0f}%, <=10 {np.mean(np.abs(cr) <= 10) * 100:.0f}%, <=20 {np.mean(np.abs(cr) <= 20) * 100:.0f}%")


if __name__ == "__main__":
    main(sys.argv[1])
