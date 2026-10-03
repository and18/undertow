#!/usr/bin/env bash
#
# budget.sh - Does a per-class resource budget protect interactive
#             traffic without penalising batch traffic?
#
# THE QUESTION
#
# At the knee the two classes compete for the same threads. The low-locality
# class has high volume and nobody waiting; the high-locality one
# has lower volume and a person waiting. Today whoever arrives first wins,
# so the second waits behind the first.
#
# The budget limits how many low-locality requests can be in
# progress at the same time. The excess ones wait briefly and,
# if the slot does not free up, receive 503 with Retry-After: a deferral, not
# a refusal. The load is not lost, it is shifted in time — something
# a batch crawler can afford and a waiting user cannot.
#
# ASYMMETRIC PREDICTION, AND IT IS THE POINT
#
#   the interactive class recovers a lot
#   the batch class loses little
#
# because the batch class was not limited by the threads: it was limited by
# the contention it created itself. If the numbers add up, the conflict is
# apparent and there is no need to block anyone.
#
# CRITERION, FIXED BEFORE THE DATA
#
#   succeeded  p99 of the interactive class below 500 ms
#              AND completed throughput of the batch class within 20%
#              of the reference value
#
#   failed     the throughput of the batch class drops in proportion to the
#              budget. In that case the asymmetry does not exist and the thesis
#              must be abandoned.
#
# The working point is alpha = 0.20, where the median p99 is 2681 ms and
# the pool occupancy 93%: just beyond the knee, where there is
# something to recover.
#
# Usage:
#   DRY=1 ./load/budget.sh
#   ./load/budget.sh
#   ALPHA=0.25 BUDGETS="0 4 2" ./load/budget.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

LAMBDA="${LAMBDA:-260}"
ALPHA="${ALPHA:-0.20}"
# 0 = budget disabled, reference. The other values are concurrent slots
# granted to the low-locality class, out of THREADS in total.
BUDGETS="${BUDGETS:-0 6 4 3 2 1}"
# Zero wait, and it is not negotiable.
#
# The semaphore is acquired by before_request, which already runs on a
# gunicorn thread: a request that WAITS for a slot keeps that thread
# busy while it waits, so the budget adds latency without freeing
# anything for the other class — the opposite of its purpose.
#
# Measured twice with the same outcome, on x86 on 2026-08-23 and on ARM
# on 2026-08-27: monotonic worsening as the budget narrows, up to
# 2.5 times the reference. Both runs are invalid.
#
# The correct value is already in env.*, but this script rewrites .env at
# every budget value: the default here must match.
BUDGET_WAIT="${BUDGET_WAIT:-0}"
REPS="${REPS:-5}"
# 180 s is the validated warm-up for the 128m cache; the cache size
# does not vary in this experiment.
WARMUP="${WARMUP:-180}"
MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"

if [[ "${DRY:-0}" == "1" ]]; then
    BUDGETS="0 2"; REPS=1; WARMUP=60; MEASURE=45; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/budget-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/budget.log"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

restore() { sed -i 's/^BUDGET_LOW=.*/BUDGET_LOW=0/' .env 2>/dev/null
            docker compose up -d --force-recreate app >/dev/null 2>&1; }
trap restore EXIT

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }
vmq() { curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '.data.result[0].value[1] // "0"'; }

HEADER="budget,rep,alpha,lambda,p99_high,p99_low,p95_high,p95_low,ok_high,ok_low,shed_high,shed_low,hit_high,miss_high,hit_low,miss_low,inflight,app_cpu,db_cpu,ts"
if [[ -e "$CSV" ]]; then
    [[ "$(head -n1 "$CSV")" == "$HEADER" ]] || { echo "incompatible CSV schema" >&2; exit 1; }
else
    echo "$HEADER" > "$CSV"
fi

{
  echo "BUDGET — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "alpha=$ALPHA lambda=$LAMBDA budgets=$BUDGETS wait=${BUDGET_WAIT}s reps=$REPS"
  grep -E '^(THREADS|BACKLOG|DB_POOL|VARNISH_SIZE|CPUSET_)' .env
} >> "$LOG"

total=0
for b in $BUDGETS; do for r in $(seq 1 "$REPS"); do total=$((total+1)); done; done
log "$total measurements, estimate $(( total * (WARMUP+MEASURE+DRAIN+50) / 60 )) minutes"

