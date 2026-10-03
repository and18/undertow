#!/usr/bin/env python3
"""
cpu_validation.py — rebuilds C1 from a traceable source.

For the 5 frontier policies of 19 September (A, B, C, D4, D6):
reads the points.csv of the runs already used in FIG-03/FIG-05, for each repetition
takes the measurement window [ts - measure, ts] and queries VictoriaMetrics
on the lab (via SSH tunnel on localhost:8428) for the mean CPU in cores of
PostgreSQL (node_cpu_seconds_total{cpu=~"3|4|5",mode!="idle"}, cores 3-5,
see harness/.env: CPUSET_DB=3,4,5, CPUSET_APP=2 — the defaults "3,4"/"5" of
harness/docker-compose.yml are not the ones in use on the lab). Averages the
repetitions per policy and writes data/derived/fig06_cpu_validation.csv.

The lab stays read-only: this script reads points.csv via `ssh lab
cat ...` and queries VictoriaMetrics through the tunnel already opened by whoever
launches it. It starts, stops and modifies nothing on the lab.

Usage:
    ssh lab 'cd ~/undertow/harness && docker compose up -d victoriametrics'
    ssh -N -L 8428:localhost:8428 lab &   # tunnel in the background
    python3 tools/cpu_validation.py
    kill %1                                # closes the tunnel
    ssh lab 'cd ~/undertow/harness && docker compose stop victoriametrics'
"""
import csv
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig06_cpu_validation.csv"

RUNS = {
    "A": "tre-20260919-072040",
    "B": "tre-20260919-080920",
    "C": "tre-20260919-085754",
    "D4": "tre-20260919-094627",
    "D6": "tre-20260919-103501",
}

VM_URL = "http://localhost:8428/api/v1/query"
CPU_QUERY = 'sum(increase(node_cpu_seconds_total{{cpu=~"3|4|5",mode!="idle"}}[{dur}s]))'


def fetch_points_csv(run):
    out = subprocess.run(
        ["ssh", "lab", f"cat ~/undertow/harness/results/{run}/points.csv"],
        capture_output=True, text=True, check=True,
    )
    return list(csv.DictReader(out.stdout.splitlines()))


def query_cpu_cores(end_ts, duration_s):
    q = CPU_QUERY.format(dur=duration_s)
    url = f"{VM_URL}?{urllib.parse.urlencode({'query': q, 'time': end_ts})}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        payload = json.load(resp)
    result = payload.get("data", {}).get("result", [])
    if not result:
        raise RuntimeError(f"no result from VictoriaMetrics for time={end_ts} dur={duration_s}s "
                            f"(query: {q})")
    cpu_seconds = float(result[0]["value"][1])
    return cpu_seconds / duration_s


def _fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_res = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot
    resid = [(y - (a + b * x)) / (a + b * x) * 100 for x, y in zip(xs, ys)]
    return a, b, r2, resid


def main():
    rows_out = []
    for policy, run in RUNS.items():
        pts = fetch_points_csv(run)
        if not pts:
            sys.exit(f"points.csv empty for {policy} ({run})")
        origin_vals = []
        cpu_vals = []
        for row in pts:
            end_dt = datetime.fromisoformat(row["ts"]).astimezone(timezone.utc)
            end_ts = int(end_dt.timestamp())
            duration = int(float(row["measure"]))
            cpu_cores = query_cpu_cores(end_ts, duration)
            origin_vals.append(float(row["origin_rps"]))
            cpu_vals.append(cpu_cores)
            print(f"  {policy} rep ts={row['ts']} measure={duration}s "
                  f"origin_rps={origin_vals[-1]:.2f} cpu_cores={cpu_cores:.4f}")
        reps = len(pts)
        origin_mean = sum(origin_vals) / reps
        cpu_mean = sum(cpu_vals) / reps
        rows_out.append((policy, origin_mean, cpu_mean, reps))
        print(f"{policy}: origin_rps={origin_mean:.3f} cpu_cores={cpu_mean:.4f} reps={reps}\n")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["policy", "origin_rps", "cpu_cores", "reps"])
        for policy, origin_mean, cpu_mean, reps in rows_out:
            w.writerow([policy, f"{origin_mean:.4f}", f"{cpu_mean:.6f}", reps])
    print(f"written {OUT_CSV}")

    xs = [r[1] for r in rows_out]
    ys = [r[2] for r in rows_out]
    a, b, r2, resid = _fit(xs, ys)
    max_resid = max(abs(r) for r in resid)
    print(f"\nfit: CPU = {a:.6f} + {b:.6f} x origin_rps   R^2 = {r2:.6f}   "
          f"max residual = {max_resid:.2f}%")
    for (policy, x, y, _reps), e in zip(rows_out, resid):
        print(f"  {policy}: origin_rps={x:.3f} cpu_cores={y:.4f} residual={e:+.2f}%")


if __name__ == "__main__":
    main()
