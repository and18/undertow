#!/usr/bin/env python3
"""
figA3_data.py — generates data/derived/figA3_honeypot.csv (FIG-A3, claim C3, C5).

The CSV used to be written by hand. Now it reads only aggregates already written by other scripts:
  data/derived/honeypot_window.csv       agent row: clients, median, mean, p90, max of distinct
                                         URLs at the peak in 143 s (tools/honeypot_aggregate.py)
  data/derived/honeypot_contiguity.csv   agent row: pairs, contiguous, repeated, connections
                                         and clients with pairs (tools/honeypot_aggregate.py)
  data/derived/honeypot_totals.csv       window [from, to) in UTC
  data/derived/generator_contiguity.csv  same metric on the generator
                                         (tools/generator_contiguity.py)
and computes on the generator:
  testbed_ws   expected number of distinct objects touched by the agentic class in 143 s at the
               lowest point (scope 0.02, configured β·λ = 0.1263 · 95 req/s), with the
               sessions of AGENT_SESSION contiguous chapters of workload.js: bases
               (r·AGENT_MUL + SEED) mod N, rank r with P(r) = ((r+1)/S)^(1−s) − (r/S)^(1−s),
               S = floor(N·scope), s = AGENT_SKEW; sessions in 143 s = β·λ·143 / AGENT_SESSION;
               E[objects] = Σ_o 1 − (1 − q_o)^sessions, q_o = probability that a session
               touches object o

No logs and no per-client data: only the aggregated CSVs above.

Usage:
    python3 tools/figA3_data.py
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "derived"
OUT_CSV = D / "figA3_honeypot.csv"

N, SEED = 16954, 42
SCOPE, SESSION, SKEW, AGENT_MUL = 0.02, 3, 0.6, 3266489917
BETA_LAMBDA = (0.1263, 95.0)      # β and λ of run tre-20260921-150237 (env.txt, points.csv)
WINDOW_S = 143


def read(name):
    with (D / name).open(newline="") as f:
        return list(csv.DictReader(f))


def row(name, cls):
    return next(r for r in read(name) if r["class"] == cls)


def testbed_ws():
    s = max(1, math.floor(N * SCOPE))
    p = [((r + 1) / s) ** (1 - SKEW) - (r / s) ** (1 - SKEW) for r in range(s)]
    base = {}
    for r, pr in enumerate(p):
        b = (r * AGENT_MUL + SEED) % N
        base[b] = base.get(b, 0.0) + pr
    sessions = BETA_LAMBDA[0] * BETA_LAMBDA[1] * WINDOW_S / SESSION
    objs = {(b + k) % N for b in base for k in range(SESSION)}
    return sum(1 - (1 - sum(base.get((o - k) % N, 0.0) for k in range(SESSION))) ** sessions
               for o in objs)


def main():
    w, c = row("honeypot_window.csv", "agent"), row("honeypot_contiguity.csv", "agent")
    tot = {r["quantity"]: r["value"] for r in read("honeypot_totals.csv")}
    g = read("generator_contiguity.csv")[0]
    if int(tot["window_s"]) != WINDOW_S:
        raise SystemExit(f"honeypot_totals.csv: window {tot['window_s']} s, expected {WINDOW_S}")
    period = f"{tot['window_from_utc'][:10]} to {tot['window_to_utc_excluded'][:10]} (excluded), UTC"
    ws = testbed_ws()
    n = w["clients"]
    rows = [
        ["agent_clients", n, "clients", f"agent-class clients with >= 5 requests; {period}"],
        ["agent_ws_median", w["median"], "objects", f"{n} agent clients; distinct objects per 143 s window"],
        ["agent_ws_mean", w["mean"], "objects", f"{n} agent clients"],
        ["agent_ws_p90", w["p90"], "objects", f"{n} agent clients"],
        ["agent_ws_max", w["max"], "objects", f"{n} agent clients"],
        ["testbed_ws", f"{ws:.1f}", "objects", "scope 0.02 at 0.1263 x 95 req/s; expected distinct objects per 143 s window"],
        ["contiguity_observed", c["contiguous_pct"], "percent", "honeypot agent class; consecutive request pairs on one TCP connection"],
        ["repeated_observed", c["repeated_pct"], "percent", "honeypot agent class; same pairs"],
        ["pairs_observed", c["pairs"], "pairs", "honeypot agent class"],
        ["connections_observed", c["connections_with_pairs"], "connections", "agent TCP connections with at least one pair"],
        ["clients_observed", c["clients_with_pairs"], "clients", "clients of those connections"],
        ["contiguity_generator", g["contiguous_pct"], "percent", f"generator; consecutive agentic requests of one k6 VU; mean of {g['seeds']} seeds"],
        ["repeated_generator", g["repeated_pct"], "percent", "generator; same pairs"],
        ["seeds_generator", g["seeds"], "seeds", "generator simulations averaged"],
        ["pairs_generator", g["pairs"], "pairs", f"generator; scope {g['scope']}, {g['vus_with_pairs']} VUs, {g['measure_s']} s"],
        ["window_from_utc", tot["window_from_utc"], "", "honeypot window start"],
        ["window_to_utc_excluded", tot["window_to_utc_excluded"], "", "honeypot window end, excluded"],
    ]
    with OUT_CSV.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["quantity", "value", "unit", "note"])
        wr.writerows(rows)
    for r in rows:
        print(f"  {r[0]:24s} {r[1]}")
    print(f"written {OUT_CSV}")


if __name__ == "__main__":
    main()