i=0
for budget in $BUDGETS; do
    if [[ "$budget" == "0" ]]; then
        log "budget disabled (reference)"
    else
        log "budget = $budget concurrent slots for the low-locality class"
    fi

    # The budget is applied at process start: changing it requires
    # recreating the application container.
    grep -q '^BUDGET_LOW=' .env && sed -i "s/^BUDGET_LOW=.*/BUDGET_LOW=$budget/" .env \
        || echo "BUDGET_LOW=$budget" >> .env
    grep -q '^BUDGET_WAIT=' .env && sed -i "s/^BUDGET_WAIT=.*/BUDGET_WAIT=$BUDGET_WAIT/" .env \
        || echo "BUDGET_WAIT=$BUDGET_WAIT" >> .env
    docker compose up -d --force-recreate app >/dev/null 2>&1
    sleep 12

    # The repetitions are shuffled inside each budget value: that is where
    # the machine's temporal drift could be confounded with the
    # effect. The budget itself is not randomised because changing it
    # requires restarting the application.
    mapfile -t reps < <(seq 1 "$REPS" | shuf --random-source=<(yes "$SEED"))

    for rep in "${reps[@]}"; do
        i=$((i+1))
        grep -q "^$budget,$rep," "$CSV" 2>/dev/null && { echo "  [$i/$total] already done"; continue; }

        printf '  [%2d/%2d] budget=%-2s rep=%s ... ' "$i" "$total" "$budget" "$rep"
        tag="b${budget}-r${rep}"

        docker compose restart varnish >/dev/null 2>&1
        sleep 8

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$ALPHA" -e RATE="$LAMBDA" -e DURATION="${WARMUP}s" -e SEED="$SEED" \
            -e ENDPOINT=chapter -e OUTFILE="w-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-w-$tag.log" 2>&1
        rm -f "$HARNESS/results/w-$tag.json"

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$ALPHA" -e RATE="$LAMBDA" -e DURATION="${MEASURE}s" -e SEED="$SEED" \
            -e ENDPOINT=chapter -e OUTFILE="m-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-$tag.log" 2>&1 &
        kp=$!

        sleep 15
        inf=0; ac=0; dc=0; ns=0
        while kill -0 "$kp" 2>/dev/null; do
            v=$(vmq 'ut_requests_inflight')
            read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
                | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
            inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
            ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
            dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
            ns=$((ns+1)); sleep 3
        done
        wait "$kp" 2>/dev/null
        inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

        f="$HARNESS/results/m-$tag.json"
        if [[ -f "$f" ]]; then
            mv "$f" "$OUT/"; f="$OUT/m-$tag.json"
            read -r p99h p99l p95h p95l okh okl shh shl hh mh hl ml <<<"$(jq -r '[
                ((.metrics.ut_lat_zipf.values["p(99)"] // 0)*10|round/10),
                ((.metrics.ut_lat_traversal.values["p(99)"] // 0)*10|round/10),
                ((.metrics.ut_lat_zipf.values["p(95)"] // 0)*10|round/10),
                ((.metrics.ut_lat_traversal.values["p(95)"] // 0)*10|round/10),
                (.metrics.ut_ok_zipf.values.count // 0),
                (.metrics.ut_ok_traversal.values.count // 0),
                (.metrics.ut_shed_zipf.values.count // 0),
                (.metrics.ut_shed_traversal.values.count // 0),
                (.metrics.ut_hit_zipf.values.count // 0),
                (.metrics.ut_miss_zipf.values.count // 0),
                (.metrics.ut_hit_traversal.values.count // 0),
                (.metrics.ut_miss_traversal.values.count // 0)] | @tsv' "$f")"
            echo "$budget,$rep,$ALPHA,$LAMBDA,$p99h,$p99l,$p95h,$p95l,$okh,$okl,$shh,$shl,$hh,$mh,$hl,$ml,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
            printf 'p99 high=%s low=%s   ok low=%s   deferred=%s\n' "$p99h" "$p99l" "$okl" "$shl"
        else
            echo "$budget,$rep,$ALPHA,$LAMBDA,,,,,,,,,,,,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
            echo "FAILED — see $OUT/k6-$tag.log"
        fi
        sleep "$DRAIN"
    done
done

# --- summary ---------------------------------------------------------------
{
  echo
  echo "================================================================"
  echo "RESULT — medians per budget"
  echo "================================================================"
  awk -F, 'NR>1 && $5!="" {
      b=$1; n[b]++
      ph[b,n[b]]=$5; pl[b,n[b]]=$6
      okl[b]+=$10; shl[b]+=$12; okh[b]+=$9
  }
  function med(k, c,   i,j,t,arr) { return 0 }
  END {
    printf "%-8s %5s %11s %11s %12s %12s %10s\n",
           "budget","n","p99 high","p99 low","ok low","deferred","% deferred"
    for (b in n) {
      c=n[b]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) {
        if(ph[b,j]+0<ph[b,i]+0){t=ph[b,i];ph[b,i]=ph[b,j];ph[b,j]=t}
        if(pl[b,j]+0<pl[b,i]+0){t=pl[b,i];pl[b,i]=pl[b,j];pl[b,j]=t}
      }
      mh=(c%2)?ph[b,(c+1)/2]:(ph[b,c/2]+ph[b,c/2+1])/2
      ml=(c%2)?pl[b,(c+1)/2]:(pl[b,c/2]+pl[b,c/2+1])/2
      tot=okl[b]+shl[b]
      printf "%-8s %5d %11.1f %11.1f %12.0f %12.0f %9.1f%%\n",
             (b==0?"off":b), c, mh, ml, okl[b]/c, shl[b]/c,
             (tot>0)?100*shl[b]/tot:0
    }
  }' "$CSV" | (read -r hdr; echo "$hdr"; sort -k1,1)

  echo
  echo "HOW TO READ"
  echo
  echo "  p99 high     latency of the interactive class, the one with a"
  echo "               person waiting. It is the number that must go down."
  echo "  ok low       batch-class requests completed with 200."
  echo "               It is the number that must NOT collapse."
  echo "  deferred     batch-class requests that received"
  echo "               503 with Retry-After. They are not lost: they are shifted."
  echo
  echo "  SUCCEEDED if there is a budget with p99 high below 500 ms and ok"
  echo "  low within 20% of the reference. It means that protecting"
  echo "  interactive traffic costs the batch traffic little, and therefore"
  echo "  that the conflict is apparent."
  echo
  echo "  FAILED if ok low falls in proportion to the budget. The asymmetry"
  echo "  does not exist, the batch class really was limited by the threads, and"
  echo "  the thesis must be abandoned."
  echo
  echo "  ALSO WORTH LOOKING AT: if p99 low rises a lot while ok low"
  echo "  stays high, the crawler is served more slowly but"
  echo "  completely — which is exactly the intended behaviour."
  echo
  echo "Data: $CSV"
} | tee -a "$LOG"