"""
Raw data around captured boundaries (aligner2/PERFECTION_WORKFLOW.md, step 2 "inspect raw data case by case").

    python -m aligner2.cap_case --type stop>V            # every mismatched boundary of one junction class
    python -m aligner2.cap_case --clip 3 --j 12          # one junction (word j | word j+1) of clip 3 (1-based clip)
    python -m aligner2.cap_case --type pause-end --ms 4  # 4 ms rows instead of 2

Per boundary: the words, our cut vs golden, the rule trace, then a row per step from 40 ms before the earlier cut to 40 ms
after the later one: loudness (dB over the 10th percentile of the window), voicing (periodicity), zcr, high band (dB),
transient, glottal; O = ours, G = golden.
"""
import argparse
import contextlib
import io

import numpy as np

from aligner2 import cap_bench as CB
from aligner2.captures import load_captures

H = 0.002


def table(z, t_ours, t_gold, step_ms=2, pad_ms=40):
    a, b = sorted((t_ours, t_gold))
    i0, i1 = int((a - pad_ms / 1000) / H), int((b + pad_ms / 1000) / H)
    i0 = max(0, i0); i1 = min(len(z["loudness"]) - 1, i1)
    L = z["loudness"]; ref = np.percentile(L[i0:i1 + 1], 10)
    io_, ig = int(round(t_ours / H)), int(round(t_gold / H))
    cols = [("L", lambda i: L[i] - ref, "{:5.0f}"), ("voic", lambda i: z["periodicity"][i], "{:5.2f}"),
            ("zcr", lambda i: z["zcr"][i], "{:5.2f}"), ("hi", lambda i: z["high_ratio"][i], "{:5.0f}"),
            ("trans", lambda i: z["transient"][i], "{:5.1f}"), ("glot", lambda i: z["glottal"][i], "{:5.1f}")]
    out = ["      t(s)    " + " ".join(f"{c:>5}" for c, _, _ in cols)]
    step = max(1, int(step_ms / 2))
    for i in range(i0, i1 + 1, step):
        mark = ("O" if abs(i - io_) < step else " ") + ("G" if abs(i - ig) < step else " ")
        out.append(f"   {mark} {i * H:8.3f} " + " ".join(f.format(fn(i)) for _, fn, f in cols))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", default=""); ap.add_argument("--clip", type=int); ap.add_argument("--j", type=int)
    ap.add_argument("--ms", type=int, default=2); ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--min-err", type=float, default=1.0)
    args = ap.parse_args()
    prep = CB.load_prepared(load_captures())
    res = CB.run(prep)
    with contextlib.redirect_stdout(io.StringIO()):
        rows = CB.report(res)
    Z = {c["clip"]: z for c, m, z in prep}
    sel = []
    for r in rows:
        k = r["j"] if r["side"] == "end" else r["j"] - 1
        kind = ("pause-end" if r["pause"] and r["side"] == "end" else "pause-start" if r["pause"] else r["jtype"])
        if args.clip is not None:
            if r["clip"] + 1 == args.clip and k == args.j:
                sel.append(r)
        elif kind == args.type and abs(r["err"]) > args.min_err:
            sel.append(r)
    for r in sel[:args.max]:
        print(f"\n=== clip {r['clip'] + 1} [{r['prv']}|{r['nxt']}] {r['side']} of '{r['text']}' {r['jtype']} | ours {r['err']:+.0f} ms "
              f"({'corrected' if r['changed'] else 'was right'}) :: {r['rule'][:140]}")
        print(table(Z[r["clip"]], r["ours"], r["gold"], args.ms))
    print(f"\n{len(sel)} boundaries")


if __name__ == "__main__":
    main()
