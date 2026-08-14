#!/usr/bin/env python3
"""
pick_terms.py - Seleziona i termini di ricerca in una banda di costo.

PERCHE'

Il costo di una ricerca full-text dipende da quanti capitoli contengono
il termine: sul corpus attuale va da 83 ms per "whale" a 1330 ms per
"night", un fattore 16. Un termine scelto liberamente renderebbe il
costo per richiesta una variabile NON CONTROLLATA del workload — e se i
profili umano e agentico campionassero termini con costo diverso, si
confonderebbe la composizione del traffico con il costo delle query.

La varianza non si elimina riscrivendo la query: e' intrinseca al
ranking full-text, che deve calcolare ts_rank su ogni corrispondenza.
Si controlla selezionando a monte i termini che cadono in una banda
stretta, misurata sul corpus in uso.

Il risultato e' un file versionato: chiunque replichi l'esperimento usa
gli stessi termini e ottiene lo stesso costo per richiesta.

TARATURA DELLA BANDA

La banda va scelta in funzione della legge di Little. Perche' un pool di
N thread si saturi a un ritmo di lambda richieste al secondo all'origine
serve W = N / lambda. Con N=16 e un ginocchio desiderato attorno ai
320 req/s, W deve valere circa 50 ms.

USO

    python tools/pick_terms.py --target 8080 --lo 35 --hi 70 --want 40
    # scrive harness/profiles/search-terms.txt
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Candidati: parole comuni nella narrativa e nella saggistica di lingua
# inglese, scelte per coprire un ampio intervallo di frequenza nel corpus.
# L'elenco e' volutamente lungo: la selezione la fa la misura, non l'autore.
CANDIDATES = """
whale ship ocean captain sailor harbour voyage anchor storm tide
love heart marriage wedding kiss letter promise sorrow tears joy
night morning evening winter summer autumn dawn dusk moonlight sunrise
house garden window door chamber staircase kitchen parlour attic cottage
horse carriage road journey village town city street bridge river
soldier battle sword captain colonel regiment victory retreat siege wound
church priest prayer sermon bible altar chapel monastery convent pilgrim
money fortune debt inheritance business merchant contract wages profit rent
doctor illness fever medicine hospital nurse patient remedy plague wound
mother father brother sister daughter uncle cousin nephew widow orphan
forest mountain valley meadow river lake island desert cliff cavern
book library manuscript letter newspaper poem novel author reader page
king queen prince duke count baron peasant servant master mistress
justice court judge lawyer prison trial witness verdict crime punishment
laughter silence whisper shout song music violin piano dance melody
cathedral revolution monsieur elephant telescope philosophy machinery
chocolate umbrella lantern spectacles waistcoat handkerchief carriage
""".split()


def measure(base, term, repeats=3):
    """Latenza mediana di una ricerca, in millisecondi.

    Mediana e non media: una singola esecuzione fredda produce un valore
    molto piu' alto delle successive e trascinerebbe la media.
    """
    url = f"{base}/search?q={urllib.parse.quote(term)}"
    times, hits = [], 0
    for i in range(repeats + 1):          # +1 = giro di riscaldamento
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = json.loads(r.read())
        except Exception as e:
            return None, 0
        dt = (time.perf_counter() - t0) * 1000
        if i > 0:
            times.append(dt)
        hits = len(body.get("results", []))
    return statistics.median(times), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--lo", type=float, default=35.0,
                    help="estremo inferiore della banda, ms")
    ap.add_argument("--hi", type=float, default=70.0,
                    help="estremo superiore della banda, ms")
    ap.add_argument("--want", type=int, default=40,
                    help="quanti termini selezionare")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    out = Path(args.out) if args.out else repo / "harness/profiles/search-terms.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    terms = sorted(set(CANDIDATES))
    print(f"misuro {len(terms)} termini su {args.base}\n")

    measured = []
    for i, t in enumerate(terms, 1):
        ms, hits = measure(args.base, t)
        if ms is None:
            print(f"  [{i:3}/{len(terms)}] {t:<14} errore")
            continue
        mark = "  <--" if args.lo <= ms <= args.hi else ""
        print(f"  [{i:3}/{len(terms)}] {t:<14} {ms:8.1f} ms  {hits:2} hit{mark}")
        measured.append((t, ms, hits))

    inband = [m for m in measured if args.lo <= m[1] <= args.hi]
    inband.sort(key=lambda x: x[1])

    print(f"\n{'='*60}")
    print(f"termini misurati:     {len(measured)}")
    print(f"nella banda {args.lo:.0f}-{args.hi:.0f} ms: {len(inband)}")

    if len(inband) < args.want:
        print(f"\nSOLO {len(inband)} termini nella banda, ne servono {args.want}.")
        print("Allarga la banda, oppure cambia il costo dell'endpoint:")
        allms = sorted(m[1] for m in measured)
        if allms:
            q = statistics.quantiles(allms, n=10)
            print(f"  distribuzione: min={allms[0]:.0f}  d1={q[0]:.0f}  "
                  f"mediana={statistics.median(allms):.0f}  "
                  f"d9={q[-1]:.0f}  max={allms[-1]:.0f} ms")
        sys.exit(1)

    # Selezione uniforme lungo la banda, non i primi N: cosi' il campione
    # copre l'intervallo invece di addensarsi al suo estremo inferiore.
    step = len(inband) / args.want
    chosen = [inband[int(i * step)] for i in range(args.want)]

    costs = [c[1] for c in chosen]
    print(f"\nselezionati {len(chosen)} termini")
    print(f"  costo:  min={min(costs):.1f}  mediana={statistics.median(costs):.1f}  "
          f"max={max(costs):.1f} ms")
    print(f"  rapporto max/min: {max(costs)/min(costs):.2f}x")
    print(f"  W medio: {statistics.mean(costs):.1f} ms")

    n_threads = 16
    lam = n_threads / (statistics.mean(costs) / 1000)
    print(f"\n  Con {n_threads} thread, il pool satura a ~{lam:.0f} req/s "
          f"all'origine.")

    with out.open("w", encoding="utf-8") as f:
        f.write("# Termini di ricerca dell'esperimento — generato da "
                "tools/pick_terms.py\n")
        f.write(f"# banda: {args.lo:.0f}-{args.hi:.0f} ms  "
                f"corpus: vedi harness/.env\n")
        f.write(f"# generato: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        f.write("# formato: termine <tab> costo_mediano_ms <tab> risultati\n")
        for t, ms, hits in chosen:
            f.write(f"{t}\t{ms:.1f}\t{hits}\n")

    print(f"\nscritto: {out}")


if __name__ == "__main__":
    main()
