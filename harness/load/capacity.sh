#!/usr/bin/env bash
#
# capacity.sh - Quanti oggetti tiene davvero la cache.
#
# PERCHE' ESISTE
#   Ho derivato "681 oggetti" dividendo 128 MB per 192,4 KB. Ma 192,4 KB e'
#   il LAVORO A POSTGRESQL per richiesta misurato da classcost.py (corpo del
#   capitolo + righe di indice + byte dei capitoli correlati), non la
#   dimensione dell'oggetto HTTP che Varnish memorizza. Se l'oggetto medio
#   fosse ~25,8 KB (438 MB di corpus / 16 954 oggetti) la capienza sarebbe
#   ~4 955 oggetti, sette volte la mia stima, e l'insieme di lavoro agentico
#   passerebbe da "a cavallo del confine" (1,49x) a "ben dentro" (0,21x).
#
#   Non si stima. Varnish lo sa: n_object e i byte occupati.
#
# NON LANCIA NESSUNA CAMPAGNA. Dura ~4 minuti.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # docker-compose.yml sta in harness/
WARM="${WARM:-180}"; RATE="${RATE:-200}"; N_CORPUS="${N_CORPUS:-16954}"

echo "=== 1. riempimento della cache: traversata uniforme ${WARM}s a ${RATE} req/s"
docker compose restart varnish >/dev/null 2>&1; sleep 3
docker compose --profile load run --rm -T \
  -e ALPHA=1 -e BETA=0 -e RATE="$RATE" -e DURATION="${WARM}s" \
  -e TARGET=http://varnish:80 -e OUTFILE=cap-warm \
  k6 run --quiet /scripts/workload.js </dev/null >/dev/null 2>&1
rm -f results/cap-warm.json

echo "=== 2. stato della cache"
docker compose exec -T varnish varnishstat -1 > /tmp/vstat.txt 2>/dev/null \
  || { echo "varnishstat non raggiungibile"; exit 1; }
grep -E 'n_object|g_bytes|g_space|cache_hit|cache_miss|n_lru_nuked' /tmp/vstat.txt

echo
echo "=== 3. capienza effettiva"
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
    sys.exit("n_object assente: guarda /tmp/vstat.txt e mandamelo")
tot = (used or 0) + (free or 0)
print(f"  oggetti in cache      : {nobj:,}")
if used:
    print(f"  byte occupati         : {used/1048576:.1f} MB   (chiave {kb})")
    print(f"  byte liberi           : {(free or 0)/1048576:.1f} MB")
    print(f"  dimensione totale     : {tot/1048576:.1f} MB")
    print(f"  OGGETTO MEDIO         : {used/nobj/1024:.1f} KB")
    cap = tot/(used/nobj) if used else nobj
else:
    cap = nobj
print(f"  CAPIENZA STIMATA      : {cap:,.0f} oggetti = {100*cap/N:.1f}% del corpus di {N:,}")
if free is not None and free > 0.05*tot:
    print("  ATTENZIONE: la cache non e' piena, la capienza e' sottostimata."
          "  Rilancia con WARM=400.")
print()
print("=== 4. valori di AGENT_SCOPE che collocano l'insieme di lavoro agentico")
print("    (insieme nominale = scope x corpus x 3 capitoli contigui;")
print("     con Zipf(0,6) l'insieme efficace e' circa un terzo del nominale)")
print()
print(f"  {'obiettivo':>12s}  {'scope':>8s}  {'basi':>7s}  {'ogg. nominali':>14s}  {'x capienza':>11s}")
for tgt in (0.1, 0.3, 1.0, 3.0, 10.0):
    objs = tgt*cap; bases = objs/3; scope = bases/N
    print(f"  {tgt:10.1f}x  {scope:8.4f}  {bases:7.0f}  {objs:14.0f}  {objs/cap:11.2f}")
print()
print(f"  scope attuale 0.0200 -> {0.02*N:.0f} basi, {0.02*N*3:.0f} oggetti nominali, "
      f"{0.02*N*3/cap:.2f}x la capienza")
PY
echo
echo "Mandami tutto questo output. Non lanciare lo sweep prima."