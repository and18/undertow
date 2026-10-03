#!/usr/bin/env python3
"""
frontier_tc.py — approximate characteristic time for each frontier policy
(claim A4, A5, A6, D2, D5; docs/VERIFICA-finale-20261002.md, point 1; claims v3.11).

WHY
  The frontier runs (19-20 Sep, λ = 185, α = 0.35, β = 0.10) use the shared
  traversal counter: a chapter goes through the traversal every N/λ = 91.6 s and is requested
  by the exhaustive class with probability α. If the return falls within the cache's
  characteristic time T, the exhaustive hits can be inflated. T depends on the policy.

HOW
  T ≈ C / origin_rps, with C = 5,263 objects (C2, data/derived/cache_capacity.csv) and origin_rps
  the mean of the repetitions of points.csv. origin_rps counts the misses served with 200
  (workload.js): the 403s of the block are no-store and the 503s of the deferral are not cacheable, so
  it is the rate at which objects enter the cache. It is an approximation, not a measurement of T.

The lab stays read-only: only `ssh lab cat` (with the lab off, ~/undertow-backup/shim-scope).

Usage:
    python3 tools/frontier_tc.py
"""
import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "frontier_tc.csv"
CAP_CSV = ROOT / "data" / "derived" / "cache_capacity.csv"
CORPUS, LAMBDA, ALPHA = 16954, 185, 0.35

# policy -> run (registry: frontier of 19-20 Sep)
POLICIES = [
    ("A", "no policy", "tre-20260919-072040"),
    ("B", "block exhaustive", "tre-20260919-080920"),
    ("C", "block exhaustive and agentic", "tre-20260919-085754"),
    ("D1", "defer, budget 1", "tre-20260920-075220"),
    ("D2", "defer, budget 2", "tre-20260920-070346"),
    ("D3", "defer, budget 3", "tre-20260920-061512"),
    ("D4", "defer, budget 4", "tre-20260919-094627"),
    ("D6", "defer, budget 6", "tre-20260919-103501"),
]


def main():
    with CAP_CSV.open() as f:
        cap = statistics.fmean(float(r["n_object_avg"]) for r in csv.DictReader(f))
    ret = CORPUS / LAMBDA
    rows = []
    for key, label, run in POLICIES:
        pts = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
        org = statistics.fmean(float(r["origin_rps"]) for r in pts)
        t = cap / org
        within = "yes" if ret < t else "no"
        rows.append([key, label, run, len(pts), f"{org:.4f}", f"{t:.1f}", f"{ret:.1f}", within])
        print(f"  {key:3s} {label:30s} origin {org:7.3f}  T {t:6.1f} s  return {ret:.1f} s  "
              f"within T: {within}")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["policy", "label", "run", "reps", "origin_rps", "T_s", "return_s",
                    "return_within_T"])
        w.writerows(rows)
    print(f"capacity {cap:.1f} objects; return in the traversal {ret:.1f} s "
          f"(requested by the exhaustive class with probability {ALPHA})\nwritten {OUT_CSV}")


if __name__ == "__main__":
    main()
