#!/usr/bin/env python3
"""
figA3_data.py — genera data/derived/figA3_honeypot.csv (FIG-A3, claim C3, C5).

Prima il CSV era scritto a mano. Ora legge solo aggregati gia' scritti da altri script:
  data/derived/honeypot_window.csv       riga agent: client, mediana, media, p90, max di URL
                                         distinti al picco in 143 s (tools/honeypot_aggregate.py)
  data/derived/honeypot_contiguity.csv   riga agent: coppie, contigue, ripetute, connessioni
                                         e client con coppie (tools/honeypot_aggregate.py)
  data/derived/honeypot_totals.csv       finestra [from, to) in UTC
  data/derived/generator_contiguity.csv  stessa metrica sul generatore
                                         (tools/generator_contiguity.py)
e calcola sul generatore:
  testbed_ws   numero atteso di oggetti distinti toccati dalla classe agentica in 143 s al
               punto piu' basso (scope 0,02, β·λ configurato = 0,1263 · 95 req/s), con le
               sessioni di AGENT_SESSION capitoli contigui di workload.js: basi
               (r·AGENT_MUL + SEED) mod N, rango r con P(r) = ((r+1)/S)^(1−s) − (r/S)^(1−s),
               S = floor(N·scope), s = AGENT_SKEW; sessioni in 143 s = β·λ·143 / AGENT_SESSION;
               E[oggetti] = Σ_o 1 − (1 − q_o)^sessioni, q_o = probabilita' che una sessione
               tocchi l'oggetto o

Nessun log e nessun dato per client: solo i CSV aggregati sopra.

Uso:
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
BETA_LAMBDA = (0.1263, 95.0)      # β e λ del run tre-20260921-150237 (env.txt, points.csv)
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
        raise SystemExit(f"honeypot_totals.csv: finestra {tot['window_s']} s, attesi {WINDOW_S}")
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
    print(f"scritto {OUT_CSV}")


if __name__ == "__main__":
    main()
