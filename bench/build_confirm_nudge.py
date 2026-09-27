"""
Listening round for the phone-detector NUDGE (2026-09-27; the user: "test more approaches" for the 3-11 ms micro
corrections). aligner2/fc_nudge.py (skip_stops, radius 8 ms, tau 8 ms, window 40 ms; chosen on 009 + 026) moves a cut
at a touching-word junction by up to 8 ms in the direction the 10 ms phone detector points, except next to a stop.
On the data so far its moves go closer to the user's hand-moved gold 73 %, to the user's own review cuts 85 %, to an
accepted ear cut 68 % (all sets pooled) -- this round asks the ear directly.

  items:   junctions it moves by >= 3 ms; per set a random 30 (009, 026, 049, old14 -> up to 120)
  options: the current cut and the nudged cut, shuffled (A / B), blind

Decision, fixed before listening: among items where exactly one of the two cuts is accepted, the nudged cut must win
>= 60 % on dev (009 + 026 pooled) and must not lose (< 50 %) on 049 (held out, reject-only); old14 is reported.

    python bench/build_confirm_nudge.py    -> bench/review/confirm_nudge/items_public.json, items_private.json
    REVIEW_DIR=bench/review/confirm_nudge REVIEW_PORT=8769 python bench/review_server.py
    python -m aligner2.nudge_round         # scores the answers against the rule above
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from aligner2 import fc_nudge, micro_eval as M  # noqa: E402
from aligner2.cue_ear_eval import load_z  # noqa: E402

OUT = os.path.join(HERE, "review", "confirm_nudge")
SETTING = dict(radius=0.008, tau=0.008, win=0.040, skip_stops=True)
MIN_MOVE_MS, PER_SET, PAD = 3.0, 30, 0.60
ORDER = {"009": 0, "026": 1, "049": 2, "old14": 3}


def main():
    rnd = random.Random(927)
    clips, base, arpa, J = M.setup()
    pools = {s: [] for s in ORDER}
    for c in clips:
        k = f"{c['set']}|{c['clip']}"; toks = c["tokens"]
        z = load_z(c["set"], c["clip"], c["wav"])
        P = fc_nudge.nudge(z, base[k], arpa[k], **SETTING)
        for j in range(len(toks) - 1):
            old = (base[k][j]["end"] + base[k][j + 1]["start"]) / 2; new = (P[j]["end"] + P[j + 1]["start"]) / 2
            if abs(new - old) * 1000 >= MIN_MOVE_MS:
                pools[c["set"]].append((c, j, old, new))
    public, private = [], {}
    for s, pool in pools.items():
        chosen = rnd.sample(pool, min(PER_SET, len(pool)))
        for c, j, old, new in chosen:
            k = f"{c['set']}|{c['clip']}"; toks = c["tokens"]
            iid = f"{s}-{int(c['clip'])}-{j}"
            opts = [{"t": old, "cues": ["current"]}, {"t": new, "cues": ["nudged"]}]
            rnd.shuffle(opts)
            lo, hi = min(old, new), max(old, new)
            public.append({"id": iid, "set": s, "kind": "confirm", "badge": "blind A/B", "w1": toks[j]["text"],
                           "w2": toks[j + 1]["text"], "w1_start": base[k][j]["start"], "w2_end": base[k][j + 1]["end"],
                           "win_start": max(0.0, lo - PAD - 0.05), "win_end": hi + PAD + 0.05,
                           "options": [{"key": key, "t": o["t"]} for key, o in zip("AB", opts)]})
            private[iid] = {"set": s, "kind": "nudge", "clip": str(c["clip"]), "pair": j, "wav": c["wav"],
                            "rule": "FCN", "class": M.junction_type(arpa[k], j),
                            "gold": (toks[j]["end"] + toks[j + 1]["start"]) / 2, "live": old, "cand": new,
                            "options": {key: o for key, o in zip("AB", opts)}}
        print(f"{s}: {len(chosen)} of {len(pool)} moved junctions", flush=True)
    rnd.shuffle(public)
    public.sort(key=lambda p: ORDER[p["set"]])
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    print(f"TOTAL {len(public)} items -> {OUT}")


if __name__ == "__main__":
    main()
