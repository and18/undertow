#!/usr/bin/env python3
"""
fase1.py — simulatore di cache, fase 1: validazione sui dati del lab, come pre-registrato in
docs/PREREG-simulatore-fase1.md (commit c026e0b, pushato prima del confronto).

Due passi separati, nell'ordine della pre-registrazione:

  python3 tools/sim/fase1.py gates      G0, G1, G2 (con H = 512 e 250 byte)
  python3 tools/sim/fase1.py confronto  T1-T3, M1-M2 e grandezze senza soglia;
                                        parte solo se data/sim/fase1/gates.csv ha
                                        G0, G1 e G2 tutti PASSA

Ogni numero prodotto qui e' SIMULATO. Si ferma se tools/sim/ ha modifiche non committate:
il commit scritto in testa ai file di uscita deve essere quello che li ha prodotti.
Lab in sola lettura (`ssh lab cat`): points.csv e JSON di k6 dei run della replica.
"""
import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trace as tr  # noqa: E402  (tools/sim/trace.py, non il modulo standard)
from cache import LRU  # noqa: E402
assert hasattr(tr, "repetition"), "importato il modulo standard trace invece di tools/sim/trace.py"

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sim" / "fase1"
H, HDR = 512, 250            # pre-registrati
SEEDS = range(1, 21)         # 20 ripetizioni simulate per punto
G0_SEEDS = range(1, 6)
SEP, SHR = 3266489917, 2654435761

# nome -> (λ, α, β, scope, AGENT_MUL)
POINTS = {
    "S12": (95, 0.2947, 0.1263, 0.02, SEP),        # = scope 0,02, quota 13%
    "S36": (119, 0.2353, 0.3025, 0.02, SEP),       # = scope 0,02, quota 30%
    "C12": (95, 0.2947, 0.1263, 0.02, SHR),
    "C36": (119, 0.2353, 0.3025, 0.02, SHR),
    "P0": (83, 0.3373, 0.0, 0.02, SHR),
    "S12_006": (95, 0.2947, 0.1263, 0.06, SEP),
    "S36_006": (119, 0.2353, 0.3025, 0.06, SEP),
    "S12_020": (95, 0.2947, 0.1263, 0.20, SEP),
    "S36_020": (119, 0.2353, 0.3025, 0.20, SEP),
}
# scope -> (punto a quota 13%, punto a quota 30%), per T1 (class_miss_by_scope.csv)
SCOPE_POINTS = {"0.02": ("S12", "S36"), "0.06": ("S12_006", "S36_006"),
                "0.20": ("S12_020", "S36_020")}
# replica del 25-26 set (docs/RISULTATO-replica-20260924.md)
REPLICA = {"C12": "tre-20260925-213527", "S12": "tre-20260925-225538",
           "S36": "tre-20260926-001550", "P0": "tre-20260926-013602",
           "C36": "tre-20260926-025613"}
T2_LAB = {"S12": 37.678, "S36": 36.706, "C12": 36.796, "C36": 35.834, "P0": 36.468}
D_RATE = 35.9975 - 11.9985     # 23,9990
C2 = 5263.0


# ------------------------------------------------------------------ utilita'
def commit():
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "tools/sim"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        sys.exit(f"tools/sim/ ha modifiche non committate:\n{dirty}")
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def lab_cat(path):
    return subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{path}"],
                          capture_output=True, text=True, check=True).stdout


def sizes():
    ids, cum = tr.corpus()
    pos = {}
    with open(ROOT / "data" / "derived" / "chapter_sizes.csv", newline="") as f:
        for r in csv.DictReader(f):
            pos[(r["book_id"], int(r["n"]))] = int(r["bytes"])
    out = []
    for i in range(cum[-1]):
        out.append(pos[tr.locate(ids, cum, i)])
    return out


def mean_se(v):
    return statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))


def verdict(ok):
    return "PASSA" if ok else "NON PASSA"


