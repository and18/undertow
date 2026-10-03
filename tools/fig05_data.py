#!/usr/bin/env python3
"""
fig05_data.py — generates data/derived/fig05_accounting.csv (FIG-05, claim B2, A9).

The CSV used to be written by hand, with misses rounded to 3 decimals and nominal rates
(12 / 24 / 55 / 28 req/s). Now from the unrounded means and the configured rates.

Three primary runs at scope 0.02, 5 repetitions each, same day (28 Sep), exhaustive traversal
in a scenario of its own (TRAV_MODE=scen, claims v3.8; docs/RISULTATO-lab-trav-own-20260928.md),
λ from env.txt:
  0 agentic req/s    tre-20260928-174217 (β = 0)
  12 req/s           tre-20260928-150154 (separate mapping)
  36 req/s           tre-20260928-162206 (separate mapping)
The rows with step "runs" say which run each point comes from. The previous measurements, with the
global-index traversal (R7), are no longer in this file: they are in claims.md (A9, B2).

For each run: configured class rate (human (1−α−β)·λ, exhaustive α·λ, agentic β·λ)
and mean class miss m = mean(1 − h) over the repetitions (h_zipf, h_trav, h_agent of
points.csv). Decomposition of Δ(Σ rate·miss) between a low point (0) and a high one (1):
  new agentic requests               (g1 − g0) · m_agent1
  agentic requests already present   g0 · (m_agent1 − m_agent0)
  human class                        u1 · m_human1 − u0 · m_human0
  exhaustive class                   e1 · m_exh1 − e0 · m_exh0
  sum of terms                       sum of the four terms
  measured / measured_se             mean(origin_rps) high − low, combined SE
  closure_pct                        |sum − measured| / |measured|, in %, from the unrounded
                                     values
The rows 0-36 (net, net_se, net_ci95_lo/hi) are the same net as tools/net_agentic.py
(claim A9): combined SE, 95% CI with Student's t at the Welch degrees of freedom.

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/fig05_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net_agentic  # noqa: E402
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig05_accounting.csv"

# nominal agentic -> (run, configured λ or None to read it from env.txt)
RUNS = {0: ("tre-20260928-174217", None), 12: ("tre-20260928-150154", None),
        36: ("tre-20260928-162206", None)}
STEPS = ((0, 12), (12, 36))


def read_run(run, lam):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows or len({(r["alpha"], r["beta"]) for r in rows}) != 1:
        sys.exit(f"{run}: points.csv empty or with more than one point")
    if lam is None:
        lam = float(st.read_env(run)["LAMBDA"])
    else:
        measured = statistics.fmean(x["lambda"] for x in net_agentic.read_run(run))
        if abs(measured - lam) / lam > 0.01:
            sys.exit(f"{run}: measured λ {measured:.2f} far from {lam}")
    a, b = float(rows[0]["alpha"]), float(rows[0]["beta"])
    o = [float(r["origin_rps"]) for r in rows]

    def miss(col):
        return statistics.fmean(1 - float(r[col]) for r in rows)

    return {"u": (1 - a - b) * lam, "e": a * lam, "g": b * lam,
            "mu": miss("h_zipf"), "me": miss("h_trav"), "mg": miss("h_agent") if b > 0 else 0.0,
            "mean": statistics.fmean(o), "var_mean": statistics.variance(o) / len(o), "n": len(o)}


def main():
    r = {k: read_run(run, lam) for k, (run, lam) in RUNS.items()}
    for k, x in r.items():
        print(f"  {k:2d} req/s: human rate {x['u']:.4f} exhaustive {x['e']:.4f} agentic {x['g']:.4f}  "
              f"miss {x['mu']:.4f} / {x['me']:.4f} / {x['mg']:.4f}  "
              f"origin {x['mean']:.4f} +/- {math.sqrt(x['var_mean']):.4f}  (n = {x['n']})")
    out = []
    for lo, hi in STEPS:
        p, q = r[lo], r[hi]
        terms = [("new agentic requests", (q["g"] - p["g"]) * q["mg"]),
                 ("agentic requests already present", p["g"] * (q["mg"] - p["mg"])),
                 ("human class", q["u"] * q["mu"] - p["u"] * p["mu"]),
                 ("exhaustive class", q["e"] * q["me"] - p["e"] * p["me"])]
        total = sum(v for _, v in terms)
        meas = q["mean"] - p["mean"]
        se = math.sqrt(p["var_mean"] + q["var_mean"])
        step = f"{lo}-{hi}"
        out += [[step, t, f"{v:.3f}"] for t, v in terms]
        out += [[step, "sum of terms", f"{total:.3f}"], [step, "measured", f"{meas:.3f}"],
                [step, "measured_se", f"{se:.3f}"],
                [step, "closure_pct", f"{100 * abs(total - meas) / abs(meas):.2f}"]]
        print(f"  {step}: " + "  ".join(f"{t} {v:+.4f}" for t, v in terms))
        print(f"        sum {total:+.4f}  measured {meas:+.4f} +/- {se:.4f}  "
              f"deviation {100 * (total - meas) / abs(meas):+.1f}%")
    for step, (a, b) in (("0-36", (r[0], r[36])),):
        va, vb = a["var_mean"], b["var_mean"]
        net, se = b["mean"] - a["mean"], math.sqrt(va + vb)
        df = (va + vb) ** 2 / (va ** 2 / (a["n"] - 1) + vb ** 2 / (b["n"] - 1))
        q = net_agentic.t_quantile(0.975, df)
        out += [[step, "net", f"{net:.3f}"], [step, "net_se", f"{se:.3f}"],
                [step, "net_ci95_lo", f"{net - q * se:.3f}"],
                [step, "net_ci95_hi", f"{net + q * se:.3f}"]]
        print(f"  net {step}: {net:+.4f} +/- {se:.4f}  95% CI [{net - q * se:+.4f}, "
              f"{net + q * se:+.4f}]  (Welch df {df:.2f})")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["step", "term", "value"])
        w.writerows(out)
        w.writerows([["runs", f"{k} req/s", run] for k, (run, _) in RUNS.items()])
    print(f"written {OUT_CSV}")


if __name__ == "__main__":
    main()
