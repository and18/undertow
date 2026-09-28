#!/usr/bin/env python3
"""
trav_own_analysis.py — criteri V1-V5 del rilancio con la traversata esaustiva in uno scenario
proprio (TRAV_MODE=scen). Implementa esattamente docs/PREREG-lab-trav-own-20260928.md.

Legge i run da harness/results/replica-own-20260928.tsv sul lab (`ssh lab cat`, sola lettura):
per ogni punto l'ultima riga del manifest (il rifacimento '-bis' sostituisce l'originale).
Controlla in env.txt di ogni run la modalita' della traversata attesa.

Calcoli (come la replica, tools/replica_analysis.py): origin_rps di points.csv per ripetizione;
media e SE = s/sqrt(n) per punto; differenze con SE = sqrt(SE1^2 + SE2^2); t di Welch con df di
Welch-Satterthwaite; divisore di m 23,9990 (rate configurati); miss esaustivo = 1 - h_trav.
Nessun valore arrotondato entra nei calcoli.

  V1  m = (O(S36) - O(S12)) / 23,9990 < 0 e dentro [-0,0450, -0,0076]
  V2  d12 = O(S12) - O(C12), d36 = O(S36) - O(C36): > 0, t >= 3, dentro [+0,355, +1,422] e
      [+0,624, +1,147]
  V3  netto O(S36) - O(P0) dentro [+0,74, +1,46]
  V4  Delta miss esaustivo S36 - P0 dentro [-0,0341, -0,0207]
  V5  livelli dei 5 punti rispetto all'IC previsto: solo descrittivo (deriva fra giorni non
      inclusa negli IC)
Si riportano anche: t di m contro zero, IC 95% del netto, termine esaustivo di B2
(alpha*lambda)36 * miss_e(S36) - (alpha*lambda)12 * miss_e(S12).

Uso:
    python3 tools/trav_own_analysis.py
    python3 tools/trav_own_analysis.py --manifest replica-20260924.tsv --mode glob   # collaudo
"""
import argparse
import csv
import math
import statistics
import sys

import replica_analysis as ra
from net_agentic import t_quantile

DESIGN = ra.DESIGN                      # punto -> (alpha, beta, lambda) configurati
D_RATE = ra.D_RATE                      # 23,9990
RATE_E = {p: float(a) * lam for p, (a, _, lam) in DESIGN.items()}   # alpha*lambda

# previsioni e criteri: docs/PREREG-lab-trav-own-20260928.md
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
    """Valore di TRAV_MODE in env.txt ('glob' se assente o vuota)."""
    for line in ra.lab_cat(f"{run}/env.txt").splitlines():
        if line.startswith("TRAV_MODE="):
            return line.split("=", 1)[1] or "glob"
    return "glob"


