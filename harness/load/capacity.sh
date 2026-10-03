#!/usr/bin/env bash
#
# capacity.sh - How many objects the cache really holds.
#
# WHY IT EXISTS
#   I derived "681 objects" by dividing 128 MB by 192.4 KB. But 192.4 KB is
#   the POSTGRESQL WORK per request measured by classcost.py (chapter body
#   + index rows + bytes of the related chapters), not the size of the
#   HTTP object that Varnish stores. If the average object were ~25.8 KB
#   (438 MB of corpus / 16,954 objects) the capacity would be ~4,955
#   objects, seven times my estimate, and the agentic working set would
#   go from "straddling the boundary" (1.49x) to "well inside" (0.21x).
#
#   We do not estimate. Varnish knows: n_object and the occupied bytes.
#
# DOES NOT LAUNCH ANY CAMPAIGN. Takes ~4 minutes.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # docker-compose.yml lives in harness/
WARM="${WARM:-180}"; RATE="${RATE:-200}"; N_CORPUS="${N_CORPUS:-16954}"

echo "=== 1. cache fill: uniform traversal ${WARM}s at ${RATE} req/s"
docker compose restart varnish >/dev/null 2>&1; sleep 3
docker compose --profile load run --rm -T \
  -e ALPHA=1 -e BETA=0 -e RATE="$RATE" -e DURATION="${WARM}s" \
  -e TARGET=http://varnish:80 -e OUTFILE=cap-warm \
  k6 run --quiet /scripts/workload.js </dev/null >/dev/null 2>&1
rm -f results/cap-warm.json

echo "=== 2. cache state"
docker compose exec -T varnish varnishstat -1 > /tmp/vstat.txt 2>/dev/null \
  || { echo "varnishstat not reachable"; exit 1; }
grep -E 'n_object|g_bytes|g_space|cache_hit|cache_miss|n_lru_nuked' /tmp/vstat.txt

echo
echo "=== 3. effective capacity"
python3 - "$N_CORPUS" <<'PY'
import re, sys
N = int(sys.argv[1])
v = {}
for line in open('/tmp/vstat.txt'):
    m = re.match(r'^(\S+)\s+(\d+)', line)
    if m: v[m.group(1)] = int(m.group(2))
def pick(suffix):
    for k in v:
        if k.endswith(suffix): return k, v[k]
    return None, None
_, nobj = pick('n_object')
kb, used = pick('g_bytes')
ks, free = pick('g_space')
if not nobj:
    sys.exit("n_object missing: look at /tmp/vstat.txt and send it to me")
tot = (used or 0) + (free or 0)
print(f"  objects in cache      : {nobj:,}")
if used:
    print(f"  bytes used            : {used/1048576:.1f} MB   (key {kb})")
    print(f"  bytes free            : {(free or 0)/1048576:.1f} MB")
    print(f"  total size            : {tot/1048576:.1f} MB")
    print(f"  AVERAGE OBJECT        : {used/nobj/1024:.1f} KB")
    cap = tot/(used/nobj) if used else nobj
else:
    cap = nobj
print(f"  ESTIMATED CAPACITY    : {cap:,.0f} objects = {100*cap/N:.1f}% of the corpus of {N:,}")
if free is not None and free > 0.05*tot:
    print("  WARNING: the cache is not full, the capacity is underestimated."
          "  Rerun with WARM=400.")
print()
print("=== 4. AGENT_SCOPE values that place the agentic working set")
print("    (nominal set = scope x corpus x 3 contiguous chapters;")
print("     with Zipf(0.6) the effective set is about a third of the nominal)")
print()
print(f"  {'target':>12s}  {'scope':>8s}  {'bases':>7s}  {'nominal objs':>14s}  {'x capacity':>11s}")
for tgt in (0.1, 0.3, 1.0, 3.0, 10.0):
    objs = tgt*cap; bases = objs/3; scope = bases/N
    print(f"  {tgt:10.1f}x  {scope:8.4f}  {bases:7.0f}  {objs:14.0f}  {objs/cap:11.2f}")
print()
print(f"  current scope 0.0200 -> {0.02*N:.0f} bases, {0.02*N*3:.0f} nominal objects, "
      f"{0.02*N*3/cap:.2f}x the capacity")
PY
echo
echo "Send me all of this output. Do not launch the sweep first."