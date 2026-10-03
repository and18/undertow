#!/usr/bin/env python3
"""
trav_own_analysis.py — criteria V1-V5 of the rerun with the exhaustive traversal in a scenario
of its own (TRAV_MODE=scen). Implements exactly docs/PREREG-lab-trav-own-20260928.md.

Reads the runs from harness/results/replica-own-20260928.tsv on the lab (`ssh lab cat`, read-only):
for each point the last row of the manifest (the '-bis' redo replaces the original).
Checks in the env.txt of each run the expected traversal mode.

Calculations (as the replica, tools/replica_analysis.py): origin_rps of points.csv per repetition;
mean and SE = s/sqrt(n) per point; differences with SE = sqrt(SE1^2 + SE2^2); Welch t with
Welch-Satterthwaite df; divisor of m 23.9990 (configured rates); exhaustive miss = 1 - h_trav.
No rounded value enters the calculations.

  V1  m = (O(S36) - O(S12)) / 23.9990 < 0 and inside [-0.0450, -0.0076]
  V2  d12 = O(S12) - O(C12), d36 = O(S36) - O(C36): > 0, t >= 3, inside [+0.355, +1.422] and
      [+0.624, +1.147]
  V3  net O(S36) - O(P0) inside [+0.74, +1.46]
  V4  Delta exhaustive miss S36 - P0 inside [-0.0341, -0.0207]
  V5  levels of the 5 points against the predicted CI: descriptive only (drift between days not
      included in the CIs)
Also reported: t of m against zero, 95% CI of the net, exhaustive term of B2
(alpha*lambda)36 * miss_e(S36) - (alpha*lambda)12 * miss_e(S12).

Usage:
    python3 tools/trav_own_analysis.py
    python3 tools/trav_own_analysis.py --manifest replica-20260924.tsv --mode glob   # check
"""
import argparse
import csv
import math
import statistics
import sys

import replica_analysis as ra
from net_agentic import t_quantile

DESIGN = ra.DESIGN                      # point -> (alpha, beta, lambda) configured
D_RATE = ra.D_RATE                      # 23.9990
RATE_E = {p: float(a) * lam for p, (a, _, lam) in DESIGN.items()}   # alpha*lambda

# predictions and criteria: docs/PREREG-lab-trav-own-20260928.md
IC_LEVEL = {"C12": (36.842, 37.495), "S12": (37.635, 38.479), "S36": (37.271, 37.580),
            "P0": (36.000, 36.651), "C36": (36.329, 36.752)}
IC_M = (-0.0450, -0.0076)
IC_D = {"12": (0.355, 1.422), "36": (0.624, 1.147)}
IC_NET = (0.74, 1.46)
IC_EXH = (-0.0341, -0.0207)


def verdict(ok):
    return "PASSA" if ok else "NON PASSA"


def inside(x, ic):
    return ic[0] <= x <= ic[1]


def trav_mode(run):
    """Value of TRAV_MODE in env.txt ('glob' if absent or empty)."""
    for line in ra.lab_cat(f"{run}/env.txt").splitlines():
        if line.startswith("TRAV_MODE="):
            return line.split("=", 1)[1] or "glob"
    return "glob"


