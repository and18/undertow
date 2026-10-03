#!/usr/bin/env bash
#
# scopesweep.sh - The last experiment: the sensitivity of a class's cost
# as a function of where its working set sits relative to the capacity.
#
# HYPOTHESIS (recorded before the run)
#   The sensitivity of a class's per-request cost to the traffic
#   composition does not depend on the class having locality, but on the
#   ratio between its working set and the cache capacity.
#
# PREDICTION (shape, not threshold)
#   Measuring the sensitivity S(scope) = excursion of the agentic miss
#   ratio between share 13% and share 30%, the relation of S against
#   (working set / capacity) must be NON-MONOTONIC: low when the set is
#   far below the capacity, highest around the capacity, low again when
#   it is far above.
#
# FALSIFICATION
#   S monotonic in scope, or S statistically indistinguishable among the
#   three points. The criterion is a test on the shape, not a hand-picked
#   threshold: it requires S(central) greater than S(low) AND S(high),
#   each with a separation of at least 2 combined standard errors.
#
# IF IT IS NEGATIVE
#   The residency-boundary mechanism falls. What remains is the empirical
#   characterisation (4.09x against 1.02x and 1.03x) without a
#   mechanistic explanation: level 2, publishable, weaker.
#
# PREREQUISITES, both mandatory
#   1. capacity.sh executed: the real capacity is known
#   2. patch-agentenv.py applied: AGENT_SCOPE reaches k6
#
# Usage:  SCOPE_LOW=... SCOPE_HIGH=... bash scopesweep.sh
#   The two values come from the table printed by capacity.sh:
#   SCOPE_LOW  -> set ~0.1x the capacity
#   SCOPE_HIGH -> set ~10x the capacity
#   The central point (scope 0.02) is NOT rerun: it was measured yesterday.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

: "${SCOPE_LOW:?SCOPE_LOW is missing - take it from the capacity.sh table}"
: "${SCOPE_HIGH:?SCOPE_HIGH is missing - take it from the capacity.sh table}"
REPS="${REPS:-5}"

echo "AGENT_SCOPE sweep: $SCOPE_LOW and $SCOPE_HIGH   ($REPS repetitions)"
echo "central point 0.02 already measured on 21 September, not rerun"
echo "separate mapping active at all points (AGENT_MUL=3266489917)"
echo

for SC in "$SCOPE_LOW" "$SCOPE_HIGH"; do
  for PT in "95:0.2947:0.1263" "119:0.2353:0.3025"; do
    LAM="${PT%%:*}"; REST="${PT#*:}"; A="${REST%%:*}"; B="${REST##*:}"
    printf '\n######## scope=%s  share=%s  lambda=%s ########  %s\n' \
      "$SC" "$B" "$LAM" "$(date +%H:%M)"
    AGENT_MUL=3266489917 AGENT_SCOPE="$SC" \
      LAMBDA="$LAM" REPS="$REPS" GATE=0 WARMUP=300 MEASURE_FORCE=620 \
      POINTS="$A:$B" bash treclassi.sh
  done
done

echo
echo "================================================================"
echo "  Comparison to make: for each scope, the excursion of the agentic"
echo "  miss ratio between share 13% and share 30%."
echo "  Reference already measured at scope 0.02: 0.180 -> 0.044 = 4.09x"
echo
echo "  Extract with:"
echo "    cd ~/undertow/harness/results"
echo "    for d in \$(ls -td tre-* | head -4); do"
echo "      printf '%-26s scope=%-8s ' \"\$d\" \\"
echo "        \"\$(grep -oP 'AGENT_SCOPE=\\K.*' \$d/env.txt)\""
echo "      tail -n +2 \$d/points.csv | awk -F, '{s+=\$9; n++} END {printf \"h_agent=%.3f\\n\", s/n}'"
echo "    done"
