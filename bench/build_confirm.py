"""
Build the confirmation round for the ear-target rules R1-R5 (candidate aligner vs live aligner).

Items: EVERY boundary the candidate moves by > 0.5 ms that the listener has never heard -- pairs
outside the first review (verified / untouched / accepted pairs, cascades through short tokens),
plus reviewed pairs whose new cut lands > 5 ms from every cut already judged there.

Each item gets BLIND options: the live cut, the candidate cut and the human's earlier boundary,
merged when closer than 3 ms. Identities (and which rule moved it) stay server-side.

    python bench/build_confirm.py      -> bench/review/confirm_ear/items_public.json, items_private.json
    REVIEW_DIR=bench/review/confirm_ear REVIEW_PORT=8766 python bench/review_server.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_review as AR  # noqa: E402
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

OUT = os.path.join(HERE, "review", "confirm_ear")
BASE, CAND = "{}_h13.json", "{}_ear.json"
RULE = {("case14", 1666): "R1", ("case4", 1248): "R2", ("case10", 1457): "R3", ("case10", 1451): "R4", ("case6", 1324): "R5"}
MOVE_MS, HEARD_MS, MERGE_MS, PAD = 0.5, 5.0, 3.0, 0.60
BADGE = {"human": "you corrected this pair", "dragged": "you corrected this pair", "verified": "you verified this pair",
         "untouched": "you left this pair untouched", "accepted": "you accepted this pair"}
ORDER = {"026": 0, "049": 1, "old14": 2}


def heard(a, t):
    cuts = [o["t"] for o in a["options"].values()] + ([a["manual"]] if a["manual"] is not None else [])
    return any(abs(c - t) * 1000 <= HEARD_MS for c in cuts)


def make_item(name, r, iid, old, new, wav, rule, kind, rnd):
    """one blind item: live cut, candidate cut, the human's earlier boundary (merged under MERGE_MS)"""
    cand = [("live", old), ("candidate", new), ("yours", LS.gold(r))]
    merged = []
    for c, t in sorted(cand, key=lambda x: x[1]):
        if merged and (t - merged[-1]["t"]) * 1000 < MERGE_MS:
            merged[-1]["cues"].append(c)
        else:
            merged.append({"t": t, "cues": [c]})
    rnd.shuffle(merged)
    letters = "ABCDEF"[:len(merged)]
    tmin, tmax = min(m["t"] for m in merged), max(m["t"] for m in merged)
    p1, p2 = r.get("prov_w1end"), r.get("prov_w2start")
    badge = BADGE.get(p1 if p1 == p2 else ("human" if "human" in (p1, p2) or "dragged" in (p1, p2) else p1), "")
    pub = {"id": iid, "set": name, "kind": "confirm", "badge": badge, "w1": r["w1"], "w2": r["w2"],
           "w1_start": r["w1_start"], "w2_end": r["w2_end"],
           "win_start": max(0.0, tmin - PAD - 0.05), "win_end": tmax + PAD + 0.05,
           "options": [{"key": k, "t": m["t"]} for k, m in zip(letters, merged)]}
    prv = {"set": name, "kind": kind or f"{p1}/{p2}", "clip": r["clip"], "pair": r["i"], "wav": wav, "rule": rule,
           "branch": r["branch"], "leaf_line": r["leaf_line"], "class": f"{LL.coda(r['w1'])}>{LL.onset(r['w2'])}",
           "gold": LS.gold(r), "live": old, "cand": new, "options": {k: m for k, m in zip(letters, merged)}}
    return pub, prv


def main():
    rnd = random.Random(55)
    reviewed = {a["id"]: a for a in AR.load()}
    public, private = [], {}
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        B = json.load(open(os.path.join(HERE, "prov_runs", BASE.format(name)), encoding="utf-8"))["preds"]
        C = json.load(open(os.path.join(HERE, "prov_runs", CAND.format(name)), encoding="utf-8"))["preds"]
        rows = {(r["clip"], r["i"]): r for r in json.load(open(rows_p, encoding="utf-8"))}
        cut = lambda P, clip, i: (P[clip][i]["end"] + P[clip][i + 1]["start"]) / 2
        n_new = n_rev = 0
        for clip in sorted(B, key=int):
            for i in range(len(B[clip]) - 1):
                old, new = cut(B, clip, i), cut(C, clip, i)
                if abs(new - old) * 1000 <= MOVE_MS:
                    continue
                iid = f"{name}-{clip}-{i}"
                if iid in reviewed and heard(reviewed[iid], new):
                    continue
                r = rows[(clip, i)]
                n_rev += iid in reviewed; n_new += iid not in reviewed
                rule = RULE.get((r["branch"], r["leaf_line"]), "cascade")
                pub, prv = make_item(name, r, iid, old, new, RGB.find_wav(gt[clip]["filename"]), rule,
                                     "reviewed" if iid in reviewed else None, rnd)
                public.append(pub); private[iid] = prv
        print(f"{name}: {n_new} never-heard pairs + {n_rev} reviewed pairs with an unheard new cut", flush=True)
    rnd.shuffle(public)
    public.sort(key=lambda p: ORDER[p["set"]])
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    n_opt = [len(p["options"]) for p in public]
    print(f"TOTAL {len(public)} items, {sum(n_opt)} options; single-option items (all cuts within {MERGE_MS:.0f} ms): "
          f"{sum(n == 1 for n in n_opt)}")


if __name__ == "__main__":
    main()
