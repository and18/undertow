#!/usr/bin/env bash
#
# measure-model.sh - Measures the model parameters and derives the
#                    operating point. To be run BEFORE any sweep.
#
# WHY
#
# The load that reaches the origin is:
#
#     lambda_origin(a) = lambda_tot * [ (1-h_H) + a*(h_H - h_A) ]
#
# where h_H and h_A are the hit ratios of the two profiles and a is the
# agentic fraction. The knee falls where lambda_origin(a) reaches the
# origin capacity C:
#
#     a* = [ C/lambda_tot - (1-h_H) ] / (h_H - h_A)
#
# If h_H, h_A and C are ASSUMED instead of measured, the operating point
# is chosen at random. With h_H=0.90, h_A=0.20, lambda=800 and C=620 the
# knee would fall at a*=0.96: the system would collapse only with almost
# entirely agentic traffic — the opposite of the thesis, which speaks
# of a modest fraction.
#
# By measuring the three parameters one can instead DERIVE the lambda_tot
# that places the knee where needed, and above all one gets a
# PREDICTION to compare the measurement against. Predicted knee against
# observed knee is worth much more than an isolated empirical curve.
#
# Uso:
#   ./load/measure-model.sh
#   ALPHA_TARGET=0.25 DURATION=300s ./load/measure-model.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

DURATION="${DURATION:-300s}"          # long: steady state is needed
SETTLE="${SETTLE:-180}"               # sampling only after this time
ALPHA_TARGET="${ALPHA_TARGET:-0.25}"  # where the knee is wanted
PROBE_RATE="${PROBE_RATE:-400}"       # rate for measuring h_H and h_A
CAP_RATES="${CAP_RATES:-10 20 30 40 50 60 80 100}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HARNESS/results/model-$STAMP"
REPORT="$OUT/report.txt"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

THREADS=$(grep -E '^THREADS=' .env | cut -d= -f2 | tr -d ' ')
VSIZE=$(grep -E '^VARNISH_SIZE=' .env | cut -d= -f2 | tr -d ' ')

cold_cache() {
    # Every measurement starts from a cold cache: without it, the eviction
    # history of the previous run contaminates the next.
    docker compose restart varnish >/dev/null 2>&1
    sleep 6
}

run_k6() {  # model, rate, outfile, [alpha]
    # Two phases: the first warms the cache and is DISCARDED, the second
    # measures. Without this separation the hit ratio would include the
    # compulsory misses of the initial fill and would come out much lower
    # than the steady-state value — distorting h_H and with it the whole
    # model derived from it.
    docker compose --profile load run --rm -T \
        -e MODEL="$1" -e RATE="$2" -e DURATION="${SETTLE}s" \
        -e ALPHA="${4:-0}" -e OUTFILE="warm-$3" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-warm-$3.log" 2>&1
    rm -f "$HARNESS/results/warm-$3.json"

    docker compose --profile load run --rm -T \
        -e MODEL="$1" -e RATE="$2" -e DURATION="$DURATION" \
        -e ALPHA="${4:-0}" -e OUTFILE="$3" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-$3.log" 2>&1
}