def read_point(name, run):
    """Come replica_analysis.read_point, piu' il miss esaustivo per ripetizione."""
    rows = list(csv.DictReader(ra.lab_cat(f"{run}/points.csv").splitlines()))
    a, b, _ = DESIGN[name]
    if {(r["alpha"], r["beta"]) for r in rows} != {(a, b)}:
        sys.exit(f"{name} {run}: alpha/beta diversi da {a}/{b}")
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
                    help="TRAV_MODE atteso in env.txt (glob solo per il collaudo)")
    a = ap.parse_args()

    ra.MANIFEST = a.manifest
    runs = ra.read_manifest()
    print(f"== run da {a.manifest} (TRAV_MODE atteso: {a.mode})")
    P, usable = {}, set()
    for name in ("C12", "S12", "S36", "P0", "C36"):
        if name not in runs:
            print(f"  {name}: assente dal manifest")
            continue
        run, esito = runs[name]
        mode = trav_mode(run)
        if mode != a.mode:
            sys.exit(f"{name} {run}: TRAV_MODE={mode} in env.txt, atteso {a.mode}")
        P[name] = read_point(name, run)
        ok = esito == "ok" and P[name]["n"] == 5
        if ok:
            usable.add(name)
        print(f"  {name}  {run}  esito {esito}  ripetizioni {P[name]['n']}  TRAV_MODE {mode}"
              f"{'' if ok else '  -> NON UTILIZZABILE'}")

    def need(*names):
        miss = [n for n in names if n not in usable]
        if miss:
            print(f"  non valutabile: punti non utilizzabili {', '.join(miss)}")
        return not miss

    print("\n== V1 (A1): m = (O(S36) - O(S12)) / 23,9990")
    if need("S12", "S36"):
        d, se, t, df = ra.welch(P["S12"], P["S36"])
        m, sm = d / D_RATE, se / D_RATE
        ok = m < 0 and inside(m, IC_M)
        print(f"  m {m:+.4f} ± {sm:.4f}  t contro zero {t:+.2f} (df {df:.2f})  "
              f"IC previsto [{IC_M[0]:+.4f}, {IC_M[1]:+.4f}]  V1: {verdict(ok)}")

    print("\n== V2 (A3): d = O(Sq) - O(Cq)")
    if need("S12", "C12", "S36", "C36"):
        oks = []
        for q in ("12", "36"):
            d, se, t, df = ra.welch(P[f"C{q}"], P[f"S{q}"])
            ok = d > 0 and t >= 3 and inside(d, IC_D[q])
            oks.append(ok)
            print(f"  d{q} {d:+.4f} ± {se:.4f}  t {t:+.2f} (df {df:.2f})  IC previsto "
                  f"[{IC_D[q][0]:+.3f}, {IC_D[q][1]:+.3f}]  {verdict(ok)}")
        print(f"  V2: {verdict(all(oks))}")

    print("\n== V3 (A9): netto O(S36) - O(P0)")
    if need("S36", "P0"):
        d, se, t, df = ra.welch(P["P0"], P["S36"])
        q = t_quantile(0.975, df)
        print(f"  netto {d:+.4f} ± {se:.4f}  t {t:+.2f} (df {df:.2f})  IC 95% "
              f"[{d - q * se:+.4f}, {d + q * se:+.4f}]  intervallo previsto "
              f"[{IC_NET[0]:+.2f}, {IC_NET[1]:+.2f}]  V3: {verdict(inside(d, IC_NET))}")

    print("\n== V4 (D8, B2): Delta miss esaustivo S36 - P0")
    if need("S36", "P0"):
        e0, e36 = P["P0"]["exh"], P["S36"]["exh"]
        se = math.sqrt(P["P0"]["exh_var_mean"] + P["S36"]["exh_var_mean"])
        d = e36 - e0
        print(f"  miss esaustivo P0 {e0:.4f} ± {math.sqrt(P['P0']['exh_var_mean']):.4f}  ->  "
              f"S36 {e36:.4f} ± {math.sqrt(P['S36']['exh_var_mean']):.4f}")
        print(f"  Delta {d:+.4f} ± {se:.4f}  IC previsto [{IC_EXH[0]:+.4f}, {IC_EXH[1]:+.4f}]  "
              f"V4: {verdict(inside(d, IC_EXH))}")
    if need("S12", "S36"):
        e12, e36 = P["S12"]["exh"], P["S36"]["exh"]
        term = RATE_E["S36"] * e36 - RATE_E["S12"] * e12
        se = math.sqrt(RATE_E["S36"] ** 2 * P["S36"]["exh_var_mean"]
                       + RATE_E["S12"] ** 2 * P["S12"]["exh_var_mean"])
        print(f"  termine esaustivo di B2 (S12 -> S36): {term:+.4f} ± {se:.4f} req/s "
              f"(miss_e {e12:.4f} -> {e36:.4f}; alpha*lambda {RATE_E['S12']:.4f} -> "
              f"{RATE_E['S36']:.4f})")

    print("\n== V5: livelli rispetto all'IC previsto (solo descrittivo; deriva fra giorni fino a "
          "0,154 req/s non inclusa)")
    for name, ic in IC_LEVEL.items():
        if name in P:
            o, se = P[name]["mean"], math.sqrt(P[name]["var_mean"])
            where = "dentro" if inside(o, ic) else ("sotto" if o < ic[0] else "sopra")
            print(f"  {name}: O {o:.4f} ± {se:.4f}  IC [{ic[0]:.3f}, {ic[1]:.3f}]  {where}")


if __name__ == "__main__":
    main()
