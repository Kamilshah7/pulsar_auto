"""
Freeze a gold-label set so the next bundle download can't destroy it.

Run after exporting golden_labels.json with extract_golden_labels.js. Timing no longer matters:
pipeline.py archives every bundle to bench/bundle_archive/<bundle>/ before a new bundle clears
it, and --source auto (default) finds the bundle a label file belongs to, live or archived.
(Bundles run on a pipeline.py older than 2026-09-23 were never archived -- snapshot those
before starting the next bundle.)

    python bench/snapshot_gold.py path/to/golden_labels.json --reviewed 0,1,2,5
    python bench/snapshot_gold.py path/to/golden_labels.json --reviewed all

--reviewed lists the clips where you checked EVERY boundary. On those clips an untouched
boundary means "a human looked and it is right"; on the others it only means "not moved".

Because output/injected_tokens.json records exactly what we injected, each gold boundary is
labelled directly instead of inferred from timestamp precision:
    moved              you changed it (> 0.5 ms from what we injected)  -> human-placed
    reviewed_accepted  untouched, on a clip you fully reviewed          -> human-verified
    unreviewed         untouched, on a clip you did not fully review    -> our own output
    no_injection_match token you added/split/merged, nothing to compare -> human-placed

Output: bench/gold_sets/<date>_<bundle>/  with the WAVs, sidecars, pipeline intermediates,
the raw export, gt_per_clip.json (clip-local times + per-boundary status) and manifest.json.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "audio")
OUTPUT = os.path.join(ROOT, "output")
MOVE_TOL_MS = 0.5  # injector rounds to whole ms; anything beyond half a ms was dragged

INTERMEDIATES = [
    "ordered_clips.json", "current_bundle.txt", "injected_tokens.json", "llm_corrected_tokens.json",
    "groq_transcriptions.json", "wav2vec2_acoustic_transcriptions.json",
    "microslice_repaired_transcriptions.json", "pulsar_llm_prompt.txt", "pulsar_llm_input.txt",
    "clip_list.json", "bundle_manifest.json", "inject_console.js",
]


def die(msg):
    sys.exit(f"FATAL: {msg}")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(w):
    return re.sub(r"[^a-z0-9']", "", str(w).lower())


def match_tokens(gold, inj, max_mid_diff=0.5):
    """One-to-one pairing of gold tokens with the injected tokens they came from.

    Pure text alignment is wrong for exactly the tokens people edit most: in a stutter
    ("you you") where one copy is deleted, it cannot tell which copy survived and pairs the
    survivor with its neighbour, making both of its edges look 'moved' by the full word
    length. Editor token ids don't help either -- if the editor renumbers after a deletion,
    the survivor's id points at its neighbour (verified with a renumbered-id self-test).

    What does discriminate: a human drag almost always moves ONE edge, so the true source
    token shares an untouched edge with the gold token exactly. Cost = min(|d_start|, |d_end|),
    tie-broken by midpoint distance; same text only; assigned globally cheapest-first,
    one-to-one."""
    mid = lambda t: (float(t["start"]) + float(t["end"])) / 2.0
    pairs, used_g, used_i = {}, set(), set()
    cand = sorted((min(abs(float(t["start"]) - float(s["start"])), abs(float(t["end"]) - float(s["end"]))),
                   abs(mid(t) - mid(s)), j, k)
                  for j, t in enumerate(gold)
                  for k, s in enumerate(inj)
                  if norm(s["text"]) == norm(t["text"]) and abs(mid(t) - mid(s)) <= max_mid_diff)
    for _, _, j, k in cand:
        if j not in used_g and k not in used_i:
            pairs[j] = inj[k]; used_g.add(j); used_i.add(k)
    return pairs


ARCHIVE = os.path.join(ROOT, "bench", "bundle_archive")


def resolve_source(wavs, source):
    """(audio_dir, output_dir, description) holding these WAVs. 'live' = audio/ + output/;
    'auto' tries live, then every bench/bundle_archive/<bundle>/ (written by
    pipeline.archive_bundle before a new bundle clears the old one); anything else is taken as
    an archive directory."""
    def has(d):
        return all(os.path.exists(os.path.join(d, w)) for w in wavs)
    if source in ("auto", "live") and has(AUDIO) and os.path.exists(os.path.join(OUTPUT, "ordered_clips.json")):
        return AUDIO, OUTPUT, "live audio/ + output/"
    if source == "live":
        die("the labels' WAVs are not in audio/ any more -- use --source auto to search the archive")
    if source == "auto":
        cands = [os.path.join(ARCHIVE, d) for d in sorted(os.listdir(ARCHIVE))] if os.path.isdir(ARCHIVE) else []
    else:
        cands = [source]
    for d in cands:
        if has(os.path.join(d, "audio")) and os.path.exists(os.path.join(d, "pipeline", "ordered_clips.json")):
            return os.path.join(d, "audio"), os.path.join(d, "pipeline"), f"archive {d}"
    die(f"no source holds these labels' WAVs ({sorted(wavs)[:2]}...). Checked live audio/ and {len(cands)} archive(s).")


def wav_of(token_id):
    m = re.match(r"t_(.+\.wav)_\d+$", str(token_id))
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("labels", help="golden_labels.json downloaded by extract_golden_labels.js")
    ap.add_argument("--reviewed", required=True,
                    help="comma-separated clip indices you fully reviewed, or 'all' or 'none'")
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "gold_sets"))
    ap.add_argument("--note", default="")
    ap.add_argument("--source", default="auto",
                    help="auto (default: live audio/ first, then bench/bundle_archive), live, or an archive dir")
    args = ap.parse_args()

    gold = json.load(open(args.labels, encoding="utf-8"))
    tokens = gold["tokens"] if isinstance(gold, dict) else gold
    if not tokens:
        die("label file has no tokens")

    audio_dir, output_dir, where = resolve_source({wav_of(t["id"]) for t in tokens} - {None}, args.source)
    print(f"Source: {where}")
    ordered_p = os.path.join(output_dir, "ordered_clips.json")
    if not os.path.exists(ordered_p):
        die("output/ordered_clips.json missing -- run this before starting the next bundle")
    ordered = {c["index"]: c for c in json.load(open(ordered_p, encoding="utf-8"))}

    by_clip = {}
    for t in tokens:
        by_clip.setdefault(int(t["clipIndex"]), []).append(t)
    for ci in by_clip:
        by_clip[ci].sort(key=lambda t: t["start"])

    # --- the labels must belong to the bundle that is currently in audio/ ---
    for ci, toks in by_clip.items():
        if ci not in ordered:
            die(f"labels have clip {ci} but ordered_clips.json does not -- wrong bundle loaded?")
        want = ordered[ci]["filename"]
        ids = {wav_of(t["id"]) for t in toks} - {None}
        if ids and want not in ids:
            die(f"clip {ci}: labels reference {sorted(ids)} but this bundle's clip {ci} is {want}")
        if not os.path.exists(os.path.join(audio_dir, want)):
            die(f"clip {ci}: {want} is not in audio/ -- the bundle was already replaced")

    if args.reviewed.strip().lower() == "all":
        reviewed = set(by_clip)
    elif args.reviewed.strip().lower() == "none":
        reviewed = set()
    else:
        reviewed = {int(x) for x in args.reviewed.split(",") if x.strip()}
        unknown = reviewed - set(by_clip)
        if unknown:
            die(f"--reviewed lists clips {sorted(unknown)} that are not in the labels")

    inj_p = os.path.join(output_dir, "injected_tokens.json")
    injected = {}
    if not os.path.exists(inj_p):
        # Without the injection nothing can be classified: every boundary would come out
        # 'no_injection_match', which is scored as human-placed -- silently wrong.
        die(f"no injected_tokens.json in {output_dir}. The LLM/inject step never ran for this bundle, "
            f"or the archive left out an injection that belonged to the previous bundle.")
    inj_all = json.load(open(inj_p, encoding="utf-8"))
    label_wavs = {wav_of(t["id"]) for t in tokens} - {None}
    inj_wavs = {wav_of(t.get("id")) for t in inj_all} - {None}
    if inj_wavs and not (inj_wavs & label_wavs):
        # The inject step isn't cleared on a new bundle, so a bundle whose LLM/inject step never
        # ran still carries the PREVIOUS bundle's injection.
        die(f"injected_tokens.json belongs to a different bundle ({sorted(inj_wavs)[0]}...) than these labels "
            f"({sorted(label_wavs)[0]}...). Comparing against it would mislabel every boundary.")
    for t in inj_all:
        injected.setdefault(int(t["clipIndex"]), []).append(t)
    for ci in injected:
        injected[ci].sort(key=lambda t: t["start"])

    bundle = open(os.path.join(output_dir, "current_bundle.txt"), encoding="utf-8").read().strip() \
        if os.path.exists(os.path.join(output_dir, "current_bundle.txt")) else "unknown_bundle"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    dest = os.path.join(args.out, f"{stamp}_{re.sub(r'[^A-Za-z0-9_.-]', '_', bundle)[:80]}")
    if os.path.exists(dest):
        die(f"{dest} already exists")
    os.makedirs(os.path.join(dest, "audio"))
    os.makedirs(os.path.join(dest, "pipeline"))

    # --- per-clip, clip-local gold with a recorded status on every boundary ---
    gt, counts = {}, {}
    for ci in sorted(by_clip):
        off = float(ordered[ci]["start_sec"])
        g = by_clip[ci]
        inj = injected.get(ci, [])
        pairs = match_tokens(g, inj)
        out = []
        for j, t in enumerate(g):
            rec = {"text": t["text"], "start": round(t["start"] - off, 4), "end": round(t["end"] - off, 4)}
            for side in ("start", "end"):
                p = pairs.get(j)
                if p is None:
                    status = "no_injection_match"
                elif abs(float(t[side]) - round(float(p[side]), 3)) * 1000 > MOVE_TOL_MS:
                    status = "moved"
                else:
                    status = "reviewed_accepted" if ci in reviewed else "unreviewed"
                rec[f"{side}_status"] = status
                counts[status] = counts.get(status, 0) + 1
            out.append(rec)
        gt[str(ci)] = {"filename": ordered[ci]["filename"], "n_tokens": len(out),
                       "reviewed": ci in reviewed, "tokens": out}

    # --- freeze the audio and every intermediate the next bundle would overwrite ---
    files = {}
    for ci in sorted(by_clip):
        fn = ordered[ci]["filename"]
        for name in (fn, fn[:-4] + ".json"):
            src = os.path.join(audio_dir, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dest, "audio", name))
                files["audio/" + name] = sha(src)
    for name in INTERMEDIATES:
        src = os.path.join(output_dir, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, "pipeline", name))
            files["pipeline/" + name] = sha(src)
    shutil.copy2(args.labels, os.path.join(dest, "golden_labels_raw.json"))
    json.dump(gt, open(os.path.join(dest, "gt_per_clip.json"), "w", encoding="utf-8"), indent=1)

    n_b = sum(counts.values())
    manifest = {
        "bundle": bundle, "snapshot_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "labels_extracted_at": gold.get("extracted_at") if isinstance(gold, dict) else None,
        "reviewed_clips": sorted(reviewed), "n_clips": len(by_clip),
        "n_tokens": sum(len(v) for v in by_clip.values()), "n_boundaries": n_b,
        "boundary_status_counts": counts, "move_tolerance_ms": MOVE_TOL_MS,
        "note": args.note, "files_sha256": files,
    }
    json.dump(manifest, open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8"), indent=1)

    print(f"Snapshot written to {dest}")
    print(f"  {len(by_clip)} clips, {manifest['n_tokens']} tokens, {n_b} boundaries; "
          f"fully reviewed clips: {sorted(reviewed) or 'none'}")
    for k in ("moved", "reviewed_accepted", "unreviewed", "no_injection_match"):
        print(f"  {k:<20} {counts.get(k, 0):5d}  ({100 * counts.get(k, 0) / max(n_b, 1):4.1f}%)")
    print(f"  {len(files)} files frozen (audio + pipeline intermediates), sha256 in manifest.json")


if __name__ == "__main__":
    main()
