#!/usr/bin/env python3
"""
fase2b.py — artefatto della traversata esaustiva (docs/PREREG-simulatore-fase2b.md).

TRAV-GLOB: generatore della fase 1 (trace.phase): indice esaustivo dall'indice globale di
           iterazione, come workload.js:276-278.
TRAV-OWN:  identico, ma l'indice esaustivo e' permuteTrav(offset + c), c = richieste esaustive
           gia' fatte nella ripetizione (da 0 all'inizio del warm-up, prosegue nella misura).
           Stessi numeri casuali dell'originale: a parita' di seme cambia solo il capitolo
           esaustivo.

  python3 tools/sim/fase2b.py       R0b, poi il lancio unico e i criteri

Ogni numero e' SIMULATO. Nessun dato del lab.
"""
import csv
import math
import random
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trace as tr  # noqa: E402  (tools/sim/trace.py, non il modulo standard)
import fase1  # noqa: E402
import fase2  # noqa: E402
from net_agentic import t_quantile  # noqa: E402
from policies import POLICIES  # noqa: E402

assert hasattr(tr, "repetition"), "importato il modulo standard trace invece di tools/sim/trace.py"

ROOT = fase1.ROOT
OUT = ROOT / "data" / "sim" / "fase2b"
PTS = ("P0", "S12", "S36")
POLS = ("LRU", "S3FIFO")
VARIANTS = ("GLOB", "OWN")
RATE = {p: fase1.POINTS[p][0] * fase1.POINTS[p][1] for p in PTS}   # alpha*lambda configurati


def phase_own(rnd, n, lam, alpha, beta, scope, agent_mul, duration, c0, session=3, skew=0.6):
    """trace.phase con l'indice esaustivo da un contatore proprio della classe. Restituisce
    (richieste, contatore finale). Consumo di numeri casuali identico a trace.phase."""
    iters = int(round(lam * duration))
    nvu = min(max(math.ceil(2 * lam), 200), 4000)
    s_bases = max(1, math.floor(n * scope))
    offset = (tr.SEED * 7919) % n
    tmul = tr.TRAV_MUL % n
    state = [None] * nvu
    out = []
    expo = 1 / (1 - skew)
    c = c0
    for i in range(iters):
        u = rnd.random()
        if u < alpha:
            idx = (((offset + c) % n) * tmul + tr.SEED * 7919) % n
            c += 1
            out.append((tr.TRAV, idx, -1))
        elif u < alpha + beta:
            v = i % nvu
            s = state[v]
            if s is None or s[1] <= 0:
                r = min(s_bases - 1, math.floor(s_bases * rnd.random() ** expo))
                s = state[v] = [(r * agent_mul + tr.SEED) % n, session, 0]
            s[1] -= 1
            idx = (s[0] + s[2]) % n
            s[2] += 1
            out.append((tr.AGENT, idx, v))
        else:
            r = min(math.floor(n ** rnd.random()), n - 1)
            out.append((tr.HUMAN, (r * tr.PERM_MUL + tr.SEED) % n, -1))
    return out, c


def repetition(variant, seed, name):
    n = len(fase2._SIZES)
    lam, alpha, beta, scope, mul = fase1.POINTS[name]
    if variant == "GLOB":
        return tr.repetition(seed, n, lam, alpha, beta, scope, mul)
    rnd = random.Random(seed)
    warm, c = phase_own(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0)
    meas, _ = phase_own(rnd, n, lam, alpha, beta, scope, mul, tr.MEASURE, c)
    return warm, meas


def reuse(warm, meas, lam):
    """Quota di richieste esaustive della misura che ritrovano un capitolo gia' chiesto
    dall'esaustiva nella ripetizione, e intervallo mediano (s)."""
    last = {}
    for i, rec in enumerate(warm):
        if rec[0] == tr.TRAV:
            last[rec[1]] = i / lam
    gaps, tot = [], 0
    for i, rec in enumerate(meas):
        if rec[0] == tr.TRAV:
            t = tr.WARMUP + i / lam
            tot += 1
            if rec[1] in last:
                gaps.append(t - last[rec[1]])
            last[rec[1]] = t
    return len(gaps) / tot, (statistics.median(gaps) if gaps else float("nan"))


