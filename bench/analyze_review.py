"""Analyse bench/review/answers.jsonl: cue acceptability, self-consistency, tolerance, contexts."""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CUES = ["yours", "live", "pipe_start", "vowel_onset", "burst_end", "closure_start"]


def load():
    A = {}
    for line in open(os.path.join(HERE, "review", "answers.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            a = json.loads(line)
            A[a["id"]] = a
    return list(A.values())


def cue_rows(A):
    """one row per (item, cue): accepted?, distance from the human's earlier boundary"""
    rows = []
    for a in A:
        for k, o in a["options"].items():
            for c in o["cues"]:
                rows.append({"id": a["id"], "set": a["set"], "kind": a["kind"], "class": a["class"],
                             "leaf": f'{a["branch"]}|{a["leaf_line"]}', "cue": c, "ok": o["ok"],
                             "t": o["t"], "d_gold_ms": (o["t"] - a["gold"]) * 1000,
                             "manual": a["manual"], "merged": len(o["cues"]) > 1})
    return rows


def rate(xs):
    return (100 * np.mean(xs), len(xs)) if len(xs) else (float("nan"), 0)


if __name__ == "__main__":
    A = load()
    R = cue_rows(A)
    print(f"{len(A)} items\n")
    print("ACCEPTANCE RATE BY CUE  (share of items where that cue's cut was marked acceptable)")
    print(f"{'cue':<14}" + "".join(f"{s + '/' + k:>20}" for s in ("026", "049", "old14") for k in ("corrected", "verified")
                                   if not (s != "026" and k == "verified")))
    for c in CUES:
        cells = []
        for s in ("026", "049", "old14"):
            for k in ("corrected", "verified"):
                if s != "026" and k == "verified":
                    continue
                r, n = rate([x["ok"] for x in R if x["cue"] == c and x["set"] == s and x["kind"] == k])
                cells.append(f"{r:6.0f}% (n={n:>3})" if n else f"{'-':>14}")
        print(f"{c:<14}" + "".join(f"{x:>20}" for x in cells))
