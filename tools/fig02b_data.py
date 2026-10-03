#!/usr/bin/env python3
"""
fig02b_data.py — generates data/derived/fig02b_exhaustive_marginal.csv (FIG-02 b, claim A7).

The CSV used to be written by hand. Crawler series of 16 September (block B of
harness/load/marginale2.sh: human 55 and agentic 12 req/s fixed, exhaustive 0 → 42,
shared mapping, window 1211 s, 3 repetitions per point):
  marginal / marginal_se  (mean origin_rps of the high point − mean of the low point)
                          / (α·λ high − α·λ low), SE combined from the two means;
                          α from points.csv, λ configured in marginale2.sh (the runs
                          predate env.txt), checked against the measured k6 rate
                          (http_reqs / measure)
  elasticity              exhaustive miss at 42 req/s / exhaustive miss at 14 req/s,
                          mean(1 − h_trav) over the repetitions (ratio of the means);
                          at 0 req/s the exhaustive miss does not exist
  from_rps, to_rps        nominal labels of the step (0, 14, 28, 42)

The lab stays read-only: only `ssh lab cat`.

Usage:
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig02b_exhaustive_marginal.csv"
SERIES = "crawler series 16 Sep 2026 (shared mapping; 1211 s window; 3 reps)"

# nominal exhaustive -> (run, λ configured in marginale2.sh, block B)
POINTS = {
    0: ("tre-20260916-013722", 67),
    14: ("tre-20260916-025527", 81),
    28: ("tre-20260916-041332", 95),
    42: ("tre-20260916-053137", 109),
}


def read_point(run, lam):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows or len({r["alpha"] for r in rows}) != 1:
        sys.exit(f"{run}: points.csv empty or with more than one point")
    origin = [float(r["origin_rps"]) for r in rows]
    measured = []
    for r in rows:
        m = json.loads(st.lab_cat(run, f"m-a{r['alpha']}-b{r['beta']}-{r['rep']}.json"))["metrics"]
        measured.append(m["http_reqs"]["values"]["count"] / float(r["measure"]))
    rate = statistics.fmean(measured)
    if abs(rate - lam) / lam > 0.01:
        sys.exit(f"{run}: measured λ {rate:.2f} far from the configured {lam}")
    return {
        "exh": float(rows[0]["alpha"]) * lam,
        "mean": statistics.fmean(origin),
        "var_mean": statistics.variance(origin) / len(origin),
        "miss": statistics.fmean(1 - float(r["h_trav"]) for r in rows),
        "n": len(rows), "lam_measured": rate,
    }


def main():
    pts = {k: read_point(run, lam) for k, (run, lam) in POINTS.items()}
    for k, p in pts.items():
        print(f"  exhaustive {k:2d}: α·λ {p['exh']:.4f}  measured λ {p['lam_measured']:.3f}  "
              f"origin {p['mean']:.4f} +/- {math.sqrt(p['var_mean']):.4f}  "
              f"exhaustive miss {p['miss']:.4f}  (n = {p['n']})")
    elast = pts[42]["miss"] / pts[14]["miss"]
    print(f"  elasticity 14 -> 42: {elast:.4f}")
    rows = []
    keys = list(pts)
    for lo, hi in zip(keys, keys[1:]):
        d = pts[hi]["exh"] - pts[lo]["exh"]
        m = (pts[hi]["mean"] - pts[lo]["mean"]) / d
        se = math.sqrt(pts[hi]["var_mean"] + pts[lo]["var_mean"]) / d
        print(f"  {lo} -> {hi}: marginal {m:.5f} +/- {se:.5f}")
        rows.append([lo, hi, f"{m:.4f}", f"{se:.4f}", f"{elast:.4f}", SERIES])
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["from_rps", "to_rps", "marginal", "marginal_se", "elasticity", "series"])
        w.writerows(rows)
    print(f"written {OUT_CSV}")


if __name__ == "__main__":
    main()
