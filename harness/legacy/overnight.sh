#!/usr/bin/env bash
#
# overnight.sh - Four campaigns in sequence, with a drift check.
#
# WHAT IT CLOSES, IN ORDER OF IMPORTANCE
#
#   1. RETRY   is the cost of the budget lost work or only postponed
#              work? If the batch class that respects Retry-After
#              recovers the throughput, the conflict between classes is
#              apparent and the mitigation costs nothing.
#
#   2. POOL    does the relation depend on the pool size? The stability
#              boundary was observed at THREADS=8 in all five previous
#              campaigns. If at 4 and 12 the knee stays at the same
#              occupancy, the normalisation is demonstrated and not assumed.
#
#   3. F2      re-measurement of the per-class hit ratios with the
#              deterministic offset. The previous values are retracted
#              (findings.md, 2026-08-26) and with them the bidirectional
#              decomposition.
#
#   4. BAND    does the instability band exist on this machine? On
#              x86 the dispersion at the knee was over 300%, on ARM
#              4%. Twenty repetitions on a fine step tell whether the
#              phenomenon is real or was platform variability.
#
# DRIFT CHECK
#
# Between one campaign and the next the same fixed point is re-measured. If the
# reference p99 changes by more than 30%, the machine is no longer the one
# it was and the following campaigns are not comparable: the script stops
# instead of producing non-comparable data. It happened on
# 2026-08-18, when PostgreSQL warmed up during a campaign and the
# knee disappeared.
#
# Usage:
#   nohup bash load/overnight.sh > /tmp/overnight.log 2>&1 &
#
# Uso:
#   nohup bash load/overnight.sh > /tmp/overnight.log 2>&1 &
#
set -uo pipefail

H="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$H"
STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="$H/results/overnight-$STAMP"
mkdir -p "$BASE"; chmod 777 "$H/results" 2>/dev/null || true
LOG="$BASE/overnight.log"

log() { printf '\n\033[1m===> %s\033[0m  (%s)\n' "$*" "$(date +%H:%M)" | tee -a "$LOG"; }

# Fixed control point: alpha 0.25, lambda 220, budget off.
checkpoint() {
    docker compose restart varnish >/dev/null 2>&1; sleep 8
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE=220 -e DURATION=120s -e OUTFILE=cp-w \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    rm -f "$H/results/cp-w.json"
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE=220 -e DURATION=120s -e OUTFILE=cp \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    local v
    v=$(jq -r '(.metrics.ut_lat_zipf.values["p(99)"] // 0)|round' "$H/results/cp.json" 2>/dev/null || echo 0)
    mv "$H/results/cp.json" "$BASE/checkpoint-$(date +%H%M).json" 2>/dev/null
    echo "$v"
}

restore_env() {
    sed -i 's/^THREADS=.*/THREADS=8/' .env
    sed -i 's/^BUDGET_LOW=.*/BUDGET_LOW=0/' .env
    docker compose up -d --force-recreate app >/dev/null 2>&1; sleep 10
}
trap restore_env EXIT

REF=$(checkpoint)
log "initial reference: p99 high = ${REF} ms"
[[ "$REF" -lt 100 ]] && { echo "implausible reference, stopping" | tee -a "$LOG"; exit 1; }

drift_ok() {
    local now pct
    now=$(checkpoint)
    pct=$(awk -v a="$REF" -v b="$now" 'BEGIN{printf "%.0f", 100*(b-a)/a}')
    log "drift check: ${now} ms against ${REF} ms  (${pct}%)"
    awk -v p="$pct" 'BEGIN{exit !(p<-30 || p>30)}' && {
        echo "DRIFT BEYOND 30% — following campaigns not comparable" | tee -a "$LOG"
        return 1; }
    return 0
}

# --- 1. RETRY ------------------------------------------------------------
log "1/4  RETRY — does the budget cost work or only time?"
OUT="$BASE/retry" LAMBDA=220 ALPHA=0.25 BUDGETS="0 5 4" REPS=5 \
    RETRY_MAX=3 MEASURE=300 bash load/budget.sh >> "$LOG" 2>&1
restore_env

drift_ok || exit 1

# --- 2. POOL -------------------------------------------------------------
# The rate is scaled with the pool size to keep the expected occupancy
# constant: that is the meaning of the normalisation.
log "2/4  POOL — does the boundary depend on the pool size?"
for t in 4 12; do
    lam=$(awk -v t="$t" 'BEGIN{printf "%.0f", 220*t/8}')
    log "     THREADS=$t  lambda=$lam"
    sed -i "s/^THREADS=.*/THREADS=$t/" .env
    docker compose up -d --force-recreate app >/dev/null 2>&1; sleep 12
    OUT="$BASE/pool-$t" LAMBDA="$lam" ALPHAS="0.10 0.15 0.20 0.25 0.30 0.40" \
        REPS=3 bash load/sweep.sh >> "$LOG" 2>&1
done
restore_env

drift_ok || exit 1

# --- 3. F2 ---------------------------------------------------------------
log "3/4  F2 — per-class hit ratio, with deterministic offset"
OUT="$BASE/f2" LAMBDA=220 ALPHAS="0.00 0.10 0.20 0.30 0.40 0.50" \
    REPS=3 bash load/sweep.sh >> "$LOG" 2>&1

drift_ok || exit 1

# --- 4. BAND -------------------------------------------------------------
log "4/4  BAND — is the transition bimodal or only steep?"
OUT="$BASE/band" LAMBDA=220 ALPHAS="0.22 0.24 0.26 0.28" \
    REPS=20 bash load/sweep.sh >> "$LOG" 2>&1

log "all campaigns completed"
echo "results in $BASE" | tee -a "$LOG"
ls -d "$BASE"/*/ | tee -a "$LOG"