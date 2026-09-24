"""
Residual error of the rule stage on the dev sets, grouped by the rule that placed each boundary.

    python -m aligner2.residuals                # table: rule x kind -> n, MAE, bias, share of all error
    python -m aligner2.residuals --list "J9" 20 # the 20 worst boundaries placed by rules starting with J9
"""
import argparse
import collections

import numpy as np

from aligner2 import refine as R
from aligner2.benchmark import _kind
from aligner2.local_bench import clip_inputs


def rows(sets=("009", "026")):
    out = []
    for c, z, ar, coarse, lx in clip_inputs(sets):
        toks = c["tokens"]; tr = {}
        new = R.refine(z, [t["text"] for t in toks], ar, coarse, tr, lex=lx)
        for j, (g, q) in enumerate(zip(toks, new)):
            for side in ("start", "end"):
                k = j if side == "end" else j - 1
                t = tr.get(k, "") if k >= 0 else tr.get(-1, "")
                if side == "start" and k >= 0 and "P2" in t:
                    rule = "P2"
                elif side == "end" and t.startswith("P1"):
                    rule = " ".join(t.split()[:2])
                elif j == 0 and side == "start":
                    rule = "E1" if t else "E1-none"
                else:
                    rule = t.split(" ")[0] if t and not t.startswith(" |") else "coarse"
                    if rule.startswith("P1") and side == "start":
                        rule = "coarse"
                pair = f"{R.pclass(R.last_phone(ar[k])) if k >= 0 else '#'}>" \
                       f"{R.pclass(R.first_phone(ar[k + 1])) if k + 1 < len(toks) else '#'}"
                vpause = 0 <= k < len(toks) - 1 and coarse[k + 1]["start"] - coarse[k]["end"] > 0.005
                out.append(dict(set=c["set"], clip=int(c["clip"]), j=j, text=g["text"], side=side, vpause=vpause,
                                kind=_kind(toks, j, side), rule=rule, pair=pair, h=g[f"{side}_human"],
                                err=(q[side] - g[side]) * 1000, v16=(coarse[j][side] - g[side]) * 1000,
                                gold=g[side], trace=t))
    return out


def compact(D, t0, t1, step, marks):
    """narrow 2 ms table: t, dB99, dBfl, per, cent, hi, lo, zcr, trn, sep, ctc, markers"""
    import numpy as np
    z = D["z"]; out = ["      t  dB fl  per cent    hi    lo  zcr  trn  sep ctc"]
    for i in range(int(t0 / 0.002), min(int(t1 / 0.002), len(z["loudness"])), int(round(step / 2))):
        t = i * 0.002
        mk = [lab for tm, lab in marks if t - 1e-9 <= tm < t + step / 1000 - 1e-9]
        L = z["loudness"][i]
        p = D["p"]; kk = min(len(p) - 1, int(t / 0.02)); o = np.argsort(p[kk])[::-1]
        import joins
        c = joins.SHOW.get(o[0], joins.LETTERS[o[0]])
        out.append(f"{t:7.3f} {L - D['p99']:3.0f} {L - D['floor'][i]:2.0f} {z['periodicity'][i]:4.2f} {z['centroid'][i]:4.1f}"
                   f" {z['high_ratio'][i]:5.1f} {z['low_ratio'][i]:5.1f} {z['zcr'][i]:4.2f} {z['transient'][i]:4.1f}"
                   f" {z['ctc_wordsep'][i]:4.2f} {c}" + (" " + " ".join(mk) if mk else ""))
    return "\n".join(out)


def show(set_clip, k, ms, step=2):
    """2 ms table around join k|k+1 of one dev/test clip, with gold (G), v16 (S), refined (N) and letter-peak
    (L: word k's last letter, F: word k+1's first letter) markers"""
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bench", "tools"))
    import joins
    st, cl = set_clip.split("-")
    D = joins.load(f"{st}_{int(cl):02d}")
    for c, z, ar, coarse, lx in clip_inputs((st,)):
        if int(c["clip"]) != int(cl):
            continue
        toks = c["tokens"]; tr = {}
        new = R.refine(z, [t["text"] for t in toks], ar, coarse, tr, lex=lx)
        t0 = min(toks[k]["end"], coarse[k]["end"], new[k]["end"]) - ms / 1000
        t1 = max(toks[k + 1]["start"], coarse[k + 1]["start"], new[k + 1]["start"]) + ms / 1000
        a, b = toks[k]["text"], toks[k + 1]["text"]
        marks = [(toks[k]["end"], "G:e"), (toks[k + 1]["start"], "G:s"), (coarse[k]["end"], "S:e"),
                 (coarse[k + 1]["start"], "S:s"), (new[k]["end"], "N:e"), (new[k + 1]["start"], "N:s"),
                 (lx["last"][k] * R.HOP, "L"), (lx["first"][k + 1] * R.HOP, "F")]
        print(f"{set_clip} j{k} {a}|{b}  {ar[k]} | {ar[k + 1]}  gold {toks[k]['end']:.3f}{'H' if toks[k]['end_human'] else ''}"
              f"/{toks[k + 1]['start']:.3f}{'H' if toks[k + 1]['start_human'] else ''}  v16 {coarse[k]['end']:.3f}/"
              f"{coarse[k + 1]['start']:.3f}  new {new[k]['end']:.3f}/{new[k + 1]['start']:.3f}  [{tr.get(k, '')}]")
        print(compact(D, t0, t1, step, marks))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--list", nargs=2); ap.add_argument("--kind")
    ap.add_argument("--show", nargs=3, metavar=("SET_CLIP", "K", "MS"), help="2 ms table around join k|k+1")
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--fp", action="store_true", help="--list: only v16 false pauses (gold continuous)")
    args = ap.parse_args()
    if args.show:
        show(args.show[0], int(args.show[1]), float(args.show[2]), args.step)
        return
    X = rows()
    tot = sum(abs(r["err"]) for r in X)
    if args.list:
        pre, n = args.list[0], int(args.list[1])
        L = [r for r in X if r["rule"].startswith(pre) and (not args.kind or r["kind"] == args.kind)]
        if args.fp:
            L = [r for r in L if r["vpause"]]
        L.sort(key=lambda r: -abs(r["err"]))
        for r in L[:n]:
            print(f"{r['set']}-{r['clip']:02d} k{r['j'] if r['side'] == 'end' else r['j'] - 1:<3} {r['text']:<14} {r['side']:5} {r['kind']:5} {r['pair']:10} gold "
                  f"{r['gold']:.3f}{'H' if r['h'] else ' '} err {r['err']:+6.0f} v16 {r['v16']:+6.0f} [{r['trace'][:70]}]")
        return
    g = collections.defaultdict(list)
    for r in X:
        g[(r["rule"], r["kind"])].append(r)
    print(f"total abs error {tot / 1000:.1f} s over {len(X)} boundaries (MAE {tot / len(X):.1f})")
    print(f"{'rule':16} {'kind':5} {'n':>5} {'MAE':>6} {'v16':>6} {'bias':>6} {'>40ms':>6} {'share':>6}")
    for (rule, kind), v in sorted(g.items(), key=lambda kv: -sum(abs(r["err"]) for r in kv[1])):
        e = np.array([r["err"] for r in v]); e16 = np.array([r["v16"] for r in v])
        print(f"{rule:16} {kind:5} {len(v):5} {np.abs(e).mean():6.1f} {np.abs(e16).mean():6.1f} {e.mean():+6.1f} "
              f"{np.mean(np.abs(e) > 40) * 100:5.0f}% {np.abs(e).sum() / tot * 100:5.1f}%")


if __name__ == "__main__":
    main()
