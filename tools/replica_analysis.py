#!/usr/bin/env python3
"""
replica_analysis.py — criteri R1-R4 della campagna di replica del 24 settembre.

Implementa esattamente docs/PREREG-replica-20260924.md (commit 3abb66f):
  - grandezza: origin_rps di points.csv, media delle 5 ripetizioni,
    SE = deviazione standard campionaria / sqrt(n); SE di una differenza
    sqrt(SE1^2 + SE2^2); t di Welch, df di Welch-Satterthwaite, quantile della
    t di Student (da tools/net_agentic.py);
  - rate agentici configurati (beta*lambda); divisore di R1 = 35,9975 - 11,9985;
  - R1 (A1): m = (O(S36) - O(S12)) / 23,9990; regge se (a) m < 0 e t <= -3
    e (b) |m - m_ref| <= 3 * sqrt(SE_m^2 + SE_ref^2);
  - R2 (A3): d_q = O(Sq) - O(Cq), q = 12 e 36; regge se d_q > 0 e t_q >= 3 per
    entrambi;
  - R3 (A9): n = O(S36) - O(P0); regge se t > -2; IC 95% riportato;
  - R4 (deriva): per i cinque punti, O(nuovo) - O(riferimento), in req/s e in SE.
    Nessuna soglia.
I riferimenti sono ricalcolati dalle ripetizioni dei run storici, non copiati
arrotondati.

I run nuovi si leggono da harness/results/replica-20260924.tsv sul lab. Per ogni
punto vale l'ultima riga (un eventuale "<punto>-bis" sostituisce l'originale); un
punto il cui esito finale non e' "ok" rende NON VALUTABILI i criteri che lo usano.

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/replica_analysis.py            # run della campagna (dal .tsv)
    python3 tools/replica_analysis.py --storici  # collaudo sui run di riferimento
"""
import csv
import math
import statistics
import subprocess
import sys

from net_agentic import t_quantile

MANIFEST = "replica-20260924.tsv"

# punto -> (alpha, beta, lambda) configurati, come nella tabella del disegno
DESIGN = {
    "C12": ("0.2947", "0.1263", 95),
    "S12": ("0.2947", "0.1263", 95),
    "S36": ("0.2353", "0.3025", 119),
    "P0": ("0.3373", "0.0000", 83),
    "C36": ("0.2353", "0.3025", 119),
}

# run di riferimento (tabella del disegno e di R4)
REFERENCE = {
    "C12": "tre-20260920-114026",
    "S12": "tre-20260921-150237",
    "S36": "tre-20260921-162248",
    "P0": "tre-20260920-102015",
    "C36": "tre-20260920-130038",
}

# riferimento di A1 (R1b): i due run separati del 21 settembre
A1_REF = ("S12", "S36")

D_RATE = (float(DESIGN["S36"][1]) * DESIGN["S36"][2]
          - float(DESIGN["S12"][1]) * DESIGN["S12"][2])      # 23,9990


def lab_cat(path):
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{path}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def read_manifest():
    """punto -> (run, esito): l'ultima riga di ogni punto, '-bis' compreso."""
    runs = {}
    for r in csv.DictReader(lab_cat(MANIFEST).splitlines(), delimiter="\t"):
        name = r["punto"].removesuffix("-bis")
        runs[name] = (r["run"], r["esito"])
    return runs


def read_point(name, run):
    rows = list(csv.DictReader(lab_cat(f"{run}/points.csv").splitlines()))
    a, b, _ = DESIGN[name]
    if {(r["alpha"], r["beta"]) for r in rows} != {(a, b)}:
        sys.exit(f"{name} {run}: alpha/beta diversi da {a}/{b}")
    o = [float(r["origin_rps"]) for r in rows]
    n = len(o)
    return {"run": run, "n": n, "mean": statistics.fmean(o),
            "var_mean": statistics.variance(o) / n}


def welch(p1, p2):
    """differenza p2 - p1, SE, t, df di Welch-Satterthwaite."""
    v1, v2 = p1["var_mean"], p2["var_mean"]
    d = p2["mean"] - p1["mean"]
    se = math.sqrt(v1 + v2)
    df = (v1 + v2) ** 2 / (v1 ** 2 / (p1["n"] - 1) + v2 ** 2 / (p2["n"] - 1))
    return d, se, d / se, df


