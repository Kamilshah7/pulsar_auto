"""
The case ledger for the perfection loop (aligner2/PERFECTION_WORKFLOW.md, "CURRENT TASK"): every golden boundary the
system misses, with what the raw data showed and what was done about it. It lives on disk so the work survives context
compactions; refresh it after every rule change.

    python -m aligner2.case_ledger refresh         # rerun the system on the captured golden bundles, update errors / status
    python -m aligner2.case_ledger summary         # progress: open / in window / exact, by junction class and error size
    python -m aligner2.case_ledger open [--cls X]  # the open cases, largest error first
    python -m aligner2.case_ledger note CLIP J SIDE "text"   # record what the raw data showed / what was done (1-based clip)

Status: exact (<= 1 ms), window (<= WINDOW_MS, or only silence between our cut and golden -- moving a cut through
silence changes nothing audible: inside the range where it sounds right -- the user, 2026-10-05: "sometimes
there's a window instead of an exact cut point where it sounds right"), open (further). Notes are kept across refreshes.
"""
import argparse
import contextlib
import io
import json
import os

import numpy as np

from aligner2.benchmark import BENCH

LEDGER = os.path.join(BENCH, "cache", "aligner2", "case_ledger.json")
WINDOW_MS = 5.0


def _key(r):
    return f"{r['set']}|{r['clip'] + 1}|{r['j']}|{r['side']}"


def load():
    return json.load(open(LEDGER, encoding="utf-8")) if os.path.exists(LEDGER) else {"cases": {}, "history": []}


def save(L):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(L, open(LEDGER, "w", encoding="utf-8"), indent=1)


def refresh(tag=""):
    from aligner2 import cap_bench as CB, refine as R
    from aligner2.captures import load_captures
    prep = CB.load_prepared(load_captures())
    res = CB.run(prep, set(R.RULES))
    with contextlib.redirect_stdout(io.StringIO()):
        rows = CB.report(res, zs={c["clip"]: z for c, m, z in prep})
    L = load()
    seen = set()
    for r in rows:
        k = _key(r); seen.add(k)
        a = abs(r["err"])
        st = "exact" if a <= 1 else "window" if a <= WINDOW_MS or r.get("silent") else "open"
        c = L["cases"].get(k)
        if c is None and st == "exact":
            continue                                   # never missed: not a case
        c = c or {"notes": [], "first_err": round(r["err"], 1)}
        c.update(err=round(r["err"], 1), status=st, word=r["text"], pair=f"{r['prv']}|{r['nxt']}", jtype=r["jtype"],
                 pause=bool(r["pause"]), corrected=bool(r["changed"]), rule=r["rule"][:160])
        L["cases"][k] = c
    n = len(rows); e = np.abs([r["err"] for r in rows])
    win = sum(1 for r in rows if abs(r["err"]) <= WINDOW_MS or r.get("silent"))
    L["history"].append({"tag": tag, "exact": int((e <= 1).sum()), "window": win, "n": n,
                         "mae": round(float(e.mean()), 2)})
    save(L)
    return L


def summary(L):
    cs = L["cases"]
    h = L["history"][-1] if L["history"] else None
    if h:
        print(f"last refresh '{h['tag']}': {h['n']} golden boundaries -- exact {h['exact']} ({h['exact'] / h['n']:.1%}), "
              f"in window (<= {WINDOW_MS:.0f} ms) {h['window']} ({h['window'] / h['n']:.1%}), MAE {h['mae']} ms")
    by = {}
    for k, c in cs.items():
        g = "pause-end" if c["pause"] and c["word"] and k.endswith("end") else "pause-start" if c["pause"] else c["jtype"]
        d = by.setdefault(g, {"open": 0, "window": 0, "exact": 0, "noted": 0})
        d[c["status"]] += 1; d["noted"] += bool(c["notes"])
    print(f"{'group':14} {'open':>5} {'window':>7} {'fixed':>6} {'notes':>6}")
    for g, d in sorted(by.items(), key=lambda x: -x[1]["open"]):
        print(f"{g:14} {d['open']:5} {d['window']:7} {d['exact']:6} {d['noted']:6}")
    for x in L["history"][-8:]:
        print(f"   history: {x['tag'][:40]:40} exact {x['exact']}, window {x['window']}, MAE {x['mae']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("refresh", "summary", "open", "note"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--cls", default=""); ap.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.cmd == "refresh":
        summary(refresh(a.tag))
    elif a.cmd == "summary":
        summary(load())
    elif a.cmd == "open":
        L = load()
        rows = [(k, c) for k, c in L["cases"].items() if c["status"] == "open" and (not a.cls or c["jtype"] == a.cls
                or (a.cls == "pause" and c["pause"]))]
        for k, c in sorted(rows, key=lambda x: -abs(x[1]["err"])):
            print(f"{k:34} [{c['pair']}] {c['jtype']:10} {'PAUSE ' if c['pause'] else ''}err {c['err']:+6.0f} "
                  f"(first {c['first_err']:+.0f}) :: {c['rule'][:60]}" + (f"\n      notes: {' / '.join(c['notes'])}" if c["notes"] else ""))
        print(f"{len(rows)} open")
    elif a.cmd == "note":
        clip, j, side, text = a.args[0], a.args[1], a.args[2], " ".join(a.args[3:])
        L = load()
        k = next((k for k in L["cases"] if k.split("|")[1:] == [clip, j, side]), None)
        if k is None:
            raise SystemExit(f"no case clip {clip} j {j} {side}")
        L["cases"][k]["notes"].append(text); save(L); print(k, "->", L["cases"][k]["notes"])


if __name__ == "__main__":
    main()
