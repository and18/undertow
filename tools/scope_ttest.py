#!/usr/bin/env python3
"""
scope_ttest.py — parametri e separazione statistica di A1 (sweep AGENT_SCOPE).

Per i sei run dello sweep (due per scope: quota agentica 13% e 30%, mappatura
separata, 5 ripetizioni ciascuno):
  1. legge da env.txt solo le chiavi del disegno (AGENT_SCOPE, AGENT_MUL, LAMBDA,
     POINTS, REPS) e da points.csv alpha e beta, e stampa i rate offerti configurati
     per classe (umana (1-alpha-beta)*lambda, esaustiva alpha*lambda, agentica
     beta*lambda) e il numero di oggetti che il generatore puo' toccare
     (floor(corpus * scope) basi x AGENT_SESSION capitoli, come in workload.js);
  2. calcola il marginale di ogni scope dalle medie per ripetizione di origin_rps:
     (media_hi - media_lo) / (beta_hi*lambda_hi - beta_lo*lambda_lo), SE combinato
     dalle due medie;
  3. calcola il t di Welch fra scope consecutivi (0,02-0,06 e 0,06-0,20), con i
     gradi di liberta' di Welch-Satterthwaite sui quattro gruppi coinvolti.

Nessun valore arrotondato entra nei calcoli: si parte dalle ripetizioni. (origin_rps
e' gia' scritto a 2 decimali da treclassi.sh: e' il dato grezzo disponibile.)

Run primari (claims.md v3.8, 29 set 2026): traversata esaustiva in scenario proprio
(TRAV_MODE=scen, voce R7 di docs/retractions.md): scope 0,02 dal rilancio del 28 set
(docs/RISULTATO-lab-trav-own-20260928.md), 0,06 e 0,20 dal rilancio del 29 set
(docs/RISULTATO-lab-trav-own-scope-20260929.md). Lo sweep del 21-22 set (traversata a indice
globale) resta in RUNS_GLOB come misura precedente; --glob lo rianalizza.

Oggetti: `reachable()` conta i capitoli DISTINTI del reachable set, (r*AGENT_MUL + SEED) mod N
per r < floor(N*scope), piu' i due successivi (workload.js): a scope 0,20 le 10 170 posizioni
sono 10 020 capitoli distinti, perche' sessioni di basi vicine si sovrappongono.

Il lab resta in sola lettura: si fa solo `ssh lab cat ...` (a lab spento, il finto ssh di
~/undertow-backup/shim-scope). Di env.txt si stampano solo le chiavi elencate sopra, mai il
resto dell'ambiente.

Uso:
    python3 tools/scope_ttest.py
"""
import csv
import math
import statistics
import subprocess
import sys

CORPUS = 16954
SESSION_DEFAULT = 3            # AGENT_SESSION di default in treclassi.sh e workload.js
SCOPE_DEFAULT = "0.02"         # AGENT_SCOPE di default in treclassi.sh (${AGENT_SCOPE:-0.02})

SEED = 42                      # SEED di default in workload.js
AGENT_MUL_DEFAULT = 2654435761 # AGENT_MUL di default in workload.js

# scope -> (run a quota 13%, run a quota 30%), come in data/derived/fig01_*.csv
# Primari (claims v3.8): TRAV_MODE=scen, mappatura separata.
RUNS = {
    "0.02": ("tre-20260928-150154", "tre-20260928-162206"),
    "0.06": ("tre-20260929-064412", "tre-20260929-080424"),
    "0.20": ("tre-20260929-092436", "tre-20260929-104448"),
}
# Misura precedente: sweep del 21-22 set, traversata a indice globale (R7).
RUNS_GLOB = {
    "0.02": ("tre-20260921-150237", "tre-20260921-162248"),
    "0.06": ("tre-20260921-214946", "tre-20260921-230947"),
    "0.20": ("tre-20260922-002958", "tre-20260922-015010"),
}
ENV_KEYS = ("AGENT_SCOPE", "AGENT_MUL", "AGENT_SESSION", "LAMBDA", "POINTS", "REPS",
            "TRAV_MODE")


def reachable(scope, mul, session=SESSION_DEFAULT, n=CORPUS, seed=SEED):
    """(posizioni, capitoli distinti) del reachable set agentico, come workload.js."""
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
        sys.exit(f"points.csv vuoto: {run}")
    alphas = {r["alpha"] for r in rows}
    betas = {r["beta"] for r in rows}
    if len(alphas) != 1 or len(betas) != 1:
        sys.exit(f"{run}: piu' di un punto (alpha {alphas}, beta {betas})")
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
    print("== 1. parametri dai run (env.txt + points.csv)")
    for scope, (lo_id, hi_id) in runs.items():
        lo, hi = read_run(lo_id), read_run(hi_id)
        for r in (lo, hi):
            e = r["env"]
            print(f"  {r['run']}  AGENT_SCOPE={e.get('AGENT_SCOPE', SCOPE_DEFAULT + ' (default)')}  "
                  f"AGENT_MUL={e.get('AGENT_MUL', '(assente)')}  "
                  f"AGENT_SESSION={e.get('AGENT_SESSION', '(default)')}  "
                  f"LAMBDA={e.get('LAMBDA')}  POINTS={e.get('POINTS')}  reps={r['n']}")
            print(f"      rate offerti: umana {r['human']:.4f}  esaustiva {r['exhaustive']:.4f}  "
                  f"agentica {r['agentic']:.4f} req/s")
            if e.get("AGENT_SCOPE", SCOPE_DEFAULT) != scope:
                sys.exit(f"  {r['run']}: AGENT_SCOPE non corrisponde a {scope}")
            if runs is RUNS and e.get("TRAV_MODE") != "scen":
                sys.exit(f"  {r['run']}: TRAV_MODE non e' scen")
        session = int(lo["env"].get("AGENT_SESSION", SESSION_DEFAULT))
        mul = int(lo["env"].get("AGENT_MUL", AGENT_MUL_DEFAULT))
        pos, distinct = reachable(scope, mul, session)
        print(f"  scope {scope}: {pos} posizioni, {distinct} capitoli distinti "
              f"(AGENT_MUL {mul})")

        d_rate = hi["agentic"] - lo["agentic"]
        m = (hi["mean"] - lo["mean"]) / d_rate
        v = (hi["var_mean"] + lo["var_mean"]) / d_rate ** 2
        marg[scope] = (m, v, [(lo["var_mean"] / d_rate ** 2, lo["n"]),
                              (hi["var_mean"] / d_rate ** 2, hi["n"])])
        print(f"  origine: lo {lo['mean']:.4f} +/- {math.sqrt(lo['var_mean']):.4f}  "
              f"hi {hi['mean']:.4f} +/- {math.sqrt(hi['var_mean']):.4f}  "
              f"delta rate agentico {d_rate:.4f}")
        print(f"  MARGINALE {scope}: {m:+.5f} +/- {math.sqrt(v):.5f}\n")

    print("== 2. t di Welch fra scope consecutivi")
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