def job(args):
    variant, name, seed = args
    warm, meas = repetition(variant, seed, name)
    lam = fase1.POINTS[name][0]
    share, med = reuse(warm, meas, lam)
    out = []
    for pol in POLS:
        r = fase2.run_policy(POLICIES[pol], warm, meas, lam)
        r.update(variant=variant, policy=pol, point=name, seed=seed, h=fase1.H,
                 reuse_share=share, reuse_median_s=med)
        out.append(r)
    return out


def write(name, cm, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with open(path, "w", newline="") as f:
        f.write(f"# commit {cm}; docs/PREREG-simulatore-fase2b.md; stato SIMULATO\n")
        f.write(f"# fonte: {fase2.SOURCE}\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header + ["stato"])
        for r in rows:
            w.writerow(list(r) + ["SIMULATO"])
    print(f"scritto {path.relative_to(ROOT)}")


def main():
    cm = fase1.commit()
    jobs = [(v, p, s) for v in VARIANTS for p in PTS for s in fase1.SEEDS]
    with Pool(initializer=fase2._init) as pool:
        res = [r for rs in pool.map(job, jobs, chunksize=1) for r in rs]
    write("reps.csv", cm, ["variant", "policy"] + fase1.REP_HDR + ["reuse_share", "reuse_median_s"],
          [[r["variant"], r["policy"]] + fase2.fmt(r) +
           [f"{r['reuse_share']:.6f}", f"{r['reuse_median_s']:.3f}"] for r in res])

    # R0b: TRAV-GLOB = fase 2, cifra per cifra
    with open(ROOT / "data" / "sim" / "fase2" / "reps.csv") as f:
        ref = {(r["session"], r["policy"], r["point"], r["seed"]): r
               for r in csv.DictReader(line for line in f if not line.startswith("#"))}
    keys = fase1.REP_HDR
    diff = 0
    for r in res:
        if r["variant"] != "GLOB":
            continue
        want = ref[("GEN", r["policy"], r["point"], str(r["seed"]))]
        got = dict(zip(keys, (str(x) for x in fase2.fmt(r))))
        diff += any(got[k] != want[k] for k in keys)
    n_glob = sum(r["variant"] == "GLOB" for r in res)
    ok = diff == 0
    print(f"== R0b: TRAV-GLOB contro data/sim/fase2/reps.csv: {n_glob} righe, diverse {diff}  "
          f"{'PASSA' if ok else 'NON PASSA'}")
    rows = [["R0b", "rows_different", diff, "", "", "PASSA" if ok else "NON PASSA"]]
    if not ok:
        write("criteri.csv", cm, ["criterion", "quantity", "value", "se", "t", "note"], rows)
        sys.exit("R0b non passa: ci si ferma")

    by = {}
    for r in res:
        by.setdefault((r["variant"], r["policy"], r["point"]), []).append(r)
    ms = fase1.mean_se
    delta = {}
    for pol in POLS:
        for v in VARIANTS:
            g = lambda p: by[(v, pol, p)]  # noqa: E731
            me = {p: ms([r["miss_share"][tr.TRAV] for r in g(p)]) for p in PTS}
            O = {p: ms([r["origin_rps"] for r in g(p)]) for p in PTS}
            ru = {p: (statistics.fmean(r["reuse_share"] for r in g(p)),
                      statistics.fmean(r["reuse_median_s"] for r in g(p))) for p in PTS}
            print(f"\n==== {pol}  TRAV-{v}")
            for p in PTS:
                print(f"  {p}: miss esaustivo {me[p][0]:.4f} ± {me[p][1]:.4f}   origin_rps "
                      f"{O[p][0]:.3f} ± {O[p][1]:.3f}   riuso esaustivo {100 * ru[p][0]:.2f}% "
                      f"(mediana {ru[p][1]:.0f} s)")
                rows.append([f"{pol}_{v}", f"miss_exh_{p}", f"{me[p][0]:.6f}", f"{me[p][1]:.6f}",
                             "", f"origin {O[p][0]:.6f} ± {O[p][1]:.6f}; reuse {ru[p][0]:.6f}, "
                             f"median {ru[p][1]:.3f} s"])
            for a in ("S36", "S12"):
                d, se, t, _ = fase2.welch(me[a], me["P0"])
                if a == "S36":
                    delta[(pol, v)] = (d, se)
                print(f"  Δ_esa {a} − P0: {d:+.4f} ± {se:.4f}  (t {t:+.2f})")
                rows.append([f"{pol}_{v}", f"delta_exh_{a}_P0", f"{d:.6f}", f"{se:.6f}", f"{t:.3f}",
                             ""])
            n_, se_, t_, df_ = fase2.welch(O["S36"], O["P0"])
            q = t_quantile(0.975, df_)
            print(f"  netto S36 − P0: {n_:+.4f} ± {se_:.4f}  t {t_:+.2f}  IC95 "
                  f"[{n_ - q * se_:+.4f}, {n_ + q * se_:+.4f}]")
            rows.append([f"{pol}_{v}", "net_S36_P0", f"{n_:.6f}", f"{se_:.6f}", f"{t_:.3f}",
                         f"IC95 [{n_ - q * se_:.6f}, {n_ + q * se_:.6f}] df {df_:.3f}"])
            tm =(RATE["S36"] * me["S36"][0] - RATE["S12"] * me["S12"][0],
                  math.sqrt((RATE["S36"] * me["S36"][1]) ** 2 + (RATE["S12"] * me["S12"][1]) ** 2))
            dm, sm, tt, _ = fase2.welch(O["S36"], O["S12"])
            print(f"  termine esaustivo di B2 (S12 -> S36): {tm[0]:+.4f} ± {tm[1]:.4f} req/s;  "
                  f"m a 0,02: {dm / fase1.D_RATE:+.4f} ± {sm / fase1.D_RATE:.4f} "
                  f"(t {tt:+.2f})")
            rows.append([f"{pol}_{v}", "B2_exh_term_S12_S36", f"{tm[0]:.6f}", f"{tm[1]:.6f}", "",
                         "req/s, rate configurati"])
            rows.append([f"{pol}_{v}", "m_0.02", f"{dm / fase1.D_RATE:.6f}",
                         f"{sm / fase1.D_RATE:.6f}", f"{tt:.3f}", ""])
    print("\n==== Criterio (TRAV-OWN): |Δ_esa(S36 − P0)| < 3 SE -> artefatto; altrimenti effetto "
          "della cache")
    for pol in POLS:
        d, se = delta[(pol, "OWN")]
        dg, _ = delta[(pol, "GLOB")]
        art = abs(d) < 3 * se
        verdict = "ARTEFATTO DEL GENERATORE" if art else f"EFFETTO DELLA CACHE (segno {'+' if d > 0 else '−'})"
        print(f"  {pol}: Δ_OWN {d:+.4f} ± {se:.4f} (|Δ|/SE {abs(d) / se:.2f}); Δ_GLOB {dg:+.4f}; "
              f"quota del calo che resta {d / dg:.3f}  ->  {verdict}")
        rows.append(["criterio", f"{pol}", f"{d:.6f}", f"{se:.6f}", f"{abs(d) / se:.3f}",
                     f"delta_GLOB {dg:.6f}; ratio {d / dg:.6f}; {verdict}"])
    write("criteri.csv", cm, ["criterion", "quantity", "value", "se", "t", "note"], rows)


if __name__ == "__main__":
    main()
