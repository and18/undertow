#!/usr/bin/env bash
#
# costmap.sh - The cost map, and the test that can kill N1.
#
# HYPOTHESIS UNDER TEST
#
# The per-request cost of a class is not a property of the class: it
# depends on the composition of the traffic. If this is true, an admission
# controller that uses costs calibrated in isolation - that is, all the
# published ones: DAGOR with declared priorities, Rajomon with per-API
# prices, UCP with isolated utility curves - uses a false input.
#
# And the error is self-confirming: if it throttles the agentic class
# because it believes it expensive, it lowers its share, and at a low share
# that class IS really expensive. The next measurement proves it right.
# A lock-in to a worse operating point through positive feedback.
#
# BEFORE BUILDING ANY CONTROLLER we measure the map and compute on paper
# the decision each one would take. If they coincide, the idea dies in one
# night instead of two weeks.
#
# BLOCK 1 - isolation. Each class alone, at the volumes it has in the
#   mixes of block 2. This is the calibration of the static controller.
#   Note: there is no "right" volume to calibrate at, and that is part of
#   the problem.
#
# BLOCK 2 - mixes. The same quantity measured in situ.
#   The difference between block 1 and block 2, at the same class volume,
#   IS the error of the exogenous cost.
#
# BLOCK 3 - the threat. With TTL 60 s the system-level benefit of agentic
#   traffic almost disappears (R9: from -7.2% to -0.6%). If no better
#   operating point exists, the static controller is not getting anything
#   important wrong and N1 only holds for slowly changing content. We must
#   know NOW, not after building.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift; env "$@" bash treclassi.sh
}

# --- block 1: isolation ----------------------------------------------------
# traversal: POINTS alpha=1.00 because MEASURE must cover the corpus
run "ISO traversal @22"  MODEL=traversal LAMBDA=22 REPS=2 POINTS="1.00:0.00"
run "ISO traversal @44"  MODEL=traversal LAMBDA=44 REPS=2 POINTS="1.00:0.00"
run "ISO agent @5"       MODEL=agent     LAMBDA=5  REPS=2 POINTS="0.00:1.00"
run "ISO agent @22"      MODEL=agent     LAMBDA=22 REPS=2 POINTS="0.00:1.00"
run "ISO zipf @44"       MODEL=zipf      LAMBDA=44 REPS=2 POINTS="0.00:0.00"
run "ISO zipf @88"       MODEL=zipf      LAMBDA=88 REPS=2 POINTS="0.00:0.00"

# --- block 2: mixes ---------------------------------------------------------
run "MIX grid" LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.20:0.05 0.20:0.20 0.30:0.05 0.30:0.20 0.40:0.05 0.40:0.20"

# --- block 3: the same grid with realistic expiry ---------------------
run "MIX grid TTL=60s" OBJECT_TTL=60 LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.02 0.25:0.10 0.25:0.20 0.25:0.30"

echo
echo "================================================================"
echo "  Per-request cost of a class = 1 - the class's hit ratio."
echo "  ISO: what a static controller believes."
echo "  MIX: what is true in situ."
echo "  The error is the difference, at the same class volume."
echo "  Block 3: if at TTL 60 the origin load no longer falls as beta"
echo "  grows, there is no better operating point to miss, and N1 only"
echo "  holds for slow content."
