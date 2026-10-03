#!/usr/bin/env bash
#
# sweep.sh - Sweep over the traffic composition at constant volume.
#
# THE EXPERIMENT
#
# Only independent variable: alpha, the fraction of agentic traffic.
# The total rate lambda stays CONSTANT. If the volume grew with
# alpha, any knee would only show that more load saturates
# a system — a result known since 1961.
#
# Model prediction (measured parameters, cache 128m):
#   h_H = 0.830   h_A = 0.493   C = 74 req/s   r = 2.98
#   lambda_origin(alpha) = lambda * 0.170 * (1 + 1.98*alpha)
#   predicted knee at alpha = 0.35, starting from u_0 = 0.60
#
# KNEE — pre-registered definition (docs/decisions.md §15)
#   K = inf{ alpha : p99(alpha) > 10 * p99(0) }
#
# RANDOMISED ORDER
#
# The points are not run in increasing order of alpha. Over a six-hour
# campaign the machine drifts — temperature, fragmentation, kernel
# state — and with a monotonic order the drift would be indistinguishable
# from the effect of alpha. Randomisation turns it into distributed
# noise. The seed is fixed, so the order is reproducible.
#
# RESUMPTION
#
# Every completed measurement is written to CSV immediately. By rerunning the
# script with the same OUT, the points already present are skipped: an
# interruption at five hours does not cost five hours.
#
# Usage:
#   DRY=1 ./load/sweep.sh          quick test of the logic (~15 min)
#   ./load/sweep.sh                full campaign (~6.5 h)
#   OUT=results/sweep-XXX ./load/sweep.sh    resumes a campaign
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

LAMBDA="${LAMBDA:-260}"
ALPHAS="${ALPHAS:-0.00 0.05 0.10 0.15 0.20 0.25 0.30 0.35 0.40 0.45 0.50}"
REPS="${REPS:-5}"
REPS_NEAR="${REPS_NEAR:-10}"          # repetitions at the points near the knee
NEAR="${NEAR:-0.30 0.35 0.40}"
WARMUP="${WARMUP:-180}"
MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"
ENDPOINT="${ENDPOINT:-chapter}"

if [[ "${DRY:-0}" == "1" ]]; then
    ALPHAS="0.00 0.25 0.50"; REPS=1; REPS_NEAR=1; NEAR=""
    WARMUP=30; MEASURE=30; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/sweep-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/sweep.log"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

# Grafana annotation: vertical lines on the charts, indispensable for
# rereading an overnight campaign without counting minutes by hand.
annotate() {
    curl -s -X POST http://localhost:3000/api/annotations \
        -H 'Content-Type: application/json' -u "admin:$(grep -oP '^GRAFANA_ADMIN_PASSWORD=\K.*' .env 2>/dev/null)" \
        -d "{\"time\":$(date +%s)000,\"tags\":[\"undertow\",\"sweep\"],\"text\":\"$1\"}" \
        >/dev/null 2>&1 || true
}

# --- preliminary checks ---------------------------------------------------
for svc in varnish app db victoriametrics; do
    docker compose ps --status running --format '{{.Service}}' | grep -qx "$svc" || {
        echo "ERROR: service $svc is not running. docker compose up -d" >&2; exit 1; }
done
[[ -f "$HARNESS/.env" ]] || { echo "ERROR: .env missing" >&2; exit 1; }

if [[ ! -f "$CSV" ]]; then
    echo "alpha,rep,lambda,scheduled,completed,dropped,failed,timeout,p50,p95,p99,p999,max,hit_h,miss_h,hit_a,miss_a,inflight,app_cpu,db_cpu,ts" > "$CSV"
fi

{
  echo "SWEEP — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "lambda=$LAMBDA endpoint=$ENDPOINT warmup=${WARMUP}s measure=${MEASURE}s seed=$SEED"
  grep -E '^(THREADS|BACKLOG|DB_POOL|VARNISH_SIZE|CPUSET_)' .env
} >> "$LOG"

# --- building the job list, then shuffled ---------------------------------
jobs=()
for a in $ALPHAS; do
    n=$REPS
    for near in $NEAR; do [[ "$a" == "$near" ]] && n=$REPS_NEAR; done
    for r in $(seq 1 "$n"); do jobs+=("$a:$r"); done
done
mapfile -t jobs < <(printf '%s\n' "${jobs[@]}" | shuf --random-source=<(yes "$SEED"))