hit_ratio() {  # json file, metric prefix
    jq -r --arg p "$2" '
        ((.metrics["ut_hit_"+$p].values.count // 0) as $h |
         (.metrics["ut_miss_"+$p].values.count // 0) as $m |
         if ($h+$m) > 0 then ($h/($h+$m)*1000|round/1000) else 0 end)' "$1"
}

{
  echo "MEASUREMENT OF THE MODEL PARAMETERS — $(date -Is)"
  echo "================================================================"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "THREADS=$THREADS  VARNISH_SIZE=$VSIZE  duration=$DURATION"
  echo "nproc=$(nproc)"
  echo
  lscpu -e=CPU,CORE,MAXMHZ 2>/dev/null | head -20 | sed 's/^/  /'
  echo
} > "$REPORT"

# --- 1. h_H : hit ratio of the pure human profile ------------------------
log "measuring h_H (pure Zipf) at $PROBE_RATE req/s"
cold_cache
run_k6 zipf "$PROBE_RATE" "zipf"
mv "$HARNESS/results/zipf.json" "$OUT/" 2>/dev/null
H_H=$(hit_ratio "$OUT/zipf.json" zipf)

# --- 2. h_A : hit ratio of the pure agentic profile ----------------------
log "measuring h_A (pure traversal) at $PROBE_RATE req/s"
cold_cache
run_k6 traversal "$PROBE_RATE" "trav"
mv "$HARNESS/results/trav.json" "$OUT/" 2>/dev/null
H_A=$(hit_ratio "$OUT/trav.json" traversal)

{
  echo "----------------------------------------------------------------"
  echo "MEASURED PARAMETERS"
  echo "----------------------------------------------------------------"
  printf '  h_H  hit ratio human profile      %.3f\n' "$H_H"
  printf '  h_A  hit ratio agentic profile    %.3f\n' "$H_A"
  printf '  gap                               %.3f\n' \
         "$(awk -v a="$H_H" -v b="$H_A" 'BEGIN{print a-b}')"
  echo
} >> "$REPORT"

# --- 3. C : origin capacity ----------------------------------------------
log "measuring C (origin capacity) with traversal at increasing rates"
{
  echo "----------------------------------------------------------------"
  echo "ORIGIN CAPACITY"
  echo "----------------------------------------------------------------"
  printf '%-8s %10s %9s %9s %9s %10s\n' \
         rate 'origin' 'pool use' 'app CPU%' 'db CPU%' 'p99 ms'
} >> "$REPORT"

C=""
for rate in $CAP_RATES; do
    printf '    %s req/s ... ' "$rate"
    cold_cache
    sleep 30
    docker compose --profile load run --rm -T \
        -e MODEL=traversal -e RATE="$rate" -e DURATION=120s \
        -e OUTFILE="cap-$rate" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-cap-$rate.log" 2>&1 &
    kp=$!

    sleep 60
    inf=0; acpu=0; dcpu=0
    for s in $(seq 1 15); do
        i=$(vmq 'ut_requests_inflight')
        read -r a d <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' \
            | awk '/ut-app /{gsub(/%/,"",$2); x=$2} /ut-db /{gsub(/%/,"",$2); y=$2} END{print x+0, y+0}')"
        inf=$(awk -v s="$inf" -v v="$i" 'BEGIN{print s+v}')
        acpu=$(awk -v m="$acpu" -v v="$a" 'BEGIN{print (v>m)?v:m}')
        dcpu=$(awk -v m="$dcpu" -v v="$d" 'BEGIN{print (v>m)?v:m}')
        sleep 1
    done
    inf=$(awk -v s="$inf" 'BEGIN{printf "%.1f", s/15}')
    util=$(awk -v i="$inf" -v n="$THREADS" 'BEGIN{printf "%.0f", 100*i/n}')
    wait $kp 2>/dev/null

    f="$HARNESS/results/cap-$rate.json"
    [[ -f "$f" ]] && mv "$f" "$OUT/" && f="$OUT/cap-$rate.json"
    p99=$(jq -r '(.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10' "$f" 2>/dev/null || echo 0)
    ha=$(hit_ratio "$f" traversal 2>/dev/null || echo 0)
    orig=$(awk -v r="$rate" -v h="$ha" 'BEGIN{printf "%.0f", r*(1-h)}')

    printf '%-8s %10s %8s%% %9s %9s %10s\n' \
           "$rate" "$orig" "$util" "$acpu" "$dcpu" "$p99" >> "$REPORT"
    echo "origin=$orig use=${util}% appcpu=$acpu"

    # C = origin rate beyond which the pool exceeds 90%
    if [[ -z "$C" ]] && awk -v u="$util" 'BEGIN{exit !(u>=90)}'; then
        C="$orig"
    fi
    sleep 10
done

[[ -z "$C" ]] && C=$(awk -v r="$(echo $CAP_RATES | awk '{print $NF}')" 'BEGIN{print r}')

# --- 4. derived operating point -------------------------------------------
{
  echo
  echo "----------------------------------------------------------------"
  echo "DERIVED OPERATING POINT"
  echo "----------------------------------------------------------------"
  awk -v hH="$H_H" -v hA="$H_A" -v C="$C" -v at="$ALPHA_TARGET" -v n="$THREADS" '
  BEGIN {
    d = hH - hA
    printf "  C   measured origin capacity      %.0f req/s\n", C
    printf "  a*  target agentic fraction       %.2f\n\n", at
    if (d <= 0.01) {
      print "  ERROR: h_H and h_A are almost equal."
      print "  The two access models do not produce distinct hit ratios."
      print "  Without a gap, the composition cannot generate the phenomenon."
      print "  Check the cache size relative to the corpus."
      exit
    }
    lt = C / ((1-hH) + at*d)
    printf "  derived lambda_tot                %.0f req/s\n", lt
    printf "\n  Model prediction:\n"
    printf "    a=0.00  origin %.0f req/s   pool use %.0f%%\n", lt*(1-hH), 100*lt*(1-hH)/C
    printf "    a=%.2f  origin %.0f req/s   pool use %.0f%%  <- predicted knee\n", at, lt*((1-hH)+at*d), 100*lt*((1-hH)+at*d)/C
    printf "    a=1.00  origin %.0f req/s   pool use %.0f%%\n", lt*(1-hA), 100*lt*(1-hA)/C
    printf "\n  Recommended sweep: alpha from 0 to %.2f in steps of 0.05,\n", (at*2>1?1:at*2)
    printf "  at fixed lambda_tot=%.0f, at least 5 repetitions per point\n", lt
    printf "  (10 at the three points around alpha=%.2f).\n", at
  }' >> "$REPORT"

  echo
  echo "CHECKS BEFORE PROCEEDING"
  echo
  echo "  1. app CPU% at the knee must be below 50%. The observed GIL"
  echo "     ceiling is ~80%: beyond it, the knee would be partly an"
  echo "     artefact of the interpreter and not of the queue."
  echo "  2. If the frequencies in lscpu differ between cores, the cpusets"
  echo "     assign components to different core types. Reassign,"
  echo "     keeping each component on a single type."
  echo "  3. The gap h_H - h_A must exceed 0.3, otherwise the"
  echo "     composition has too little leverage on the origin load."
  echo
  echo "Details in: $OUT"
} >> "$REPORT"

echo; cat "$REPORT"; echo
log "report: $REPORT"