#!/usr/bin/env bash
#
# notte.sh - Long unattended campaign.
#
# PHASE 1 (F5, priority). Sweep in lambda on just two configurations.
#
#   On 30 August the protection cost +10.2% of origin load
#   without giving latency, because at rho=0.67 the latency is flat. But if it
#   shifts +10% onto the origin, the protected system must saturate at a
#   lower lambda. With capacity 90 req/s and knee at rho=0.89:
#
#     shared     h=0.4535 -> predicted knee at lambda = 146
#     protected  h=0.4015 -> predicted knee at lambda = 134
#
#   If the protected one breaks first, scan-resistance causes the collapse
#   it is supposed to prevent. If they break together, the cost exists but
#   has no operational consequences: a negative result, publishable anyway.
#
# PHASE 2 (F4). Full curve in r at fixed lambda, only if time remains.
#   shared appears twice: drift check.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

HOURS="${HOURS:-9}"
DEADLINE=$(( $(date +%s) + $(awk -v h="$HOURS" 'BEGIN{printf "%d", h*3600}') ))
LAMBDAS="${LAMBDAS:-110 125 135 145 155}"

STAMP="$(date +%Y%m%d-%H%M%S)"
IDX="../results/notte-$STAMP.csv"
echo "fase,lambda,dir" > "$IDX"

run() {   # run <phase> <lambda> <fractions> <gate> <reps>
    printf '\n\033[1m######## %s  lambda=%s  r={%s} ########\033[0m  %s\n' \
        "$1" "$2" "$3" "$(date +%H:%M)"
    LAMBDA="$2" ALPHA=0.50 TOTAL_MB=128 FRACTIONS="$3" REPS="$5" GATE="$4" bash split.sh
    echo "$1,$2,$(basename "$(ls -td ../results/split-*/ | head -1)")" >> "$IDX"
}

for L in $LAMBDAS; do
    if [[ $(date +%s) -gt $DEADLINE ]]; then echo "time is up, phase 1 interrupted"; break; fi
    run F5 "$L" "shared 1.00" 0 3
done

if [[ $(date +%s) -lt $((DEADLINE - 10800)) ]]; then
    run F4 110 "shared 0.50 0.75 0.90 1.00 shared" 1 3
else
    echo "phase 2 skipped: not enough time left"
fi

echo; echo "==================== SUMMARY ===================="
printf '%-4s %-7s %-8s %4s %9s %9s %10s %9s\n' \
    "phase" "lambda" "r" "n" "p99 high" "hit high" "hit low" "orig rps"
tail -n +2 "$IDX" | while IFS=, read -r fase lam dir; do
    [[ -f "../results/$dir/points.csv" ]] || continue
    awk -F, -v f="$fase" -v l="$lam" 'NR>1 && $3!="" {
        r=$1; n[r]++; p[r]+=$3; hh[r]+=$5; mh[r]+=$6; hl[r]+=$7; ml[r]+=$8; o[r]+=$9 }
      END { for (r in n) printf "%-4s %-7s %-8s %4d %9.1f %9.3f %10.3f %9.2f\n",
        f, l, r, n[r], p[r]/n[r], hh[r]/(hh[r]+mh[r]),
        (hl[r]+ml[r]>0)?hl[r]/(hl[r]+ml[r]):0, o[r]/n[r] }' "../results/$dir/points.csv"
done
echo "Index: $IDX"