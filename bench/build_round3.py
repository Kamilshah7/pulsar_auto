"""Listening round 3: landmark-derived fixes G1 (velar stop -> vowel: voicing onset - 2.3ms) and
G2 (liquid onset after vowel: raw CTC w2 start - 47.3ms). Same page format as round 1."""
import glob, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_listening as BL
import landmark_search as LS
import run_gold_bench as RGB
SET = glob.glob(os.path.join(HERE, "gold_sets", "*bundle_049"))[0]
import json
GT = json.load(open(os.path.join(SET, "gt_per_clip.json"), encoding="utf-8"))
RGB.AUDIO_DIRS.insert(0, os.path.join(SET, "audio"))

def g1(r, *a):
    lm = LS.landmarks(r, LS.feats(RGB.find_wav(GT[r["clip"]]["filename"])))
    return lm["vox_on"] - 0.0023 if "vox_on" in lm else BL.cur(r)

BL.N_CORRECTED = 99  # small leaves: every corrected pair
BL.FIXES = [
    ("G1", "velar stop into vowel, compact pipe", ("case10", 1394), "voicing onset of the vowel, minus 2.3ms", g1),
    ("G2", "liquid (/l/, /r/) onset after a vowel", ("case9", 1382), "CTC's raw start of word 2, minus 47ms",
     lambda r, *a: r["in_w2_start"] - 0.0473),
]
sys.argv = ["x", "--rows", os.path.join(HERE, "prov_runs", "b049_branches_v2.json"), "--set", SET,
            "--out", os.path.join(HERE, "listening", "fixes_round3.html"), "--seed", "5"]
BL.main()
