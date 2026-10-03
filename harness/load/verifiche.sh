#!/usr/bin/env bash
#
# verifiche.sh - The three tests that can close the direction.
#
# A  TTL. The endogenous cost of the agentic class rests on the residency
#    of a small set. With a realistic expiry that residency disappears
#    and the effect with it. Prediction recorded before the
#    measurement: collapse between TTL 30 and 120 s, with the agentic class
#    losing much more than the human one (return interval ~45 s against
#    fractions of a second).
#
# B  Endogeneity on a denser interval. If the unit cost of the
#    agentic class depends on its own share, the curve must be
#    monotonic and not an artefact of two points.
#
# C  Second bottleneck. So far it is always the PostgreSQL CPU that
#    saturates. Tightening the connection pool below the thread pool, the
#    resource that saturates changes nature: it runs out of slots,
#    not of compute. If the knee stays at the same rho, generality is
#    demonstrated; if it falls, we have found the missing variable
#    (the variability of the service time).
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() { printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"; shift; env "$@" bash treclassi.sh; }

for T in 0 300 120 60 30; do
  run "A  TTL=${T}s" OBJECT_TTL=$T LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.25:0.02 0.25:0.20"
done

run "B  endogeneity of the agentic class" LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.02 0.25:0.05 0.25:0.10 0.25:0.15 0.25:0.20 0.25:0.30"

for P in 4 12; do
  run "C  pool DB=${P}" DB_POOL_MAX=$P LAMBDA=160 REPS=2 GATE=0 \
      POINTS="0.00:0.05 0.30:0.05 0.40:0.05"
done

echo
echo "================================================================"
echo "  A: if agent hit collapses between TTL 120 and 30, the effect is an"
echo "     artefact of immutable content and the direction is closed."
echo "  B: the curve must be monotonic over six points, not two."
echo "  C: if the knee stays at rho 0.89-0.97 with pool 4, the threshold"
echo "     is a property of queues and not of our database."
