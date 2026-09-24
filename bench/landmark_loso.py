"""
Leave-one-set-out landmark search across ALL gold sets.

For each group of continuous-speech pairs (a leaf, or a leaf split by sound class) and each
acoustic landmark: learn offset = median(gold - landmark) on the corrected pairs of all sets
but one, apply it to the held-out set's corrected pairs, rotate. A candidate must beat the
current output on EVERY fold it can be scored on. Collateral = how far it moves boundaries
the human verified/accepted where ours currently matches theirs (<=2ms).

    python bench/landmark_loso.py --out bench/prov_runs/loso.json [--split]
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

HUMAN = ("human", "dragged")
MIN_TRAIN, MIN_FOLD = 8, 3


def sets():
    b049 = glob.glob(os.path.join(HERE, "gold_sets", "*bundle_049"))[0]
    b026 = glob.glob(os.path.join(HERE, "gold_sets", "*bundle_026"))[0]
    return [("026", b026, os.path.join(HERE, "prov_runs", "b026_branches.json")),
            ("049", b049, os.path.join(HERE, "prov_runs", "b049_branches_v3.json")),
            ("old14", None, os.path.join(HERE, "prov_runs", "old14_branches_v3.json"))]


def letters(w):
    return re.sub(r"[^a-z]", "", str(w).lower())


def coda(w):
    s = letters(w)
    if len(s) == 1 and s not in ("a", "i"): return "letter"
    if not s: return "?"
    if s.endswith(("ng", "m", "n")): return "nasal"
    if s.endswith(("sh", "ch", "th", "s", "z", "f", "v", "x", "ce", "se", "ve")): return "fric"
    if s[-1] in "pbtdkg" or s.endswith("ck"): return "stop"
    if s[-1] in "lr" or s.endswith(("re", "le")): return "liquid"
    return "vowel"


def onset(w):
    s = letters(w)
    if len(s) == 1 and s not in ("a", "i"): return "letter"
    if not s: return "?"
    if s.startswith(("th", "sh", "ch", "wh")): return {"th": "dh/th", "sh": "fric", "ch": "fric", "wh": "glide"}[s[:2]]
    c = s[0]
    if c in "aeiou": return "vowel"
    if c == "h": return "h"
    if c in "wy": return "glide"
    if c in "lr": return "liquid"
    if c in "mn": return "nasal"
    if c in "pbtdkg": return "stop"
    return "fric"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", action="store_true", help="also split leaves by (w1 coda, w2 onset) class")
    args = ap.parse_args()

    rows = []
    for name, set_dir, rows_p in sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        for r in json.load(open(rows_p, encoding="utf-8")):
            if r["gold_gap_ms"] > 5 or r.get("p_start") is None:
                continue
            r["_set"] = name
            r["_fixed"] = r["prov_w1end"] in HUMAN and r["prov_w2start"] in HUMAN
            r["_kept"] = (r["prov_w1end"] not in HUMAN and r["prov_w2start"] not in HUMAN
                          and abs(LS.cur(r) - LS.gold(r)) * 1000 <= 2)
            if not (r["_fixed"] or r["_kept"]):
                continue
            r["_lm"] = LS.landmarks(r, LS.feats(RGB.find_wav(gt[r["clip"]]["filename"])))
            r["_leaf"] = f'{r["branch"]}|{r["leaf_line"]}'
            r["_cls"] = f'{coda(r["w1"])}>{onset(r["w2"])}'
            rows.append(r)
    set_names = [s[0] for s in sets()]

    groups = collections.defaultdict(list)
    for r in rows:
        groups[("leaf", r["_leaf"])].append(r)
        if args.split:
            groups[("leaf+class", f'{r["_leaf"]} :: {r["_cls"]}')].append(r)
            groups[("class", r["_cls"])].append(r)

    results = []
    for gkey, G in groups.items():
        F = [r for r in G if r["_fixed"]]
        if len(F) < MIN_TRAIN + MIN_FOLD:
            continue
        K = [r for r in G if r["_kept"]]
        base = {s: [abs(LS.cur(r) - LS.gold(r)) * 1000 for r in F if r["_set"] == s] for s in set_names}
        lms = sorted({k for r in F for k in r["_lm"]})
        for lm in lms:
            fold, all_pred = {}, []
            for s in set_names:
                test = [r for r in F if r["_set"] == s and lm in r["_lm"]]
                train = [r for r in F if r["_set"] != s and lm in r["_lm"]]
                if len(test) < MIN_FOLD or len(train) < MIN_TRAIN:
                    continue
                off = float(np.median([LS.gold(r) - r["_lm"][lm] for r in train]))
                e = [abs(r["_lm"][lm] + off - LS.gold(r)) * 1000 for r in test]
                b = [abs(LS.cur(r) - LS.gold(r)) * 1000 for r in test]
                fold[s] = {"n": len(e), "mae": float(np.mean(e)), "base": float(np.mean(b)),
                           "w5": float(np.mean(np.array(e) <= 5) * 100), "base_w5": float(np.mean(np.array(b) <= 5) * 100),
                           "off_ms": off * 1000}
            if len(fold) < 2:
                continue
            off_all = float(np.median([LS.gold(r) - r["_lm"][lm] for r in F if lm in r["_lm"]]))
            moves = [abs(r["_lm"][lm] + off_all - LS.cur(r)) * 1000 for r in K if lm in r["_lm"]]
            wins_all = all(v["mae"] < v["base"] for v in fold.values())
            results.append({"group": gkey, "landmark": lm, "offset_ms": off_all * 1000, "folds": fold,
                            "wins_all_folds": wins_all,
                            "pooled_mae": float(np.average([v["mae"] for v in fold.values()], weights=[v["n"] for v in fold.values()])),
                            "pooled_base": float(np.average([v["base"] for v in fold.values()], weights=[v["n"] for v in fold.values()])),
                            "n_fixed": len(F), "n_kept": len(K),
                            "kept_move_med": float(np.median(moves)) if moves else 0.0,
                            "kept_move_gt10": int(sum(m > 10 for m in moves))})
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=1)

    win = sorted([x for x in results if x["wins_all_folds"]], key=lambda x: x["pooled_mae"] - x["pooled_base"])
    print(f"{len(rows)} pairs ({sum(r['_fixed'] for r in rows)} corrected, {sum(r['_kept'] for r in rows)} kept) | "
          f"{len(results)} (group, landmark) candidates | {len(win)} win on every fold\n")
    print(f"{'group':<44}{'landmark':<14}{'off':>7} | {'LOSO MAE base->new':>19} | per-fold w5 base->new              | kept n, move med, >10")
    seen = set()
    for x in win:
        g = x["group"][1]
        if g in seen: continue
        seen.add(g)
        folds = "  ".join(f"{s}:{v['base_w5']:.0f}->{v['w5']:.0f}%" for s, v in x["folds"].items())
        print(f"{g[:43]:<44}{x['landmark']:<14}{x['offset_ms']:+7.1f} | {x['pooled_base']:7.1f} -> {x['pooled_mae']:6.1f}   | {folds:<35}| "
              f"{x['n_kept']:>4}, {x['kept_move_med']:5.1f}, {x['kept_move_gt10']}")


if __name__ == "__main__":
    main()
