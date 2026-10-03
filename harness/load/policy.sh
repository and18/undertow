#!/usr/bin/env bash
# policy.sh - The admission policies compared, at the knee.
#
#   A   no policy                        the web default
#   B   block the exhaustive class       admission by identity
#   C   block exhaustive and agentic     Cloudflare default, 15 Sep 2026
#   D4  budget with deferral, 4 slots    our mitigation
#   D6  budget with deferral, 6 slots
#
# The deciding comparison is C against D: C rejects the class that costs
# less to serve, D defers the one that costs more. If D achieves an
# interactive latency close to that of C while continuing to serve the
# agentic class, blocking by identity pays a price that is not needed.
#
# The block is at the origin, not at the edge: a blocked request that
# finds the object in cache is served by Varnish anyway. On the origin
# load the effect is identical, because a hit does not reach the origin
# in any case.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
LAM="${LAM:-185}"
echo "lambda=$LAM  alpha=0.35  beta=0.10  cache=128MB  3 repetitions"
for P in "A::0" "B:low:0" "C:low,agent:0" "D4::4" "D6::6"; do
  N="${P%%:*}"; R="${P#*:}"; B="${R%%:*}"; BU="${R##*:}"
  printf '\n######## policy %s  block=[%s] budget=%s ########  %s\n' \
      "$N" "$B" "$BU" "$(date +%H:%M)"
  BLOCK_CLASSES="$B" BUDGET_LOW="$BU" BUDGET_WAIT=0 LAMBDA="$LAM" \
    REPS=3 GATE=0 WARMUP=300 MEASURE_FORCE=620 TOTAL_MB=128 \
    POINTS=0.35:0.10 bash treclassi.sh
done
