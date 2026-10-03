#!/usr/bin/env bash
#
# Campaign of 3 September. Re-measures everything that depended on the
# free ride, after the TRAV_SKIP fix.
#
# The bug: warm-up and measurement are two separate k6 invocations, so
# iterationInTest restarted from zero and the exhaustive class revisited
# exactly the objects inserted WARMUP seconds earlier. hit_low
# measured the cache's survival curve, not the free ride.
# Signature: at 128 MB it is 0.163 with warm-up 180 s and 0.089 with 300 s.
#
# With TRAV_SKIP the measurement resumes the traversal where the warm-up
# left it, so the exhaustive class does not meet its own insertions
# and everything it finds in cache was put there by the human class.
#
# alpha=0.25 and not 0.50: at 0.50 the traversal wraps around the corpus
# (26,400 requests over 16,954 objects) and the repeat passes come back through
# another door. At 0.25 they are 13,200, below the corpus size.
#
# smoke  does the fix work? it must give hit low ~ 0
# C      the true free ride, against the cache/corpus ratio
# A      control without the human class: nobody fills the cache for the
#        scanner, so hit low must stay ~ 0. It is NOT a term to
#        subtract from C: without the human class the insertion rate is
#        almost halved and the cache behaves differently.
# D      the cost of partitioning re-measured cleanly (it was O8b)
# B      hit low must no longer depend on the warm-up
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift
    env "$@" bash split.sh
}

run "smoke  exhaustive only, 128m" LAMBDA=28 ALPHA=1.00 TOTAL_MB=128 \
    FRACTIONS=shared REPS=1 WARMUP=300 MEASURE=180

for MB in 32 64 128 256 384; do
  run "C  cache=${MB}m  with human class" LAMBDA=110 ALPHA=0.25 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

for MB in 32 64 128 256 384; do
  run "A  cache=${MB}m  exhaustive only" LAMBDA=28 ALPHA=1.00 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

run "D  cost of partitioning, corrected generator" LAMBDA=110 ALPHA=0.25 \
    TOTAL_MB=128 FRACTIONS="shared 0.75 1.00 shared" REPS=3 WARMUP=300 MEASURE=180

for W in 120 300 600; do
  run "B  warmup=${W}s" LAMBDA=110 ALPHA=0.25 TOTAL_MB=128 \
      FRACTIONS=shared REPS=3 WARMUP=$W MEASURE=180
done

echo
echo "================================================================"
echo "  smoke and A: hit low must be ~ 0. If it is not, TRAV_SKIP does not"
echo "  work and the rest of the night is to be thrown away."
echo "  C: the free ride. Does it grow with the cache/corpus ratio?"
echo "  D: shared twice as a drift check, they must coincide."
echo "  B: the three rows must give the same hit low."