"""
Explicit boundary rules by SOUND CLASS, scored against every listening judgment (all review rounds).

A rule = "cut at acoustic landmark X + fixed offset", optionally GATED (applied only when that cut is
within G ms of the current one). Groups: coda>onset pairs, then broader ones (w1 coda only, w2 onset
only, all pairs) to see whether a general rule exists.

Offset: the value that maximises hits on two gold sets; scored on the third (leave-one-set-out).
Hit = within 5ms of a cut the listener accepted; a cut nobody judged counts as a miss.
Kept only if it (a) wins on every scorable held-out set, (b) fixes more than it breaks on pairs
that were NOT human-corrected (the population: mostly already right), (c) net-fixes >= 3 pairs.

Also prints, per group, the landmark that the accepted cuts sit most consistently next to
(smallest IQR of accepted-cut minus landmark) -- descriptive, to read the acoustics.

    python bench/ear_class_rules.py
"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

ROUNDS = ["", "confirm_ear", "confirm_ranker"]
PRED = "{}_final.json"
SETS = ("026", "049", "old14")
TOL_MS = 5.0
GATES = (10, 20, 30, 40, None)
OFFSETS = np.arange(-0.060, 0.0601, 0.001)
MIN_N = 15


def judgments():
    J = collections.defaultdict(lambda: {"acc": [], "rej": [], "corrected": False})
    for r in ROUNDS:
        path = os.path.join(HERE, "review", r, "answers.jsonl")
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            a = json.loads(line)
            if "disregard" in a["note"].lower():
                continue
            j = J[a["id"]]
            for o in a["options"].values():
                (j["acc"] if o["ok"] else j["rej"]).append(o["t"])
            if a["manual"] is not None:
                j["acc"].append(a["manual"])
            j["corrected"] |= a["kind"] == "corrected"
    return J


def load():
    J = judgments()
    items = []
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        P = json.load(open(os.path.join(HERE, "prov_runs", PRED.format(name)), encoding="utf-8"))["preds"]
        for r in json.load(open(rows_p, encoding="utf-8")):
            iid = f"{name}-{r['clip']}-{r['i']}"
            if iid not in J or not J[iid]["acc"] or r.get("p_start") is None:
                continue
            live = (P[r["clip"]][r["i"]]["end"] + P[r["clip"]][r["i"] + 1]["start"]) / 2
            lm = LS.landmarks(r, LS.feats(RGB.find_wav(gt[r["clip"]]["filename"])))
            lm.pop("current", None)
            items.append({"id": iid, "set": name, "live": live, "acc": J[iid]["acc"], "corrected": J[iid]["corrected"],
                          "coda": LL.coda(r["w1"]), "onset": LL.onset(r["w2"]), "lm": lm, "w": f"{r['w1']}|{r['w2']}",
                          "lo": r["w1_start"] + 0.010, "hi": r["w2_end"] - 0.010,
                          "wav": RGB.find_wav(gt[r["clip"]]["filename"]), "p_start": r["p_start"], "p_end": r["p_end"]})
    return items


def hit(t, a):
    return any(abs(t - x) * 1000 <= TOL_MS for x in a["acc"])


def apply(a, lm, off, gate):
    if lm not in a["lm"]:
        return a["live"]
    t = a["lm"][lm] + off
    if not (a["lo"] < t < a["hi"]) or (gate is not None and abs(t - a["live"]) * 1000 > gate):
        return a["live"]
    return t


def tally(I, lm, off, gate):
    f = b = 0
    for a in I:
        o, n = hit(a["live"], a), hit(apply(a, lm, off, gate), a)
        f += (not o) and n; b += o and not n
    return f, b


def best_offset(train, lm, gate):
    best = None
    for off in OFFSETS:
        f, b = tally(train, lm, off, gate)
        if best is None or f - b > best[0]:
            best = (f - b, off)
    return best[1]


def search(I):
    lms = sorted({k for a in I for k in a["lm"]})
    found = []
    for lm in lms:
        for gate in GATES:
            folds, ok = {}, True
            for s in SETS:
                test = [a for a in I if a["set"] == s]; train = [a for a in I if a["set"] != s]
                if len(test) < 5 or len(train) < 10:
                    continue
                folds[s] = tally(test, lm, best_offset(train, lm, gate), gate)
                ok &= folds[s][0] > folds[s][1]
            if not ok or len(folds) < 2:
                continue
            off = best_offset(I, lm, gate)
            pf, pb = tally([a for a in I if not a["corrected"]], lm, off, gate)
            net = sum(f - b for f, b in folds.values())
            if pf < pb or net < 3:
                continue
            found.append((net, lm, gate, off, folds, (pf, pb)))
    return sorted(found, key=lambda x: -x[0])


def describe(I):
    rows = []
    for lm in sorted({k for a in I for k in a["lm"]}):
        g = [min(a["acc"], key=lambda x: abs(x - a["live"])) - a["lm"][lm] for a in I if lm in a["lm"]]
        if len(g) >= 10:
            rows.append((float(np.percentile(g, 75) - np.percentile(g, 25)) * 1000, lm, float(np.median(g)) * 1000))
    return sorted(rows)[:3]


def report(groups, label):
    print(f"\n=== {label} ===")
    for g, I in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(I) < MIN_N:
            continue
        base = np.mean([hit(a["live"], a) for a in I]) * 100
        d = describe(I)
        tight = ", ".join(f"{lm} {med:+.0f}ms (IQR {iqr:.0f})" for iqr, lm, med in d)
        res = search(I)
        print(f"{g:<22} n={len(I):>3} live hit {base:3.0f}% | accepted cuts sit nearest: {tight}")
        for net, lm, gate, off, folds, (pf, pb) in res[:2]:
            ft = "  ".join(f"{s} +{f}/-{b}" for s, (f, b) in folds.items())
            print(f"      RULE {lm}{off*1000:+.0f}ms {'ungated' if gate is None else f'gate {gate}ms'} | held-out {ft} | "
                  f"uncorrected pairs +{pf}/-{pb}")
        if not res:
            print("      (no rule passes)")


def main():
    items = load()
    print(f"{len(items)} judged pairs")
    by = lambda key: {k: [a for a in items if key(a) == k] for k in {key(a) for a in items}}
    report(by(lambda a: f"{a['coda']}>{a['onset']}"), "coda > onset")
    report(by(lambda a: f"{a['coda']}>*"), "word-1 ending")
    report(by(lambda a: f"*>{a['onset']}"), "word-2 start")
    report({"ALL": items}, "all pairs")


if __name__ == "__main__":
    main()
