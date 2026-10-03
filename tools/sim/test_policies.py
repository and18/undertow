#!/usr/bin/env python3
"""
test_policies.py — gate K of phase 2 (docs/PREREG-simulatore-fase2.md, «Collaudo prima
dell'uso», with amendment 1). Committed before any trace of phase 2.

1. Small traces, objects of size 1 (H = 0), capacity 3 or 4: the expected hit/miss sequence
   is derived by hand (comment next to each step) and written here before running.
   For W-TinyLFU with capacity 4 the window (1% = 0 bytes) is empty: every object skips it and
   is immediately a candidate (Algorithm 1, lines 6-7); the admission is tested.
2. Invariants on random traces of 10,000 requests with the real sizes
   (data/derived/chapter_sizes.csv).

Usage:  python3 tools/sim/test_policies.py      (exits with code 1 if a test fails)
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
    print(f"  {'PASSA' if ok else 'NON PASSA'}  {name}: expected {want}  obtained {got}")
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
    print("== 1. small traces, sequences derived by hand")

    # LRU, capacity 3. A B C | A hit (B C A) | D evicts B | B evicts C | E evicts A | A evicts D
    c = LRU(unit("ABCDE"), 0, 3)
    check("LRU canonical", run(c, "ABCADBEA"), "MMMHMMMM")

    # SIEVE, capacity 3. [C B A]; A hit (A.v=1). D: hand from the tail: A visited -> A.v=0,
    # moves on to B; B not visited -> evicted, hand on C. [D C A]. B: C evicted, hand
    # on D. [B D A]. E: D evicted, hand on B. [E B A]. A hit (A.v=1). B hit, E hit.
    # F: B visited -> 0, E visited -> 0, head passed -> back to the tail: A visited -> 0,
    # B not visited -> evicted, hand on E. [F E A]. G: E evicted. [G F A]. A hit.
    c = SIEVE(unit("ABCDEFG"), 0, 3)
    check("SIEVE hand and return to the tail", run(c, "ABCADBEABEFGA"), "MMMHMMMHHHMMH")

    # S3-FIFO, capacity 4 (S >= 0.4 -> evict from S if S is not empty).
    # A A A: fA=2. B C D: S=[A B C D]. E: cache full, evict from S: A (f=2) -> M with f=0;
    # B (f=0) -> G; S=[C D], then E -> S=[C D E]. An object seen once (B) leaves without M.
    c = S3FIFO(unit("ABCDE"), 0, 4)
    check("S3-FIFO seen once -> G, f>1 -> M", run(c, "AAABCDE"), "MHHMMMM")
    check("S3-FIFO state: M=[A] S=[C D E] G=[B]",
          (list(c.M), list(c.S), list(c.G)), (["A"], ["C", "D", "E"], ["B"]))

    # A A A B B B: fA=fB=2, S=[A B]. C D: S=[A B C D]. E: A -> M, B -> M, C -> G; S=[D E].
    # F: D -> G (G=[C D]); S=[E F]. D (in G): E -> G, G beyond |M|=2 -> C leaves: G=[D E];
    # D returns from the ghost directly into M: M=[A B D], G=[E], S=[F].
    # A hit (fA=1). E (in G): F -> G=[E F]; E in M: M=[A B D E], G=[F], S=[].
    # X: S empty -> evict from M: A (f=1) reinserted at the head with f=0; B (f=0) evicted;
    # S=[X]. A hit (survived), B miss.
    c = S3FIFO(unit("ABCDEFX"), 0, 4)
    got = run(c, "AAABBBCDEFD")
    check("S3-FIFO return from the ghost into M", got, "MHHMHHMMMMM")
    check("S3-FIFO state: M=[A B D] S=[F] G=[E]",
          (list(c.M), list(c.S), list(c.G)), (["A", "B", "D"], ["F"], ["E"]))
    check("S3-FIFO reinsertion in M with freq-1", run(c, "AEXAB"), "HMMHM")

    # W-TinyLFU, capacity 4: window 0, main 4, protected 3.
    # A A: A on probation then protected. B B, C C: protected [A B C]. D D: protected [A B C D] > 3 ->
    # A goes back on probation. E (estimate 1) against victim A (estimate 2): rejected; A promoted ->
    # protected [B C D A] -> B on probation. E (estimate 2) against B (estimate 2): 2 >= 2, admitted, B leaves.
    # B (estimate 3) against E (estimate 2): admitted, E leaves.
    c = WTinyLFU(unit("ABCDE"), 0, 4)
    got = run(c, "AABBCCDDE")
    check("W-TinyLFU rejected against a more frequent victim", got, "MHMHMHMHM")
    check("W-TinyLFU after the rejection: E absent, A in protected",
          (present(c, "E"), "A" in c.prot, list(c.prob)), (False, True, ["B"]))
    check("W-TinyLFU tie admitted (>=), then B comes back", run(c, "EB"), "MM")
    check("W-TinyLFU state: probation=[B]", list(c.prob), ["B"])

    # Scan: protected [A B C]; X1..X6 seen once replace each other in probation; A B C hit.
    c = WTinyLFU(unit(["A", "B", "C", "X1", "X2", "X3", "X4", "X5", "X6"]), 0, 4)
    got = run(c, ["A", "A", "B", "B", "C", "C", "X1", "X2", "X3", "X4", "X5", "X6", "A", "B", "C"])
    check("W-TinyLFU scan does not move the protected", got, "MHMHMH" + "M" * 6 + "HHH")

    # Aggregate victims: A(1) protected, B(1) C(1) on probation; Z (size 3, estimate 1) must
    # evict B and C (sum of estimates 2): rejected, B and C promoted (protected [A B C]).
    # Z again (estimate 2): victims A (2) and B (1), sum 3 > 2: rejected.
    c = WTinyLFU(unit("ABC", {"Z": 3}), 0, 4)
    check("W-TinyLFU aggregate victims (AV)", run(c, "AABCZZ"), "MHMMMM")
    check("W-TinyLFU state: Z absent, protected [C A B]",
          (present(c, "Z"), list(c.prot)), (False, ["C", "A", "B"]))


def invariants():
    print("\n== 2. invariants on random traces (10,000 requests, real sizes)")
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
            print(f"  {'PASSA' if ok else 'NON PASSA'}  {name} capacity {cap}: violations {bad}, "
                  f"bytes counted {real} = occupied {c.used}")
            if not ok:
                FAIL.append(f"invariants {name} {cap}")
    total = sum(s + 512 for s in sizes)
    distinct = len(set(keys))
    for name, cls in POLICIES.items():
        c = cls(sizes, 512, total)
        miss = sum(not c.get(k, i / 100) for i, k in enumerate(keys))
        ok = miss == distinct
        print(f"  {'PASSA' if ok else 'NON PASSA'}  {name} capacity = whole corpus: "
              f"miss {miss}, compulsory {distinct}")
        if not ok:
            FAIL.append(f"compulsory misses {name}")


if __name__ == "__main__":
    small()
    invariants()
    print(f"\nCANCELLO K: {'PASSA' if not FAIL else 'NON PASSA: ' + ', '.join(FAIL)}")
    sys.exit(1 if FAIL else 0)
