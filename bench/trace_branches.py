"""
Which branch of snap_boundaries_hybrid decided each word-pair boundary, on a gold set.

Attribution reads the pair loop's own variable `i` from the frame when a branch marker
line executes. An earlier version counted hits of a marker inside the CONTINUOUS branch
and assumed hit k == pair k; TRUE PAUSE pairs never reach that marker, so every pair after
a clip's first pause was attributed to the wrong branch. Guard: every pair must receive
exactly one label or this exits instead of printing a table.

Labels: prepass_fillers ('uh uh'), prepass_cutoff ('word-' + vowel), pause (TRUE PAUSE),
pipe_gap / empty_window (continuous-branch early exits), case1..case14 (continuous dispatch).

    python bench/trace_branches.py [--set bench/gold_sets/<dir>] --out bench/prov_runs/x.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_gold_bench as RGB  # noqa: E402


BRANCH_DESC = {}
LEAF_LINES = {}  # line -> source of every `bnd = ...` in the dispatch; last one hit = deciding leaf


def find_markers(src):
    m = {}
    for n, l in enumerate(src, 1):
        if 'gap_si = s2i(max(0.0, w1["end"] - 0.005))' in l:
            m[n] = "pause"
        if l.strip() == "if si >= ei:" and src[n].strip() == "bnd = p_mid":
            m[n + 1] = "empty_window"
        if l.strip() == "if is_pipe_gap:":
            m[n + 1] = "pipe_gap"      # continuous branch: CTC separator span used as a real gap
    # Pairs claimed by a pre-pass are skipped by the main loop (`if i in skip_pairs: continue`)
    adds = [n for n, l in enumerate(src, 1) if l.strip() == "skip_pairs.add(i)"]
    for n, lab in zip(adds, ("prepass_fillers", "prepass_cutoff")):
        m[n] = lab
    # Continuous-speech dispatch: walk the REAL if/elif/else chain with the AST, marking the
    # first body line of every branch. Deriving branches from "# N." comments missed
    # unnumbered branches (e.g. the two `c2 == "you"` elifs after case 3) and anchored the
    # bare `else:` of case 14 on a nested if -- both silently left pairs unlabelled.
    import ast
    text = "\n".join(src)
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "snap_boundaries_hybrid")
    head = next(n for n in ast.walk(fn) if isinstance(n, ast.If)
                and ast.get_source_segment(text, n.test) == 'starts_with_sibilant(w2["text"])')

    def case_no(test_line, floor):
        """'# N.' header directly above this branch (only comments/blank lines between)."""
        for n in range(test_line - 1, floor, -1):
            t = src[n - 1].strip()
            if t.startswith("# ") and len(t) > 3 and t[2].isdigit() and ". " in t[:6]:
                try:
                    return int(t[2:t.index(".")])
                except ValueError:
                    return None
            if t and not t.startswith("#"):
                return None
        return None

    node, prev_end = head, head.lineno - 30
    while True:
        num = case_no(node.lineno, prev_end)
        cond = ast.get_source_segment(text, node.test)
        label = f"case{num}" if num else f"case@{node.lineno}"
        m[node.body[0].lineno] = label
        BRANCH_DESC[label] = cond[:90]
        prev_end = node.body[-1].end_lineno
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If) and \
                src[node.orelse[0].lineno - 1].strip().startswith("elif"):
            node = node.orelse[0]
            continue
        if node.orelse:  # final bare else:
            num = case_no(node.orelse[0].lineno - 1, prev_end)
            label = f"case{num}" if num else f"else@{node.orelse[0].lineno}"
            m[node.orelse[0].lineno] = label
            BRANCH_DESC[label] = "else (default)"
        break
    last = node.orelse[-1].end_lineno if node.orelse else node.body[-1].end_lineno
    for n in range(head.lineno, last + 1):
        t = src[n - 1].strip()
        if t.startswith("bnd =") or t.startswith("bnd="):
            LEAF_LINES[n] = t[:110]
    if any(list(m.values()).count(k) != 1 for k in ("pause", "empty_window", "pipe_gap")):
        sys.exit(f"FATAL: could not locate pause / empty_window markers: {m}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import forced_aligner as FA
    src = open(FA.__file__, encoding="utf-8").read().splitlines()
    markers = find_markers(src)
    fname = FA.__file__  # exact co_filename string; never rebuild this path by hand

    if args.set:
        gt = json.load(open(os.path.join(args.set, "gt_per_clip.json"), encoding="utf-8"))
        RGB.AUDIO_DIRS.insert(0, os.path.join(args.set, "audio"))
    else:
        gt = json.load(open(os.path.join(ROOT, "bench", "gt_per_clip.json"), encoding="utf-8"))

    labels, ctx, leaf = {}, {}, {}

    def tracer(frame, event, arg):
        if event == "line" and frame.f_code.co_filename == fname:
            if frame.f_lineno in LEAF_LINES and frame.f_code.co_name == "snap_boundaries_hybrid":
                leaf[frame.f_locals.get("i")] = frame.f_lineno
            lab = markers.get(frame.f_lineno)
            if lab is not None and frame.f_code.co_name == "snap_boundaries_hybrid":
                L = frame.f_locals
                i = L.get("i")
                labels.setdefault(i, []).append(lab)
                # the CTC pipe span and pre-decision word edges this branch worked from
                ctx.setdefault(i, {k: (float(L[k]) if isinstance(L.get(k), (int, float)) else None)
                                   for k in ("p_start", "p_end", "p_mid")})
                if isinstance(L.get("w1"), dict):
                    ctx[i]["in_w1_end"] = float(L["w1"]["end"]); ctx[i]["in_w2_start"] = float(L["w2"]["start"])
        return tracer

    aligner = FA.ForcedAligner()
    rows = []
    for ci in sorted(gt, key=int):
        toks = gt[ci]["tokens"]
        labels.clear(); ctx.clear(); leaf.clear()
        sys.settrace(tracer)
        pred = aligner.align(RGB.find_wav(gt[ci]["filename"]), [t["text"] for t in toks], hybrid=True)
        sys.settrace(None)
        bad = [i for i in range(len(toks) - 1) if len(labels.get(i, [])) != 1]
        if bad:
            sys.exit(f"FATAL clip {ci}: pairs without exactly one branch label: "
                     f"{[(i, labels.get(i)) for i in bad[:8]]}")
        for i in range(len(toks) - 1):
            g1, g2 = toks[i], toks[i + 1]
            rows.append({
                "clip": ci, "i": i, "branch": labels[i][0], "w1": g1["text"], "w2": g2["text"],
                "gold_gap_ms": (g2["start"] - g1["end"]) * 1000.0,
                "pred_gap_ms": (pred[i + 1]["start"] - pred[i]["end"]) * 1000.0,
                "err_w1end": (pred[i]["end"] - g1["end"]) * 1000.0,
                "err_w2start": (pred[i + 1]["start"] - g2["start"]) * 1000.0,
                "prov_w1end": RGB.provenance(g1["end"], g1.get("end_status")),
                "prov_w2start": RGB.provenance(g2["start"], g2.get("start_status")),
                "gold_w1end": g1["end"], "gold_w2start": g2["start"],
                "pred_w1end": pred[i]["end"], "pred_w2start": pred[i + 1]["start"],
                "w1_start": g1["start"], "w2_end": g2["end"], **ctx.get(i, {}),
                "leaf_line": leaf.get(i), "leaf_src": LEAF_LINES.get(leaf.get(i)),
            })
        print(f"  clip {ci}: {len(toks) - 1} pairs, all labelled", flush=True)
    json.dump(rows, open(args.out, "w", encoding="utf-8"), indent=1)
    print(f"wrote {len(rows)} pair rows -> {args.out}")


if __name__ == "__main__":
    main()