def write(path, cm, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        f.write(f"# commit {cm}; docs/PREREG-simulatore-fase1.md; stato SIMULATO\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header + ["stato"])
        for r in rows:
            w.writerow(list(r) + ["SIMULATO"])
    print(f"scritto {path.relative_to(ROOT)}")


# -------------------------------------------------------------- simulazione
_SIZES = None


def _init():
    global _SIZES
    _SIZES = sizes()


def simulate(args):
    """Una ripetizione simulata: (punto, seme) -> dizionario di uscite della misura."""
    name, seed, h = args
    lam, alpha, beta, scope, mul = POINTS[name]
    n = len(_SIZES)
    warm, meas = tr.repetition(seed, n, lam, alpha, beta, scope, mul)
    c = LRU(_SIZES, h)
    for i, (_, idx, _) in enumerate(warm):
        c.get(idx, i / lam)
    req, miss = [0, 0, 0], [0, 0, 0]
    body = 0
    nobj = []
    for i, (cl, idx, _) in enumerate(meas):
        if i % lam == 0:                       # campione al secondo
            nobj.append(len(c))
        req[cl] += 1
        body += _SIZES[idx]
        if not c.get(idx, tr.WARMUP + i / lam):
            miss[cl] += 1
    return {"point": name, "seed": seed, "h": h,
            "req": req, "miss": miss,
            "miss_share": [miss[k] / req[k] if req[k] else float("nan") for k in range(3)],
            "origin_rps": sum(miss) / tr.MEASURE,
            "n_object": statistics.fmean(nobj),
            "body_per_req": body / len(meas)}


def run_points(names, h):
    jobs = [(p, s, h) for p in names for s in SEEDS]
    with Pool(initializer=_init) as pool:
        res = pool.map(simulate, jobs)
    by = {}
    for r in res:
        by.setdefault(r["point"], []).append(r)
    return by


def rep_rows(by):
    rows = []
    for p, rs in by.items():
        for r in sorted(rs, key=lambda x: x["seed"]):
            rows.append([p, r["seed"], r["h"], *r["req"], *r["miss"],
                         *(f"{x:.6f}" for x in r["miss_share"]), f"{r['origin_rps']:.6f}",
                         f"{r['n_object']:.3f}", f"{r['body_per_req']:.3f}"])
    return rows


REP_HDR = ["point", "seed", "H", "req_human", "req_agentic", "req_exhaustive",
           "miss_human", "miss_agentic", "miss_exhaustive", "miss_share_human",
           "miss_share_agentic", "miss_share_exhaustive", "origin_rps", "n_object_avg",
           "body_bytes_per_req"]


# -------------------------------------------------------------------- gates
def gates():
    cm = commit()
    rows, ok = [], {}
    ids, cum = tr.corpus()
    n = cum[-1]

    print("== G0 — contiguita' delle tracce a S12, sola misura, semi 1-5")
    lam, alpha, beta, scope, mul = POINTS["S12"]
    share = []
    for s in G0_SEEDS:
        _, meas = tr.repetition(s, n, lam, alpha, beta, scope, mul)
        p, a = tr.contiguity(meas, ids, cum)
        share.append(100 * a / p)
        print(f"  seme {s}: coppie {p}  contigue {a}  ({100 * a / p:.2f}%)")
    g0 = statistics.fmean(share)
    ok["G0"] = abs(g0 - 66.9) <= 0.5
    print(f"  media {g0:.2f}%  (soglia 66,9 ± 0,5)  {verdict(ok['G0'])}")
    rows.append(["G0", "contiguity_pct_S12", f"{g0:.4f}", "66.9", "|x-66.9|<=0.5",
                 verdict(ok["G0"])])

    print(f"\n== G1 — oggetti in cache, scope 0,20, H = {H}, 20 semi")
    by = run_points(["S12_020", "S36_020", "S12"], H)
    for p in ("S12_020", "S36_020"):
        m, se = mean_se([r["n_object"] for r in by[p]])
        g = abs(m - C2) / C2 <= 0.05
        ok[f"G1_{p}"] = g
        print(f"  {p}: {m:.1f} ± {se:.1f}  contro {C2:.0f}  ({100 * (m / C2 - 1):+.2f}%)  "
              f"{verdict(g)}")
        rows.append(["G1", f"n_object_{p}", f"{m:.4f}", f"{C2:.0f}", "|x/5263-1|<=0.05",
                     verdict(g)])

    print(f"\n== G2 — byte per richiesta a S12, corpo + {HDR}, 20 semi")
    lab = []
    for k in range(1, 6):
        j = json.loads(lab_cat(f"{REPLICA['S12']}/m-a0.2947-b0.1263-{k}.json"))
        lab.append(j["metrics"]["data_received"]["values"]["count"]
                   / j["metrics"]["http_reqs"]["values"]["count"])
    lab_m = statistics.fmean(lab)
    sim_m, sim_se = mean_se([r["body_per_req"] + HDR for r in by["S12"]])
    ok["G2"] = abs(sim_m - lab_m) / lab_m <= 0.05
    print(f"  lab {lab_m:.1f} (5 rip.)  sim {sim_m:.1f} ± {sim_se:.1f}  "
          f"({100 * (sim_m / lab_m - 1):+.2f}%)  {verdict(ok['G2'])}")
    rows.append(["G2", "bytes_per_req_S12", f"{sim_m:.4f}", f"{lab_m:.4f}",
                 "|x/lab-1|<=0.05", verdict(ok["G2"])])

    write(OUT / "gates.csv", cm, ["gate", "quantity", "sim", "lab", "rule", "verdict"], rows)
    allok = all(ok.values())
    print(f"\nCANCELLI: {verdict(allok)}")
    if not allok:
        print("Uno o piu' cancelli non passano: il confronto non si esegue (vedi la "
              "pre-registrazione per la ricalibrazione ammessa).")


# ---------------------------------------------------------------- confronto
def lab_replica():
    out = {}
    for p, run in REPLICA.items():
        rows = list(csv.DictReader(lab_cat(f"{run}/points.csv").splitlines()))
        out[p] = mean_se([float(r["origin_rps"]) for r in rows])
    return out


def confronto():
    cm = commit()
    with open(OUT / "gates.csv") as f:
        g = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    if not g or any(r["verdict"] != "PASSA" for r in g):
        sys.exit("gates.csv assente o con un cancello NON PASSA: confronto non eseguito")

    by = run_points(list(POINTS), H)
    write(OUT / "reps.csv", cm, REP_HDR, rep_rows(by))
    S = {p: {"O": mean_se([r["origin_rps"] for r in rs]),
             "miss": [mean_se([r["miss_share"][k] for r in rs]) for k in range(3)],
             "nobj": mean_se([r["n_object"] for r in rs])} for p, rs in by.items()}
    rows, crit = [], {}

    print("== T1 — miss per classe (soglia |Δ| <= 0,02)")
    col = {"human": tr.HUMAN, "agentic": tr.AGENT, "exhaustive": tr.TRAV}
    with open(ROOT / "data" / "derived" / "class_miss_by_scope.csv", newline="") as f:
        lab_miss = list(csv.DictReader(f))
    inside = 0
    for r in lab_miss:
        lo, hi = SCOPE_POINTS[r["scope"]]
        k = col[r["class"]]
        for q, p, key in (("13", lo, "miss_share13"), ("30", hi, "miss_share30")):
            sm, sse = S[p]["miss"][k]
            lm = float(r[key])
            ok = abs(sm - lm) <= 0.02
            inside += ok
            print(f"  scope {r['scope']} quota {q} {r['class']:10s} sim {sm:.4f} ± {sse:.4f}  "
                  f"lab {lm:.4f}  Δ {sm - lm:+.4f}  {verdict(ok)}")
            rows.append(["T1", f"miss_{r['class']}_scope{r['scope']}_q{q}", f"{sm:.6f}",
                         f"{sse:.6f}", f"{lm:.4f}", r[key.replace("miss_share", "se")],
                         "|d|<=0.02", verdict(ok)])
        f_sim = S[lo]["miss"][k][0] / S[hi]["miss"][k][0]
        print(f"      fattore 13%->30% sim {f_sim:.4f}  lab {float(r['factor']):.4f}  (senza soglia)")
        rows.append(["A2", f"factor_{r['class']}_scope{r['scope']}", f"{f_sim:.6f}", "",
                     r["factor"], "", "senza soglia", ""])
    crit["T1"] = inside == 2 * len(lab_miss)
    print(f"  entro soglia: {inside} su {2 * len(lab_miss)}  T1 {verdict(crit['T1'])}")

    print("\n== T2 — origin_rps ai 5 punti della replica (soglia 3%)")
    lab = lab_replica()
    t2 = True
    for p, ref in T2_LAB.items():
        if round(lab[p][0], 3) != ref:
            sys.exit(f"points.csv di {REPLICA[p]} non riproduce Ō = {ref}: {lab[p][0]}")
        sm, sse = S[p]["O"]
        ok = abs(sm - ref) / ref <= 0.03
        t2 &= ok
        print(f"  {p}: sim {sm:.4f} ± {sse:.4f}  lab {lab[p][0]:.4f} ± {lab[p][1]:.4f}  "
              f"({100 * (sm / ref - 1):+.2f}%)  {verdict(ok)}")
        rows.append(["T2", f"origin_rps_{p}", f"{sm:.6f}", f"{sse:.6f}", f"{lab[p][0]:.6f}",
                     f"{lab[p][1]:.6f}", "|x/lab-1|<=0.03", verdict(ok)])
    crit["T2"] = t2
    print(f"  T2 {verdict(t2)}")

    def diff(a, b, src, div=1.0):
        return (src[a][0] - src[b][0]) / div, math.sqrt(src[a][1] ** 2 + src[b][1] ** 2) / div

    simO = {p: S[p]["O"] for p in S}
    quant = {"m": ("S36", "S12", D_RATE), "d12": ("S12", "C12", 1.0), "d36": ("S36", "C36", 1.0)}
    print("\n== T3 — ampiezza delle differenze (soglia 3 SE combinati)  e  M1, M2 (segni)")
    val = {}
    for q, (a, b, dv) in quant.items():
        xs, ss = diff(a, b, simO, dv)
        xl, sl = diff(a, b, lab, dv)
        val[q] = (xs, ss)
        tol = 3 * math.sqrt(ss ** 2 + sl ** 2)
        ok = abs(xs - xl) <= tol
        crit[f"T3_{q}"] = ok
        print(f"  {q}: sim {xs:+.4f} ± {ss:.4f} (t {xs / ss:+.2f})  lab {xl:+.4f} ± {sl:.4f}  "
              f"|Δ| {abs(xs - xl):.4f}  soglia {tol:.4f}  {verdict(ok)}")
        rows.append(["T3", q, f"{xs:.6f}", f"{ss:.6f}", f"{xl:.6f}", f"{sl:.6f}",
                     f"|d|<={tol:.6f}", verdict(ok)])
    m, sm_ = val["m"]
    crit["M1"] = m < 0 and m / sm_ <= -3
    crit["M2"] = all(val[q][0] > 0 and val[q][0] / val[q][1] >= 3 for q in ("d12", "d36"))
    print(f"  M1: m_sim {m:+.4f}, t {m / sm_:+.2f}  {verdict(crit['M1'])}")
    print(f"  M2: d12 t {val['d12'][0] / val['d12'][1]:+.2f}, d36 t "
          f"{val['d36'][0] / val['d36'][1]:+.2f}  {verdict(crit['M2'])}")
    rows.append(["M1", "m_sign", f"{m:.6f}", f"{sm_:.6f}", "", "", "m<0 and t<=-3",
                 verdict(crit["M1"])])
    rows.append(["M2", "d_sign", f"{val['d12'][0]:.6f};{val['d36'][0]:.6f}",
                 f"{val['d12'][1]:.6f};{val['d36'][1]:.6f}", "", "", "d>0 and t>=3 both",
                 verdict(crit["M2"])])

    print("\n== Senza soglia")
    for sc, (lo, hi) in SCOPE_POINTS.items():
        x, s = diff(hi, lo, simO, D_RATE)
        print(f"  marginale scope {sc}: sim {x:+.4f} ± {s:.4f}")
        rows.append(["extra", f"marginal_scope{sc}", f"{x:.6f}", f"{s:.6f}", "", "",
                     "senza soglia", ""])
    x, s = diff("S36", "P0", simO)
    xl, sl = diff("S36", "P0", lab)
    print(f"  netto S36 - P0 (A9): sim {x:+.4f} ± {s:.4f}  lab {xl:+.4f} ± {sl:.4f}")
    rows.append(["extra", "net_S36_P0", f"{x:.6f}", f"{s:.6f}", f"{xl:.6f}", f"{sl:.6f}",
                 "senza soglia", ""])
    for p in POINTS:
        nm, ns = S[p]["nobj"]
        print(f"  oggetti in cache {p}: {nm:.1f} ± {ns:.1f}")
        rows.append(["extra", f"n_object_{p}", f"{nm:.4f}", f"{ns:.4f}", "", "",
                     "senza soglia", ""])

    write(OUT / "criteri.csv", cm, ["criterion", "quantity", "sim", "sim_se", "lab", "lab_se",
                                     "rule", "verdict"], rows)
    print("\n== Esito")
    for k, v in crit.items():
        print(f"  {k}: {verdict(v)}")
    if not (crit["M1"] and crit["M2"]):
        print("  M1 o M2 non passa: simulatore NON valido per la fase 2.")
    elif all(v for k, v in crit.items() if k.startswith("T")):
        print("  Valido per segni e ampiezze.")
    else:
        print("  Valido SOLO per i segni.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("gates", "confronto"))
    a = ap.parse_args()
    gates() if a.step == "gates" else confronto()
