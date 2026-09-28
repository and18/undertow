#!/usr/bin/env python3
"""
test_policies.py — cancello K della fase 2 (docs/PREREG-simulatore-fase2.md, «Collaudo prima
dell'uso», con l'emendamento 1). Committato prima di qualunque traccia della fase 2.

1. Tracce piccole, oggetti di dimensione 1 (H = 0), capienza 3 o 4: la sequenza hit/miss
   attesa e' derivata a mano (commento accanto a ogni passo) e scritta qui prima di eseguire.
   Per W-TinyLFU con capienza 4 la finestra (1% = 0 byte) e' vuota: ogni oggetto la salta ed
   e' subito candidato (Algoritmo 1, righe 6-7); si collauda l'ammissione.
2. Invarianti su tracce casuali di 10 000 richieste con le dimensioni reali
   (data/derived/chapter_sizes.csv).

Uso:  python3 tools/sim/test_policies.py      (esce con codice 1 se un test non passa)
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from policies import LRU, POLICIES, S3FIFO, SIEVE, WTinyLFU  # noqa: E402

FAIL = []


def run(cache, trace):
    return "".join("H" if cache.get(k, 0.0) else "M" for k in trace)


def check(name, got, want):
    ok = got == want
    print(f"  {'PASSA' if ok else 'NON PASSA'}  {name}: atteso {want}  ottenuto {got}")
    if not ok:
        FAIL.append(name)


def unit(keys, extra=None):
    sizes = {k: 1 for k in keys}
    sizes.update(extra or {})
    return sizes


def present(cache, k):
    return k in cache.d if isinstance(cache, LRU) else k in cache


def contents(cache):
    if isinstance(cache, LRU):
        return list(cache.d)
    if isinstance(cache, SIEVE):
        return list(cache.nodes)
    if isinstance(cache, S3FIFO):
        return [*cache.S, *cache.M]
    return [*cache.win, *cache.prob, *cache.prot]


def small():
    print("== 1. tracce piccole, sequenze derivate a mano")

    # LRU, capienza 3. A B C | A hit (B C A) | D sfratta B | B sfratta C | E sfratta A | A sfratta D
    c = LRU(unit("ABCDE"), 0, 3)
    check("LRU canonica", run(c, "ABCADBEA"), "MMMHMMMM")

    # SIEVE, capienza 3. [C B A]; A hit (A.v=1). D: lancetta dalla coda: A visitato -> A.v=0,
    # avanza a B; B non visitato -> sfrattato, lancetta su C. [D C A]. B: C sfrattato, lancetta
    # su D. [B D A]. E: D sfrattato, lancetta su B. [E B A]. A hit (A.v=1). B hit, E hit.
    # F: B visitato -> 0, E visitato -> 0, testa superata -> ritorno alla coda: A visitato -> 0,
    # B non visitato -> sfrattato, lancetta su E. [F E A]. G: E sfrattato. [G F A]. A hit.
    c = SIEVE(unit("ABCDEFG"), 0, 3)
    check("SIEVE lancetta e ritorno alla coda", run(c, "ABCADBEABEFGA"), "MMMHMMMHHHMMH")

    # S3-FIFO, capienza 4 (S >= 0,4 -> si sfratta da S se S non e' vuota).
    # A A A: fA=2. B C D: S=[A B C D]. E: cache piena, sfratto da S: A (f=2) -> M con f=0;
    # B (f=0) -> G; S=[C D], poi E -> S=[C D E]. Oggetto visto una volta (B) esce senza M.
    c = S3FIFO(unit("ABCDE"), 0, 4)
    check("S3-FIFO visto una volta -> G, f>1 -> M", run(c, "AAABCDE"), "MHHMMMM")
    check("S3-FIFO stato: M=[A] S=[C D E] G=[B]",
          (list(c.M), list(c.S), list(c.G)), (["A"], ["C", "D", "E"], ["B"]))

    # A A A B B B: fA=fB=2, S=[A B]. C D: S=[A B C D]. E: A -> M, B -> M, C -> G; S=[D E].
    # F: D -> G (G=[C D]); S=[E F]. D (in G): E -> G, G oltre |M|=2 -> esce C: G=[D E];
    # D ritorna dal fantasma direttamente in M: M=[A B D], G=[E], S=[F].
    # A hit (fA=1). E (in G): F -> G=[E F]; E in M: M=[A B D E], G=[F], S=[].
    # X: S vuota -> sfratto da M: A (f=1) reinserito in testa con f=0; B (f=0) sfrattato;
    # S=[X]. A hit (sopravvissuto), B miss.
    c = S3FIFO(unit("ABCDEFX"), 0, 4)
    got = run(c, "AAABBBCDEFD")
    check("S3-FIFO ritorno dal fantasma in M", got, "MHHMHHMMMMM")
    check("S3-FIFO stato: M=[A B D] S=[F] G=[E]",
          (list(c.M), list(c.S), list(c.G)), (["A", "B", "D"], ["F"], ["E"]))
    check("S3-FIFO reinserimento in M con freq-1", run(c, "AEXAB"), "HMMHM")

    # W-TinyLFU, capienza 4: finestra 0, principale 4, protetta 3.
    # A A: A in prova poi protetta. B B, C C: protetta [A B C]. D D: protetta [A B C D] > 3 ->
    # A torna in prova. E (stima 1) contro vittima A (stima 2): respinto; A promosso ->
    # protetta [B C D A] -> B in prova. E (stima 2) contro B (stima 2): 2 >= 2, ammesso, B esce.
    # B (stima 3) contro E (stima 2): ammesso, E esce.
    c = WTinyLFU(unit("ABCDE"), 0, 4)
    got = run(c, "AABBCCDDE")
    check("W-TinyLFU respinto contro vittima piu' frequente", got, "MHMHMHMHM")
    check("W-TinyLFU dopo il rifiuto: E assente, A in protetta",
          (present(c, "E"), "A" in c.prot, list(c.prob)), (False, True, ["B"]))
    check("W-TinyLFU pareggio ammesso (>=), poi B rientra", run(c, "EB"), "MM")
    check("W-TinyLFU stato: prova=[B]", list(c.prob), ["B"])

    # Scansione: protetta [A B C]; X1..X6 visti una volta si sostituiscono in prova; A B C hit.
    c = WTinyLFU(unit(["A", "B", "C", "X1", "X2", "X3", "X4", "X5", "X6"]), 0, 4)
    got = run(c, ["A", "A", "B", "B", "C", "C", "X1", "X2", "X3", "X4", "X5", "X6", "A", "B", "C"])
    check("W-TinyLFU scansione non sposta la protetta", got, "MHMHMH" + "M" * 6 + "HHH")

    # Vittime aggregate: A(1) protetta, B(1) C(1) in prova; Z (dimensione 3, stima 1) deve
    # sfrattare B e C (somma stime 2): respinto, B e C promossi (protetta [A B C]).
    # Z di nuovo (stima 2): vittime A (2) e B (1), somma 3 > 2: respinto.
    c = WTinyLFU(unit("ABC", {"Z": 3}), 0, 4)
    check("W-TinyLFU vittime aggregate (AV)", run(c, "AABCZZ"), "MHMMMM")
    check("W-TinyLFU stato: Z assente, protetta [C A B]",
          (present(c, "Z"), list(c.prot)), (False, ["C", "A", "B"]))


def invariants():
    print("\n== 2. invarianti su tracce casuali (10 000 richieste, dimensioni reali)")
    import trace as tr
    import fase1
    sizes = fase1.sizes()
    n = len(sizes)
    rnd = random.Random(7)
    keys = [min(int(n ** rnd.random()), n - 1) if rnd.random() < 0.7 else rnd.randrange(n)
            for _ in range(10_000)]
    assert tr.HUMAN == 0
    for cap in (5_000_000, 134_217_728):
        for name, cls in POLICIES.items():
            c = cls(sizes, 512, cap)
            bad = 0
            for i, k in enumerate(keys):
                was = present(c, k)
                hit = c.get(k, i / 100)
                bad += hit != was
                bad += c.used > cap
            real = sum(sizes[k] + 512 for k in contents(c))
            ok = bad == 0 and real == c.used
            print(f"  {'PASSA' if ok else 'NON PASSA'}  {name} capienza {cap}: violazioni {bad}, "
                  f"byte contati {real} = occupati {c.used}")
            if not ok:
                FAIL.append(f"invarianti {name} {cap}")
    total = sum(s + 512 for s in sizes)
    distinct = len(set(keys))
    for name, cls in POLICIES.items():
        c = cls(sizes, 512, total)
        miss = sum(not c.get(k, i / 100) for i, k in enumerate(keys))
        ok = miss == distinct
        print(f"  {'PASSA' if ok else 'NON PASSA'}  {name} capienza = tutto il corpus: "
              f"miss {miss}, obbligatori {distinct}")
        if not ok:
            FAIL.append(f"miss obbligatori {name}")


if __name__ == "__main__":
    small()
    invariants()
    print(f"\nCANCELLO K: {'PASSA' if not FAIL else 'NON PASSA: ' + ', '.join(FAIL)}")
    sys.exit(1 if FAIL else 0)
