#!/usr/bin/env python3
"""
scope_ttest.py — parameters and statistical separation of A1 (AGENT_SCOPE sweep).

For the six runs of the sweep (two per scope: agentic share 13% and 30%, separate
mapping, 5 repetitions each):
  1. reads from env.txt only the design keys (AGENT_SCOPE, AGENT_MUL, LAMBDA,
     POINTS, REPS) and from points.csv alpha and beta, and prints the configured offered
     rates per class (human (1-alpha-beta)*lambda, exhaustive alpha*lambda, agentic
     beta*lambda) and the number of objects the generator can touch
     (floor(corpus * scope) bases x AGENT_SESSION chapters, as in workload.js);
  2. computes the marginal of each scope from the per-repetition means of origin_rps:
     (mean_hi - mean_lo) / (beta_hi*lambda_hi - beta_lo*lambda_lo), SE combined
     from the two means;
  3. computes Welch's t between consecutive scopes (0.02-0.06 and 0.06-0.20), with the
     Welch-Satterthwaite degrees of freedom on the four groups involved.

No rounded value enters the calculations: we start from the repetitions. (origin_rps
is already written to 2 decimals by treclassi.sh: it is the raw data available.)

Primary runs (claims.md v3.8, 29 Sep 2026): exhaustive traversal in a scenario of its own
(TRAV_MODE=scen, entry R7 of docs/retractions.md): scope 0.02 from the rerun of 28 Sep
(docs/RISULTATO-lab-trav-own-20260928.md), 0.06 and 0.20 from the rerun of 29 Sep
(docs/RISULTATO-lab-trav-own-scope-20260929.md). The sweep of 21-22 Sep (global-index
traversal) stays in RUNS_GLOB as the previous measurement; --glob reanalyses it.

Objects: `reachable()` counts the DISTINCT chapters of the reachable set, (r*AGENT_MUL + SEED) mod N
for r < floor(N*scope), plus the next two (workload.js): at scope 0.20 the 10,170 positions
are 10,020 distinct chapters, because sessions of nearby bases overlap.

The lab stays read-only: only `ssh lab cat ...` is done (with the lab off, the fake ssh of
~/undertow-backup/shim-scope). Of env.txt only the keys listed above are printed, never the
rest of the environment.

Usage:
    python3 tools/scope_ttest.py
"""
import csv
import math
import statistics
import subprocess
import sys

CORPUS = 16954
SESSION_DEFAULT = 3            # default AGENT_SESSION in treclassi.sh and workload.js
SCOPE_DEFAULT = "0.02"         # default AGENT_SCOPE in treclassi.sh (${AGENT_SCOPE:-0.02})

SEED = 42                      # default SEED in workload.js
AGENT_MUL_DEFAULT = 2654435761 # default AGENT_MUL in workload.js

# scope -> (run at 13% share, run at 30% share), as in data/derived/fig01_*.csv
# Primary (claims v3.8): TRAV_MODE=scen, separate mapping.
RUNS = {
    "0.02": ("tre-20260928-150154", "tre-20260928-162206"),
    "0.06": ("tre-20260929-064412", "tre-20260929-080424"),
    "0.20": ("tre-20260929-092436", "tre-20260929-104448"),
}
# Previous measurement: sweep of 21-22 Sep, global-index traversal (R7).
RUNS_GLOB = {
    "0.02": ("tre-20260921-150237", "tre-20260921-162248"),
    "0.06": ("tre-20260921-214946", "tre-20260921-230947"),
    "0.20": ("tre-20260922-002958", "tre-20260922-015010"),
}
ENV_KEYS = ("AGENT_SCOPE", "AGENT_MUL", "AGENT_SESSION", "LAMBDA", "POINTS", "REPS",
            "TRAV_MODE")


def reachable(scope, mul, session=SESSION_DEFAULT, n=CORPUS, seed=SEED):
    """(positions, distinct chapters) of the agentic reachable set, as workload.js."""
    bases = max(1, math.floor(n * float(scope)))
    chapters = {((r * mul + seed) % n + k) % n for r in range(bases) for k in range(session)}
    return bases * session, len(chapters)


