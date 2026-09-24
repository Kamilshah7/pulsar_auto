"""
Learned boundary placement trained on the listener's ear (both review rounds).

For every judged pair, score candidate cuts on a 2ms grid around the live cut with a gradient-boosted
classifier ("would the listener accept a cut here?") and move the cut to the best-scoring candidate.
Features: distance to every acoustic landmark (landmark_search.landmarks), local acoustics at the
candidate (energy level/slopes, voicing, HF ratio, spectral flux and change, each relative to the
pair), the sound classes on each side, word/pipe durations, the aligner leaf.

Labels: candidate within POS_MS of a cut the listener accepted (option or hand-placed) = 1, farther
than NEG_MS from all of them = 0, the ring between is left out.
Evaluation is leave-one-set-out: train on two gold sets, place cuts on the third, hit = within 5ms
of an accepted cut (a cut nobody judged counts as a MISS, so this is conservative).

    python bench/ear_ranker.py
"""
import collections
import json
import os
import sys
import zlib

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_review as AR  # noqa: E402
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

SCR = os.environ.get("EAR_PRED_DIR", os.path.join(HERE, "prov_runs"))
PRED = os.environ.get("EAR_PRED_FMT", "{}_final.json")
GRID = np.arange(-0.080, 0.0501, 0.002)
POS_MS, NEG_MS, TOL_MS = 4.0, 8.0, 5.0
SETS = ("026", "049", "old14")
ROUNDS = [r for r in os.environ.get("EAR_ROUNDS", "confirm_ear,confirm_ranker").split(",") if r]
LMS = ["p_start", "p_mid", "p_end", "raw_w1_end", "raw_w2_start", "rms_dip", "rise3", "fall3", "rise10", "fall10",
       "rise20", "fall20", "vox_on", "vox_off", "hf_on", "hf_off", "flux_max", "burst_end", "closure_start", "spec_change"]
CLS = ["vowel", "stop", "fric", "nasal", "liquid", "glide", "h", "dh/th", "letter", "other"]


def answers():
    R = {}
    for path in [os.path.join(HERE, "review", "answers.jsonl")] + [os.path.join(HERE, "review", r, "answers.jsonl") for r in ROUNDS]:
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.strip():
                a = json.loads(line)
                if "disregard" not in a["note"].lower():
                    R.setdefault(a["id"], []).append(a)
    out = {}
    for iid, L in R.items():
        acc, rej = [], []
        for a in L:
            for o in a["options"].values():
                (acc if o["ok"] else rej).append(o["t"])
            if a["manual"] is not None:
                acc.append(a["manual"])
        out[iid] = (acc, rej, L[0]["kind"] if L[0]["kind"] in ("corrected", "verified") else "confirm")
    return out


def cls_id(x):
    return CLS.index(x) if x in CLS else len(CLS) - 1


def frame_feats(F, t):
    sr, hop, fl = F["sr"], F["hop"], F["fl"]
    k = int(np.clip((t * sr - fl / 2) / hop, 0, len(F["vox"]) - 1))
    s = int(np.clip(t * sr, 0, len(F["rms"]) - 1))
    db = lambda i: 20 * np.log10(F["rms"][int(np.clip(i, 0, len(F["rms"]) - 1))] + 1e-6)
    w = lambda ms: int(ms / 1000 * sr)
    kk = lambda dk: int(np.clip(k + dk, 0, len(F["vox"]) - 1))
    ls = F["lspec"]
    sc = float(np.linalg.norm(ls[max(0, k - 10):k].mean(0) - ls[k:k + 10].mean(0))) if 10 <= k < len(ls) - 10 else 0.0
    return [db(s), db(s + w(5)) - db(s - w(5)), db(s + w(15)) - db(s - w(15)), db(s + w(3)) - db(s - w(3)),
            F["vox"][k], F["vox"][kk(5)] - F["vox"][kk(-5)], F["vox"][kk(10)], F["vox"][kk(-10)],
            F["hf"][k], F["hf"][kk(5)] - F["hf"][kk(-5)], F["flux"][k], sc]


