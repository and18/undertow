#!/usr/bin/env bash
#
# marginale2.sh - Error bars on the agent, and the same design for the
# crawler. The claim to support is not a number about the agent: it is
# that the isolated calibration errs ASYMMETRICALLY between the two
# classes, measured with identical methodology.
#
# A  agent: 5 repetitions on the points where the slope changes sign.
#    The first run (14 Sep) gave marginal +0.047 / +0.023 / -0.014 /
#    -0.070 with 2 repetitions and a dispersion of 0.1-0.5 req/s on the
#    origin load: the sign of the last stretch is at 2 sigma.
#
# B  crawler: human and agent FIXED in absolute value (55 and 12 req/s),
#    crawler from 0 to 42. PREDICTION RECORDED: marginal close to 1.0 and
#    slightly above, because the crawler consumes residency and worsens
#    the others too. If it comes out ~1.0 flat while the agent is
#    decreasing and negative, the asymmetry is demonstrated.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift
    LAMBDA="$1" REPS="$4" GATE=0 WARMUP=300 MEASURE_FORCE="${MF:-620}" \
        POINTS="$2:$3" bash treclassi.sh
}

# A - agent, human 55 + crawler 28 fixed, 5 repetitions
run "A agents=0"   83  0.3373 0.0000 5
run "A agents=12"  95  0.2947 0.1263 5
run "A agents=24" 107  0.2617 0.2243 5
run "A agents=36" 119  0.2353 0.3025 5

# B - crawler, human 55 + agent 12 fixed
export MF=1211
run "B crawler=0"   67  0.0000 0.1791 3
run "B crawler=14"  81  0.1728 0.1481 3
run "B crawler=28"  95  0.2947 0.1263 3
run "B crawler=42" 109  0.3853 0.1101 3

echo
echo "================================================================"
echo "  A: slope of the origin load against agentic requests,"
echo "     with 5 repetitions to get a dispersion."
echo "  B: same slope for the crawler. Check: h hum must"
echo "     stay flat in both blocks."
