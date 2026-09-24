"""
Listening round for the learned ear ranker (bench/ear_ranker.py).

Every continuous pair is placed by a model trained on the OTHER two gold sets' judgments (what a
fresh bundle would get). Items: every pair it moves that the listener has never judged, plus judged
pairs whose new cut lands > 5ms from every cut already judged there. Blind options: live cut, ranker
cut, the human's earlier boundary.

    python bench/build_confirm_ranker.py   -> bench/review/confirm_ranker/
    REVIEW_DIR=bench/review/confirm_ranker REVIEW_PORT=8767 python bench/review_server.py
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_confirm as BC  # noqa: E402
import ear_ranker as ER  # noqa: E402

OUT = os.path.join(HERE, "review", "confirm_ranker")
MARGIN = 0.3


def main():
    rnd = random.Random(77)
    public, private, moves = [], {}, []
    for d, new in ER.held_out_moves(MARGIN):
        moves.append({"id": d["id"], "live": d["live"], "new": new, "judged": bool(d["acc"])})
        if abs(new - d["live"]) * 1000 <= BC.MOVE_MS:
            continue
        judged = d["acc"] + d["rej"]
        if any(abs(new - t) * 1000 <= BC.HEARD_MS for t in judged):
            continue
        pub, prv = BC.make_item(d["set"], d["r"], d["id"], d["live"], new, d["wav"], "ranker",
                                "judged" if d["acc"] else None, rnd)
        public.append(pub); private[d["id"]] = prv
    rnd.shuffle(public)
    public.sort(key=lambda p: BC.ORDER[p["set"]])
    os.makedirs(OUT, exist_ok=True)
    json.dump(public, open(os.path.join(OUT, "items_public.json"), "w", encoding="utf-8"))
    json.dump(private, open(os.path.join(OUT, "items_private.json"), "w", encoding="utf-8"), indent=1)
    json.dump(moves, open(os.path.join(OUT, "moves.json"), "w", encoding="utf-8"))
    for s in BC.ORDER:
        print(f"{s}: {sum(p['set'] == s for p in public)} items")
    print(f"TOTAL {len(public)} items ({sum(v['kind'] == 'judged' for v in private.values())} on judged pairs)")


if __name__ == "__main__":
    main()
