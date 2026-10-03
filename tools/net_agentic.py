#!/usr/bin/env python3
"""
net_agentic.py — net 0 -> 36 agentic req/s at scope 0.02 (row A9 of claims.md).

Compares the run without the agentic class (tre-20260920-102015, beta = 0) with the run at
agentic share 30% (tre-20260921-162248, beta*lambda = 36), separate mapping,
5 repetitions each. For each repetition:
  - origin_rps from points.csv;
  - MEASURED rate of each class from the k6 JSON of the repetition
    (m-a<alpha>-b<beta>-<rep>.json): (ut_hit_<class> + ut_miss_<class>) / measure,
    the same normalisation as origin_rps in treclassi.sh; measured lambda = sum.
Then: net = mean(origin_hi) - mean(origin_0), combined SE, Welch t, Welch-Satterthwaite
degrees of freedom, 95% CI with the Student t quantile.

It is needed because the run at beta = 0 is from 20 September, before env.txt: lambda and the
per-class rates are not recorded in the configuration and must be rebuilt from the
requests actually generated.

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/net_agentic.py
"""
import csv
import json
import math
import statistics
import subprocess
import sys

RUN_ZERO = "tre-20260920-102015"
RUN_HI = "tre-20260921-162248"
CLASSES = (("human", "zipf"), ("exhaustive", "traversal"), ("agentic", "agent"))


def lab_cat(run, name):
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{run}/{name}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def read_run(run):
    rows = list(csv.DictReader(lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    reps = []
    for r in rows:
        name = f"m-a{r['alpha']}-b{r['beta']}-{r['rep']}.json"
        m = json.loads(lab_cat(run, name))["metrics"]
        measure = float(r["measure"])
        rates = {}
        for label, key in CLASSES:
            n = sum(m.get(f"ut_{kind}_{key}", {}).get("values", {}).get("count", 0)
                    for kind in ("hit", "miss"))
            rates[label] = n / measure
        rates["lambda"] = sum(rates[label] for label, _ in CLASSES)
        reps.append({"rep": r["rep"], "alpha": r["alpha"], "beta": r["beta"],
                     "measure": measure, "origin": float(r["origin_rps"]), **rates})
    return reps


# ── Student's t without scipy: CDF via regularised incomplete beta function ──
def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1 + aa / 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1 + aa / 1e-300
        dl = d * c
        h *= dl
        if abs(dl - 1) < 1e-14:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def t_cdf(t, df):
    p = 0.5 * _betai(df / 2, 0.5, df / (df + t * t))
    return 1 - p if t > 0 else p


def t_quantile(q, df):
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def summary(reps, label):
    for r in reps:
        print(f"  rep {r['rep']}  alpha={r['alpha']} beta={r['beta']} measure={r['measure']:.0f}s  "
              f"human {r['human']:.3f}  exhaustive {r['exhaustive']:.3f}  agentic {r['agentic']:.3f}  "
              f"lambda {r['lambda']:.3f}  origin {r['origin']:.2f}")
    for k in ("human", "exhaustive", "agentic", "lambda"):
        v = [r[k] for r in reps]
        print(f"  {label} mean {k:10s} {statistics.fmean(v):8.3f} req/s  "
              f"(min {min(v):.3f}, max {max(v):.3f})")


def main():
    zero, hi = read_run(RUN_ZERO), read_run(RUN_HI)
    print(f"== {RUN_ZERO} (agentic at 0)")
    summary(zero, "0 ")
    print(f"\n== {RUN_HI} (agentic at 36)")
    summary(hi, "36")

    o0 = [r["origin"] for r in zero]
    o1 = [r["origin"] for r in hi]
    n0, n1 = len(o0), len(o1)
    m0, m1 = statistics.fmean(o0), statistics.fmean(o1)
    v0, v1 = statistics.variance(o0) / n0, statistics.variance(o1) / n1
    net = m1 - m0
    se = math.sqrt(v0 + v1)
    t = net / se
    df = (v0 + v1) ** 2 / (v0 ** 2 / (n0 - 1) + v1 ** 2 / (n1 - 1))
    q = t_quantile(0.975, df)
    p_two = 2 * (1 - t_cdf(abs(t), df))
    print("\n== net 0 -> 36 agentic req/s (origin req/s)")
    print(f"  origin at 0 : {m0:.4f} +/- {math.sqrt(v0):.4f}  (n = {n0})")
    print(f"  origin at 36: {m1:.4f} +/- {math.sqrt(v1):.4f}  (n = {n1})")
    print(f"  net        : {net:+.4f} +/- {se:.4f}")
    print(f"  Welch t    : {t:+.3f}   df = {df:.2f}   two-sided p = {p_two:.4f}")
    print(f"  95% CI     : [{net - q * se:+.4f}, {net + q * se:+.4f}]   (t_0.975 = {q:.4f})")


if __name__ == "__main__":
    main()
