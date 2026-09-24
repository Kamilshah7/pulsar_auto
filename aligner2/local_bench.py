"""
Local (CPU) benchmark for the rule-based boundary stage (aligner2/refine.py).

Input per clip: the cached signals (bench/cache/aligner2/<key>_98e63a51.npz via bench/tools/clip_cache_map.json),
the v16 coarse word times and the per-token ARPAbet (bench/prov_runs/aligner2_v16.json). No GPU, no training:
the rules are fixed; the gold sets only score them.

Development sets: 009 and 026 (read in full in bench/cache/aligner2/fullread/NOTES.md). Held-out set: 049 --
never read boundary by boundary; score it only with --test.

    python -m aligner2.local_bench                 # v16 vs refined on 009 + 026
    python -m aligner2.local_bench --pairs         # + error by phone-class pair
    python -m aligner2.local_bench --test          # also the held-out 049 set
    python -m aligner2.local_bench --dump out.json # refined predictions
    python -m aligner2.local_bench --audit         # also score against the audited gold (aligner2/gold_audit.py)
"""
import argparse
import collections
import json
import os

import numpy as np

from aligner2 import refine
from aligner2.benchmark import BENCH, _kind, evaluate, load_sets, report

ROOT = os.path.dirname(BENCH)
V16 = os.path.join(BENCH, "prov_runs", "aligner2_v16.json")
CACHE = os.path.join(BENCH, "cache", "aligner2")
MAP = os.path.join(BENCH, "tools", "clip_cache_map.json")


LEX_CACHE = os.path.join(CACHE, "lexical_peaks_letter4.json")


def clip_inputs(sets):
    """[(gold clip, signals, arpabet, v16 coarse, lexical peaks)]"""
    R = json.load(open(V16))
    M = json.load(open(MAP))
    lexc = json.load(open(LEX_CACHE)) if os.path.exists(LEX_CACHE) else {}
    out, dirty = [], False
    for c in load_sets(sets):
        key = f"{c['set']}|{int(c['clip'])}"
        zf = np.load(os.path.join(CACHE, M[f"{c['set']}_{int(c['clip']):02d}"]["npz"]))
        z = {k: zf[k] for k in zf.files}
        if key not in lexc:
            lexc[key] = refine.lexical_peaks(z, [t["text"] for t in c["tokens"]]); dirty = True
        out.append((c, z, R["arpabet"][key], R["grid_preds"][0][key], lexc[key]))
    if dirty:
        json.dump(lexc, open(LEX_CACHE, "w"))
    return out


def pair_table(clips, preds, arpa):
    rows = []
    for c in clips:
        toks, p, ar = c["tokens"], preds[(c["set"], c["clip"])], arpa[(c["set"], c["clip"])]
        for j, (g, q) in enumerate(zip(toks, p)):
            for side in ("start", "end"):
                kind = _kind(toks, j, side)
                if kind == "edge":
                    continue
                k = j if side == "end" else j - 1
                pair = f"{refine.pclass(refine.last_phone(ar[k]))}>{refine.pclass(refine.first_phone(ar[k + 1]))}"
                rows.append((kind, side, pair, g[f"{side}_human"], (q[side] - g[side]) * 1000))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--pairs", action="store_true")
    ap.add_argument("--dump")
    ap.add_argument("--rules", help="comma-separated rule names to enable (default: refine.RULES)")
    ap.add_argument("--sides", action="store_true", help="pause ends / starts separately")
    ap.add_argument("--audit", action="store_true", help="also score against the audited gold")
    args = ap.parse_args()
    if args.rules is not None:
        refine.RULES.clear(); refine.RULES.update(r for r in args.rules.split(",") if r)
    sets = ("009", "026", "049") if args.test else ("009", "026")
    data = clip_inputs(sets)
    C = [c for c, *_ in data]
    base = {(c["set"], c["clip"]): coarse for c, z, ar, coarse, lx in data}
    arpa = {(c["set"], c["clip"]): ar for c, z, ar, coarse, lx in data}
    new = {}
    for c, z, ar, coarse, lx in data:
        new[(c["set"], c["clip"])] = refine.refine(z, [t["text"] for t in c["tokens"]], ar, coarse, lex=lx)
    golds = [("", C)]
    if args.audit:
        from aligner2 import gold_audit
        CA, log = gold_audit.audited(data)
        golds.append((f" -- AUDITED gold ({len(log)} boundaries corrected)", CA))
    for (gname, G), (name, P) in [(g, p) for g in golds for p in (("v16 (coarse input)", base), ("refined", new))]:
        name += gname
        S, rows = evaluate(G, P, ear={})
        print(report(S, name))
        if args.sides:
            for kind in ("pause", "edge", "cont"):
                for side in ("end", "start"):
                    e = np.array([r["err"] for r in rows if r["kind"] == kind and r["side"] == side])
                    h = np.array([r["err"] for r in rows if r["kind"] == kind and r["side"] == side and r["human"]])
                    if len(e):
                        print(f"   {kind:5} {side:5} n={len(e):4} MAE {np.abs(e).mean():5.1f} med {np.median(np.abs(e)):5.1f}"
                              f" bias {e.mean():+6.1f} w10 {np.mean(np.abs(e) <= 10) * 100:3.0f}%"
                              + (f" | H n={len(h)} MAE {np.abs(h).mean():5.1f} bias {h.mean():+6.1f}" if len(h) else ""))
    if args.pairs:
        rb, rn = pair_table(C, base, arpa), pair_table(C, new, arpa)
        g = collections.defaultdict(lambda: [[], []])
        for (kind, side, pair, h, e), (_, _, _, _, e2) in zip(rb, rn):
            g[(kind, side, pair)][0].append(e); g[(kind, side, pair)][1].append(e2)
        print(f"\n{'kind':5} {'side':5} {'pair':11} {'n':>4} {'v16':>6} {'new':>6} {'bias16':>7} {'biasN':>7}")
        for key, (a, b) in sorted(g.items(), key=lambda kv: -np.abs(kv[1][0]).sum())[:45]:
            a, b = np.array(a), np.array(b)
            print(f"{key[0]:5} {key[1]:5} {key[2]:11} {len(a):4} {np.abs(a).mean():6.1f} {np.abs(b).mean():6.1f}"
                  f" {a.mean():+7.1f} {b.mean():+7.1f}")
    if args.dump:
        json.dump({f"{k[0]}|{k[1]}": v for k, v in new.items()}, open(args.dump, "w"))


if __name__ == "__main__":
    main()
