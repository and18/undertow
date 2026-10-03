#!/usr/bin/env python3
"""
figA_data.py — generates the CSVs of FIG-A1 and FIG-A2 (previously written by hand).

From the points.csv of the six AGENT_SCOPE sweep runs (same runs as FIG-01, via
scope_ttest.py) and with the same capacity as fig01_data.py (mean of n_object_avg in
data/derived/cache_capacity.csv):

  data/derived/figA1_human_externality.csv   (claim B5) — runs at 30% share:
      human_p99_ms / _se   mean and SE of p99_zipf over the repetitions
      human_hit            mean of h_zipf
      origin_rps / _se     mean and SE of origin_rps

  data/derived/figA2_elasticity_model.csv    (claim B3, B4):
      observed             elasticity of the agentic miss = mean(1 - h_agent) at 13% share
                           / mean(1 - h_agent) at 30% share (ratio of the means)
      prior, tolerance     prediction written before the first results at scope 0.06 and 0.20
                           (docs/PREREGISTRAZIONE-scopesweep.md, table lines 61-62,
                           tolerance line 65): copied constants, not measurements
      posthoc_realdist     post hoc recomputation with the generator's real distribution
                           (docs/RISULTATO-scopesweep.md, lines 33-35): copied constants

Runs: the primary ones of scope_ttest.RUNS (TRAV_MODE=scen, claims v3.8), written in the columns
run (A1) and run_lo / run_hi (A2); W_over_capacity with the distinct chapters of the reachable set
(scope_ttest.reachable).

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/figA_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402
from fig01_data import capacity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_A1 = ROOT / "data" / "derived" / "figA1_human_externality.csv"
OUT_A2 = ROOT / "data" / "derived" / "figA2_elasticity_model.csv"

# scope -> (prior, tolerance, posthoc_realdist, role)
MODEL = {
    "0.02": ("", "", "7.75", "anchor (measured before the prediction was written)"),
    "0.06": ("3.10", "0.30", "2.06", "prediction"),
    "0.20": ("1.40", "0.30", "1.29", "prediction"),
}


def points(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    return rows


def mean_se(v):
    return statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))


def main():
    cap = capacity()
    a1, a2 = [], []
    for scope, (lo_id, hi_id) in st.RUNS.items():
        lo, hi = points(lo_id), points(hi_id)
        env = st.read_env(lo_id)
        _, w = st.reachable(scope, int(env.get("AGENT_MUL", st.AGENT_MUL_DEFAULT)),
                            int(env.get("AGENT_SESSION", st.SESSION_DEFAULT)))
        ratio = f"{w / cap:.4f}"
        p99, p99_se = mean_se([float(r["p99_zipf"]) for r in hi])
        hit = statistics.fmean(float(r["h_zipf"]) for r in hi)
        org, org_se = mean_se([float(r["origin_rps"]) for r in hi])
        a1.append([scope, ratio, f"{p99:.3f}", f"{p99_se:.3f}", f"{hit:.4f}",
                   f"{org:.4f}", f"{org_se:.4f}", hi_id])
        miss_lo = statistics.fmean(1 - float(r["h_agent"]) for r in lo)
        miss_hi = statistics.fmean(1 - float(r["h_agent"]) for r in hi)
        obs = miss_lo / miss_hi
        a2.append([scope, ratio, f"{obs:.4f}", *MODEL[scope], lo_id, hi_id])
        print(f"  scope {scope}: W/cap {ratio}  human p99 {p99:.3f} +/- {p99_se:.3f}  "
              f"human hit {hit:.4f}  origin {org:.4f} +/- {org_se:.4f}  "
              f"agentic miss {miss_lo:.4f} -> {miss_hi:.4f}  elasticity {obs:.4f}")
    for path, header, rows in (
        (OUT_A1, ["scope", "W_over_capacity", "human_p99_ms", "human_p99_se", "human_hit",
                  "origin_rps", "origin_se", "run"], a1),
        (OUT_A2, ["scope", "W_over_capacity", "observed", "prior", "tolerance",
                  "posthoc_realdist", "role", "run_lo", "run_hi"], a2),
    ):
        with path.open("w", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(header)
            wr.writerows(rows)
        print(f"written {path}")
    print(f"capacity used: {cap:.1f} objects")


if __name__ == "__main__":
    main()