def build(unjudged=False):
    """judged pairs (labelled); with unjudged=True also every other continuous pair (no labels)"""
    A = answers()
    data = []
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        P = json.load(open(os.path.join(SCR, PRED.format(name)), encoding="utf-8"))["preds"]
        for r in json.load(open(rows_p, encoding="utf-8")):
            iid = f"{name}-{r['clip']}-{r['i']}"
            if r.get("p_start") is None or (iid not in A and not (unjudged and r["gold_gap_ms"] <= 5)):
                continue
            acc, rej, kind = A.get(iid, ([], [], "unjudged"))
            if iid in A and not acc:
                continue
            F = LS.feats(RGB.find_wav(gt[r["clip"]]["filename"]))
            lm = LS.landmarks(r, F)
            live = (P[r["clip"]][r["i"]]["end"] + P[r["clip"]][r["i"] + 1]["start"]) / 2
            lo, hi = r["w1_start"] + 0.010, r["w2_end"] - 0.010
            cands = [live + g for g in GRID if lo < live + g < hi] or [live]
            ref = frame_feats(F, live)
            X, y = [], []
            for t in cands:
                ff = frame_feats(F, t)
                x = [t - live] + [(t - lm[k]) if k in lm else np.nan for k in LMS] + ff + [a - b for a, b in zip(ff, ref)]
                x += [cls_id(LL.coda(r["w1"])), cls_id(LL.onset(r["w2"])), r["w2_end"] - r["w1_start"],
                      live - r["w1_start"], r["w2_end"] - live, r["p_end"] - r["p_start"], zlib.crc32(r["branch"].encode()) % 997]
                d = min(abs(t - a) for a in acc) * 1000 if acc else 0.0
                X.append(x); y.append(-1 if not acc else (1 if d <= POS_MS else (0 if d > NEG_MS else -1)))
            data.append({"id": iid, "set": name, "kind": kind, "live": live, "acc": acc, "rej": rej, "cands": cands,
                         "X": np.array(X, float), "y": np.array(y), "cls": f"{LL.coda(r['w1'])}>{LL.onset(r['w2'])}",
                         "w": f"{r['w1']}|{r['w2']}", "r": r, "wav": RGB.find_wav(gt[r["clip"]]["filename"])})
    return data


def hit(t, d):
    return any(abs(t - a) * 1000 <= TOL_MS for a in d["acc"])


def fit(train):
    X = np.vstack([d["X"][d["y"] >= 0] for d in train]); y = np.concatenate([d["y"][d["y"] >= 0] for d in train])
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                       categorical_features=[len(LMS) + 25, len(LMS) + 26], random_state=0)
    return m.fit(X, y)


def place(m, d, margin, cap_ms=None, p=None):
    p = m.predict_proba(d["X"])[:, 1] if p is None else p
    ok = [k for k, c in enumerate(d["cands"]) if cap_ms is None or abs(c - d["live"]) * 1000 <= cap_ms]
    i0 = int(np.argmin([abs(c - d["live"]) for c in d["cands"]]))
    ib = max(ok, key=lambda k: p[k])
    return d["cands"][ib] if p[ib] - p[i0] > margin else d["live"]


def main():
    data = [d for d in build() if d["acc"]]
    print(f"{len(data)} judged pairs, {sum(len(d['cands']) for d in data)} candidate cuts")
    for margin in (0.0, 0.1, 0.2, 0.3):
        tot = collections.Counter(); res = {}
        for s in SETS:
            test = [d for d in data if d["set"] == s]; m = fit([d for d in data if d["set"] != s])
            for d in test:
                d["_new"] = place(m, d, margin)
                b, n = hit(d["live"], d), hit(d["_new"], d)
                tot[(s, "live")] += b; tot[(s, "new")] += n; tot[(s, "n")] += 1
                tot[(s, "fixed")] += (not b) and n; tot[(s, "broken")] += b and not n
                tot[(d["kind"], "live")] += b; tot[(d["kind"], "new")] += n; tot[(d["kind"], "n")] += 1
        cells = "  ".join(f"{s}: {100*tot[(s,'live')]/tot[(s,'n')]:.0f}->{100*tot[(s,'new')]/tot[(s,'n')]:.0f}% "
                          f"(+{tot[(s,'fixed')]}/-{tot[(s,'broken')]})" for s in SETS)
        kinds = "  ".join(f"{k}: {100*tot[(k,'live')]/tot[(k,'n')]:.0f}->{100*tot[(k,'new')]/tot[(k,'n')]:.0f}%"
                          for k in ("corrected", "verified", "confirm") if tot[(k, "n")])
        print(f"margin {margin:.1f} | {cells} | {kinds}")
        res[margin] = [(d["id"], d["live"], d["_new"]) for d in data]
        json.dump(res, open(os.path.join(HERE, "prov_runs", f"ear_ranker_m{margin:.1f}.json"), "w"))


def held_out_moves(margin=0.3):
    """LOSO placement for EVERY continuous pair (judged or not): pairs of set s are placed by a model
    trained on the other two sets' judgments -- what a fresh bundle would get."""
    data = build(unjudged=True)
    out = []
    for s in SETS:
        m = fit([d for d in data if d["set"] != s and d["acc"]])
        for d in data:
            if d["set"] == s:
                out.append((d, place(m, d, margin)))
    return out


if __name__ == "__main__":
    main()
