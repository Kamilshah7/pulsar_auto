"""
Per-junction listing for one class pair (dev sets only): gold, v16, refined, error, H flags.

    python -m aligner2.rule_debug "stop>V"            # all continuous joins of that class pair
    python -m aligner2.rule_debug "stop>V" --worst 20 # the refined output's worst ones first
    python -m aligner2.rule_debug "V>fric" --kind pause --side start --audit   # against the audited gold
"""
import argparse

from aligner2 import refine
from aligner2.local_bench import clip_inputs


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pair"); ap.add_argument("--worst", type=int, default=0)
    ap.add_argument("--kind", default="cont"); ap.add_argument("--rules")
    ap.add_argument("--side", choices=("end", "start"))
    ap.add_argument("--audit", action="store_true", help="against the audited gold (aligner2/gold_audit.py)")
    args = ap.parse_args()
    if args.rules is not None:
        refine.RULES.clear(); refine.RULES.update(r for r in args.rules.split(",") if r)
    rows = []
    data = clip_inputs(("009", "026"))
    if args.audit:
        from aligner2.gold_audit import audited
        data = [(cc, *d[1:]) for cc, d in zip(audited(data)[0], data)]
    for c, z, ar, coarse, lx in data:
        toks = c["tokens"]; tr = {}; new = refine.refine(z, [t["text"] for t in toks], ar, coarse, tr, lex=lx)
        for k in range(len(toks) - 1):
            pair = f"{refine.pclass(refine.last_phone(ar[k]))}>{refine.pclass(refine.first_phone(ar[k + 1]))}"
            gap = toks[k + 1]["start"] - toks[k]["end"]
            kind = "cont" if gap <= 0.005 else "pause"
            if (args.pair != "*" and pair != args.pair) or kind != args.kind:
                continue
            g, q, v = toks[k], new[k], coarse[k]
            g2, q2, v2 = toks[k + 1], new[k + 1], coarse[k + 1]
            en, sn = (q["end"] - g["end"]) * 1000, (q2["start"] - g2["start"]) * 1000
            ev, sv = (v["end"] - g["end"]) * 1000, (v2["start"] - g2["start"]) * 1000
            score = abs(en) if args.side == "end" else abs(sn) if args.side == "start" else abs(en) + abs(sn)
            rows.append((score, f"{c['set']}-{int(c['clip']):02d} j{k:<3} {g['text']}|{g2['text']:<14} "
                         f"{ar[k].split()[-1] if ar[k] else '*'}>{ar[k + 1].split()[0] if ar[k + 1] else '*'}  "
                         f"gold {g['end']:.3f}{'H' if g['end_human'] else ' '}/{g2['start']:.3f}{'H' if g2['start_human'] else ' '}"
                         f"  v16 {ev:+5.0f}/{sv:+5.0f}  new {en:+5.0f}/{sn:+5.0f}  [{tr.get(k, '')}]"))
    if args.worst:
        rows.sort(key=lambda r: -r[0]); rows = rows[:args.worst]
    for _, r in rows:
        print(r)


if __name__ == "__main__":
    main()
