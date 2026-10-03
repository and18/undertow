#!/usr/bin/env bash
#
# poolfix.sh - Can the application pool be too large?
#
# THE HYPOTHESIS, contrary to common practice
#
# A thread pool larger than the backend's capacity does not increase
# the throughput. It only increases how much work can pile up in front of
# a saturated resource, and therefore makes the system SENSITIVE to the
# traffic composition. A smaller pool makes it immune,
# because it rejects upstream instead of queueing.
#
# If it holds: against exhaustive traffic one does not need more
# application capacity, one needs less.
#
# THE DESIGN
#
# lambda FIXED, ONLY the number of threads varies. It is the correction to the run
# of 2026-08-28, where lambda followed N and the two effects were not
# separable — what looked like immunity of the small pool could have
# been just lower load.
#
# alpha goes up to 0.80 because beyond 0.40 the origin load exceeds the
# capacity for any pool: that is where one sees whether the small pool
# holds where the large one collapses.
#
# DRIFT CHECK
#
# Between one pool and the next the same fixed point is re-measured. On 2026-08-28
# the database drifted by 31% in eight hours, which makes comparisons
# between the beginning and the end of the campaign meaningless. The script stops
# instead of producing non-comparable data.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-220}"
THREADS_LIST="${THREADS_LIST:-3 4 6 8 12 16}"
ALPHAS="${ALPHAS:-0.10 0.25 0.40 0.60 0.80}"
REPS="${REPS:-5}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="results/poolfix-$STAMP"
mkdir -p "$BASE"
SUM="$BASE/summary.txt"

restore() { sed -i 's/^THREADS=.*/THREADS=8/' .env
            docker compose up -d --force-recreate app >/dev/null 2>&1; }
trap restore EXIT

# Fixed point: THREADS=8, alpha=0.25, the known knee.
checkpoint() {
    sed -i 's/^THREADS=.*/THREADS=8/' .env
    docker compose up -d --force-recreate app >/dev/null 2>&1; sleep 12
    docker compose restart varnish >/dev/null 2>&1; sleep 8
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE="$LAMBDA" -e DURATION=120s -e OUTFILE=cpw \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    rm -f results/cpw.json
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE="$LAMBDA" -e DURATION=120s -e OUTFILE=cp \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    local v
    v=$(jq -r '(.metrics.ut_lat_zipf.values["p(99)"] // 0)|round' results/cp.json 2>/dev/null || echo 0)
    mv results/cp.json "$BASE/cp-$(date +%H%M).json" 2>/dev/null
    echo "$v"
}

REF=$(checkpoint)
echo "reference: p99 = ${REF} ms" | tee -a "$SUM"
[[ "$REF" -lt 100 ]] && { echo "implausible reference, stopping" | tee -a "$SUM"; exit 1; }

for t in $THREADS_LIST; do
    printf '\n\033[1m==> THREADS=%s  lambda=%s\033[0m  (%s)\n' "$t" "$LAMBDA" "$(date +%H:%M)" | tee -a "$SUM"
    sed -i "s/^THREADS=.*/THREADS=$t/" .env
    docker compose up -d --force-recreate app >/dev/null 2>&1
    sleep 12
    OUT="$BASE/t$t" LAMBDA="$LAMBDA" ALPHAS="$ALPHAS" REPS="$REPS" \
        bash load/sweep.sh 2>&1 | tail -20 | tee -a "$SUM"

    now=$(checkpoint)
    pct=$(awk -v a="$REF" -v b="$now" 'BEGIN{printf "%.0f", 100*(b-a)/a}')
    echo "   drift after t=$t: ${now} ms against ${REF} ms (${pct}%)" | tee -a "$SUM"
    awk -v p="$pct" 'BEGIN{exit !(p<-30 || p>30)}' && {
        echo "DRIFT BEYOND 30% — stopping" | tee -a "$SUM"; break; }
done

# --- final table ---------------------------------------------------------
# The completed requests per class are the number that decides whether the small
# pool is a cure or a bottleneck moved elsewhere.
{
  echo
  echo "================================================================"
  echo "RESULT — interactive p99 and throughput, per pool and composition"
  echo "================================================================"
  printf '%-8s %-7s %11s %11s %11s %9s\n' \
         "THREADS" "alpha" "p99 high" "ok high" "ok low" "hit"
  for d in "$BASE"/t*/points.csv; do
    [[ -f "$d" ]] || continue
    t=$(basename "$(dirname "$d")" | tr -d 't')
    awk -F, -v t="$t" 'NR>1 && $11!="" {
        a=$1; n[a]++; v[a,n[a]]=$11
        okh[a]+=$5; okl[a]+=$0*0
        hh[a]+=$14; mh[a]+=$15; ha[a]+=$16; ma[a]+=$17
        comp[a]+=$5 }
      END { for (a in n) {
        c=n[a]
        for(i=1;i<=c;i++) for(j=i+1;j<=c;j++)
          if(v[a,j]+0<v[a,i]+0){x=v[a,i];v[a,i]=v[a,j];v[a,j]=x}
        m=(c%2)?v[a,(c+1)/2]:(v[a,c/2]+v[a,c/2+1])/2
        tot=hh[a]+mh[a]+ha[a]+ma[a]
        printf "%-8s %-7s %11.1f %11.0f %11.0f %9.3f\n",
               t, a, m, (hh[a]+mh[a])/c, (ha[a]+ma[a])/c,
               (tot>0)?(hh[a]+ha[a])/tot:0 } }' "$d"
  done | sort -n -k1,1 -k2,2
  echo
  echo "HOW TO READ"
  echo
  echo "  p99 high   latency of the interactive class. If it stays low"
  echo "             on the small pools even at high alpha, the hypothesis"
  echo "             holds."
  echo "  ok high    interactive requests served. It must NOT collapse:"
  echo "             if it falls with the pool, the small pool is not a cure"
  echo "             but a bottleneck moved elsewhere."
  echo "  ok low     requests of the exhaustive class served."
  echo
  echo "  HYPOTHESIS CONFIRMED if there is a small pool with low p99 high"
  echo "  at every alpha AND ok high comparable with the large pools."
  echo "  It means the large pool does not produce throughput, it produces"
  echo "  only queue."
  echo
  echo "  HYPOTHESIS FALSIFIED if the knee appears at every pool,"
  echo "  or if the small pool avoids it only because it serves fewer"
  echo "  requests."
} | tee -a "$SUM"

echo; echo "data in $BASE"
