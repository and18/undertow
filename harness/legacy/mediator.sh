#!/usr/bin/env bash
#
# mediator.sh - Intervention on the mediator: is the cache really the mechanism?
#
# THE QUESTION
#
# The sweep shows that raising the fraction of low-locality traffic
# makes the system go through a knee. But correlation is not mechanism:
# alpha drives every link of the chain by construction, so all the
# correlations along the chain are close to 1 without identifying anything.
#
# The only way to identify the cause is to INTERVENE on the hypothesised
# mediator.
#
# FALSIFIABLE PREDICTION
#
#   cache < working set   the knee is present, and its position
#                         depends on the cache/working-set ratio
#
#   cache >= working set  the contribution of cache competition to the
#                         knee disappears or is drastically reduced,
#                         even at alpha = 1
#
# Deliberately cautious wording: "the cache-mediated contribution
# disappears" and not "the knee must disappear". Other mechanisms
# independent of the cache — generation cost, connection churn,
# burstiness — might produce one anyway. The experiment is
# informative in all three possible outcomes.
#
# PRIMARY MEASUREMENT OF THE ORIGIN LOAD
#
# So far the origin load was DEDUCED from lambda*(1-hit). Here it is
# also MEASURED, as the delta of the ut_requests_total counter divided by the
# time actually elapsed. The comparison between the two is the quantitative
# check of the central link of the chain: if they coincide, the
# cache -> origin step is closed; if they do not, there is a
# path the model does not see.
#
# The counter delta is exact; an average of rate() samples is
# an approximation. The former is used as the measurement, the latter only
# as a diagnostic of the peak.
#
# TERMINOLOGY
#
# alpha is the fraction of LOW-LOCALITY traffic, not yet the
# agentic fraction: only one of the nine workload parameters varies.
# See docs/findings.md.
#
# WORKING SET
#
#   Measured footprint: ~438 MB (16,954 objects, 25.9 KB average in cache).
#   The 245 MB cited in earlier versions was the size of the text
#   in PostgreSQL, not that of the objects stored by Varnish.
#
# Usage:
#   DRY=1 ./load/mediator.sh          logic check, NOT data
#   ./load/mediator.sh                full campaign
#   SIZES="128m 512m" REPS=3 ./load/mediator.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

# --- experimental parameters ---------------------------------------------

LAMBDA="${LAMBDA:-260}"

#   128m =  52% of the working set   strong competition
#   256m = 104% of the working set   at the limit
#   512m = 209% of the working set   no competition
SIZES="${SIZES:-128m 256m 512m}"

# alpha=1.00 is indispensable: "no knee at any alpha" cannot be
# tested by stopping at 0.50.
ALPHAS="${ALPHAS:-0.00 0.15 0.30 0.50 1.00}"

REPS="${REPS:-3}"

# Validated minimum for the 512 MB cache on this workload. With 300 s the
# hit ratios at 128m and 512m come out identical — we are measuring the
# cache fill, not the steady state. Shorter warm-ups do not
# produce valid measurements.
WARMUP="${WARMUP:-600}"

MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"

if [[ "${DRY:-0}" == "1" ]]; then
    # ONLY a check of the script's logic. The numbers produced by a
    # dry run are not experimental data under any circumstance.
    SIZES="128m 512m"; ALPHAS="0.00 0.50"; REPS=1
    WARMUP=120; MEASURE=45; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/mediator-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/mediator.log"

mkdir -p "$OUT"
# The k6 container runs as a non-root user and writes to /results.
chmod 777 "$HARNESS/results" 2>/dev/null || true

ORIG_SIZE=$(grep -E '^VARNISH_SIZE=' .env | cut -d= -f2 | tr -d ' ')
restore() { sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$ORIG_SIZE/" .env
            docker compose up -d --force-recreate varnish >/dev/null 2>&1; }
trap restore EXIT

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }

# --data-urlencode avoids hand-encoding the square brackets, which has
# already cost a run: %5B30s%5] instead of %5B30s%5D fails silently
# always returning zero.
vmq() {
    curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '.data.result[0].value[1] // "0"'
}
vmq_sum() {
    curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '[.data.result[].value[1]|tonumber] | add // 0'
}

# --- CSV schema ------------------------------------------------------------
# Two different CSV schemas in the same project (sweep.sh and mediator.sh)
# are a latent risk: an analysis written for one and applied to the
# other reads the wrong columns without errors. Here the schema is
# checked and, if it does not match, we exit instead of migrating silently.

HEADER="cache,alpha,rep,lambda,completed,dropped,failed,p50,p95,p99,p999,hit_h,miss_h,hit_a,miss_a,inflight,app_cpu,db_cpu,origin_rps_mean,origin_rps_max,ts"

