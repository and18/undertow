#!/usr/bin/env python3
"""
fase2.py — simulatore, fase 2: politiche di sostituzione e sessioni realistiche, come
pre-registrato in docs/PREREG-simulatore-fase2.md (cf214d2, emendamento 1 in a9c854d, pushati
prima di qualunque codice). Passi, nell'ordine pre-registrato:

  python3 tools/sim/test_policies.py    K     collaudo delle politiche
  python3 tools/sim/fase2.py r0          R0    LRU x Q-GEN = fase 1, esattamente
  python3 tools/sim/fase2.py calibra           p_r, p_c di Q-REAL (semi 101-105, S12)
  python3 tools/sim/fase2.py g0r         G0-R  contiguita' e ripetizioni con p_r, p_c fissati
  python3 tools/sim/fase2.py lancio            le 8 combinazioni in un solo lancio, poi i criteri

Ogni passo parte solo se i precedenti hanno scritto un esito PASSA in data/sim/fase2/.
Ogni numero e' SIMULATO. Nessun dato del lab: tutto viene dal repository.
"""
import argparse
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
from net_agentic import t_quantile  # noqa: E402
from policies import POLICIES  # noqa: E402

assert hasattr(tr, "repetition"), "importato il modulo standard trace invece di tools/sim/trace.py"

ROOT = fase1.ROOT
OUT = ROOT / "data" / "sim" / "fase2"
H = fase1.H
SEEDS = fase1.SEEDS                 # 1..20
CAL_SEEDS = range(101, 106)
G0R_SEEDS = range(1, 6)
TARGET_C, TARGET_R = 4.25, 19.44    # data/derived/honeypot_contiguity.csv, classe agent
POINTS = fase1.POINTS
POLICY_ORDER = ("LRU", "SIEVE", "S3FIFO", "WTinyLFU")
SESSIONS = ("GEN", "REAL")
SOURCE = "nessun dato del lab: books.csv, chapter_sizes.csv, honeypot_contiguity.csv dal repository"


# -------------------------------------------------------------- sessioni realistiche
def phase_real(rnd, n, lam, alpha, beta, scope, agent_mul, duration, trav_skip, p_r, p_c,
               skew=0.6):
    """Come trace.phase, con la classe agentica di Q-REAL: catena per VU a tre esiti
    (ripetizione p_r, adiacente nel blocco di 3 p_c, estrazione nuova altrimenti).
    Estrazione nuova: base come nel generatore (Zipf(0,6) sullo scope, permuteAgent) e
    scostamento uniforme k in {0, 1, 2}."""
    iters = int(round(lam * duration))
    nvu = min(max(math.ceil(2 * lam), 200), 4000)
    s_bases = max(1, math.floor(n * scope))
    offset = (tr.SEED * 7919) % n
    tmul = tr.TRAV_MUL % n
    state = [None] * nvu                      # (base, k) dell'ultima richiesta agentica del VU
    out = []
    expo = 1 / (1 - skew)
    for i in range(iters):
        u = rnd.random()
        if u < alpha:
            idx = (((offset + trav_skip + i) % n) * tmul + tr.SEED * 7919) % n
            out.append((tr.TRAV, idx, -1))
        elif u < alpha + beta:
            v = i % nvu
            s = state[v]
            x = rnd.random() if s is not None else 1.0
            if s is not None and x < p_r:
                base, k = s
            elif s is not None and x < p_r + p_c:
                base, k = s
                k = 1 if k != 1 else (0 if rnd.random() < 0.5 else 2)
            else:
                r = min(s_bases - 1, math.floor(s_bases * rnd.random() ** expo))
                base = (r * agent_mul + tr.SEED) % n
                k = min(int(rnd.random() * 3), 2)
            state[v] = (base, k)
            out.append((tr.AGENT, (base + k) % n, v, k))
        else:
            r = min(math.floor(n ** rnd.random()), n - 1)
            out.append((tr.HUMAN, (r * tr.PERM_MUL + tr.SEED) % n, -1))
    return out


