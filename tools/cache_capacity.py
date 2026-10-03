#!/usr/bin/env python3
"""
cache_capacity.py — rebuilds C2 (cache capacity in objects) from a traceable source.

The value of C2 (5,274 objects) was only noted in docs/decisions.md §30, from the output
of harness/load/capacity.sh, never archived. Here it is re-read from VictoriaMetrics, where
varnish-exporter recorded it during the campaigns: for the two runs at scope 0.20
(agentic set 1.93x the capacity, hence a saturated cache), for each repetition the
measurement window [ts - measure, ts] is taken and the following are queried
  varnish_main_n_object            objects in cache (min, mean, max in the window)
  varnish_sma_s0_g_bytes / g_space bytes used and free of storage s0 (mean;
                                   transient is a separate storage, excluded)
  varnish_main_n_lru_nuked         LRU evictions in the window (proof of saturation)
Writes data/derived/cache_capacity.csv (one row per repetition) and prints the mean.

The lab stays read-only: points.csv via `ssh lab cat`, VictoriaMetrics via the
tunnel opened by whoever launches the script.

Usage:
    ssh lab 'cd ~/undertow/harness && docker compose up -d victoriametrics'
    ssh -N -L 8428:localhost:8428 lab &   # tunnel in the background
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
RUNS = ["tre-20260922-002958", "tre-20260922-015010"]      # scope 0.20
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
        raise RuntimeError(f"no result from VictoriaMetrics for time={end_ts} (query: {q})")
    if len(result) > 1:
        raise RuntimeError(f"{len(result)} series for {q}: expected one")
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
                  f"used {v['bytes_used']:.0f} B  free {v['bytes_free']:.0f} B  "
                  f"lru_nuked {v['lru_nuked']:.0f}")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["run", "rep", "ts", "measure"] + list(QUERIES)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.1f}" if isinstance(r[k], float) else r[k]) for k in cols})
    print(f"written {OUT_CSV}")

    avg = [r["n_object_avg"] for r in rows]
    cap = statistics.fmean(avg)
    se = statistics.stdev(avg) / len(avg) ** 0.5
    used = statistics.fmean(r["bytes_used"] for r in rows)
    free = statistics.fmean(r["bytes_free"] for r in rows)
    print(f"\ncapacity (mean of the {len(rows)} windows): {cap:.1f} +/- {se:.1f} objects   "
          f"min {min(r['n_object_min'] for r in rows):.0f}  max {max(r['n_object_max'] for r in rows):.0f}")
    print(f"bytes used {used:.0f}  free {free:.0f}  average object {used / cap / 1024:.2f} KiB")
    print(f"deviation from 5,274: {100 * (cap - 5274) / 5274:+.2f}%")


if __name__ == "__main__":
    main()
