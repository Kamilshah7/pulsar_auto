"""
Check that every case in bench/regression_suite.json still meets its
max_acceptable_error_ms bound in a given benchmark results file. Run after every
change to forced_aligner.py to prove a fix generalized (still holds) rather than
having been silently reverted or broken by a later change.

Usage: python bench/check_regressions.py bench/results_XXX.json
"""
import json
import sys

def main():
    results_path = sys.argv[1] if len(sys.argv) > 1 else "bench/results_latest.json"
    suite = json.load(open("bench/regression_suite.json", encoding="utf-8"))
    results = json.load(open(results_path, encoding="utf-8"))

    all_ok = True
    for case in suite["cases"]:
        ci = case["clip"]
        idx = case["token_idx"]
        rows = results["per_clip"].get(ci, {}).get("rows", [])
        if idx >= len(rows):
            print(f"[MISSING] {case['id']}: clip {ci} idx {idx} not found in {results_path}")
            all_ok = False
            continue
        row = rows[idx]
        err = max(abs(row["start_err_ms"]), abs(row["end_err_ms"]))
        bound = case["max_acceptable_error_ms"]
        status = "OK" if err <= bound else "REGRESSED"
        if status == "REGRESSED":
            all_ok = False
        print(f"[{status}] {case['id']}: clip{ci} idx{idx} '{row['text']}' "
              f"err={err:.1f}ms (bound={bound}ms, was {case['error_after_ms']:.1f}ms when fixed)")

    print()
    print("ALL REGRESSION CASES PASS" if all_ok else "!! REGRESSION DETECTED !!")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
