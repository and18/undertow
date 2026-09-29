#!/usr/bin/env python3
"""
trav_own_scope_analysis.py — criteri W1-W4 del rilancio degli scope 0,06 e 0,20 con
TRAV_MODE=scen. Implementa esattamente docs/PREREG-lab-trav-own-scope-20260929.md.

Run: da harness/results/replica-own-scope-20260929.tsv sul lab (`ssh lab cat`, sola lettura),
l'ultima riga di ogni punto ('-bis' sostituisce l'originale); in env.txt si controllano
TRAV_MODE e AGENT_SCOPE attesi.

m a scope 0,02: quello misurato il 28 settembre con TRAV_MODE=scen. I run S12 e S36 si leggono
dalla tabella della campagna in docs/RISULTATO-lab-trav-own-20260928.md; m si ricalcola da quei
run a piena precisione (nessun valore arrotondato entra nei calcoli) e si controlla che,
arrotondato a 4 decimali, coincida con il valore scritto nella riga V1 dello stesso documento.

Calcoli: origin_rps di points.csv; Ō e SE = s/sqrt(n); m_s = (Ō(S36_s) − Ō(S12_s)) / 23,9990,
SE = sqrt(SE² + SE²) / 23,9990; t contro zero = m / SE; differenze fra marginali con
t = Δ / sqrt(SE² + SE²).
  W1  m06 > 0 e m20 > 0 con t >= 3; con m02 < 0 (28 set) il cambio di segno regge
  W2  m02 < m06 < m20 con t >= 3 per ciascuna differenza consecutiva
  W3  m06 dentro [+0,1251, +0,1665] e m20 dentro [+0,4057, +0,4404]
  W4  livelli dei 4 punti rispetto all'IC previsto: solo descrittivo
Senza soglia: miss agentico ai due tassi e fattore 13% -> 30% per scope; confronto con i run di
riferimento (glob, 21-22 set).

Uso:
    python3 tools/trav_own_scope_analysis.py
    python3 tools/trav_own_scope_analysis.py --runs S12_006=tre-20260921-214946,... \\
        --mode glob --m02-runs tre-20260921-150237,tre-20260921-162248      # collaudo
"""
import argparse
import csv
import math
import re
import statistics
import sys
from pathlib import Path

import replica_analysis as ra

ROOT = Path(__file__).resolve().parent.parent
RESULT_0928 = ROOT / "docs" / "RISULTATO-lab-trav-own-20260928.md"
MANIFEST = "replica-own-scope-20260929.tsv"
D_RATE = ra.D_RATE                                  # 23,9990
DESIGN = {"S12": ra.DESIGN["S12"], "S36": ra.DESIGN["S36"]}
SCOPE = {"006": "0.06", "020": "0.20"}
POINTS = ("S12_006", "S36_006", "S12_020", "S36_020")
REFERENCE = {"S12_006": "tre-20260921-214946", "S36_006": "tre-20260921-230947",
             "S12_020": "tre-20260922-002958", "S36_020": "tre-20260922-015010"}

# previsioni e criteri: docs/PREREG-lab-trav-own-scope-20260929.md
IC_M = {"006": (0.1251, 0.1665), "020": (0.4057, 0.4404)}
IC_LEVEL = {"S12_006": (40.269, 40.670), "S36_006": (43.514, 44.424),
            "S12_020": (42.278, 42.714), "S36_020": (52.293, 53.003)}


def verdict(ok):
    return "PASSA" if ok else "NON PASSA"


def inside(x, ic):
    return ic[0] <= x <= ic[1]


def env(run):
    out = {}
    for line in ra.lab_cat(f"{run}/env.txt").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def read_point(kind, run):
    """kind = 'S12' o 'S36'. Ō, varianza della media, miss agentico."""
    rows = list(csv.DictReader(ra.lab_cat(f"{run}/points.csv").splitlines()))
    a, b, _ = DESIGN[kind]
    if {(r["alpha"], r["beta"]) for r in rows} != {(a, b)}:
        sys.exit(f"{run}: alpha/beta diversi da {a}/{b}")
    o = [float(r["origin_rps"]) for r in rows]
    g = [1 - float(r["h_agent"]) for r in rows]
    n = len(o)
    return {"run": run, "n": n, "mean": statistics.fmean(o),
            "var_mean": statistics.variance(o) / n, "agent_miss": statistics.fmean(g)}


def marginal(p12, p36):
    d, se, _, _ = ra.welch(p12, p36)
    return d / D_RATE, se / D_RATE


