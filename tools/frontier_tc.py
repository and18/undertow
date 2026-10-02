#!/usr/bin/env python3
"""
frontier_tc.py — tempo caratteristico approssimato per ciascuna politica della frontiera
(claim A4, A5, A6, D2, D5; docs/VERIFICA-finale-20261002.md, punto 1; claims v3.11).

PERCHE'
  I run della frontiera (19-20 set, λ = 185, α = 0,35, β = 0,10) usano il contatore di
  traversata condiviso: un capitolo passa nella traversata ogni N/λ = 91,6 s ed e' richiesto
  dall'esaustiva con probabilita' α. Se il ritorno cade entro il tempo caratteristico T della
  cache, gli hit esaustivi possono essere gonfiati. T dipende dalla politica.

COME
  T ≈ C / origin_rps, con C = 5 263 oggetti (C2, data/derived/cache_capacity.csv) e origin_rps
  la media delle ripetizioni di points.csv. origin_rps conta i miss serviti con 200
  (workload.js): i 403 del blocco sono no-store e i 503 del rinvio non sono cacheabili, quindi
  e' il tasso con cui entrano oggetti in cache. E' un'approssimazione, non una misura di T.

Il lab resta in sola lettura: solo `ssh lab cat` (a lab spento, ~/undertow-backup/shim-scope).

Uso:
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

# politica -> run (registry: frontiera del 19-20 set)
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
        print(f"  {key:3s} {label:30s} origine {org:7.3f}  T {t:6.1f} s  ritorno {ret:.1f} s  "
              f"entro T: {within}")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["policy", "label", "run", "reps", "origin_rps", "T_s", "return_s",
                    "return_within_T"])
        w.writerows(rows)
    print(f"capienza {cap:.1f} oggetti; ritorno nella traversata {ret:.1f} s "
          f"(richiesto dall'esaustiva con probabilita' {ALPHA})\nscritto {OUT_CSV}")


if __name__ == "__main__":
    main()
