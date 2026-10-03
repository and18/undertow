#!/usr/bin/env python3
"""
fig03_data.py — generates data/derived/fig03_frontier.csv (FIG-03, claim A4, A6).

The CSV used to be written by hand. For each of the 8 frontier policies
(λ = 185, α = 0.35, β = 0.10, 3 repetitions; runs in docs/registry.csv):
  served / served_se   requests served per repetition = sum of the counters
                       ut_ok_zipf + ut_ok_agent + ut_ok_traversal of the k6 JSON
                       (m-a<alpha>-b<beta>-<rep>.json); mean and SE = stdev / sqrt(n)
  p99_ms / p99_se      human p99 = p99_zipf of points.csv; mean and SE

It also prints, for comparison with claims.md, B − C (served and p99, combined SE, t) and the
slopes between consecutive points of the curve in ms per 1000 served, computed from the means.

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/fig03_data.py
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
OUT_CSV = ROOT / "data" / "derived" / "fig03_frontier.csv"

# policy -> (run, label, family), in order of increasing served
POLICIES = {
    "C": ("tre-20260919-085754", "block exhaustive + agentic", "block"),
    "B": ("tre-20260919-080920", "block exhaustive", "block"),
    "D1": ("tre-20260920-075220", "defer budget 1", "defer"),
    "D2": ("tre-20260920-070346", "defer budget 2", "defer"),
    "D3": ("tre-20260920-061512", "defer budget 3", "defer"),
    "D4": ("tre-20260919-094627", "defer budget 4", "defer"),
    "D6": ("tre-20260919-103501", "defer budget 6", "defer"),
    "A": ("tre-20260919-072040", "no policy", "none"),
}
OK = ("ut_ok_zipf", "ut_ok_agent", "ut_ok_traversal")


def mean_se(v):
    return statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))


def read_policy(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    served, p99 = [], []
    for r in rows:
        m = json.loads(st.lab_cat(run, f"m-a{r['alpha']}-b{r['beta']}-{r['rep']}.json"))["metrics"]
        served.append(sum(m.get(k, {}).get("values", {}).get("count", 0) for k in OK))
        p99.append(float(r["p99_zipf"]))
    return served, p99


def main():
    out, stats = [], {}
    for pol, (run, label, family) in POLICIES.items():
        served, p99 = read_policy(run)
        s, s_se = mean_se(served)
        p, p_se = mean_se(p99)
        stats[pol] = (s, s_se, p, p_se, len(served))
        out.append([pol, label, family, f"{s:.0f}", f"{s_se:.0f}", f"{p:.2f}", f"{p_se:.2f}"])
        print(f"  {pol:3s} {run}  served {s:9.1f} +/- {s_se:6.1f}   human p99 "
              f"{p:7.3f} +/- {p_se:6.3f}   (n = {len(served)}, served {served})")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["policy", "label", "family", "served", "served_se", "p99_ms", "p99_se"])
        w.writerows(out)

    b, c = stats["B"], stats["C"]
    d_s, se_s = b[0] - c[0], math.hypot(b[1], c[1])
    d_p, se_p = b[2] - c[2], math.hypot(b[3], c[3])
    print(f"\n  B - C served: {d_s:+.1f} +/- {se_s:.1f}  t = {d_s / se_s:.2f}")
    print(f"  C - B human p99: {-d_p:+.3f} +/- {se_p:.3f} ms")
    print("  slopes (ms per 1000 additional served):")
    order = list(POLICIES)
    for p0, p1 in zip(order, order[1:]):
        x0, x1 = stats[p0], stats[p1]
        print(f"    {p0} -> {p1}: {(x1[2] - x0[2]) / (x1[0] - x0[0]) * 1000:8.2f}")
    print(f"written {OUT_CSV}")


if __name__ == "__main__":
    main()
