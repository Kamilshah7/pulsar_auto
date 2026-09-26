"""
Build the listening round for the old / new HYBRID question (2026-09-26; the user: "any way we can hybridize the old and
new aligner to get even better results? especially on the ear test set").

On the ear data so far, the old aligner's cut was ALWAYS one of the options heard while the new aligner's (v25) cut often
was not, so the two cannot be compared where only the old one was heard. Where both were heard (176 junctions, cuts
> 2 ms apart) the new one wins 77 : 12. The one hybrid the data leave open is "take the old cut at junctions into a
th-word" (and possibly fric / vowel > stop): the old cut was accepted there 73 % of the time, the new cut was almost
never played. This round plays both, blind:

  target:  continuous junctions of class X>dh/th and fric / vowel>stop where the two cuts are > 3 ms apart and the new
           cut was never heard (no judged option or manual placement within 3 ms of it): per set a random 30 X>dh/th
           and 15 X>stop (of 211 / 124 such junctions)
  control: per set a random 15 of the other classes (reviewed junctions, the old cut heard, the new not, 3-40 ms
           apart): checks whether a preference for the old cut is general or specific to those classes

Options: the old (live) cut and the new (v25) cut, shuffled (A / B). 180 items.

Decision, fixed before listening: a class group switches to the old cut only if, among its items where exactly one of
the two cuts is accepted, the old one wins on 026 (dev) AND does not lose on 049 (held out, reject-only) or old14.

    python bench/build_confirm_hybrid.py    -> bench/review/confirm_hybrid/items_public.json, items_private.json
    REVIEW_DIR=bench/review/confirm_hybrid REVIEW_PORT=8767 python bench/review_server.py
"""
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402
from aligner2.benchmark import BENCH, REVIEW_ROUNDS  # noqa: E402

OUT = os.path.join(HERE, "review", "confirm_hybrid")
V25 = os.path.join(HERE, "prov_runs", "aligner2_v25.json")
TARGET = ("stop>dh/th", "fric>dh/th", "nasal>dh/th", "vowel>dh/th", "liquid>dh/th", "glide>dh/th",
          "fric>stop", "vowel>stop")
APART_MS, HEARD_MS, PAUSE_MS, PAD = 3.0, 3.0, 5.0, 0.60
PER_SET = {"dh/th": 30, "stop": 15, "control": 15}
CONTROL_MAX_MS = 40.0
ORDER = {"026": 0, "049": 1, "old14": 2}


def heard_cuts():
    """{id: [every cut heard in any round: options + manual placements]}"""
    H = collections.defaultdict(list)
    for r in REVIEW_ROUNDS:
        p = os.path.join(BENCH, "review", r, "answers.jsonl")
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            if line.strip():
                a = json.loads(line)
                H[a["id"]] += [o["t"] for o in a["options"].values()]
                if a.get("manual") is not None:
                    H[a["id"]].append(a["manual"])
    return H


def make_item(name, r, iid, old, new, wav, group, rnd):
    opts = [{"t": old, "cues": ["old"]}, {"t": new, "cues": ["new"]}]
    rnd.shuffle(opts)
    tmin, tmax = min(old, new), max(old, new)
    pub = {"id": iid, "set": name, "kind": "confirm", "badge": "", "w1": r["w1"], "w2": r["w2"],
           "w1_start": r["w1_start"], "w2_end": r["w2_end"],
           "win_start": max(0.0, tmin - PAD - 0.05), "win_end": tmax + PAD + 0.05,
           "options": [{"key": k, "t": o["t"]} for k, o in zip("AB", opts)]}
    prv = {"set": name, "kind": group, "clip": r["clip"], "pair": r["i"], "wav": wav, "rule": group,
           "branch": r["branch"], "leaf_line": r["leaf_line"], "class": f"{LL.coda(r['w1'])}>{LL.onset(r['w2'])}",
           "gold": LS.gold(r), "live": old, "cand": new, "options": {k: o for k, o in zip("AB", opts)}}
    return pub, prv


def main():
    rnd = random.Random(26)
    H = heard_cuts()
    v25 = json.load(open(V25))["grid_preds"][3]
    public, private = [], {}
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        target, control = [], []
        for r in json.load(open(rows_p, encoding="utf-8")):
            p = v25.get(f"{name}|{int(r['clip'])}")
            i = r["i"]
            if p is None or r["branch"] == "pause" or (p[i + 1]["start"] - p[i]["end"]) * 1000 > PAUSE_MS:
                continue                                   # continuous junctions only (as every earlier round)
            old, new = LS.cur(r), (p[i]["end"] + p[i + 1]["start"]) / 2
            gap = abs(new - old) * 1000
            iid = f"{name}-{int(r['clip'])}-{i}"
            if gap <= APART_MS or any(abs(c - new) * 1000 <= HEARD_MS for c in H.get(iid, [])):
                continue
            cls = f"{LL.coda(r['w1'])}>{LL.onset(r['w2'])}"
            if cls in TARGET:
                target.append((r, iid, old, new, "dh/th" if cls.endswith("dh/th") else "stop"))
            elif iid in H and gap <= CONTROL_MAX_MS and any(abs(c - old) * 1000 <= HEARD_MS for c in H[iid]):
                control.append((r, iid, old, new, "control"))
        chosen = []
        for g in PER_SET:
            pool = [x for x in target + control if x[4] == g]
            chosen += rnd.sample(pool, min(PER_SET[g], len(pool)))
        for r, iid, old, new, group in chosen:
            pub, prv = make_item(name, r, iid, old, new, RGB.find_wav(gt[str(r["clip"])]["filename"]), group, rnd)
            public.append(pub); private[iid] = prv
        print(f"{name}: " + ", ".join(f"{g} {sum(x[4] == g for x in chosen)} of {sum(x[4] == g for x in target + control)}"
                                      for g in PER_SET), flush=True)
    rnd.shuffle(public)
    public.sort(key=lambda p: ORDER[p["set"]])
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    print(f"TOTAL {len(public)} items -> {OUT}")


if __name__ == "__main__":
    main()
