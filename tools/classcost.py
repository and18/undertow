#!/usr/bin/env python3
"""
classcost.py - I tre profili di costo, confrontati senza far girare nulla.

PERCHE'
  Tutti i risultati del banco prova sono espressi in "origin rps", che
  conta i MISS. Un miss pero' non e' un'unita' di lavoro: l'endpoint
  /book/<id>/ch/<n> esegue quattro query, e tre hanno costo variabile.
  La dominante e' ts_headline su c.body dei dodici capitoli collegati,
  che scandisce il testo intero di ciascuno.

  Il corpus e' a coda pesante (mediana 9,5 KB, media 15,0 KB, deviazione
  standard 32,4 KB, massimo 1,9 MB). La classe esaustiva attraversa tutto
  il corpus, quindi il suo costo medio tende alla media del corpus; le
  classi umana e agentica insistono su ~1000 capitoli scelti da una
  permutazione. Un solo capitolo da 1,9 MB dentro mille sposta la media
  del 13%.

  Se i tre profili coincidono, "origin rps" e' un proxy valido per i
  confronti FRA classi e tutti i risultati reggono. Se divergono, le
  grandezze comparative (costo marginale agentico contro esaustivo)
  sono in unita' sbagliate.

METODO
  Replica esattamente permute(), permuteTrav(), zipfRank() e
  agenticIndex() di harness/load/workload.js, con gli stessi seed e
  moltiplicatori, e la stessa mappa indice->capitolo di locate().
  Il vettore cumulativo viene preso da /library, cioe' dalla stessa
  fonte che usa setup() in k6: nessuna assunzione sull'ordinamento.

  Per ogni classe genera l'insieme di indici che quella classe
  richiederebbe, e ne calcola il profilo di costo dalle grandezze reali
  in PostgreSQL.

  Per la classe Zipf il confronto e' PESATO sulla probabilita' di
  richiesta, perche' il suo flusso non e' uniforme sul proprio insieme.

Uso:  python3 classcost.py [--lambda 110] [--measure 620]
"""
import argparse, json, os, statistics, sys, urllib.request

SEED       = 42
PERM_MUL   = 2654435761
TRAV_MUL   = 2246822519
AGENT_SCOPE   = 0.02
AGENT_SESSION = 3
AGENT_SKEW    = 0.6

ap = argparse.ArgumentParser()
ap.add_argument("--app", default="http://localhost:8080")
ap.add_argument("--lam", type=float, default=110.0)
ap.add_argument("--measure", type=int, default=620)
ap.add_argument("--alpha", type=float, default=0.25)
ap.add_argument("--beta", type=float, default=0.12)
a = ap.parse_args()


# ---------------------------------------------------- corpus, da /library
with urllib.request.urlopen(a.app + "/library", timeout=30) as r:
    books = json.loads(r.read())
ids, cum, total = [], [], 0
for b in books:
    ids.append(b["id"])
    total += b["n_chapters"]
    cum.append(total)
print(f"corpus: {len(ids)} libri, {total} capitoli")


def locate(idx):
    lo, hi = 0, len(cum) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] <= idx:
            lo = mid + 1
        else:
            hi = mid
    base = cum[lo - 1] if lo > 0 else 0
    return ids[lo], idx - base + 1


def permute(rank, N):
    return (rank * PERM_MUL + SEED) % N


def permute_trav(i, N):
    return ((i % N) * (TRAV_MUL % N) + SEED * 7919) % N


offset = (SEED * 7919) % total

# ------------------------------------------------- insiemi per classe
# esaustiva: attraversa il corpus in sequenza dall'offset
n_trav = int(a.lam * a.alpha * a.measure)
trav = {}
for i in range(min(n_trav, total)):
    trav[permute_trav(offset + i, total)] = trav.get(permute_trav(offset + i, total), 0) + 1

# umana: Zipf(1) sul rango, pesata. CDF(r)=H_r/H_N, r ~ N^u.
# Si costruisce la distribuzione esatta invece di campionarla: la
# probabilita' del rango r e' 1/(r*H_N).
H = sum(1.0 / r for r in range(1, total + 1))
zipf = {}
for r in range(1, total + 1):
    p = 1.0 / (r * H)
    if p * a.lam * (1 - a.alpha - a.beta) * a.measure < 0.5:
        break            # ranghi che non verrebbero richiesti nemmeno una volta
    zipf[permute(r - 1, total)] = p

