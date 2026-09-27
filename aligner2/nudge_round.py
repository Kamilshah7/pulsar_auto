"""
Scores the phone-detector nudge listening round (bench/build_confirm_nudge.py -> bench/review/confirm_nudge) against
the decision fixed before listening: among items where exactly one of the two cuts is accepted, the nudged cut must win
>= 60 % on dev (009 + 026 pooled) and must not lose (< 50 %) on 049; old14 is reported.

    python -m aligner2.nudge_round
"""
import collections
import json
import os

from aligner2.benchmark import BENCH

D = os.path.join(BENCH, "review", "confirm_nudge")


def main():
    prv = json.load(open(os.path.join(D, "items_private.json")))
    p = os.path.join(D, "answers.jsonl")
    ans = {}
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.strip():
                a = json.loads(line); ans[a["id"]] = a                    # the last answer per item counts
    T = collections.defaultdict(lambda: collections.Counter()); by_class = collections.defaultdict(collections.Counter)
    for iid, a in ans.items():
        if "disregard" in a.get("note", "").lower():
            continue
        it = prv[iid]; ok = {it["options"][k]["cues"][0]: a["ok"].get(k, False) for k in it["options"]}
        res = ("nudged" if ok["nudged"] and not ok["current"] else "current" if ok["current"] and not ok["nudged"]
               else "both" if ok["nudged"] else "neither")
        T[it["set"]][res] += 1; by_class[it["class"]][res] += 1
    print(f"answered {len(ans)} of {len(prv)}")

    def share(c):
        n = c["nudged"] + c["current"]
        return (c["nudged"] / n if n else float("nan")), n

    for s in ("009", "026", "049", "old14"):
        c = T[s]; sh, n = share(c)
        print(f"  {s:6} nudged only {c['nudged']:3} | current only {c['current']:3} | both {c['both']:3} | neither {c['neither']:3}"
              f"  -> nudged wins {sh:.0%} of {n}")
    dev = T["009"] + T["026"]; sd, nd = share(dev); sh, nh = share(T["049"])
    verdict = ("SHIP" if nd and sd >= 0.60 and (not nh or sh >= 0.50) else "REJECT" if nd else "no answers yet")
    print(f"dev (009 + 026): nudged wins {sd:.0%} of {nd}; 049: {sh:.0%} of {nh} -> {verdict} "
          f"(rule: dev >= 60 %, 049 >= 50 %)")
    print("by junction type: " + ", ".join(f"{k} {v['nudged']}:{v['current']}" for k, v in sorted(by_class.items(), key=lambda x: -sum(x[1].values()))))


if __name__ == "__main__":
    main()