def repetition(session, seed, name, p=(0.0, 0.0)):
    n = len(_SIZES) if _SIZES is not None else tr.corpus()[1][-1]
    lam, alpha, beta, scope, mul = POINTS[name]
    if session == "GEN":
        return tr.repetition(seed, n, lam, alpha, beta, scope, mul)
    rnd = random.Random(seed)
    warm = phase_real(rnd, n, lam, alpha, beta, scope, mul, tr.WARMUP, 0, *p)
    skip = int(tr.WARMUP * lam * alpha)
    meas = phase_real(rnd, n, lam, alpha, beta, scope, mul, tr.MEASURE, skip, *p)
    return warm, meas


def pair_stats(meas, ids, cum):
    """Metrica di C5 (honeypot_scope.py sez. 4): coppie consecutive per sessione (= VU),
    contigua = stesso libro e capitolo adiacente, ripetuta = stesso libro e capitolo."""
    seq = {}
    for rec in meas:
        if rec[0] == tr.AGENT:
            seq.setdefault(rec[2], []).append(tr.locate(ids, cum, rec[1]))
    pairs = adj = rep = 0
    for q in seq.values():
        for x, y in zip(q, q[1:]):
            pairs += 1
            if x[0] == y[0]:
                adj += abs(y[1] - x[1]) == 1
                rep += y[1] == x[1]
    return pairs, adj, rep


# ----------------------------------------------------------------------- simulazione
_SIZES = None


def _init():
    global _SIZES
    _SIZES = fase1.sizes()


def run_policy(cls, warm, meas, lam):
    """Stesse uscite di fase1.simulate, per una politica qualunque."""
    c = cls(_SIZES, H)
    for i, rec in enumerate(warm):
        c.get(rec[1], i / lam)
    req, miss = [0, 0, 0], [0, 0, 0]
    body = 0
    nobj = []
    for i, rec in enumerate(meas):
        cl, idx = rec[0], rec[1]
        if i % lam == 0:
            nobj.append(len(c))
        req[cl] += 1
        body += _SIZES[idx]
        if not c.get(idx, tr.WARMUP + i / lam):
            miss[cl] += 1
    return {"req": req, "miss": miss,
            "miss_share": [miss[k] / req[k] if req[k] else float("nan") for k in range(3)],
            "origin_rps": sum(miss) / tr.MEASURE,
            "n_object": statistics.fmean(nobj),
            "body_per_req": body / len(meas)}


def job(args):
    """(sessione, punto, seme, p, politiche) -> una riga per politica, stessa traccia."""
    session, name, seed, p, pols = args
    warm, meas = repetition(session, seed, name, p)
    lam = POINTS[name][0]
    out = []
    for pol in pols:
        r = run_policy(POLICIES[pol], warm, meas, lam)
        r.update(session=session, policy=pol, point=name, seed=seed, h=H)
        out.append(r)
    return out


def run_jobs(jobs):
    with Pool(initializer=_init) as pool:
        return [r for rs in pool.map(job, jobs, chunksize=1) for r in rs]


def fmt(r):
    """Stessa formattazione di fase1.rep_rows."""
    return [r["point"], r["seed"], r["h"], *r["req"], *r["miss"],
            *(f"{x:.6f}" for x in r["miss_share"]), f"{r['origin_rps']:.6f}",
            f"{r['n_object']:.3f}", f"{r['body_per_req']:.3f}"]


# ----------------------------------------------------------------------------- uscite
def write(name, cm, header, rows, extra=""):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with open(path, "w", newline="") as f:
        f.write(f"# commit {cm}; docs/PREREG-simulatore-fase2.md (emendamento 1); stato SIMULATO\n")
        f.write(f"# fonte: {SOURCE}{extra}\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header + ["stato"])
        for r in rows:
            w.writerow(list(r) + ["SIMULATO"])
    print(f"scritto {path.relative_to(ROOT)}")


def read(name):
    path = OUT / name
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))


def require(name, what):
    rows = read(name)
    if not rows or any(r.get("verdict") not in ("PASSA", "") for r in rows):
        sys.exit(f"{name} assente o con un esito NON PASSA: {what} non si esegue")
    return rows


def verdict(ok):
    return "PASSA" if ok else "NON PASSA"


