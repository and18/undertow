#!/usr/bin/env python3
"""
classcost.py - The three cost profiles, compared without running anything.

WHY
  All the test-bench results are expressed in "origin rps", which
  counts MISSES. A miss, however, is not a unit of work: the endpoint
  /book/<id>/ch/<n> runs four queries, and three have variable cost.
  The dominant one is ts_headline on c.body of the twelve linked chapters,
  which scans the whole text of each.

  The corpus is heavy-tailed (median 9.5 KB, mean 15.0 KB, standard
  deviation 32.4 KB, maximum 1.9 MB). The exhaustive class traverses the whole
  corpus, so its mean cost tends to the corpus mean; the
  human and agentic classes insist on ~1000 chapters chosen by a
  permutation. A single 1.9 MB chapter among a thousand shifts the mean
  by 13%.

  If the three profiles coincide, "origin rps" is a valid proxy for the
  comparisons BETWEEN classes and all the results hold. If they diverge, the
  comparative quantities (agentic against exhaustive marginal cost)
  are in the wrong units.

METHOD
  Replicates exactly permute(), permuteTrav(), zipfRank() and
  agenticIndex() of harness/load/workload.js, with the same seeds and
  multipliers, and the same index->chapter map as locate().
  The cumulative vector is taken from /library, that is from the same
  source that setup() uses in k6: no assumption on the ordering.

  For each class it generates the set of indices that class
  would request, and computes its cost profile from the real sizes
  in PostgreSQL.

  For the Zipf class the comparison is WEIGHTED by the request probability,
  because its flow is not uniform over its own set.

Usage:  python3 classcost.py [--lambda 110] [--measure 620]
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


# ---------------------------------------------------- corpus, from /library
with urllib.request.urlopen(a.app + "/library", timeout=30) as r:
    books = json.loads(r.read())
ids, cum, total = [], [], 0
for b in books:
    ids.append(b["id"])
    total += b["n_chapters"]
    cum.append(total)
print(f"corpus: {len(ids)} books, {total} chapters")


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

# ------------------------------------------------- sets per class
# exhaustive: traverses the corpus in sequence from the offset
n_trav = int(a.lam * a.alpha * a.measure)
trav = {}
for i in range(min(n_trav, total)):
    trav[permute_trav(offset + i, total)] = trav.get(permute_trav(offset + i, total), 0) + 1

# human: Zipf(1) on the rank, weighted. CDF(r)=H_r/H_N, r ~ N^u.
# The exact distribution is built instead of sampled: the
# probability of rank r is 1/(r*H_N).
H = sum(1.0 / r for r in range(1, total + 1))
zipf = {}
for r in range(1, total + 1):
    p = 1.0 / (r * H)
    if p * a.lam * (1 - a.alpha - a.beta) * a.measure < 0.5:
        break            # ranks that would not be requested even once
    zipf[permute(r - 1, total)] = p

# agentic: Zipf(0.6) on a subset, then 3 contiguous chapters
scope = max(1, int(total * AGENT_SCOPE))
agent = {}
for r in range(scope):
    p = ((r + 1) ** (1 - AGENT_SKEW) - r ** (1 - AGENT_SKEW)) / (scope ** (1 - AGENT_SKEW))
    base = permute(r, total)
    for k in range(AGENT_SESSION):
        idx = (base + k) % total
        agent[idx] = agent.get(idx, 0) + p / AGENT_SESSION

print(f"sets: exhaustive {len(trav)}, human {len(zipf)}, agentic {len(agent)} distinct chapters")

# ------------------------------------------------------ costs, from Postgres
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
print("querying PostgreSQL (16,954 rows, about a minute)...")
import subprocess
out = subprocess.run(
    ["docker", "compose", "exec", "-T", "db", "psql", "-U", "undertow", "-d", "undertow",
     "-At", "-F", "\t", "-c", SQL],
    capture_output=True, text=True, cwd=os.path.expanduser("~/undertow/harness"))
if out.returncode != 0:
    sys.exit("psql failed:\n" + out.stderr[:800])

cost = {}
for line in out.stdout.splitlines():
    p = line.split("\t")
    if len(p) < 6:
        continue
    cost[(int(p[0]), int(p[1]))] = (int(p[2]), int(p[3]), int(p[4]), int(p[5]))
print(f"loaded {len(cost)} chapters\n")


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
        vals.append(c[0] + c[2])          # bytes scanned: own + related
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


# reference: corpus mean, unweighted
allw = {i: 1.0 for i in range(total)}

rows = [("whole corpus", profile("corpus", allw)),
        ("exhaustive", profile("trav", trav)),
        ("human (Zipf)", profile("zipf", zipf)),
        ("agentic", profile("agent", agent))]

print(f"{'class':16s} {'n':>7s} {'own KB':>8s} {'toc':>6s} {'rel KB':>8s} "
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
print("SCAN KB = bytes of text that ts_headline and the chapter read")
print("traverse for each request. It is the dominant term of the cost.")
print()
ref = rows[0][1]["scan_kb"]
for name, p in rows[1:]:
    if p:
        d = 100 * (p["scan_kb"] / ref - 1)
        print(f"  {name:16s} {d:+6.1f}% relative to the corpus mean")
print()
print("CRITERION: if the three classes are within +/-10% of each other,")
print("a miss costs the same to everyone and 'origin rps' is a valid proxy")
print("for the comparisons BETWEEN classes. Beyond 20%, the comparative")
print("quantities must be re-expressed in units of work.")