# agentica: Zipf(0.6) su un sottoinsieme, poi 3 capitoli contigui
scope = max(1, int(total * AGENT_SCOPE))
agent = {}
for r in range(scope):
    p = ((r + 1) ** (1 - AGENT_SKEW) - r ** (1 - AGENT_SKEW)) / (scope ** (1 - AGENT_SKEW))
    base = permute(r, total)
    for k in range(AGENT_SESSION):
        idx = (base + k) % total
        agent[idx] = agent.get(idx, 0) + p / AGENT_SESSION

print(f"insiemi: esaustiva {len(trav)}, umana {len(zipf)}, agentica {len(agent)} capitoli distinti")

# ------------------------------------------------------ costi, da Postgres
SQL = """
SELECT c.book_id, c.n,
       length(c.body)                              AS own_bytes,
       b.n_chapters                                AS toc_rows,
       COALESCE((SELECT sum(length(c2.body))
                   FROM links l
                   JOIN chapters c2 ON c2.book_id = l.dst_book
                                   AND c2.n       = l.dst_n
                  WHERE l.src_book = c.book_id AND l.src_n = c.n), 0) AS related_bytes,
       COALESCE((SELECT count(*) FROM links l
                  WHERE l.src_book = c.book_id AND l.src_n = c.n), 0) AS related_n
  FROM chapters c JOIN books b ON b.id = c.book_id
"""
print("interrogo PostgreSQL (16.954 righe, un minuto circa)...")
import subprocess
out = subprocess.run(
    ["docker", "compose", "exec", "-T", "db", "psql", "-U", "undertow", "-d", "undertow",
     "-At", "-F", "\t", "-c", SQL],
    capture_output=True, text=True, cwd=os.path.expanduser("~/undertow/harness"))
if out.returncode != 0:
    sys.exit("psql fallito:\n" + out.stderr[:800])

cost = {}
for line in out.stdout.splitlines():
    p = line.split("\t")
    if len(p) < 6:
        continue
    cost[(int(p[0]), int(p[1]))] = (int(p[2]), int(p[3]), int(p[4]), int(p[5]))
print(f"caricati {len(cost)} capitoli\n")


def profile(name, weights):
    ow = tw = rw = rn = wsum = 0.0
    vals = []
    for idx, w in weights.items():
        key = locate(idx)
        c = cost.get(key)
        if not c:
            continue
        ow += c[0] * w; tw += c[1] * w; rw += c[2] * w; rn += c[3] * w
        wsum += w
        vals.append(c[0] + c[2])          # byte scanditi: propri + related
    if wsum == 0:
        return None
    vals.sort()
    return {
        "n": len(vals),
        "own_kb": ow / wsum / 1024,
        "toc_rows": tw / wsum,
        "related_kb": rw / wsum / 1024,
        "related_n": rn / wsum,
        "scan_kb": (ow + rw) / wsum / 1024,
        "p50_kb": vals[len(vals) // 2] / 1024,
        "p99_kb": vals[min(len(vals) - 1, int(0.99 * len(vals)))] / 1024,
        "max_kb": vals[-1] / 1024,
    }


# riferimento: media del corpus, non pesata
allw = {i: 1.0 for i in range(total)}

rows = [("corpus intero", profile("corpus", allw)),
        ("esaustiva", profile("trav", trav)),
        ("umana (Zipf)", profile("zipf", zipf)),
        ("agentica", profile("agent", agent))]

print(f"{'classe':16s} {'n':>7s} {'own KB':>8s} {'toc':>6s} {'rel KB':>8s} "
      f"{'rel n':>6s} {'SCAN KB':>9s} {'p50':>7s} {'p99':>8s} {'max':>9s}")
base = None
for name, p in rows:
    if not p:
        continue
    if base is None:
        base = p["scan_kb"]
    print(f"{name:16s} {p['n']:7d} {p['own_kb']:8.1f} {p['toc_rows']:6.1f} "
          f"{p['related_kb']:8.1f} {p['related_n']:6.1f} {p['scan_kb']:9.1f} "
          f"{p['p50_kb']:7.1f} {p['p99_kb']:8.1f} {p['max_kb']:9.1f}")

print()
print("SCAN KB = byte di testo che ts_headline e la lettura del capitolo")
print("attraversano per ogni richiesta. E' il termine dominante del costo.")
print()
ref = rows[0][1]["scan_kb"]
for name, p in rows[1:]:
    if p:
        d = 100 * (p["scan_kb"] / ref - 1)
        print(f"  {name:16s} {d:+6.1f}% rispetto alla media del corpus")
print()
print("CRITERIO: se le tre classi stanno entro +/-10% l'una dall'altra,")
print("un miss costa lo stesso a chiunque e 'origin rps' e' un proxy")
print("valido per i confronti FRA classi. Oltre il 20%, le grandezze")
print("comparative vanno riespresse in unita' di lavoro.")