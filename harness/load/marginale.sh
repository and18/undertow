#!/usr/bin/env bash
#
# marginale.sh - The marginal cost, measured instead of deduced.
#
# Every campaign so far kept the TOTAL volume constant, so raising
# beta REPLACED human traffic with agentic traffic. From that one gets
# a substitution effect, not the marginal cost.
#
# Here human and exhaustive stay fixed in ABSOLUTE value (55 and 28 req/s)
# and agents are added. The slope d(origin)/d(agentic requests)
# IS the marginal cost: the quantity a controller needs and that no
# isolated calibration produces.
#
# PREDICTION RECORDED BEFORE THE MEASUREMENT
#   If the marginal is ~0.05 (indirect estimate from the 9-11 Sep data),
#   the origin load rises by ~1.8 req/s from 0 to 36 agents/s.
#   If instead it equals the average cost at low share (0.27), it rises
#   by ~9.7. The two scenarios are distinguishable by eye.
#
# The isolated calibration of the agentic class gave 0.102 at 5 req/s and
# 0.002 at 22 req/s: if the marginal is flat around 0.05, then
# neither isolated calibration approximates it, and the choice of
# calibration volume decides the error.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## agents=%s req/s  lambda=%s ########\033[0m  %s\n' \
        "$1" "$2" "$(date +%H:%M)"
    LAMBDA="$2" REPS=2 GATE=0 WARMUP=300 POINTS="$3:$4" bash treclassi.sh
}

#   agents  lambda  alpha    beta     (human always 55, exhaustive always 28)
run  0      83      0.3373   0.0000
run  6      89      0.3146   0.0674
run  12     95      0.2947   0.1263
run  24     107     0.2617   0.2243
run  36     119     0.2353   0.3025

echo
echo "================================================================"
echo "  Marginal cost = change in orig rps / change in agentic"
echo "  requests per second. Human and exhaustive are fixed,"
echo "  so the slope is attributable to the agentic class alone."
echo "  Check: h hum and h trav must stay nearly flat. If they"
echo "  move a lot, the agentic class is also altering the others"
echo "  and the marginal includes a cross effect to be declared."
