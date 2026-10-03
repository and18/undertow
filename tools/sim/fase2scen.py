#!/usr/bin/env python3
"""
fase2scen.py — phase 2 rerun with the exhaustive traversal in a scenario of its own (SCEN), as per
docs/PREREG-simulatore-fase2.md, amendment 2. Same policies (policies.py), same points,
seeds, quantities and criteria as fase2.py; only the generator changes:

  GEN   esplora_artefatto.phase_scen (exhaustive at α·λ, regular arrivals, own counter;
        human and agentic at (1 − α)·λ, agentic with probability β/(1 − α))
  REAL  same scheme; the agentic requests follow the chain of fase2.phase_real with p_r and p_c
        calibrated in phase 2 (not recalibrated)

Steps in the order of amendment 2 (a single command): R0-SCEN, G0-R-SCEN, launch, criteria.
Every number is SIMULATED. No lab data.

Usage:  python3 tools/sim/fase2scen.py
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
import fase2  # noqa: E402
from esplora_artefatto import phase_scen  # noqa: E402
from net_agentic import t_quantile  # noqa: E402
from policies import POLICIES  # noqa: E402

assert hasattr(tr, "repetition")
ROOT = fase1.ROOT
OUT = ROOT / "data" / "sim" / "fase2-scen"
POINTS = fase1.POINTS
SEEDS = fase1.SEEDS
P_R, P_C = 0.190751953, 0.037933502          # data/sim/fase2/calibrazione.csv, not recalibrated


def phase_scen_real(rnd, n, lam, alpha, beta, scope, mul, duration, trav_skip, p_r, p_c,
                    skew=0.6):
    """As esplora_artefatto.phase_scen, with the session chain of fase2.phase_real for
    the agentic class. Record: (t, class, index, VU)."""
    out = []
    ra, rb = alpha * lam, (1 - alpha) * lam
    offset = (tr.SEED * 7919) % n
    tmul = tr.TRAV_MUL % n
    for k in range(int(round(ra * duration))):
        idx = (((offset + trav_skip + k) % n) * tmul + tr.SEED * 7919) % n
        out.append((k / ra, tr.TRAV, idx, -1))
    nvu = min(max(math.ceil(2 * rb), 200), 4000)
    s_bases = max(1, math.floor(n * scope))
    state = [None] * nvu
    pb = beta / (1 - alpha) if alpha < 1 else 0.0
    expo = 1 / (1 - skew)
    for j in range(int(round(rb * duration))):
        if rnd.random() < pb:
            v = j % nvu
            s = state[v]
            x = rnd.random() if s is not None else 1.0
            if s is not None and x < p_r:
                base, k = s
            elif s is not None and x < p_r + p_c:
                base, k = s
                k = 1 if k != 1 else (0 if rnd.random() < 0.5 else 2)
            else:
                r = min(s_bases - 1, math.floor(s_bases * rnd.random() ** expo))
                base = (r * mul + tr.SEED) % n
                k = min(int(rnd.random() * 3), 2)
            state[v] = (base, k)
            out.append((j / rb, tr.AGENT, (base + k) % n, v))
        else:
            r = min(math.floor(n ** rnd.random()), n - 1)
            out.append((j / rb, tr.HUMAN, (r * tr.PERM_MUL + tr.SEED) % n, -1))
    out.sort(key=lambda x: x[0])
    return out


def trace_of(session, seed, name):
    lam, alpha, beta, scope, mul = POINTS[name]
    n = len(fase2._SIZES)
    rnd = random.Random(seed)
    skip = int(tr.WARMUP * lam * alpha)
    if session == "GEN":
        return (phase_scen(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0),
                phase_scen(rnd, n, lam, alpha, beta, scope, mul, tr.MEASURE, skip))
    return (phase_scen_real(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0, P_R, P_C),
            phase_scen_real(rnd, n, lam, alpha, beta, scope, mul, tr.MEASURE, skip, P_R, P_C))


def run_policy(cls, warm, meas):
    """Outputs as fase2.run_policy, with the times of the record (t, class, index, ...)."""
    sizes = fase2._SIZES
    c = cls(sizes, fase1.H)
    for rec in warm:
        c.get(rec[2], rec[0])
    req, miss = [0, 0, 0], [0, 0, 0]
    body, nobj, nxt = 0, [], 0.0
    for rec in meas:
        t, cl, idx = rec[0], rec[1], rec[2]
        while t >= nxt:
            nobj.append(len(c))
            nxt += 1.0
        req[cl] += 1
        body += sizes[idx]
        if not c.get(idx, tr.WARMUP + t):
            miss[cl] += 1
    return {"req": req, "miss": miss,
            "miss_share": [miss[k] / req[k] if req[k] else float("nan") for k in range(3)],
            "origin_rps": sum(miss) / tr.MEASURE, "n_object": statistics.fmean(nobj),
            "body_per_req": body / len(meas)}


def job(args):
    session, name, seed, pols = args
    warm, meas = trace_of(session, seed, name)
    out = []
    for pol in pols:
        r = run_policy(POLICIES[pol], warm, meas)
        r.update(session=session, policy=pol, point=name, seed=seed, h=fase1.H)
        out.append(r)
    return out


def run_jobs(jobs):
    with Pool(initializer=fase2._init) as pool:
        return [r for rs in pool.map(job, jobs, chunksize=1) for r in rs]


def write(name, cm, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with open(path, "w", newline="") as f:
        f.write(f"# commit {cm}; docs/PREREG-simulatore-fase2.md emendamento 2 (SCEN); "
                f"stato SIMULATO\n")
        f.write(f"# fonte: {fase2.SOURCE}; Q-REAL p_r {P_R} p_c {P_C} (fase 2, non ricalibrati)\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header + ["stato"])
        for r in rows:
            w.writerow(list(r) + ["SIMULATO"])
    print(f"written {path.relative_to(ROOT)}")


def r0_scen(cm):
    with open(ROOT / "data" / "sim" / "esplorativo-artefatto" / "reps.csv") as f:
        ref = {(r["point"], int(r["seed"])): r
               for r in csv.DictReader(line for line in f if not line.startswith("#"))
               if r["variant"] == "SCEN" and r["point"] in POINTS}
    res = run_jobs([("GEN", p, s, ("LRU",)) for p in POINTS for s in SEEDS])
    cols = ("req_h", "req_a", "req_e", "miss_h", "miss_a", "miss_e")
    bad = sum([*r["req"], *r["miss"]] != [int(ref[(r["point"], r["seed"])][c]) for c in cols]
              for r in res)
    ok = bad == 0 and len(res) == len(ref)
    print(f"== R0-SCEN: LRU x Q-GEN (SCEN) against esplorativo-artefatto SCEN: {len(res)} rows out of "
          f"{len(ref)}, different {bad}  {fase2.verdict(ok)}")
    write("r0.csv", cm, ["gate", "rows", "rows_ref", "rows_different", "verdict"],
          [["R0-SCEN", len(res), len(ref), bad, fase2.verdict(ok)]])
    return ok


def g0r_scen(cm):
    fase2._init()
    ids, cum = tr.corpus()
    stats = []
    for s in range(1, 6):
        _, meas = trace_of("REAL", s, "S12")
        stats.append(fase2.pair_stats([(rec[1], rec[2], rec[3]) for rec in meas], ids, cum))
    c = statistics.fmean(100 * a / n for n, a, _ in stats)
    r = statistics.fmean(100 * b / n for n, _, b in stats)
    okc, okr = abs(c - fase2.TARGET_C) <= 0.5, abs(r - fase2.TARGET_R) <= 1.0
    print(f"== G0-R-SCEN: contiguous {c:.2f}% (4.25 ± 0.5) {fase2.verdict(okc)}; repeated {r:.2f}% "
          f"(19.44 ± 1.0) {fase2.verdict(okr)}")
    write("g0r.csv", cm, ["gate", "quantity", "sim", "target", "rule", "verdict"],
          [["G0-R-SCEN", "contiguous_pct_S12", f"{c:.4f}", fase2.TARGET_C, "|x-4.25|<=0.5",
            fase2.verdict(okc)],
           ["G0-R-SCEN", "repeated_pct_S12", f"{r:.4f}", fase2.TARGET_R, "|x-19.44|<=1.0",
            fase2.verdict(okr)]])
    return okc and okr


def criteria(res, cm, sessions):
    """Same criteria and same reading as fase2.lancio."""
    ms, welch = fase1.mean_se, fase2.welch
    by = {}
    for r in res:
        by.setdefault((r["session"], r["policy"], r["point"]), []).append(r)
    rows, summary = [], {}
    for sess in sessions:
        for pol in fase2.POLICY_ORDER:
            g = lambda pt: by[(sess, pol, pt)]  # noqa: E731
            O = {pt: ms([r["origin_rps"] for r in g(pt)]) for pt in POINTS}
            mh = {pt: ms([r["miss_share"][tr.HUMAN] for r in g(pt)]) for pt in POINTS}
            key = f"{pol} x {sess}"
            print(f"\n==== {key} (SCEN)")
            m = {}
            for sc, (lo, hi) in fase1.SCOPE_POINTS.items():
                d, se, _, _ = welch(O[hi], O[lo])
                m[sc] = (d / fase1.D_RATE, se / fase1.D_RATE)
                print(f"  m scope {sc}: {m[sc][0]:+.4f} ± {m[sc][1]:.4f}  (t {m[sc][0] / m[sc][1]:+.2f})")
                rows.append([sess, pol, f"m_{sc}", f"{m[sc][0]:.6f}", f"{m[sc][1]:.6f}",
                             f"{m[sc][0] / m[sc][1]:.3f}", ""])
            t02 = m["0.02"][0] / m["0.02"][1]
            a1 = ("regge" if m["0.02"][0] < 0 and t02 <= -3 else
                  "si inverte" if m["0.02"][0] > 0 and t02 >= 3 else "indeterminato")
            d1, _, t1, _ = welch(m["0.06"], m["0.02"])
            d2, _, t2, _ = welch(m["0.20"], m["0.06"])
            dep = d1 > 0 and t1 >= 3 and d2 > 0 and t2 >= 3
            t20 = m["0.20"][0] / m["0.20"][1]
            sign = dep and m["0.02"][0] < 0 and t02 <= -3 and m["0.20"][0] > 0 and t20 >= 3
            print(f"  negative sign at 0.02: {a1}; dependence: m06-m02 t {t1:+.2f}, m20-m06 t "
                  f"{t2:+.2f}: {'regge' if dep else 'non regge'}; sign change: "
                  f"{'regge' if sign else 'non regge'}")
            dd = {}
            for q in ("12", "36"):
                d, se, t, _ = welch(O[f"S{q}"], O[f"C{q}"])
                dd[q] = (d, se, t)
                print(f"  d{q}: {d:+.4f} ± {se:.4f}  (t {t:+.2f})")
                rows.append([sess, pol, f"d{q}", f"{d:.6f}", f"{se:.6f}", f"{t:.3f}", ""])
            a3 = ("regge" if all(dd[q][0] > 0 and dd[q][2] >= 3 for q in dd) else
                  "si inverte" if any(dd[q][0] < 0 and dd[q][2] <= -3 for q in dd) else
                  "indeterminato")
            print(f"  A3: {a3}")
            n_, se_, t_, df_ = welch(O["S36"], O["P0"])
            q = t_quantile(0.975, df_)
            net = "non negativo" if t_ > -2 else "negativo"
            print(f"  net P0 -> 36: {n_:+.4f} ± {se_:.4f}  t {t_:+.2f}  IC95 "
                  f"[{n_ - q * se_:+.4f}, {n_ + q * se_:+.4f}]: {net}")
            rows.append([sess, pol, "net_S36_P0", f"{n_:.6f}", f"{se_:.6f}", f"{t_:.3f}",
                         f"IC95 [{n_ - q * se_:.6f}, {n_ + q * se_:.6f}] df {df_:.3f}; {net}"])
            dh = []
            for sc, (lo, hi) in fase1.SCOPE_POINTS.items():
                for tag, pt in (("12", lo), ("36", hi)):
                    d, se, t, _ = welch(mh[pt], mh["P0"])
                    dh.append(f"{sc}/{tag} {d:+.4f}±{se:.4f}")
                    rows.append([sess, pol, f"dmiss_h_scope{sc}_q{tag}", f"{d:.6f}", f"{se:.6f}",
                                 f"{t:.3f}", f"miss_h P0 {mh['P0'][0]:.6f}"])
            print(f"  Δ human miss (against P0 {mh['P0'][0]:.4f}): " + "; ".join(dh))
            for pt in POINTS:
                rows.append([sess, pol, f"origin_{pt}", f"{O[pt][0]:.6f}", f"{O[pt][1]:.6f}", "",
                             "miss per classe " + "/".join(
                                 f"{ms([r['miss_share'][k] for r in g(pt)])[0]:.4f}"
                                 for k in range(3)) +
                             f"; oggetti {ms([r['n_object'] for r in g(pt)])[0]:.1f}"])
            rows.append([sess, pol, "reading", "", "", "",
                         f"A1 segno {a1}; dipendenza {'regge' if dep else 'non regge'}; "
                         f"cambio di segno {'regge' if sign else 'non regge'}; A3 {a3}; netto {net}"])
            summary[key] = (a1, dep, sign, a3, net)
    write("criteri.csv", cm, ["session", "policy", "quantity", "value", "se", "t", "note"], rows)
    print("\n==== Answer to the question (SCEN)")
    for k, (a1, dep, sign, a3, net) in summary.items():
        ok = a1 == "regge" and dep and a3 == "regge"
        print(f"  {k}: {'regge' if ok else 'non regge'} (sign {a1}; dependence "
              f"{'yes' if dep else 'no'}; sign change {'yes' if sign else 'no'}; A3 {a3}; "
              f"net {net})")


def main():
    cm = fase1.commit()
    if not r0_scen(cm):
        sys.exit("R0-SCEN does not pass: stopping")
    sessions = ("GEN", "REAL") if g0r_scen(cm) else ("GEN",)
    if sessions == ("GEN",):
        print("G0-R-SCEN does not pass: (b) and (c) are not evaluated with SCEN")
    res = run_jobs([(s, p, seed, fase2.POLICY_ORDER) for s in sessions for p in POINTS
                    for seed in SEEDS])
    write("reps.csv", cm, ["session", "policy"] + fase1.REP_HDR,
          [[r["session"], r["policy"]] + fase2.fmt(r) for r in res])
    criteria(res, cm, sessions)


if __name__ == "__main__":
    main()