if [[ -e "$CSV" ]]; then
    found=$(head -n1 "$CSV" 2>/dev/null || true)
    if [[ "$found" != "$HEADER" ]]; then
        echo "ERROR: incompatible CSV schema in $CSV" >&2
        echo "expected: $HEADER" >&2
        echo "found:    $found" >&2
        echo "Use a new OUT directory instead of migrating a dataset." >&2
        exit 1
    fi
else
    echo "$HEADER" > "$CSV"
fi

{
  echo "MEDIATOR — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "lambda=$LAMBDA sizes=$SIZES alphas=$ALPHAS reps=$REPS"
  echo "warmup=${WARMUP}s measure=${MEASURE}s drain=${DRAIN}s seed=$SEED"
  echo "dry_run=${DRY:-0}"
  echo "working set = 245 MB (16954 objects)"
  grep -E '^(THREADS|BACKLOG|DB_POOL|CPUSET_)' .env
} >> "$LOG"

# --- count and estimate ----------------------------------------------------
total=0
for s in $SIZES; do for a in $ALPHAS; do for r in $(seq 1 "$REPS"); do
    total=$((total+1)); done; done; done
log "$total measurements, estimate $(awk -v n="$total" -v w="$WARMUP" -v m="$MEASURE" \
    -v d="$DRAIN" 'BEGIN{printf "%.0f", n*(w+m+d+50)/60}') minutes"