total=${#jobs[@]}
done_n=$(( $(wc -l < "$CSV") - 1 ))
log "$total measurements to run, $done_n already present"
log "estimated duration: $(( total * (WARMUP+MEASURE+DRAIN+20) / 60 )) minutes"

# --- main loop ------------------------------------------------------------
i=0
for job in "${jobs[@]}"; do
    a="${job%:*}"; rep="${job#*:}"
    i=$((i+1))

    if grep -q "^$a,$rep," "$CSV" 2>/dev/null; then
        printf '  [%3d/%3d] alpha=%s rep=%s  already done\n' "$i" "$total" "$a" "$rep"
        continue
    fi

    printf '  [%3d/%3d] alpha=%s rep=%s ... ' "$i" "$total" "$a" "$rep"
    tag="a${a}-r${rep}"

    # Cold cache at every point: without it, the eviction history of the
    # previous point contaminates the next, and the points run later
    # would start with an advantage.
    docker compose restart varnish >/dev/null 2>&1
    sleep 8

    annotate "warmup alpha=$a rep=$rep"
    docker compose --profile load run --rm -T \
        -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${WARMUP}s" -e SEED="$SEED" \
        -e ENDPOINT="$ENDPOINT" -e OUTFILE="warm-$tag" \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-warm-$tag.log" 2>&1
    rm -f "$HARNESS/results/warm-$tag.json"

    annotate "MEASURE alpha=$a rep=$rep"
    docker compose --profile load run --rm -T \
        -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${MEASURE}s" -e SEED="$SEED" \
        -e ENDPOINT="$ENDPOINT" -e OUTFILE="m-$tag" \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-$tag.log" 2>&1 &
    kp=$!

    # Sampling of the occupancy during the measurement
    sleep 20
    inf=0; ac=0; dc=0; ns=0
    while kill -0 $kp 2>/dev/null && [[ $ns -lt 40 ]]; do
        v=$(vmq 'ut_requests_inflight')
        read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
            | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
        inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
        ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
        dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
        ns=$((ns+1)); sleep 3
    done
    wait $kp 2>/dev/null
    inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

    f="$HARNESS/results/m-$tag.json"
    if [[ -f "$f" ]]; then
        mv "$f" "$OUT/"; f="$OUT/m-$tag.json"
        # Complete failure accounting: a p99 of 2 seconds with 30% of
        # requests lost tells a different story from a p99 of 2
        # seconds with all requests served. Latency alone,
        # near the collapse, is misleading.
        read -r sched compl drop fail p50 p95 p99 p999 pmax hh mh ha ma <<<"$(jq -r '
          [ ((.metrics.iterations.values.count // 0) + (.metrics.dropped_iterations.values.count // 0)),
            (.metrics.http_reqs.values.count // 0),
            (.metrics.dropped_iterations.values.count // 0),
            ((.metrics.http_req_failed.values.rate // 0)*10000|round/10000),
            ((.metrics.http_req_duration.values.med // 0)*10|round/10),
            ((.metrics.http_req_duration.values["p(95)"] // 0)*10|round/10),
            ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
            ((.metrics.http_req_duration.values["p(99.9)"] // 0)*10|round/10),
            ((.metrics.http_req_duration.values.max // 0)*10|round/10),
            (.metrics.ut_hit_zipf.values.count // 0),
            (.metrics.ut_miss_zipf.values.count // 0),
            (.metrics.ut_hit_traversal.values.count // 0),
            (.metrics.ut_miss_traversal.values.count // 0)
          ] | @tsv' "$f")"
        to=$(awk -v c="$compl" -v s="$sched" 'BEGIN{printf "%.4f", (s>0)?(s-c)/s:0}')
        echo "$a,$rep,$LAMBDA,$sched,$compl,$drop,$fail,$to,$p50,$p95,$p99,$p999,$pmax,$hh,$mh,$ha,$ma,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
        printf 'p99=%s ms  inflight=%s  drop=%s\n' "$p99" "$inf" "$drop"
    else
        echo "$a,$rep,$LAMBDA,,,,,,,,,,,,,,,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
        echo "FAILED — see $OUT/k6-$tag.log"
    fi

    sleep "$DRAIN"
done

# --- summary --------------------------------------------------------------
log "campaign completed"
{
  echo
  echo "================================================================"
  echo "SUMMARY — median per alpha"
  echo "================================================================"
  printf '%-7s %5s %10s %10s %10s %9s %9s\n' alpha n 'p99 ms' 'p95 ms' 'hit tot' inflight 'lost%'
  awk -F, 'NR>1 && $11!="" {
      a=$1; n[a]++; p99[a,n[a]]=$11; p95[a,n[a]]=$10
      h[a]+=$14+$16; m[a]+=$15+$17; inf[a]+=$18; to[a]+=$8
  }
  END{
    for (a in n) {
      c=n[a]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) if(p99[a,j]+0<p99[a,i]+0){t=p99[a,i];p99[a,i]=p99[a,j];p99[a,j]=t}
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) if(p95[a,j]+0<p95[a,i]+0){t=p95[a,i];p95[a,i]=p95[a,j];p95[a,j]=t}
      med99 = (c%2) ? p99[a,(c+1)/2] : (p99[a,c/2]+p99[a,c/2+1])/2
      med95 = (c%2) ? p95[a,(c+1)/2] : (p95[a,c/2]+p95[a,c/2+1])/2
      hr = (h[a]+m[a]>0) ? h[a]/(h[a]+m[a]) : 0
      printf "%-7s %5d %10.1f %10.1f %10.3f %9.2f %8.2f%%\n", a, c, med99, med95, hr, inf[a]/c, 100*to[a]/c
    }
  }' "$CSV" | sort -n
  echo
  echo "Knee: first alpha with median p99 beyond 10x the value at alpha=0"
  echo "(pre-registered definition, docs/decisions.md §15)"
  echo
  echo "Raw data: $CSV"
} | tee -a "$LOG"