def read_point(name, run):
    """As replica_analysis.read_point, plus the exhaustive miss per repetition."""
    rows = list(csv.DictReader(ra.lab_cat(f"{run}/points.csv").splitlines()))
    a, b, _ = DESIGN[name]
    if {(r["alpha"], r["beta"]) for r in rows} != {(a, b)}:
        sys.exit(f"{name} {run}: alpha/beta different from {a}/{b}")
    o = [float(r["origin_rps"]) for r in rows]
    e = [1 - float(r["h_trav"]) for r in rows]
    n = len(o)
    return {"run": run, "n": n, "mean": statistics.fmean(o),
            "var_mean": statistics.variance(o) / n,
            "exh": statistics.fmean(e), "exh_var_mean": statistics.variance(e) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="replica-own-20260928.tsv")
    ap.add_argument("--mode", default="scen", choices=("scen", "glob"),
                    help="TRAV_MODE expected in env.txt (glob only for the check)")
    a = ap.parse_args()

    ra.MANIFEST = a.manifest
    runs = ra.read_manifest()
    print(f"== runs from {a.manifest} (expected TRAV_MODE: {a.mode})")
    P, usable = {}, set()
    for name in ("C12", "S12", "S36", "P0", "C36"):
        if name not in runs:
            print(f"  {name}: absent from the manifest")
            continue
        run, esito = runs[name]
        mode = trav_mode(run)
        if mode != a.mode:
            sys.exit(f"{name} {run}: TRAV_MODE={mode} in env.txt, expected {a.mode}")
        P[name] = read_point(name, run)
        ok = esito == "ok" and P[name]["n"] == 5
        if ok:
            usable.add(name)
        print(f"  {name}  {run}  outcome {esito}  repetitions {P[name]['n']}  TRAV_MODE {mode}"
              f"{'' if ok else '  -> NOT USABLE'}")

    def need(*names):
        miss = [n for n in names if n not in usable]
        if miss:
            print(f"  not evaluable: points not usable {', '.join(miss)}")
        return not miss

    print("\n== V1 (A1): m = (O(S36) - O(S12)) / 23.9990")
    if need("S12", "S36"):
        d, se, t, df = ra.welch(P["S12"], P["S36"])
        m, sm = d / D_RATE, se / D_RATE
        ok = m < 0 and inside(m, IC_M)
        print(f"  m {m:+.4f} ± {sm:.4f}  t against zero {t:+.2f} (df {df:.2f})  "
              f"predicted CI [{IC_M[0]:+.4f}, {IC_M[1]:+.4f}]  V1: {verdict(ok)}")

    print("\n== V2 (A3): d = O(Sq) - O(Cq)")
    if need("S12", "C12", "S36", "C36"):
        oks = []
        for q in ("12", "36"):
            d, se, t, df = ra.welch(P[f"C{q}"], P[f"S{q}"])
            ok = d > 0 and t >= 3 and inside(d, IC_D[q])
            oks.append(ok)
            print(f"  d{q} {d:+.4f} ± {se:.4f}  t {t:+.2f} (df {df:.2f})  predicted CI "
                  f"[{IC_D[q][0]:+.3f}, {IC_D[q][1]:+.3f}]  {verdict(ok)}")
        print(f"  V2: {verdict(all(oks))}")

    print("\n== V3 (A9): net O(S36) - O(P0)")
    if need("S36", "P0"):
        d, se, t, df = ra.welch(P["P0"], P["S36"])
        q = t_quantile(0.975, df)
        print(f"  net {d:+.4f} ± {se:.4f}  t {t:+.2f} (df {df:.2f})  95% CI "
              f"[{d - q * se:+.4f}, {d + q * se:+.4f}]  predicted interval "
              f"[{IC_NET[0]:+.2f}, {IC_NET[1]:+.2f}]  V3: {verdict(inside(d, IC_NET))}")

    print("\n== V4 (D8, B2): Delta exhaustive miss S36 - P0")
    if need("S36", "P0"):
        e0, e36 = P["P0"]["exh"], P["S36"]["exh"]
        se = math.sqrt(P["P0"]["exh_var_mean"] + P["S36"]["exh_var_mean"])
        d = e36 - e0
        print(f"  exhaustive miss P0 {e0:.4f} ± {math.sqrt(P['P0']['exh_var_mean']):.4f}  ->  "
              f"S36 {e36:.4f} ± {math.sqrt(P['S36']['exh_var_mean']):.4f}")
        print(f"  Delta {d:+.4f} ± {se:.4f}  predicted CI [{IC_EXH[0]:+.4f}, {IC_EXH[1]:+.4f}]  "
              f"V4: {verdict(inside(d, IC_EXH))}")
    if need("S12", "S36"):
        e12, e36 = P["S12"]["exh"], P["S36"]["exh"]
        term = RATE_E["S36"] * e36 - RATE_E["S12"] * e12
        se = math.sqrt(RATE_E["S36"] ** 2 * P["S36"]["exh_var_mean"]
                       + RATE_E["S12"] ** 2 * P["S12"]["exh_var_mean"])
        print(f"  exhaustive term of B2 (S12 -> S36): {term:+.4f} ± {se:.4f} req/s "
              f"(miss_e {e12:.4f} -> {e36:.4f}; alpha*lambda {RATE_E['S12']:.4f} -> "
              f"{RATE_E['S36']:.4f})")

    print("\n== V5: levels against the predicted CI (descriptive only; drift between days up to "
          "0.154 req/s not included)")
    for name, ic in IC_LEVEL.items():
        if name in P:
            o, se = P[name]["mean"], math.sqrt(P[name]["var_mean"])
            where = "inside" if inside(o, ic) else ("below" if o < ic[0] else "above")
            print(f"  {name}: O {o:.4f} ± {se:.4f}  CI [{ic[0]:.3f}, {ic[1]:.3f}]  {where}")


if __name__ == "__main__":
    main()
