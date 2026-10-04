#!/usr/bin/env python3
"""
esplora_artefatto.py — EXPLORATORY, not pre-registered. Extension of the artefact of the exhaustive
traversal (phase 2b) to A1, A3 and A7, and predictions for a rerun on the lab.
LRU only (tools/sim/cache.py), generator sessions, seeds 1..20. Every number is SIMULATED.

Variants of the exhaustive traversal:
  GLOB  current workload.js: index = iterationInTest (all classes)               [trace.phase]
  OWN   counter of the exhaustive requests only, arrivals drawn as in GLOB      [fase2b.phase_own]
  SCEN  implementable in k6: the exhaustive class is a scenario of its own at rate α·λ (regular arrivals,
        its iterationInTest is the counter; TRAV_SKIP = int(300·α·λ) in the measurement); human and
        agentic in a second scenario at rate (1−α)·λ, agentic with probability β/(1−α), VUs
        round-robin on that scenario only.

Usage:  python3 tools/sim/esplora_artefatto.py [--from-backup]
  --from-backup  read the replica's points.csv from the author's local copy
                 ~/undertow-backup/lab-20260928 instead of data/derived/lab_reference.csv (same values)
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
import trace as tr  # noqa: E402  (tools/sim/trace.py)
import fase1  # noqa: E402
import fase2b  # noqa: E402
from cache import LRU  # noqa: E402

assert hasattr(tr, "repetition")
ROOT = fase1.ROOT
OUT = ROOT / "data" / "sim" / "esplorativo-artefatto"
SEP, SHR = fase1.SEP, fase1.SHR
SEEDS = fase1.SEEDS
VARIANTS = ("GLOB", "OWN", "SCEN")

# name -> (λ, α, β, scope, AGENT_MUL, measurement in s)
P = {k: (*v, 620) for k, v in fase1.POINTS.items()}
P.update({                                      # A7 series (16 Sep): marginale2.sh block B
    "A7_00": (67, 0.0000, 0.1791, 0.02, SHR, 1211),
    "A7_14": (81, 0.1728, 0.1481, 0.02, SHR, 1211),
    "A7_28": (95, 0.2947, 0.1263, 0.02, SHR, 1211),
    "A7_42": (109, 0.3853, 0.1101, 0.02, SHR, 1211),
})
A7_RATE = {"A7_00": 0.0, "A7_14": 13.9968, "A7_28": 27.9965, "A7_42": 41.9977}  # claims A7

_SIZES = None


def _init():
    global _SIZES
    _SIZES = fase1.sizes()


def phase_scen(rnd, n, lam, alpha, beta, scope, mul, duration, trav_skip, session=3, skew=0.6):
    """Two k6 scenarios: exhaustive at rate α·λ with its own index; human+agentic at (1−α)·λ.
    Returns requests sorted by time: (t, class, index)."""
    out = []
    ra, rb = alpha * lam, (1 - alpha) * lam
    offset = (tr.SEED * 7919) % n
    tmul = tr.TRAV_MUL % n
    for k in range(int(round(ra * duration))):
        idx = (((offset + trav_skip + k) % n) * tmul + tr.SEED * 7919) % n
        out.append((k / ra, tr.TRAV, idx))
    nvu = min(max(math.ceil(2 * rb), 200), 4000)
    s_bases = max(1, math.floor(n * scope))
    state = [None] * nvu
    pb = beta / (1 - alpha) if alpha < 1 else 0.0
    expo = 1 / (1 - skew)
    for j in range(int(round(rb * duration))):
        if rnd.random() < pb:
            v = j % nvu
            s = state[v]
            if s is None or s[1] <= 0:
                r = min(s_bases - 1, math.floor(s_bases * rnd.random() ** expo))
                s = state[v] = [(r * mul + tr.SEED) % n, session, 0]
            s[1] -= 1
            idx = (s[0] + s[2]) % n
            s[2] += 1
            out.append((j / rb, tr.AGENT, idx))
        else:
            r = min(math.floor(n ** rnd.random()), n - 1)
            out.append((j / rb, tr.HUMAN, (r * tr.PERM_MUL + tr.SEED) % n))
    out.sort(key=lambda x: x[0])
    return out


def trace_of(variant, seed, name):
    """(warm, meas, measurement): lists of (t, class, index), t relative to the start of the phase."""
    lam, alpha, beta, scope, mul, measure = P[name]
    n = len(_SIZES)
    rnd = random.Random(seed)
    skip = int(tr.WARMUP * lam * alpha)
    if variant == "SCEN":
        return (phase_scen(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0),
                phase_scen(rnd, n, lam, alpha, beta, scope, mul, measure, skip), measure)
    if variant == "GLOB":
        w = tr.phase(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0)
        m = tr.phase(rnd, n, lam, alpha, beta, scope, mul, measure, skip)
    else:
        w, c = fase2b.phase_own(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0)
        m, _ = fase2b.phase_own(rnd, n, lam, alpha, beta, scope, mul, measure, c)
    return ([(i / lam, r[0], r[1]) for i, r in enumerate(w)],
            [(i / lam, r[0], r[1]) for i, r in enumerate(m)], measure)


def job(args):
    variant, name, seed = args
    warm, meas, measure = trace_of(variant, seed, name)
    c = LRU(_SIZES, fase1.H)
    for t, _, idx in warm:
        c.get(idx, t)
    req, miss = [0, 0, 0], [0, 0, 0]
    nobj, nxt = [], 0.0
    for t, cl, idx in meas:
        while t >= nxt:
            nobj.append(len(c))
            nxt += 1.0
        req[cl] += 1
        if not c.get(idx, tr.WARMUP + t):
            miss[cl] += 1
    return {"variant": variant, "point": name, "seed": seed, "req": req, "miss": miss,
            "share": [miss[k] / req[k] if req[k] else float("nan") for k in range(3)],
            "origin_rps": sum(miss) / measure, "n_object": statistics.fmean(nobj)}


ms = fase1.mean_se


def diff(a, b, div=1.0):
    return (a[0] - b[0]) / div, math.sqrt(a[1] ** 2 + b[1] ** 2) / div


def lab_replica():
    """Replica of 25-26 Sep (data/derived/lab_reference.csv, series replica, or the author's local
    copy with --from-backup): Ō, SE and exhaustive miss."""
    base = Path.home() / "undertow-backup" / "lab-20260928" / "fs" / "harness" / "results"
    ref = ROOT / "data" / "derived" / "lab_reference.csv"
    out = {}
    for pt, run in fase1.REPLICA.items():
        if "--from-backup" in sys.argv[1:]:
            rows = list(csv.DictReader(open(base / run / "points.csv")))
        else:
            rows = [r for r in csv.DictReader(open(ref)) if r["series"] == "replica" and r["run"] == run]
        out[pt] = {"O": ms([float(r["origin_rps"]) for r in rows]),
                   "exh": ms([1 - float(r["h_trav"]) for r in rows]) if pt else None}
    return out


def main():
    cm = fase1.commit()
    names = list(P)
    jobs = [(v, n, s) for v in VARIANTS for n in names for s in SEEDS]
    with Pool(initializer=_init) as pool:
        res = pool.map(job, jobs, chunksize=2)
    OUT.mkdir(parents=True, exist_ok=True)
    head = (f"# commit {cm}; ESPLORATIVO, non pre-registrato; stato SIMULATO; LRU, sessioni del "
            f"generatore; varianti GLOB/OWN/SCEN (tools/sim/esplora_artefatto.py)\n")
    with open(OUT / "reps.csv", "w", newline="") as f:
        f.write(head)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["variant", "point", "seed", "req_h", "req_a", "req_e", "miss_h", "miss_a",
                    "miss_e", "origin_rps", "n_object_avg", "stato"])
        for r in res:
            w.writerow([r["variant"], r["point"], r["seed"], *r["req"], *r["miss"],
                        f"{r['origin_rps']:.6f}", f"{r['n_object']:.3f}", "SIMULATO"])
    # regression: GLOB at the 9 points of phase 1 = data/sim/fase1/reps.csv (requests and misses)
    with open(ROOT / "data" / "sim" / "fase1" / "reps.csv") as f:
        ref = {(r["point"], int(r["seed"])): r
               for r in csv.DictReader(line for line in f if not line.startswith("#"))}
    cols = ("req_human", "req_agentic", "req_exhaustive", "miss_human", "miss_agentic",
            "miss_exhaustive")
    bad = sum([*r["req"], *r["miss"]] != [int(ref[(r["point"], r["seed"])][c]) for c in cols]
              for r in res if r["variant"] == "GLOB" and (r["point"], r["seed"]) in ref)
    print(f"== regression GLOB against phase 1: different rows {bad}  "
          f"{'PASSA' if bad == 0 else 'NON PASSA'}")
    if bad:
        sys.exit("regression does not pass: stopping")
    by = {}
    for r in res:
        by.setdefault((r["variant"], r["point"]), []).append(r)
    O = {k: ms([r["origin_rps"] for r in v]) for k, v in by.items()}
    E = {k: ms([r["share"][tr.TRAV] for r in v]) for k, v in by.items()
         if P[k[1]][1] > 0}
    rows = []

    def out(sec, q, v, x, se, note=""):
        rows.append([sec, q, v, f"{x:.6f}", f"{se:.6f}", note, "SIMULATO"])

    print("== 1. A1: marginals at the three scopes (LRU)")
    m = {}
    for v in VARIANTS:
        for sc, (lo, hi) in fase1.SCOPE_POINTS.items():
            m[(v, sc)] = diff(O[(v, hi)], O[(v, lo)], fase1.D_RATE)
            out("A1", f"m_{sc}", v, *m[(v, sc)])
        t02 = m[(v, "0.02")][0] / m[(v, "0.02")][1]
        t20 = m[(v, "0.20")][0] / m[(v, "0.20")][1]
        d1 = diff(m[(v, "0.06")], m[(v, "0.02")])
        d2 = diff(m[(v, "0.20")], m[(v, "0.06")])
        order = d1[0] / d1[1] >= 3 and d2[0] / d2[1] >= 3
        sign = order and m[(v, "0.02")][0] < 0 and t02 <= -3 and m[(v, "0.20")][0] > 0 and t20 >= 3
        print(f"  {v:4s}: " + "  ".join(f"m{sc} {m[(v, sc)][0]:+.4f}±{m[(v, sc)][1]:.4f}"
                                      for sc in fase1.SCOPE_POINTS)
              + f"  | ordering {'regge' if order else 'NO'}; sign change "
                f"{'regge' if sign else 'NO'}")
        out("A1", "ordering_and_sign", v, 0, 0, f"ordinamento {order}; cambio di segno {sign}")
    for v in ("OWN", "SCEN"):
        print(f"  change {v} − GLOB: " + "  ".join(
            f"{sc} {diff(m[(v, sc)], m[('GLOB', sc)])[0]:+.4f}±{diff(m[(v, sc)], m[('GLOB', sc)])[1]:.4f}"
            for sc in fase1.SCOPE_POINTS))
        for sc in fase1.SCOPE_POINTS:
            out("A1", f"dm_{sc}_vs_GLOB", v, *diff(m[(v, sc)], m[("GLOB", sc)]))

    print("\n== 2. A3: separate − shared at scope 0.02")
    for v in VARIANTS:
        d12 = diff(O[(v, "S12")], O[(v, "C12")])
        d36 = diff(O[(v, "S36")], O[(v, "C36")])
        print(f"  {v:4s}: d12 {d12[0]:+.4f}±{d12[1]:.4f} (t {d12[0] / d12[1]:+.1f})   "
              f"d36 {d36[0]:+.4f}±{d36[1]:.4f} (t {d36[0] / d36[1]:+.1f})")
        out("A3", "d12", v, *d12)
        out("A3", "d36", v, *d36)

    print("\n== 3. A7: exhaustive 0 -> 42 req/s, shared, 1211 s (lab: 0.961 / 0.997 / 0.979; 1.09)")
    seq = ["A7_00", "A7_14", "A7_28", "A7_42"]
    for v in VARIANTS:
        mg = [diff(O[(v, b)], O[(v, a)], A7_RATE[b] - A7_RATE[a]) for a, b in zip(seq, seq[1:])]
        el = E[(v, "A7_42")][0] / E[(v, "A7_14")][0]
        print(f"  {v:4s}: marginals " + " / ".join(f"{x:.3f}±{s:.3f}" for x, s in mg)
              + f"   exhaustive miss 14 -> 42: {E[(v, 'A7_14')][0]:.4f} -> {E[(v, 'A7_42')][0]:.4f}"
                f"  elasticity {el:.4f}")
        for (a, b), (x, s) in zip(zip(seq, seq[1:]), mg):
            out("A7", f"marginal_{a}_{b}", v, x, s)
        out("A7", "elasticity_42_14", v, el, 0, f"miss_e 14 {E[(v, 'A7_14')][0]:.6f}; 42 "
            f"{E[(v, 'A7_42')][0]:.6f}")

    print("\n== 4. Predictions for a rerun on the lab with the own scenario (SCEN), 5 points")
    lab = lab_replica()
    print("  method: lab_new = lab_replica + (SCEN − GLOB)_sim x k, k = Ō_lab / Ō_sim,GLOB "
          "(phase 1 scale); 95% CI = ± 1.96·√(SE_lab² + SE_var² + SE_lab²)")
    pred = {}
    for pt in ("C12", "S12", "S36", "P0", "C36"):
        lo, lse = lab[pt]["O"]
        k = lo / O[("GLOB", pt)][0]
        ch, chse = diff(O[("SCEN", pt)], O[("GLOB", pt)])
        x = lo + k * ch
        se = math.sqrt(2 * lse ** 2 + (k * chse) ** 2)
        pred[pt] = (x, se)
        de, dese = diff(E[("SCEN", pt)], E[("GLOB", pt)])
        le = lab[pt]["exh"][0]
        print(f"  {pt}: origin lab {lo:.3f}±{lse:.3f}  k {k:.4f}  simulated change "
              f"{ch:+.3f}±{chse:.3f}  -> predicted {x:.3f}  IC95 [{x - 1.96 * se:.3f}, "
              f"{x + 1.96 * se:.3f}]   lab exhaustive miss {le:.4f} -> predicted {le + de:.4f}")
        out("previsione", f"origin_{pt}", "SCEN", x, se,
            f"lab {lo:.6f}; k {k:.6f}; variazione {ch:.6f}±{chse:.6f}; IC95 "
            f"[{x - 1.96 * se:.6f}, {x + 1.96 * se:.6f}]; miss_e lab {le:.6f} -> {le + de:.6f}")
    for q, (a, b, dv) in {"m_0.02": ("S36", "S12", fase1.D_RATE), "d12": ("S12", "C12", 1.0),
                          "d36": ("S36", "C36", 1.0), "net_S36_P0": ("S36", "P0", 1.0)}.items():
        x, se = diff(pred[a], pred[b], dv)
        print(f"  {q}: predicted {x:+.4f}  IC95 [{x - 1.96 * se:+.4f}, {x + 1.96 * se:+.4f}]"
              f"   (lab replica {diff(lab[a]['O'], lab[b]['O'], dv)[0]:+.4f})")
        out("previsione", q, "SCEN", x, se, f"IC95 [{x - 1.96 * se:.6f}, {x + 1.96 * se:.6f}]")
    with open(OUT / "criteri.csv", "w", newline="") as f:
        f.write(head)
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["section", "quantity", "variant", "value", "se", "note", "stato"])
        w.writerows(rows)
    print(f"written {OUT.relative_to(ROOT)}/reps.csv and criteri.csv")


if __name__ == "__main__":
    main()
