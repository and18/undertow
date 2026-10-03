#!/usr/bin/env bash
#
# calibrate.sh - Harness calibration, unattended.
#
# Answers a single question: is the load I/O-BOUND?
#
# A thread is busy while it is BLOCKED, not while it computes. If the
# work sits in Postgres, threads pile up waiting and the application CPU
# stays low: then the pool can saturate and it is the binding resource,
# which is the premise of the whole experiment.
# If instead the CPU rises and the threads stay empty, the constraint is
# Python's GIL and the pool will never fill up.
#
# It also measures per-request costs on a COLD CACHE. Measuring them on a
# warm cache returns Varnish's latency, not the application's: a mistake
# already made once.
#
# Usage:
#   ./load/calibrate.sh
#   RATES="50 100 200 400" DURATION=45s ./load/calibrate.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

RATES="${RATES:-50 100 200 400 800}"
DURATION="${DURATION:-60s}"
GAP="${GAP:-15}"
SAMPLES="${SAMPLES:-20}"          # occupancy samples per step

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HARNESS/results/calibrate-$STAMP"
REPORT="$OUT/report.txt"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

THREADS_CFG=$(grep -E '^THREADS=' .env | cut -d= -f2 | tr -d ' ')

{
  echo "CALIBRATION — $(date -Is)"
  echo "================================================================"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)  nproc=$(nproc)"
  grep -E '^(CPUSET_|THREADS|BACKLOG|DB_POOL|VARNISH_SIZE)' .env | sed 's/^/  /'
  echo
} > "$REPORT"

# --- 1. per-request costs on a cold cache --------------------------------
log "emptying the cache"
docker compose restart varnish >/dev/null 2>&1
sleep 6

log "measuring the cold-cache costs"
{
  echo "----------------------------------------------------------------"
  echo "COST PER REQUEST (cold cache, one URL at a time)"
  echo "----------------------------------------------------------------"
} >> "$REPORT"

books=$(curl -s localhost:8080/library | jq -r '.[] | "\(.id) \(.n_chapters)"' | head -40)

ch_times=""
i=0
while read -r id nch; do
    [[ -z "$id" ]] && continue
    n=$(( (RANDOM % nch) + 1 ))
    t=$(curl -s -o /dev/null -w '%{time_total}' "localhost:8080/book/$id/ch/$n")
    ch_times="$ch_times $t"
    i=$((i+1)); [[ $i -ge 25 ]] && break
done <<< "$books"

srch_times=""
for w in $(awk '!/^#/{print $1}' profiles/search-terms.txt | head -12); do
    t=$(curl -s -o /dev/null -w '%{time_total}' "localhost:8080/search?q=$w")
    srch_times="$srch_times $t"
done

stat() {  # median and range in ms
    tr ' ' '\n' <<< "$1" | grep -v '^$' | sort -g | awk '
      {v[NR]=$1*1000}
      END{ if(NR==0){print "n/a"; exit}
           m = (NR%2) ? v[(NR+1)/2] : (v[NR/2]+v[NR/2+1])/2
           printf "median %.1f ms   min %.1f   max %.1f   n=%d", m, v[1], v[NR], NR }'
}

CH_MED=$(tr ' ' '\n' <<< "$ch_times" | grep -v '^$' | sort -g | awk '{v[NR]=$1*1000} END{print (NR%2)?v[(NR+1)/2]:(v[NR/2]+v[NR/2+1])/2}')
SR_MED=$(tr ' ' '\n' <<< "$srch_times" | grep -v '^$' | sort -g | awk '{v[NR]=$1*1000} END{print (NR%2)?v[(NR+1)/2]:(v[NR/2]+v[NR/2+1])/2}')

{
  printf '  chapter   %s\n' "$(stat "$ch_times")"
  printf '  search    %s\n' "$(stat "$srch_times")"
  echo
  echo "  Little's law: to saturate N threads at lambda req/s you need"
  echo "  W = N/lambda. With THREADS=$THREADS_CFG:"
  awk -v c="$CH_MED" -v s="$SR_MED" -v n="$THREADS_CFG" 'BEGIN{
    printf "    chapter (W=%.0f ms): the pool saturates at ~%.0f req/s at the origin\n", c, n/(c/1000)
    printf "    search  (W=%.0f ms): the pool saturates at ~%.0f req/s at the origin\n", s, n/(s/1000)
  }'
  echo
} >> "$REPORT"