# -------------------------------------------------------------------------------- R0
def r0():
    cm = fase1.commit()
    with open(ROOT / "data" / "sim" / "fase1" / "reps.csv") as f:
        ref = [r for r in csv.reader(line for line in f if not line.startswith("#"))]
    hdr, ref = ref[0], ref[1:]
    assert hdr[:-1] == fase1.REP_HDR
    ref = {(r[0], r[1]): r[:-1] for r in ref}
    res = run_jobs([("GEN", p, s, (0.0, 0.0), ("LRU",)) for p in POINTS for s in SEEDS])
    diff = []
    for r in res:
        got = [str(x) for x in fmt(r)]
        want = ref[(r["point"], str(r["seed"]))]
        if got != want:
            diff.append((r["point"], r["seed"], got, want))
    ok = not diff and len(res) == len(ref)
    print(f"== R0 — LRU x Q-GEN contro data/sim/fase1/reps.csv: {len(res)} righe su {len(ref)}, "
          f"diverse {len(diff)}  {verdict(ok)}")
    for d in diff[:5]:
        print(f"  {d[0]} seme {d[1]}\n    fase 2 {d[2]}\n    fase 1 {d[3]}")
    write("r0.csv", cm, ["gate", "rows", "rows_ref", "rows_different", "verdict"],
          [["R0", len(res), len(ref), len(diff), verdict(ok)]])


# ------------------------------------------------------------------------ calibrazione
def _metric(args):
    seed, p = args
    ids, cum = tr.corpus()
    _, meas = repetition("REAL", seed, "S12", p)
    return pair_stats(meas, ids, cum)


def metric(pool, p, seeds):
    res = pool.map(_metric, [(s, p) for s in seeds])
    c = statistics.fmean(100 * a / n for n, a, _ in res)
    r = statistics.fmean(100 * b / n for n, _, b in res)
    return c, r, res


def bisect(f, lo, hi, target, steps=40):
    """Bisezione su una funzione crescente; si ferma entro 0,1 punti dal bersaglio."""
    for _ in range(steps):
        mid = (lo + hi) / 2
        v = f(mid)
        if abs(v - target) <= 0.1:
            return mid, v
        lo, hi = (mid, hi) if v < target else (lo, mid)
    return mid, v


def calibra():
    cm = fase1.commit()
    require("r0.csv", "la calibrazione")
    rows = []
    with Pool(initializer=_init) as pool:
        p_r, p_c = TARGET_R / 100, TARGET_C / 100
        for it in range(1, 21):
            p_r, vr = bisect(lambda x: metric(pool, (x, p_c), CAL_SEEDS)[1], 0.0, 1.0 - p_c,
                             TARGET_R)
            p_c, vc = bisect(lambda x: metric(pool, (p_r, x), CAL_SEEDS)[0], 0.0, 1.0 - p_r,
                             TARGET_C)
            c, r, _ = metric(pool, (p_r, p_c), CAL_SEEDS)
            print(f"  giro {it}: p_r {p_r:.6f}  p_c {p_c:.6f}  -> contigue {c:.3f}%  "
                  f"ripetute {r:.3f}%")
            rows.append([it, f"{p_r:.9f}", f"{p_c:.9f}", f"{c:.4f}", f"{r:.4f}"])
            if abs(c - TARGET_C) <= 0.1 and abs(r - TARGET_R) <= 0.1:
                break
    ok = abs(c - TARGET_C) <= 0.1 and abs(r - TARGET_R) <= 0.1
    print(f"== calibrazione: p_r {p_r:.9f}  p_c {p_c:.9f}  (semi 101-105)  {verdict(ok)}")
    write("calibrazione.csv", cm, ["round", "p_r", "p_c", "contiguous_pct", "repeated_pct",
                                   "verdict"],
          [r + ([verdict(ok)] if r is rows[-1] else [""]) for r in rows])


def calibrated():
    rows = require("calibrazione.csv", "il passo")
    last = rows[-1]
    return float(last["p_r"]), float(last["p_c"])


