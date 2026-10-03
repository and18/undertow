#!/usr/bin/env python3
"""
pick_terms.py - Selects the search terms within a cost band.

WHY

The cost of a full-text search depends on how many chapters contain
the term: on the current corpus it goes from 83 ms for "whale" to 1330 ms for
"night", a factor of 16. A freely chosen term would make the
per-request cost an UNCONTROLLED variable of the workload — and if the
human and agentic profiles sampled terms of different cost, the
traffic composition would be confounded with the query cost.

The variance is not eliminated by rewriting the query: it is intrinsic to
full-text ranking, which has to compute ts_rank on every match.
It is controlled by selecting upstream the terms that fall in a narrow
band, measured on the corpus in use.

The result is a versioned file: anyone replicating the experiment uses
the same terms and gets the same per-request cost.

CALIBRATING THE BAND

The band must be chosen according to Little's law. For a pool of
N threads to saturate at a rate of lambda requests per second at the origin
one needs W = N / lambda. With N=16 and a desired knee around
320 req/s, W must be about 50 ms.

USAGE

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

# Candidates: common words in English-language fiction and non-fiction,
# chosen to cover a wide frequency range in the corpus.
# The list is deliberately long: the selection is made by the measurement, not the author.
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
    """Median latency of a search, in milliseconds.

    Median and not mean: a single cold execution produces a value
    much higher than the following ones and would drag the mean.
    """
    url = f"{base}/search?q={urllib.parse.quote(term)}"
    times, hits = [], 0
    for i in range(repeats + 1):          # +1 = warm-up round
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
                    help="lower end of the band, ms")
    ap.add_argument("--hi", type=float, default=70.0,
                    help="upper end of the band, ms")
    ap.add_argument("--want", type=int, default=40,
                    help="how many terms to select")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    out = Path(args.out) if args.out else repo / "harness/profiles/search-terms.txt"
    out.parent.mkdir(parents=True, exist_ok=True)

    terms = sorted(set(CANDIDATES))
    print(f"measuring {len(terms)} terms on {args.base}\n")

    measured = []
    for i, t in enumerate(terms, 1):
        ms, hits = measure(args.base, t)
        if ms is None:
            print(f"  [{i:3}/{len(terms)}] {t:<14} error")
            continue
        mark = "  <--" if args.lo <= ms <= args.hi else ""
        print(f"  [{i:3}/{len(terms)}] {t:<14} {ms:8.1f} ms  {hits:2} hit{mark}")
        measured.append((t, ms, hits))

    inband = [m for m in measured if args.lo <= m[1] <= args.hi]
    inband.sort(key=lambda x: x[1])

    print(f"\n{'='*60}")
    print(f"terms measured:     {len(measured)}")
    print(f"in the band {args.lo:.0f}-{args.hi:.0f} ms: {len(inband)}")

    if len(inband) < args.want:
        print(f"\nONLY {len(inband)} terms in the band, {args.want} needed.")
        print("Widen the band, or change the cost of the endpoint:")
        allms = sorted(m[1] for m in measured)
        if allms:
            q = statistics.quantiles(allms, n=10)
            print(f"  distribution: min={allms[0]:.0f}  d1={q[0]:.0f}  "
                  f"median={statistics.median(allms):.0f}  "
                  f"d9={q[-1]:.0f}  max={allms[-1]:.0f} ms")
        sys.exit(1)

    # Uniform selection along the band, not the first N: this way the sample
    # covers the interval instead of crowding at its lower end.
    step = len(inband) / args.want
    chosen = [inband[int(i * step)] for i in range(args.want)]

    costs = [c[1] for c in chosen]
    print(f"\nselected {len(chosen)} terms")
    print(f"  cost:  min={min(costs):.1f}  median={statistics.median(costs):.1f}  "
          f"max={max(costs):.1f} ms")
    print(f"  max/min ratio: {max(costs)/min(costs):.2f}x")
    print(f"  mean W: {statistics.mean(costs):.1f} ms")

    n_threads = 16
    lam = n_threads / (statistics.mean(costs) / 1000)
    print(f"\n  With {n_threads} threads, the pool saturates at ~{lam:.0f} req/s "
          f"at the origin.")

    with out.open("w", encoding="utf-8") as f:
        f.write("# Termini di ricerca dell'esperimento — generato da "
                "tools/pick_terms.py\n")
        f.write(f"# banda: {args.lo:.0f}-{args.hi:.0f} ms  "
                f"corpus: vedi harness/.env\n")
        f.write(f"# generato: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        f.write("# formato: termine <tab> costo_mediano_ms <tab> risultati\n")
        for t, ms, hits in chosen:
            f.write(f"{t}\t{ms:.1f}\t{hits}\n")

    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