def marginal(p12, p36):
    d, se, t, df = welch(p12, p36)
    return d / D_RATE, se / D_RATE, t, df


def verdict(ok):
    return "PASSA" if ok else "NON PASSA"


def main():
    storici = "--storici" in sys.argv[1:]
    if storici:
        runs = {k: (v, "ok") for k, v in REFERENCE.items()}
        print("== COLLAUDO sui run di riferimento (non sono i run della campagna)")
    else:
        runs = read_manifest()
        print(f"== run della campagna da {MANIFEST}")

    new, valid = {}, {}
    for name in DESIGN:
        run, esito = runs.get(name, (None, "assente"))
        valid[name] = esito == "ok"
        if run is not None:
            new[name] = read_point(name, run)
        print(f"  {name:4s} {run}  esito {esito}")
    ref = {name: read_point(name, run) for name, run in REFERENCE.items()}

    def usable(*names):
        bad = [x for x in names if not valid[x]]
        if bad:
            print(f"  NON VALUTABILE: punto non utilizzabile {', '.join(bad)}")
        return not bad

    # ── R1 ────────────────────────────────────────────────────────────────
    print(f"\n== R1 (A1): marginale S12 -> S36, divisore {D_RATE:.4f}")
    m_ref, se_ref, t_ref, _ = marginal(ref[A1_REF[0]], ref[A1_REF[1]])
    print(f"  riferimento: m_ref {m_ref:+.6f}  SE_ref {se_ref:.6f}  (t {t_ref:+.2f})")
    if usable("S12", "S36"):
        m, se, t, df = marginal(new["S12"], new["S36"])
        a = m < 0 and t <= -3
        tol = 3 * math.sqrt(se ** 2 + se_ref ** 2)
        b = abs(m - m_ref) <= tol
        print(f"  m {m:+.6f}  SE_m {se:.6f}  t {t:+.3f}  (df {df:.2f})")
        print(f"  (a) m < 0 e t <= -3: {verdict(a)}")
        print(f"  (b) |m - m_ref| = {abs(m - m_ref):.6f} <= 3*SE comb. = {tol:.6f}: {verdict(b)}")
        print(f"  R1: {verdict(a and b)}")

    # ── R2 ────────────────────────────────────────────────────────────────
    print("\n== R2 (A3): separata - condivisa")
    if usable("S12", "C12", "S36", "C36"):
        oks = []
        for q in ("12", "36"):
            d, se, t, df = welch(new["C" + q], new["S" + q])
            ok = d > 0 and t >= 3
            oks.append(ok)
            print(f"  q={q}: d {d:+.4f}  SE {se:.4f}  t {t:+.3f}  (df {df:.2f})  {verdict(ok)}")
        print(f"  R2: {verdict(all(oks))}")

    # ── R3 ────────────────────────────────────────────────────────────────
    print("\n== R3 (A9): netto P0 -> S36")
    if usable("P0", "S36"):
        n, se, t, df = welch(new["P0"], new["S36"])
        q = t_quantile(0.975, df)
        print(f"  netto {n:+.4f}  SE {se:.4f}  t {t:+.3f}  df {df:.2f}")
        print(f"  IC 95%: [{n - q * se:+.4f}, {n + q * se:+.4f}]  (t_0.975 = {q:.4f})")
        print(f"  R3 (t > -2): {verdict(t > -2)}")

    # ── R4 ────────────────────────────────────────────────────────────────
    print("\n== R4 (deriva fra giorni): nuovo - riferimento, nessuna soglia")
    for name in DESIGN:
        r = ref[name]
        line = (f"  {name:4s} rif {r['run']}  O {r['mean']:.4f}  SE {math.sqrt(r['var_mean']):.4f}")
        if valid[name]:
            p = new[name]
            d, se, t, _ = welch(r, p)
            line += (f"  | nuovo O {p['mean']:.4f}  SE {math.sqrt(p['var_mean']):.4f}"
                     f"  | delta {d:+.4f} req/s  SE {se:.4f}  = {t:+.2f} SE")
        else:
            line += "  | NON VALUTABILE"
        print(line)


if __name__ == "__main__":
    main()