def m02_from_result():
    """Run S12/S36 e m scritto nel RISULTATO del 28 settembre."""
    text = RESULT_0928.read_text(encoding="utf-8")
    runs = {k: re.search(rf"^\| {k} \| `(tre-\d{{8}}-\d{{6}})`", text, re.M) for k in ("S12", "S36")}
    mm = re.search(r"\*\*V1\*\* \(A1\) \| m = \*\*([−-]?\d+,\d+) ± (\d+,\d+)\*\*", text)
    if not all(runs.values()) or not mm:
        sys.exit(f"{RESULT_0928.name}: run S12/S36 o riga V1 non trovati")
    written = float(mm.group(1).replace("−", "-").replace(",", "."))
    return runs["S12"].group(1), runs["S36"].group(1), written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--runs", help="collaudo: punto=run separati da virgole, al posto del manifest")
    ap.add_argument("--mode", default="scen", choices=("scen", "glob"))
    ap.add_argument("--m02-runs", help="collaudo: run S12,S36 per m a 0,02 al posto del RISULTATO")
    a = ap.parse_args()

    if a.runs:
        runs = {k: (v, "ok") for k, v in (x.split("=") for x in a.runs.split(","))}
        print(f"== collaudo: run da --runs (TRAV_MODE atteso {a.mode})")
    else:
        ra.MANIFEST = a.manifest
        runs = ra.read_manifest()
        print(f"== run da {a.manifest} (TRAV_MODE atteso {a.mode})")

    P, usable = {}, set()
    for name in POINTS:
        if name not in runs:
            print(f"  {name}: assente")
            continue
        run, esito = runs[name]
        e = env(run)
        mode = e.get("TRAV_MODE", "") or "glob"
        sc = e.get("AGENT_SCOPE", "0.02")
        if mode != a.mode or sc != SCOPE[name[-3:]]:
            sys.exit(f"{name} {run}: TRAV_MODE={mode} AGENT_SCOPE={sc}, attesi {a.mode} "
                     f"{SCOPE[name[-3:]]}")
        P[name] = read_point(name[:3], run)
        ok = esito == "ok" and P[name]["n"] == 5
        if ok:
            usable.add(name)
        print(f"  {name}  {run}  esito {esito}  ripetizioni {P[name]['n']}  TRAV_MODE {mode}  "
              f"AGENT_SCOPE {sc}{'' if ok else '  -> NON UTILIZZABILE'}")

    if a.m02_runs:
        r12, r36 = a.m02_runs.split(",")
        written = None
        print(f"== m a 0,02: collaudo, run {r12} e {r36}")
    else:
        r12, r36, written = m02_from_result()
        print(f"== m a 0,02: run {r12} e {r36} da {RESULT_0928.name}")
    m02 = marginal(read_point("S12", r12), read_point("S36", r36))
    print(f"  m02 {m02[0]:+.4f} ± {m02[1]:.4f}  (t {m02[0] / m02[1]:+.2f})")
    if written is not None:
        if round(m02[0], 4) != written:
            sys.exit(f"m02 ricalcolato {m02[0]:.6f} diverso dal valore scritto {written}")
        print(f"  coincide con il valore scritto nel RISULTATO ({written:+.4f})")

    m = {"002": m02}
    for sc in ("006", "020"):
        if f"S12_{sc}" in usable and f"S36_{sc}" in usable:
            m[sc] = marginal(P[f"S12_{sc}"], P[f"S36_{sc}"])
            print(f"  m{sc[1:]} {m[sc][0]:+.4f} ± {m[sc][1]:.4f}  (t {m[sc][0] / m[sc][1]:+.2f})")
        else:
            print(f"  m{sc[1:]}: non valutabile (punti non utilizzabili)")

    have = "006" in m and "020" in m
    print("\n== W1 — segno")
    if have:
        pos = all(m[sc][0] > 0 and m[sc][0] / m[sc][1] >= 3 for sc in ("006", "020"))
        neg = m02[0] < 0
        print(f"  m06 > 0 e m20 > 0 con t >= 3: {pos}; m02 < 0: {neg}  ->  W1: {verdict(pos and neg)}"
              f"  (cambio di segno {'regge' if pos and neg else 'non regge'})")
    else:
        print("  non valutabile")

    print("\n== W2 — ordinamento m02 < m06 < m20, t >= 3 per differenza")
    if have:
        oks = []
        for lo, hi in (("002", "006"), ("006", "020")):
            d = m[hi][0] - m[lo][0]
            t = d / math.hypot(m[hi][1], m[lo][1])
            oks.append(d > 0 and t >= 3)
            print(f"  m{hi[1:]} − m{lo[1:]} = {d:+.4f}  t {t:+.2f}")
        print(f"  W2: {verdict(all(oks))}")
    else:
        print("  non valutabile")

    print("\n== W3 — valori dentro l'IC previsto")
    if have:
        oks = []
        for sc in ("006", "020"):
            ok = inside(m[sc][0], IC_M[sc])
            oks.append(ok)
            print(f"  m{sc[1:]} {m[sc][0]:+.4f}  IC [{IC_M[sc][0]:+.4f}, {IC_M[sc][1]:+.4f}]  "
                  f"{verdict(ok)}")
        print(f"  W3: {verdict(all(oks))}")
    else:
        print("  non valutabile")

    print("\n== W4 — livelli rispetto all'IC previsto (solo descrittivo; deriva fra giorni non "
          "inclusa)")
    for name, ic in IC_LEVEL.items():
        if name in P:
            o, se = P[name]["mean"], math.sqrt(P[name]["var_mean"])
            where = "dentro" if inside(o, ic) else ("sotto" if o < ic[0] else "sopra")
            print(f"  {name}: O {o:.4f} ± {se:.4f}  IC [{ic[0]:.3f}, {ic[1]:.3f}]  {where}")

    print("\n== Senza soglia: miss agentico e fattore 13% -> 30% (A2, B3, B4)")
    for sc in ("006", "020"):
        if f"S12_{sc}" in P and f"S36_{sc}" in P:
            g12, g36 = P[f"S12_{sc}"]["agent_miss"], P[f"S36_{sc}"]["agent_miss"]
            print(f"  scope {SCOPE[sc]}: miss agentico {g12:.4f} -> {g36:.4f}  fattore {g12 / g36:.4f}")
    if not a.runs:
        print("\n== Senza soglia: confronto con i run di riferimento (glob, 21-22 set)")
        for sc in ("006", "020"):
            ref = marginal(read_point("S12", REFERENCE[f"S12_{sc}"]),
                           read_point("S36", REFERENCE[f"S36_{sc}"]))
            if sc in m:
                d = m[sc][0] - ref[0]
                print(f"  m{sc[1:]}: glob {ref[0]:+.4f} ± {ref[1]:.4f}  scen {m[sc][0]:+.4f}  "
                      f"differenza {d:+.4f} ± {math.hypot(m[sc][1], ref[1]):.4f}")


if __name__ == "__main__":
    main()