# ------------------------------------------------------------------------------ G0-R
def g0r():
    cm = fase1.commit()
    p = calibrated()
    ids, cum = tr.corpus()
    with Pool(initializer=_init) as pool:
        c, r, res = metric(pool, p, G0R_SEEDS)
    okc, okr = abs(c - TARGET_C) <= 0.5, abs(r - TARGET_R) <= 1.0
    for s, (n, a, b) in zip(G0R_SEEDS, res):
        print(f"  seme {s}: coppie {n}  contigue {a} ({100 * a / n:.2f}%)  ripetute {b} "
              f"({100 * b / n:.2f}%)")
    print(f"== G0-R: contigue {c:.2f}% (4,25 ± 0,5) {verdict(okc)}; ripetute {r:.2f}% "
          f"(19,44 ± 1,0) {verdict(okr)}")
    # senza soglia: scostamenti k e oggetti agentici distinti a S12, seme 1, contro Q-GEN
    _init()
    _, meas_r = repetition("REAL", 1, "S12", p)
    _, meas_g = repetition("GEN", 1, "S12")
    ks = [rec[3] for rec in meas_r if rec[0] == tr.AGENT]
    kdist = [ks.count(k) / len(ks) for k in range(3)]
    dr = len({rec[1] for rec in meas_r if rec[0] == tr.AGENT})
    dg = len({rec[1] for rec in meas_g if rec[0] == tr.AGENT})
    print(f"  senza soglia: k = 0/1/2 {kdist[0]:.4f} / {kdist[1]:.4f} / {kdist[2]:.4f}; "
          f"oggetti agentici distinti in 620 s (seme 1) Q-REAL {dr}, Q-GEN {dg}")
    write("g0r.csv", cm, ["gate", "quantity", "sim", "target", "rule", "verdict"],
          [["G0-R", "contiguous_pct_S12", f"{c:.4f}", TARGET_C, "|x-4.25|<=0.5", verdict(okc)],
           ["G0-R", "repeated_pct_S12", f"{r:.4f}", TARGET_R, "|x-19.44|<=1.0", verdict(okr)],
           ["extra", "k_share_0_1_2", ";".join(f"{x:.4f}" for x in kdist), "", "senza soglia", ""],
           ["extra", "distinct_agent_objects_seed1_REAL_GEN", f"{dr};{dg}", "", "senza soglia",
            ""]])


# ---------------------------------------------------------------------------- lancio
def ms(v):
    return fase1.mean_se(v)


def welch(a, b):
    """(media a - media b, SE, t, df) con n = 20 per lato."""
    (ma, sa), (mb, sb) = a, b
    se = math.sqrt(sa ** 2 + sb ** 2)
    n = len(SEEDS)
    df = se ** 4 / (sa ** 4 / (n - 1) + sb ** 4 / (n - 1))
    d = ma - mb
    return d, se, d / se, df