# --- main loop -------------------------------------------------------------
i=0
for size in $SIZES; do
    log "cache = $size configured"
    sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$size/" .env
    docker compose up -d --force-recreate varnish >/dev/null 2>&1
    sleep 10

    # The cache size is NOT randomised: changing it requires restarting
    # Varnish. Alpha and repetition are randomised INSIDE each size,
    # which is where the machine's temporal drift could be
    # confounded with the effect under study.
    jobs=()
    for a in $ALPHAS; do for r in $(seq 1 "$REPS"); do jobs+=("$a:$r"); done; done
    mapfile -t jobs < <(printf '%s\n' "${jobs[@]}" | shuf --random-source=<(yes "$SEED"))

    for job in "${jobs[@]}"; do
        a="${job%:*}"; rep="${job#*:}"; i=$((i+1))
        if grep -q "^$size,$a,$rep," "$CSV" 2>/dev/null; then
            echo "  [$i/$total] $size alpha=$a rep=$rep  already done"; continue
        fi

        printf '  [%2d/%2d] %s alpha=%s rep=%s ... ' "$i" "$total" "$size" "$a" "$rep"
        tag="${size}-a${a}-r${rep}"
        max_orps=0

        # Cold cache before EVERY point: with the randomised order,
        # inheriting the cache of the previous point would be fatal.
        docker compose restart varnish >/dev/null 2>&1
        sleep 8

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${WARMUP}s" \
            -e ENDPOINT=chapter -e OUTFILE="w-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-w-$tag.log" 2>&1
        rm -f "$HARNESS/results/w-$tag.json"

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${MEASURE}s" \
            -e ENDPOINT=chapter -e OUTFILE="m-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-$tag.log" 2>&1 &
        kp=$!

        # Baseline after the generator starts: taking it before, the
        # denominator would include the container start-up and the window
        # would come out longer than the period in which the load flowed.
        sleep 2
        origin_before=$(vmq_sum 'sum(ut_requests_total{endpoint="chapter"})')
        t_before=$(date +%s.%N)

        # Diagnostic sampling for the whole window. The origin load
        # measurement does NOT come from here — it comes from the counter
        # delta — but only pool occupancy, CPU and rate peak.
        sleep 15
        inf=0; ac=0; dc=0; ns=0
        while kill -0 "$kp" 2>/dev/null; do
            v=$(vmq 'ut_requests_inflight')
            orps=$(vmq_sum 'sum(rate(ut_requests_total[30s]))')
            awk -v x="$max_orps" -v y="$orps" 'BEGIN{exit !(y>x)}' && max_orps="$orps"
            read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
                | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
            inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
            ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
            dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
            ns=$((ns+1)); sleep 3
        done
        wait "$kp" 2>/dev/null

        origin_after=$(vmq_sum 'sum(ut_requests_total{endpoint="chapter"})')
        t_after=$(date +%s.%N)

        inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

        # Delta divided by the time ACTUALLY elapsed, not the nominal
        # duration: between the initial sample and the k6 exit there are
        # the container start-up and the gracefulStop, so dividing by
        # MEASURE would overestimate.
        mean_orps=$(awk -v b="$origin_before" -v a="$origin_after" \
                        -v t0="$t_before" -v t1="$t_after" 'BEGIN{
            d = a - b; el = t1 - t0
            if (d < 0) { print "NA"; exit }        # counter reset: app restarted
            printf "%.1f", (el > 0) ? d/el : 0 }')
        [[ "$mean_orps" == "NA" ]] && log "WARNING: counter reset during $tag"

        f="$HARNESS/results/m-$tag.json"
        if [[ -f "$f" ]]; then
            mv "$f" "$OUT/"; f="$OUT/m-$tag.json"
            read -r comp drop fail p50 p95 p99 p999 hh mh ha ma <<<"$(jq -r '[
                (.metrics.http_reqs.values.count // 0),
                (.metrics.dropped_iterations.values.count // 0),
                ((.metrics.http_req_failed.values.rate // 0)*10000|round/10000),
                ((.metrics.http_req_duration.values.med // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(95)"] // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(99.9)"] // 0)*10|round/10),
                (.metrics.ut_hit_zipf.values.count // 0),
                (.metrics.ut_miss_zipf.values.count // 0),
                (.metrics.ut_hit_traversal.values.count // 0),
                (.metrics.ut_miss_traversal.values.count // 0)] | @tsv' "$f")"
            echo "$size,$a,$rep,$LAMBDA,$comp,$drop,$fail,$p50,$p95,$p99,$p999,$hh,$mh,$ha,$ma,$inf,$ac,$dc,$mean_orps,$max_orps,$(date -Is)" >> "$CSV"
            printf 'p99=%s  pool=%s  orig=%s req/s\n' "$p99" "$inf" "$mean_orps"
        else
            # 11 empty fields between lambda and inflight: completed, dropped,
            # failed, p50, p95, p99, p999, hit_h, miss_h, hit_a, miss_a.
            echo "$size,$a,$rep,$LAMBDA,,,,,,,,,,,,$inf,$ac,$dc,$mean_orps,$max_orps,$(date -Is)" >> "$CSV"
            echo "FAILED — see $OUT/k6-$tag.log"
        fi
        sleep "$DRAIN"
    done
done

# --- summary ---------------------------------------------------------------
{
  echo
  echo "================================================================"
  echo "RESULT"
  echo "================================================================"
  awk -F, 'NR>1 && $10!="" {
      k=$1" "$2; n[k]++; v[k,n[k]]=$10
      hit[k]+=$12+$14; mis[k]+=$13+$15
      if ($19 != "NA") { orps[k]+=$19; on[k]++ }
      lam[k]+=$4
  }
  END {
    printf "%-7s %-6s %4s %10s %8s %11s %11s %8s\n",
           "cache","alpha","n","p99 med","hit","orig pred","orig obs","dev"
    for (k in n) {
      c=n[k]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++)
        if(v[k,j]+0<v[k,i]+0){t=v[k,i];v[k,i]=v[k,j];v[k,j]=t}
      m=(c%2)?v[k,(c+1)/2]:(v[k,c/2]+v[k,c/2+1])/2
      h=(hit[k]+mis[k]>0)?hit[k]/(hit[k]+mis[k]):0
      pred=(lam[k]/c)*(1-h)
      obs=(on[k]>0)?orps[k]/on[k]:0
      dev=(pred>0)?100*(obs-pred)/pred:0
      split(k,p," ")
      printf "%-7s %-6s %4d %10.1f %8.3f %11.1f %11.1f %7.1f%%\n",
             p[1],p[2],c,m,h,pred,obs,dev
    }
  }' "$CSV" | (read -r hdr; echo "$hdr"; sort -k1,1 -k2,2)

  echo
  echo "HOW TO READ"
  echo
  echo "  Configured cache capacity. The actual footprint of the objects"
  echo "  in cache has not been measured: the 245 MB cited elsewhere"
  echo "  is the size of the corpus in PostgreSQL, not that of the"
  echo "  compressed responses that Varnish stores."
  echo
  echo "  CHECK OF THE CENTRAL LINK"
  echo "    orig pred = lambda x (1 - hit),  deduced"
  echo "    orig obs  = delta of ut_requests_total / time,  measured"
  echo "    A small deviation quantitatively closes the cache -> origin"
  echo "    step. A large deviation indicates a path the model does not"
  echo "    see, and is a result in itself."
  echo
  echo "  MEDIATOR OUTCOME — three levels, not two"
  echo
  echo "  SUPPORTED"
  echo "    With cache >= working set the dependence of p99 on alpha"
  echo "    disappears, while below the working set the knee is there."
  echo "    Cache competition is the mechanism, demonstrated by"
  echo "    intervention and not by correlation."
  echo
  echo "  PARTIALLY SUPPORTED"
  echo "    The knee moves a lot with the cache but does not disappear."
  echo "    The cache is an important but not the only mediator: generation"
  echo "    cost, connection churn, burstiness remain."
  echo
  echo "  NOT SUPPORTED AS THE MAIN MECHANISM"
  echo "    The knee stays substantially where it is even with ample"
  echo "    cache. The dominant mechanism is elsewhere: the next"
  echo "    thing to look at is the generation cost of the page."
  echo
  echo "  NOTE. alpha is the fraction of low-locality traffic, not"
  echo "  an empirically calibrated agentic fraction."
  echo
  echo "Dati: $CSV"
} | tee -a "$LOG"