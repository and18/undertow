#!/usr/bin/env bash
#
# verifiche2.sh - The two checks that are missing before writing.
#
# D  DURATION. Direct threat to N1. The agentic class's hit ratio
#    grows until its working set is resident. At beta=0.02
#    that class emits 1364 requests in 620 s over ~1000 distinct URLs:
#    it passes over its own set 1.4 times. At beta=0.30 it emits 20460:
#    it passes over it 20 times. So "the cost depends on the share" could
#    be "the cost depends on how many requests you have already made".
#
#    Test: FIXED share, variable duration. If at beta=0.02 the hit ratio
#    rises from 0.73 towards 0.97 as the measurement is lengthened, the
#    endogeneity is an artefact of the window and N1 dies. If it stops
#    around 0.75, the effect is real.
#
#    The control point at beta=0.30 is already saturated by construction
#    and must not move: if it moves, the problem is elsewhere.
#
# M  MEDIATOR. R2 is the only causal claim of the work and dates from
#    16 August, with the generator using the random offset withdrawn on
#    the 26th. It must be redone under the current protocol and with three
#    classes.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift; env "$@" bash treclassi.sh
}

for M in 620 1860 3720; do
  run "D  duration=${M}s  beta=0.02" MEASURE_FORCE=$M LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.25:0.02"
done
run "D  control  duration=1860s  beta=0.30" MEASURE_FORCE=1860 LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.30"

for C in 64 128 256 512; do
  run "M  cache=${C}m" TOTAL_MB=$C LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.00:0.05 0.30:0.05"
done

echo
echo "================================================================"
echo "  D: if agent h at beta=0.02 rises with the duration, N1 is an"
echo "     artefact of the measurement window. The control at beta=0.30"
echo "     must stay put."
echo "  M: the knee must shift or disappear as the cache grows."
echo "     It is the only causal test of the work and must be redone cleanly."