def lancio():
    cm = fase1.commit()
    require("r0.csv", "il lancio")
    p = calibrated()
    require("g0r.csv", "il lancio")
    jobs = [(sess, pt, s, p if sess == "REAL" else (0.0, 0.0), POLICY_ORDER)
            for sess in SESSIONS for pt in POINTS for s in SEEDS]
    res = run_jobs(jobs)
    write("reps.csv", cm, ["session", "policy"] + fase1.REP_HDR,
          [[r["session"], r["policy"]] + fmt(r) for r in res],
          extra=f"; Q-REAL p_r {p[0]:.9f} p_c {p[1]:.9f}")
    by = {}
    for r in res:
        by.setdefault((r["session"], r["policy"], r["point"]), []).append(r)
    rows = []
    summary = {}
    for sess in SESSIONS:
        for pol in POLICY_ORDER:
            g = lambda pt: by[(sess, pol, pt)]  # noqa: E731
            O = {pt: ms([r["origin_rps"] for r in g(pt)]) for pt in POINTS}
            mh = {pt: ms([r["miss_share"][tr.HUMAN] for r in g(pt)]) for pt in POINTS}
            key = f"{pol} x {sess}"
            print(f"\n==== {key}")
            m = {}
            for sc, (lo, hi) in fase1.SCOPE_POINTS.items():
                d, se, t, _ = welch(O[hi], O[lo])
                m[sc] = (d / fase1.D_RATE, se / fase1.D_RATE)
                print(f"  m scope {sc}: {m[sc][0]:+.4f} ± {m[sc][1]:.4f}  (t {m[sc][0] / m[sc][1]:+.2f})")
                rows.append([sess, pol, f"m_{sc}", f"{m[sc][0]:.6f}", f"{m[sc][1]:.6f}",
                             f"{m[sc][0] / m[sc][1]:.3f}", ""])
            t02 = m["0.02"][0] / m["0.02"][1]
            a1 = ("regge" if m["0.02"][0] < 0 and t02 <= -3 else
                  "si inverte" if m["0.02"][0] > 0 and t02 >= 3 else "indeterminato")
            d1, s1, t1, _ = welch(m["0.06"], m["0.02"])
            d2, s2, t2, _ = welch(m["0.20"], m["0.06"])
            dep = d1 > 0 and t1 >= 3 and d2 > 0 and t2 >= 3
            t20 = m["0.20"][0] / m["0.20"][1]
            sign = dep and m["0.02"][0] < 0 and t02 <= -3 and m["0.20"][0] > 0 and t20 >= 3
            print(f"  segno negativo a 0,02: {a1}")
            print(f"  dipendenza: m06-m02 {d1:+.4f} (t {t1:+.2f}), m20-m06 {d2:+.4f} (t {t2:+.2f}): "
                  f"{'regge' if dep else 'non regge'}; cambio di segno: "
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
            print(f"  netto P0 -> 36: {n_:+.4f} ± {se_:.4f}  t {t_:+.2f}  df {df_:.2f}  "
                  f"IC95 [{n_ - q * se_:+.4f}, {n_ + q * se_:+.4f}]: {net}")
            rows.append([sess, pol, "net_S36_P0", f"{n_:.6f}", f"{se_:.6f}", f"{t_:.3f}",
                         f"IC95 [{n_ - q * se_:.6f}, {n_ + q * se_:.6f}] df {df_:.3f}; {net}"])
            dh = {}
            for sc, (lo, hi) in fase1.SCOPE_POINTS.items():
                for tag, pt in (("12", lo), ("36", hi)):
                    d, se, t, _ = welch(mh[pt], mh["P0"])
                    dh[(sc, tag)] = (d, se)
                    rows.append([sess, pol, f"dmiss_h_scope{sc}_q{tag}", f"{d:.6f}", f"{se:.6f}",
                                 f"{t:.3f}", f"miss_h P0 {mh['P0'][0]:.6f}"])
            print("  Δ miss umano (contro P0 " + f"{mh['P0'][0]:.4f}): " + "; ".join(
                f"{sc}/{tag} {v[0]:+.4f}±{v[1]:.4f}" for (sc, tag), v in dh.items()))
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
    write("criteri.csv", cm, ["session", "policy", "quantity", "value", "se", "t", "note"], rows,
          extra=f"; Q-REAL p_r {p[0]:.9f} p_c {p[1]:.9f}")

    print("\n==== Risposta alla domanda (regge = segno di A1 regge, dipendenza regge, A3 regge)")
    def holds(k):  # noqa: E306
        a1, dep, _, a3, _ = summary[k]
        return a1 == "regge" and dep and a3 == "regge"
    for label, keys in (("(a) altre politiche, Q-GEN", [f"{p} x GEN" for p in POLICY_ORDER[1:]]),
                        ("(b) LRU, Q-REAL", ["LRU x REAL"]),
                        ("(c) altre politiche, Q-REAL", [f"{p} x REAL" for p in POLICY_ORDER[1:]])):
        print(f"  {label}: " + "; ".join(f"{k} {'regge' if holds(k) else 'non regge'}"
                                          for k in keys))
    print(f"  riferimento LRU x GEN: {'regge' if holds('LRU x GEN') else 'non regge'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("r0", "calibra", "g0r", "lancio"))
    a = ap.parse_args()
    {"r0": r0, "calibra": calibra, "g0r": g0r, "lancio": lancio}[a.step]()
