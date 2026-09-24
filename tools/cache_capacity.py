#!/usr/bin/env python3
"""
cache_capacity.py — ricostruisce C2 (capienza della cache in oggetti) da fonte rintracciabile.

Il valore di C2 (5 274 oggetti) era annotato solo in docs/decisions.md §30, dall'output
di harness/load/capacity.sh, mai archiviato. Qui lo si rilegge da VictoriaMetrics, dove
varnish-exporter lo ha registrato durante le campagne: per i due run a scope 0,20
(insieme agentico 1,93x la capienza, quindi cache satura), per ogni ripetizione si
prende la finestra di misura [ts - measure, ts] e si interrogano
  varnish_main_n_object            oggetti in cache (min, media, max nella finestra)
  varnish_sma_s0_g_bytes / g_space byte occupati e liberi dello storage s0 (media;
                                   transient e' uno storage separato, escluso)
  varnish_main_n_lru_nuked         evizioni LRU nella finestra (prova di saturazione)
Scrive data/derived/cache_capacity.csv (una riga per ripetizione) e stampa la media.

Il lab resta in sola lettura: points.csv via `ssh lab cat`, VictoriaMetrics via il
tunnel aperto da chi lancia lo script.

Uso:
    ssh lab 'cd ~/undertow/harness && docker compose up -d victoriametrics'
    ssh -N -L 8428:localhost:8428 lab &   # tunnel in background
    python3 tools/cache_capacity.py
    kill %1
    ssh lab 'cd ~/undertow/harness && docker compose stop victoriametrics'
"""
import csv
import json
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "cache_capacity.csv"
RUNS = ["tre-20260922-002958", "tre-20260922-015010"]      # scope 0,20
VM_URL = "http://localhost:8428/api/v1/query"
QUERIES = {
    "n_object_min": "min_over_time(varnish_main_n_object[{d}s])",
    "n_object_avg": "avg_over_time(varnish_main_n_object[{d}s])",
    "n_object_max": "max_over_time(varnish_main_n_object[{d}s])",
    "bytes_used": "avg_over_time(varnish_sma_s0_g_bytes[{d}s])",
    "bytes_free": "avg_over_time(varnish_sma_s0_g_space[{d}s])",
    "lru_nuked": "increase(varnish_main_n_lru_nuked[{d}s])",
}


def fetch_points_csv(run):
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{run}/points.csv"],
                         capture_output=True, text=True, check=True)
    return list(csv.DictReader(out.stdout.splitlines()))


def query(q, end_ts):
    url = f"{VM_URL}?{urllib.parse.urlencode({'query': q, 'time': end_ts})}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        result = json.load(resp).get("data", {}).get("result", [])
    if not result:
        raise RuntimeError(f"nessun risultato da VictoriaMetrics per time={end_ts} (query: {q})")
    if len(result) > 1:
        raise RuntimeError(f"{len(result)} serie per {q}: attese una")
    return float(result[0]["value"][1])


def main():
    rows = []
    for run in RUNS:
        for p in fetch_points_csv(run):
            end_ts = int(datetime.fromisoformat(p["ts"]).astimezone(timezone.utc).timestamp())
            d = int(float(p["measure"]))
            v = {k: query(q.format(d=d), end_ts) for k, q in QUERIES.items()}
            rows.append({"run": run, "rep": p["rep"], "ts": p["ts"], "measure": d, **v})
            print(f"  {run} rep {p['rep']}  n_object min/avg/max {v['n_object_min']:.0f} / "
                  f"{v['n_object_avg']:.1f} / {v['n_object_max']:.0f}  "
                  f"usati {v['bytes_used']:.0f} B  liberi {v['bytes_free']:.0f} B  "
                  f"lru_nuked {v['lru_nuked']:.0f}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["run", "rep", "ts", "measure"] + list(QUERIES)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.1f}" if isinstance(r[k], float) else r[k]) for k in cols})
    print(f"scritto {OUT_CSV}")

    avg = [r["n_object_avg"] for r in rows]
    cap = statistics.fmean(avg)
    se = statistics.stdev(avg) / len(avg) ** 0.5
    used = statistics.fmean(r["bytes_used"] for r in rows)
    free = statistics.fmean(r["bytes_free"] for r in rows)
    print(f"\ncapienza (media delle {len(rows)} finestre): {cap:.1f} +/- {se:.1f} oggetti   "
          f"min {min(r['n_object_min'] for r in rows):.0f}  max {max(r['n_object_max'] for r in rows):.0f}")
    print(f"byte occupati {used:.0f}  liberi {free:.0f}  oggetto medio {used / cap / 1024:.2f} KiB")
    print(f"scostamento da 5 274: {100 * (cap - 5274) / 5274:+.2f}%")


if __name__ == "__main__":
    main()
