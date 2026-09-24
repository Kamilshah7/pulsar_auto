"""
Benchmark for the from-scratch aligner (aligner2): every clip with gold labels, every boundary scored,
plus every listening judgment from the review rounds.

Gold sets (bench/gold_sets/* frozen by bench/snapshot_gold.py, and the original 14 clips):
    009 golden8 / bundle_009, 026 golden 7 / bundle_026, 049 golden 6 / bundle_049, old14 original 14 clips.
EVERY gold boundary is truth (the user: boundaries left alone were already correct). `human` marks the
ones a person moved/added (status moved / no_injection_match; sub-ms values on old14), reported
separately. Gold is not assumed infallible: large disagreements are candidates for a listening check.

Ear judgments (bench/review/**/answers.jsonl): for a judged word pair, a cut (midpoint of w1 end
and w2 start) is a HIT when within 5 ms of a cut the listener accepted (option or hand-placed).

    from aligner2.benchmark import load_sets, evaluate, report
"""
import collections
import glob
import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "bench")
AUDIO_DIRS = [os.path.join(os.path.dirname(ROOT), "pulsar_auto_audio_restore"), os.path.join(ROOT, "audio")]
CONT_MAX_GAP_MS = 5.0
EAR_TOL_MS = 5.0
REVIEW_ROUNDS = ["", "confirm_ear", "confirm_ranker", "confirm_a"]
SET_DIRS = {"009": "*bundle_009", "026": "*bundle_026", "049": "*bundle_049"}


def _find_wav(name, extra=()):
    for d in list(extra) + AUDIO_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def _human(set_name, status, t):
    """did a person place this gold timestamp (vs leave it as it was)?"""
    if status is None:
        ms = t * 1000.0
        return abs(ms - round(ms)) > 1e-6
    return status in ("moved", "no_injection_match")


def load_sets(names=("009", "026", "049", "old14")):
    """[{set, clip, wav, tokens:[{text,start,end,start_human,end_human}]}]"""
    out = []
    for name in names:
        if name == "old14":
            gt, audio = json.load(open(os.path.join(BENCH, "gt_per_clip.json"), encoding="utf-8")), ()
        else:
            d = glob.glob(os.path.join(BENCH, "gold_sets", SET_DIRS[name]))[0]
            gt, audio = json.load(open(os.path.join(d, "gt_per_clip.json"), encoding="utf-8")), (os.path.join(d, "audio"),)
        for clip in sorted(gt, key=int):
            toks = []
            for t in gt[clip]["tokens"]:
                tt = {"text": t["text"], "start": t["start"], "end": t["end"]}
                for side in ("start", "end"):
                    tt[f"{side}_human"] = _human(name, t.get(f"{side}_status"), t[side])
                toks.append(tt)
            out.append({"set": name, "clip": clip, "wav": _find_wav(gt[clip]["filename"], audio), "tokens": toks})
    return out


def ear_judgments():
    """{ "set-clip-pair": [accepted cut times] } over every review round"""
    acc = collections.defaultdict(list)
    for r in REVIEW_ROUNDS:
        p = os.path.join(BENCH, "review", r, "answers.jsonl")
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            a = json.loads(line)
            if "disregard" in a.get("note", "").lower():
                continue
            acc[a["id"]] += [o["t"] for o in a["options"].values() if o["ok"]]
            if a.get("manual") is not None:
                acc[a["id"]].append(a["manual"])
    return {k: v for k, v in acc.items() if v}


def _kind(toks, j, side):
    if side == "end":
        if j == len(toks) - 1:
            return "edge"
        gap = (toks[j + 1]["start"] - toks[j]["end"]) * 1000.0
    else:
        if j == 0:
            return "edge"
        gap = (toks[j]["start"] - toks[j - 1]["end"]) * 1000.0
    return "cont" if gap <= CONT_MAX_GAP_MS else "pause"


def _summ(e):
    a = np.abs(np.asarray(e, float))
    if not a.size:
        return {"n": 0}
    return {"n": int(a.size), "mae": float(a.mean()), "med": float(np.median(a)), "w5": float(np.mean(a <= 5) * 100),
            "w10": float(np.mean(a <= 10) * 100), "w20": float(np.mean(a <= 20) * 100), "bias": float(np.mean(e))}


def evaluate(clips, preds, ear=None):
    """preds: {(set, clip): [{"start","end"}...]} 1:1 with gold tokens. Returns (summary, rows)."""
    ear = ear_judgments() if ear is None else ear
    rows, ear_rows = [], []
    for c in clips:
        p = preds.get((c["set"], c["clip"]))
        if p is None:
            continue
        toks = c["tokens"]
        assert len(p) == len(toks), (c["set"], c["clip"], len(p), len(toks))
        for j, (g, q) in enumerate(zip(toks, p)):
            for side in ("start", "end"):
                rows.append({"set": c["set"], "clip": c["clip"], "tok": j, "side": side, "kind": _kind(toks, j, side),
                                 "human": g[f"{side}_human"], "err": (q[side] - g[side]) * 1000.0})
        for j in range(len(toks) - 1):
            iid = f"{c['set']}-{c['clip']}-{j}"
            if iid in ear:
                cut = (p[j]["end"] + p[j + 1]["start"]) / 2
                ear_rows.append({"set": c["set"], "hit": any(abs(cut - t) * 1000 <= EAR_TOL_MS for t in ear[iid])})
    S = {}
    for s in sorted({r["set"] for r in rows}) + ["ALL"]:
        R = [r for r in rows if s == "ALL" or r["set"] == s]
        S[s] = {k: _summ([r["err"] for r in R if k == "all" or r["kind"] == k]) for k in ("all", "cont", "pause", "edge")}
        S[s]["human"] = _summ([r["err"] for r in R if r["human"]])
        S[s]["cont_human"] = _summ([r["err"] for r in R if r["kind"] == "cont" and r["human"]])
        E = [r["hit"] for r in ear_rows if s == "ALL" or r["set"] == s]
        S[s]["ear"] = {"n": len(E), "hit": float(np.mean(E) * 100) if E else None}
    return S, rows


def report(S, title=""):
    lines = [f"== {title}" if title else ""]
    lines.append(f"{'set':<6}{'kind':<11}{'n':>6}{'MAE':>8}{'med':>7}{'w5':>7}{'w10':>7}{'w20':>7}{'bias':>7}")
    for s, d in S.items():
        for k in ("all", "cont", "pause", "human", "cont_human"):
            v = d[k]
            if v.get("n"):
                lines.append(f"{s:<6}{k:<11}{v['n']:>6}{v['mae']:>8.1f}{v['med']:>7.1f}{v['w5']:>6.0f}%{v['w10']:>6.0f}%"
                             f"{v['w20']:>6.0f}%{v['bias']:>+7.1f}")
        if d["ear"]["n"]:
            lines.append(f"{s:<6}{'ear-hit':<11}{d['ear']['n']:>6}{d['ear']['hit']:>7.1f}%")
    return "\n".join(lines)