def lab_cat(run, name):
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{run}/{name}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def read_env(run):
    env = {}
    for line in lab_cat(run, "env.txt").splitlines():
        k, sep, v = line.partition("=")
        if sep and k in ENV_KEYS:
            env[k] = v
    return env


def read_run(run):
    env = read_env(run)
    rows = list(csv.DictReader(lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    alphas = {r["alpha"] for r in rows}
    betas = {r["beta"] for r in rows}
    if len(alphas) != 1 or len(betas) != 1:
        sys.exit(f"{run}: more than one point (alpha {alphas}, beta {betas})")
    lam = float(env["LAMBDA"])
    a, b = float(rows[0]["alpha"]), float(rows[0]["beta"])
    origin = [float(r["origin_rps"]) for r in rows]
    return {
        "run": run, "env": env, "lambda": lam, "alpha": a, "beta": b,
        "human": (1 - a - b) * lam, "exhaustive": a * lam, "agentic": b * lam,
        "origin": origin, "n": len(origin),
        "mean": statistics.fmean(origin),
        "var_mean": statistics.variance(origin) / len(origin),
    }


def main():
    runs = RUNS_GLOB if "--glob" in sys.argv[1:] else RUNS
    marg = {}
    print("== 1. parameters from the runs (env.txt + points.csv)")
    for scope, (lo_id, hi_id) in runs.items():
        lo, hi = read_run(lo_id), read_run(hi_id)
        for r in (lo, hi):
            e = r["env"]
            print(f"  {r['run']}  AGENT_SCOPE={e.get('AGENT_SCOPE', SCOPE_DEFAULT + ' (default)')}  "
                  f"AGENT_MUL={e.get('AGENT_MUL', '(missing)')}  "
                  f"AGENT_SESSION={e.get('AGENT_SESSION', '(default)')}  "
                  f"LAMBDA={e.get('LAMBDA')}  POINTS={e.get('POINTS')}  reps={r['n']}")
            print(f"      offered rates: human {r['human']:.4f}  exhaustive {r['exhaustive']:.4f}  "
                  f"agentic {r['agentic']:.4f} req/s")
            if e.get("AGENT_SCOPE", SCOPE_DEFAULT) != scope:
                sys.exit(f"  {r['run']}: AGENT_SCOPE does not match {scope}")
            if runs is RUNS and e.get("TRAV_MODE") != "scen":
                sys.exit(f"  {r['run']}: TRAV_MODE is not scen")
        session = int(lo["env"].get("AGENT_SESSION", SESSION_DEFAULT))
        mul = int(lo["env"].get("AGENT_MUL", AGENT_MUL_DEFAULT))
        pos, distinct = reachable(scope, mul, session)
        print(f"  scope {scope}: {pos} positions, {distinct} distinct chapters "
              f"(AGENT_MUL {mul})")

        d_rate = hi["agentic"] - lo["agentic"]
        m = (hi["mean"] - lo["mean"]) / d_rate
        v = (hi["var_mean"] + lo["var_mean"]) / d_rate ** 2
        marg[scope] = (m, v, [(lo["var_mean"] / d_rate ** 2, lo["n"]),
                              (hi["var_mean"] / d_rate ** 2, hi["n"])])
        print(f"  origin: lo {lo['mean']:.4f} +/- {math.sqrt(lo['var_mean']):.4f}  "
              f"hi {hi['mean']:.4f} +/- {math.sqrt(hi['var_mean']):.4f}  "
              f"agentic rate delta {d_rate:.4f}")
        print(f"  MARGINAL {scope}: {m:+.5f} +/- {math.sqrt(v):.5f}\n")

    print("== 2. Welch's t between consecutive scopes")
    scopes = list(runs)
    for s1, s2 in zip(scopes, scopes[1:]):
        m1, v1, g1 = marg[s1]
        m2, v2, g2 = marg[s2]
        t = (m2 - m1) / math.sqrt(v1 + v2)
        comps = g1 + g2
        df = (v1 + v2) ** 2 / sum(c ** 2 / (n - 1) for c, n in comps)
        print(f"  {s1} -> {s2}: diff {m2 - m1:+.5f}  SE {math.sqrt(v1 + v2):.5f}  "
              f"t = {t:.2f}  df = {df:.1f}")


if __name__ == "__main__":
    main()
