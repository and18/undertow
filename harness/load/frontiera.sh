#!/usr/bin/env bash
#
# frontiera.sh - The hole in the work/latency frontier.
#
# THE QUESTION
#
# The 19 September campaign produced five points at the knee
# (lambda=185, alpha=0.35, beta=0.10, cache 128 MB):
#
#     policy                   served     human p99
#     A  none                  114,692      555.4 ms
#     D6 budget 6              111,384      212.3 ms
#     D4 budget 4              107,596      136.4 ms
#     B  block exhaustive       86,911       57.9 ms
#     C  block exhaust+agent    84,067       57.8 ms
#
# C is Pareto-dominated by B: same latency, 2,844 fewer requests served.
# That dominance is already demonstrated and needs nothing more.
#
# But between D4 (136 ms) and B (58 ms) there is no point. We do not know
# whether a budget with deferral exists that reaches the blocking latency
# while serving more than 86,911 requests, that is, whether DEFERRAL
# DOMINATES BLOCKING and not just its most aggressive variant.
#
# This script fills the hole: budget 1, 2, 3. The other points are
# already measured at the same operating point and are reused.
#
# OUTCOMES
#   p99 <= 60 ms with served > 86,911  ->  deferral dominates blocking
#   the curve passes above B but does not reach it in latency
#                                      ->  the two mechanisms occupy
#                                          different regions of the frontier
#   deferral always stays below B      ->  blocking is on the frontier
#
# FALSIFIES the dominance thesis: if at budget 1 the human p99 does not
# fall below ~90 ms, deferral does not reach the blocking regime.
#
# LIMIT TO DECLARE: in the measurement window a 503 and a 403 both count
# as "not served", because k6 does not retry (RETRY_MAX=0). The
# conceptual advantage of deferral - temporal shifting instead of
# loss - is NOT demonstrated by these data, and the frontier holds
# without needing to assume it.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

LAM="${LAM:-185}"
BUDGETS="${BUDGETS:-3 2 1}"

echo "lambda=$LAM  alpha=0.35  beta=0.10  cache=128MB  3 repetitions"
echo "budget: $BUDGETS   (4 and 6 already measured on 19 September)"

for BU in $BUDGETS; do
  printf '\n######## budget %s ########  %s\n' "$BU" "$(date +%H:%M)"
  BLOCK_CLASSES="" BUDGET_LOW="$BU" BUDGET_WAIT=0 LAMBDA="$LAM" \
    REPS=3 GATE=0 WARMUP=300 MEASURE_FORCE=620 TOTAL_MB=128 \
    POINTS=0.35:0.10 bash treclassi.sh
done

echo
echo "================================================================"
echo "  The summary above does NOT print the deferrals, which are the point."
echo "  Extract them from the JSON files with:"
echo
echo "    cd ~/undertow/harness/results"
echo "    for d in \$(ls -td tre-*/ | head -3); do"
echo "      printf '%-26s ' \"\$d\""
echo "      f=\$(ls \$d/m-*.json | head -1)"
echo "      jq -r '[(.metrics.ut_ok_zipf.values.count//0),"
echo "              (.metrics.ut_ok_agent.values.count//0),"
echo "              (.metrics.ut_ok_traversal.values.count//0),"
echo "              (.metrics.ut_blk_traversal.values.count//0),"
echo "              (.metrics.ut_shed_traversal.values.count//0),"
echo "              ((.metrics.ut_lat_zipf.values[\"p(99)\"]//0)|round)]|@tsv' \$f"
echo "    done"
echo
echo "  Columns: human served / agentic served / exhaustive served /"
echo "           exhaustive BLOCKED (must be 0) / exhaustive DEFERRED /"
echo "           human p99."
echo
echo "  The total served is the sum of the first three. Compare it with"
echo "  86,911 at 57.9 ms, which is the blocking point by identity."