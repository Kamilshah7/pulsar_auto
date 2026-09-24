"""Listening round 5 (bundle_026 = dev): LOSO-derived candidates H1/H2/H3. Offsets are the pooled
medians over all three gold sets (what would ship)."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_listening as BL
import landmark_search as LS
import run_gold_bench as RGB
SET = glob.glob(os.path.join(HERE, "gold_sets", "*bundle_026"))[0]
GT = json.load(open(os.path.join(SET, "gt_per_clip.json"), encoding="utf-8"))
RGB.AUDIO_DIRS.insert(0, os.path.join(SET, "audio"))
L = {x["group"][1] + "|" + x["landmark"]: x["offset_ms"] / 1000 for x in json.load(open(os.path.join(HERE, "prov_runs", "loso_v1.json"), encoding="utf-8"))}
o1, o2, o3 = L["case10|1451|current"], L["case10|1457|raw_w1_end"], L["case7|1356|p_mid"]
BL.N_CORRECTED = 3
BL.FIXES = [
    ("H1", "stop into vowel, compact pipe (was: pipe midpoint)", ("case10", 1451), f"pipe midpoint {o1*1000:+.0f}ms", lambda r, *a: BL.cur(r) + o1),
    ("H2", "stop into vowel, dip+15ms leaf (F4's leaf, new rule)", ("case10", 1457), f"CTC's raw end of word 1 {o2*1000:+.0f}ms", lambda r, *a: r["in_w1_end"] + o2),
    ("H3", "vowel into stop (F6's leaf, new rule)", ("case7", 1356), f"pipe midpoint {o3*1000:+.0f}ms", lambda r, *a: r["p_mid"] + o3),
]
sys.argv = ["x", "--rows", os.path.join(HERE, "prov_runs", "b026_branches.json"), "--set", SET,
            "--out", os.path.join(HERE, "listening", "fixes_round5.html"), "--seed", "26"]
BL.main()