# --- 2. I/O-bound check over a range of rates ----------------------------
for endpoint in chapter search; do
  log "verifica I/O-bound: endpoint $endpoint"
  {
    echo "----------------------------------------------------------------"
    echo "ENDPOINT $endpoint"
    echo "----------------------------------------------------------------"
    printf '%-7s %9s %8s %9s %9s %8s %9s %8s\n' \
           rate inflight 'util%' 'app CPU%' 'db CPU%' 'db conn' 'p99 ms' 'hit%'
  } >> "$REPORT"

  for rate in $RATES; do
    printf '    %s @ %s ... ' "$endpoint" "$rate"
    tag="$endpoint-$rate"

    docker compose --profile load run --rm -T \
      -e ENDPOINT="$endpoint" -e RATE="$rate" -e DURATION="$DURATION" \
      -e OUTFILE="p-$tag" \
      k6 run --quiet /scripts/probe-origin.js < /dev/null > "$OUT/k6-$tag.log" 2>&1 &
    k6pid=$!

    sleep 20   # steady state before sampling

    inf_sum=0; cpu_max=0; dbcpu_max=0; dbc_max=0
    for s in $(seq 1 $SAMPLES); do
      inf=$(vmq 'ut_requests_inflight')
      dbc=$(vmq 'ut_db_pool_busy')
      read -r acpu dcpu <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' \
              | awk '/ut-app /{gsub(/%/,"",$2); a=$2} /ut-db /{gsub(/%/,"",$2); d=$2} END{print a+0, d+0}')"
      inf_sum=$(awk -v a="$inf_sum" -v b="$inf" 'BEGIN{print a+b}')
      cpu_max=$(awk -v a="$cpu_max" -v b="$acpu" 'BEGIN{print (b>a)?b:a}')
      dbcpu_max=$(awk -v a="$dbcpu_max" -v b="$dcpu" 'BEGIN{print (b>a)?b:a}')
      dbc_max=$(awk -v a="$dbc_max" -v b="$dbc" 'BEGIN{print (b>a)?b:a}')
      sleep 1
    done
    inf_avg=$(awk -v s="$inf_sum" -v n="$SAMPLES" 'BEGIN{printf "%.1f", s/n}')
    util=$(awk -v i="$inf_avg" -v n="$THREADS_CFG" 'BEGIN{printf "%.0f", 100*i/n}')

    wait $k6pid 2>/dev/null

    f="$HARNESS/results/p-$tag.json"
    if [[ -f "$f" ]]; then
      mv "$f" "$OUT/"; f="$OUT/p-$tag.json"
      read -r p99 h m <<<"$(jq -r '[
          ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
          (.metrics.ut_cache_hit.values.count // 0),
          (.metrics.ut_cache_miss.values.count // 0)] | @tsv' "$f")"
      hitpc=$(awk -v h="$h" -v m="$m" 'BEGIN{t=h+m; printf "%.0f", (t>0)?100*h/t:0}')
    else
      p99="?"; hitpc="?"
    fi

    printf '%-7s %9s %8s %9s %9s %8s %9s %8s\n' \
           "$rate" "$inf_avg" "$util" "$cpu_max" "$dbcpu_max" "$dbc_max" "$p99" "$hitpc" >> "$REPORT"
    echo "inflight=$inf_avg (${util}%) appcpu=$cpu_max"
    sleep "$GAP"
  done
  echo >> "$REPORT"
done

# --- 3. verdetto ----------------------------------------------------------
{
  echo "================================================================"
  echo "HOW TO READ"
  echo "================================================================"
  echo
  echo "  inflight   busy threads on average. This is the central metric."
  echo "  util%      inflight / THREADS. The knee is to be sought where"
  echo "             this approaches 100%."
  echo "  app CPU%   100% = one core. If it stops around 80-100 while"
  echo "             inflight stays low, the constraint is the GIL and NOT the"
  echo "             pool: the load is not I/O-bound and the sweeps cannot"
  echo "             work this way."
  echo "  db CPU%    if high while app CPU is low, the work sits in the"
  echo "             database: this is the desired condition."
  echo "  hit%       percentage served from the cache. With random chapters"
  echo "             on a small cache it must be low."
  echo
  echo "CONDITION TO CHECK"
  echo
  echo "  At an attainable rate, 'util%' must exceed 70% while"
  echo "  'app CPU%' stays below 60%. If this happens, the harness is"
  echo "  ready: fix the operating rate just above that point and the"
  echo "  sweeps on traffic composition can start."
  echo
  echo "  If it does not happen at any rate, the next lever is to reduce"
  echo "  Postgres shared_buffers, to force it to read from disk"
  echo "  and produce real blocking instead of in-memory work."
  echo
  echo "Details in: $OUT"
} >> "$REPORT"

echo; cat "$REPORT"; echo
log "report: $REPORT"