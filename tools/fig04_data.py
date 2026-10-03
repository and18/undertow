#!/usr/bin/env python3
"""
fig04_data.py — generates data/derived/fig04_overlap.csv (FIG-04, claim A3).

Four primary runs at scope 0.02, 5 repetitions each, same day (28 Sep), exhaustive traversal
in a scenario of its own (TRAV_MODE=scen, claims v3.8; docs/RISULTATO-lab-trav-own-20260928.md):
  shared mapping       tre-20260928-134141 (12 req/s), tre-20260928-190230 (36 req/s):
                       AGENT_MUL=2654435761
  separate mapping     tre-20260928-150154 (12 req/s), tre-20260928-162206 (36 req/s):
                       AGENT_MUL=3266489917
The run column says which run each row comes from.
Columns:
  origin_rps / origin_se  mean and SE (stdev / sqrt(n)) of origin_rps from points.csv
  agent_hit               mean of h_agent from points.csv
  overlap_pct             share of the agentic bases that fall in the human head, on the
                          generator (harness/load/workload.js): agentic bases
                          (r·AGENT_MUL + SEED) mod N for r < floor(N·scope); human head =
                          the same 339 most popular ranks that zipfRank really draws,
                          i.e. r = 1..339 (floor(N^u) >= 1: rank 0 never comes out),
                          mapped with (r·2654435761 + SEED) mod N; N = 16954, SEED = 42
  human_mass_pct          share of the human traffic that falls on the agentic bases, with the
                          true distribution of zipfRank: r = floor(N^u), u uniform,
                          P(r = k) = log_N(k+1) − log_N(k) for k >= 1, P(0) = 0

It also prints, for comparison, the separate − shared effect with combined SE and t, and the two
quantities with the previous definitions (head = ranks 0..338, exact Zipf(1) with 1/(k·H_N)).
The file is read by FIG-04 also for the caption: effect / effect_se / t are there too.
  prev_effect / prev_effect_se / prev_t  same effect in the previous measurement, the
                          pre-registered replica of 25-26 Sep with the global-index traversal (R7):
                          C12 tre-20260925-213527, S12 tre-20260925-225538,
                          S36 tre-20260926-001550, C36 tre-20260926-025613 (prev_runs). The
                          figure draws only the primary runs; the previous measurement enters only
                          in the caption.

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/fig04_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig04_overlap.csv"

SEED = 42
HUMAN_MUL = 2654435761         # permute() of workload.js, also the default of AGENT_MUL
SEPARATED_MUL = 3266489917
# (nominal agentic, mapping) -> (run, agentic multiplier)
RUNS = {
    (12, "shared"): ("tre-20260928-134141", HUMAN_MUL),
    (12, "separated"): ("tre-20260928-150154", SEPARATED_MUL),
    (36, "shared"): ("tre-20260928-190230", HUMAN_MUL),
    (36, "separated"): ("tre-20260928-162206", SEPARATED_MUL),
}
# previous measurement: pre-registered replica of 25-26 Sep, global traversal (R7)
REPLICA = {
    (12, "shared"): "tre-20260925-213527",
    (12, "separated"): "tre-20260925-225538",
    (36, "shared"): "tre-20260926-025613",
    (36, "separated"): "tre-20260926-001550",
}


def bases(mul, ranks=None, n=st.CORPUS, scope=float(st.SCOPE_DEFAULT)):
    k = max(1, math.floor(n * scope))
    return [(r * mul + SEED) % n for r in (ranks if ranks is not None else range(k))]


def overlap(mul, head_from=1):
    """Share of the agentic bases in the human head of equal width (ranks head_from..)."""
    agent = bases(mul)
    head = set(bases(HUMAN_MUL, range(head_from, head_from + len(agent))))
    return len(head.intersection(agent)) / len(agent)


def _rank_of(n=st.CORPUS):
    return {(r * HUMAN_MUL + SEED) % n: r for r in range(n)}


def human_mass(mul, n=st.CORPUS):
    """Share of the human traffic on the agentic bases, with r = floor(N^u) of zipfRank."""
    rank = _rank_of(n)
    p = lambda k: (math.log(k + 1) - math.log(k)) / math.log(n) if k >= 1 else 0.0
    return sum(p(rank[b]) for b in bases(mul))


def human_mass_exact_zipf(mul, n=st.CORPUS):
    """Previous definition: exact Zipf(1) on the ranks 0..N−1, P(k) = 1 / ((k+1)·H_N)."""
    rank = _rank_of(n)
    h = sum(1 / k for k in range(1, n + 1))
    return sum(1 / ((rank[b] + 1) * h) for b in bases(mul))


def read_run(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    o = [float(r["origin_rps"]) for r in rows]
    return {"mean": statistics.fmean(o), "var_mean": statistics.variance(o) / len(o),
            "hit": statistics.fmean(float(r["h_agent"]) for r in rows), "n": len(o)}


def main():
    res, out = {}, {}
    for (load, mapping), (run, mul) in RUNS.items():
        r = res[(load, mapping)] = read_run(run)
        ov, mass = overlap(mul), human_mass(mul)
        out[(load, mapping)] = [load, mapping, f"{100 * ov:.1f}", f"{100 * mass:.1f}",
                                f"{r['mean']:.3f}", f"{math.sqrt(r['var_mean']):.3f}",
                                f"{r['hit']:.3f}"]
        print(f"  {load} {mapping:9s} {run}  origin {r['mean']:.4f} +/- "
              f"{math.sqrt(r['var_mean']):.4f}  agentic hit {r['hit']:.4f}  (n = {r['n']})")
        print(f"      overlap {100 * ov:.2f}% (head 0..338: {100 * overlap(mul, 0):.2f}%)  "
              f"human mass {100 * mass:.2f}% (exact Zipf(1): "
              f"{100 * human_mass_exact_zipf(mul):.2f}%)")
    rep = {k: read_run(run) for k, run in REPLICA.items()}
    rows = []
    for load in (12, 36):
        a, b = res[(load, "shared")], res[(load, "separated")]
        d, se = b["mean"] - a["mean"], math.sqrt(a["var_mean"] + b["var_mean"])
        print(f"  effect at {load} req/s: {d:+.4f} +/- {se:.4f}  t = {d / se:.2f}")
        ra, rb = rep[(load, "shared")], rep[(load, "separated")]
        rd, rse = rb["mean"] - ra["mean"], math.sqrt(ra["var_mean"] + rb["var_mean"])
        print(f"  previous (global) at {load} req/s: {rd:+.4f} +/- {rse:.4f}  t = {rd / rse:.2f}")
        prev_runs = f"{REPLICA[(load, 'shared')]} {REPLICA[(load, 'separated')]}"
        for mapping in ("shared", "separated"):
            eff = ([f"{d:.3f}", f"{se:.3f}", f"{d / se:.2f}",
                    f"{rd:.3f}", f"{rse:.3f}", f"{rd / rse:.2f}", prev_runs]
                   if mapping == "separated" else [""] * 7)
            rows.append(out[(load, mapping)] + eff + [RUNS[(load, mapping)][0]])
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_rps", "mapping", "overlap_pct", "human_mass_pct", "origin_rps",
                    "origin_se", "agent_hit", "effect", "effect_se", "t",
                    "prev_effect", "prev_effect_se", "prev_t", "prev_runs", "run"])
        w.writerows(rows)
    print(f"written {OUT_CSV}")


if __name__ == "__main__":
    main()
