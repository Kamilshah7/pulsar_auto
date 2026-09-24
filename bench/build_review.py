"""
Build the interactive boundary-review item set.

Items: every human-CORRECTED continuous-speech pair whose live-aligner boundary is > 1 ms from
the human's (all three gold sets), then a random sample of human-VERIFIED pairs from bundle_026
(so candidate cues are also judged on cuts already known to be right).

Each item gets up to 6 BLIND options (letters in random order, identities kept server-side):
live aligner, the human's earlier boundary, pipe start, and context cues -- vowel voicing onset
(w2 starts with a vowel), stop burst end (w1 ends in a stop), stop closure start (w2 starts with a
stop). Options closer than 3 ms are merged (one sound, several cues).

    python bench/build_review.py            -> bench/review/items_public.json, items_private.json
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import landmark_loso as LL  # noqa: E402
import landmark_search as LS  # noqa: E402
import run_gold_bench as RGB  # noqa: E402

OUT = os.path.join(HERE, "review")
LIVE = {"026": "026_h13.json", "049": "049_h13.json", "old14": "old14_h13.json"}
HUMAN = ("human", "dragged")
N_VERIFIED = 200
MERGE_MS = 3.0
PAD = 0.60  # playback reaches this far either side of a cut


def main():
    rnd = random.Random(2026)
    public, private = [], {}
    for name, set_dir, rows_p in LL.sets():
        if set_dir:
            RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
            gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
        else:
            gt = json.load(open(os.path.join(HERE, "gt_per_clip.json"), encoding="utf-8"))
        P = json.load(open(os.path.join(HERE, "prov_runs", LIVE[name]), encoding="utf-8"))["preds"]
        rows = [r for r in json.load(open(rows_p, encoding="utf-8")) if r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
        cur = lambda r: (P[r["clip"]][r["i"]]["end"] + P[r["clip"]][r["i"] + 1]["start"]) / 2
        corrected = [r for r in rows if r["prov_w1end"] in HUMAN and r["prov_w2start"] in HUMAN
                     and abs(cur(r) - LS.gold(r)) * 1000 > 1]
        verified = [r for r in rows if r["prov_w1end"] == "verified" and r["prov_w2start"] == "verified"]
        picks = [("corrected", r) for r in corrected]
        picks += [("verified", r) for r in rnd.sample(verified, min(N_VERIFIED, len(verified)))]
        for kind, r in picks:
            wav = RGB.find_wav(gt[r["clip"]]["filename"])
            lm = LS.landmarks(r, LS.feats(wav))
            cand = [("live", cur(r)), ("yours", LS.gold(r)), ("pipe_start", r["p_start"])]
            if LL.onset(r["w2"]) == "vowel" and "vox_on" in lm:
                cand.append(("vowel_onset", lm["vox_on"] - 0.0023))
            if LL.coda(r["w1"]) == "stop" and "burst_end" in lm:
                cand.append(("burst_end", lm["burst_end"]))
            if LL.onset(r["w2"]) == "stop" and "closure_start" in lm:
                cand.append(("closure_start", lm["closure_start"]))
            # keep cuts inside the pair: a cut past either word's outer edge is meaningless
            lo, hi = r["w1_start"] + 0.010, r["w2_end"] - 0.010
            cand = [(c, t) for c, t in cand if lo < t < hi or c == "yours"]
            merged = []
            for c, t in sorted(cand, key=lambda x: x[1]):
                if merged and (t - merged[-1]["t"]) * 1000 < MERGE_MS:
                    merged[-1]["cues"].append(c)
                else:
                    merged.append({"t": t, "cues": [c]})
            rnd.shuffle(merged)
            iid = f"{name}-{r['clip']}-{r['i']}"
            letters = "ABCDEF"[:len(merged)]
            tmin, tmax = min(m["t"] for m in merged), max(m["t"] for m in merged)
            win_s, win_e = max(0.0, tmin - PAD - 0.05), tmax + PAD + 0.05
            public.append({"id": iid, "set": name, "kind": kind, "w1": r["w1"], "w2": r["w2"],
                           "w1_start": r["w1_start"], "w2_end": r["w2_end"], "win_start": win_s, "win_end": win_e,
                           "options": [{"key": k, "t": m["t"]} for k, m in zip(letters, merged)]})
            private[iid] = {"set": name, "kind": kind, "clip": r["clip"], "pair": r["i"], "wav": wav,
                            "branch": r["branch"], "leaf_line": r["leaf_line"], "class": f"{LL.coda(r['w1'])}>{LL.onset(r['w2'])}",
                            "gold": LS.gold(r), "live": cur(r),
                            "options": {k: m for k, m in zip(letters, merged)}}
        print(f"{name}: {sum(1 for p in public if p['set'] == name)} items "
              f"({len(corrected)} corrected, {min(N_VERIFIED, len(verified))} verified)", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    n_opt = [len(p["options"]) for p in public]
    print(f"TOTAL {len(public)} items, {sum(n_opt)} options (avg {sum(n_opt) / len(n_opt):.1f} per item)")


if __name__ == "__main__":
    main()
