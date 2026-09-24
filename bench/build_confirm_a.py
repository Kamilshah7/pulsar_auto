"""
Listening round for the "before 'a'" rule: when word 2 is the article "a", cut at rise20 - 4ms (start of
the vowel's steepest 20ms energy rise, landmark_search.landmarks). Items: every continuous pair
(gold gap <= 5ms) with word 2 == "a" in the three gold sets where the rule moves the live cut > 0.5ms
to a position not already judged (within 5ms).

    python bench/build_confirm_a.py   -> bench/review/confirm_a/
    REVIEW_DIR=bench/review/confirm_a REVIEW_PORT=8768 python bench/review_server.py
"""
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_confirm as BC  # noqa: E402
import ear_class_rules as E  # noqa: E402
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

OUT = os.path.join(HERE, "review", "confirm_a")
OFFSET = -0.004


def main():
    rnd = random.Random(88)
    J = E.judgments()
    public, private, stats = [], {}, {"pairs": 0, "moved": 0, "heard": 0}
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        P = json.load(open(os.path.join(HERE, "prov_runs", E.PRED.format(name)), encoding="utf-8"))["preds"]
        for r in json.load(open(rows_p, encoding="utf-8")):
            if r["gold_gap_ms"] > 5 or r.get("p_start") is None or re.sub(r"[^a-z']", "", r["w2"].lower()) != "a":
                continue
            stats["pairs"] += 1
            wav = RGB.find_wav(gt[r["clip"]]["filename"])
            lm = LS.landmarks(r, LS.feats(wav))
            live = (P[r["clip"]][r["i"]]["end"] + P[r["clip"]][r["i"] + 1]["start"]) / 2
            if "rise20" not in lm:
                continue
            new = lm["rise20"] + OFFSET
            if not (r["w1_start"] + 0.010 < new < r["w2_end"] - 0.010) or abs(new - live) * 1000 <= BC.MOVE_MS:
                continue
            stats["moved"] += 1
            iid = f"{name}-{r['clip']}-{r['i']}"
            j = J.get(iid)
            if j and any(abs(new - t) * 1000 <= BC.HEARD_MS for t in j["acc"] + j["rej"]):
                stats["heard"] += 1
                continue
            pub, prv = BC.make_item(name, r, iid, live, new, wav, "before_a", "judged" if j else None, rnd)
            public.append(pub); private[iid] = prv
    rnd.shuffle(public)
    public.sort(key=lambda p: BC.ORDER[p["set"]])
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    print(f"{stats['pairs']} continuous 'X a' pairs, rule moves {stats['moved']}, {stats['heard']} already judged there "
          f"-> {len(public)} items")


if __name__ == "__main__":
    main()
