#!/usr/bin/env bash
#
# replica-20260924.sh - replica campaign on the same day.
# Design, predictions and rules: docs/PREREG-replica-20260924.md (written and
# committed BEFORE the launch). It does not modify the harness: it calls treclassi.sh
# five times, once per point, with the same configuration as the sweep of
# 21 September (GATE=0, WARMUP=300, MEASURE_FORCE=620, REPS=5).
#
# For each point:
#   - 30 s after the start it reads the env.txt of the run just created and stops if a
#     design key is not the expected one;
#   - at the end of the point it applies the treclassi.sh gate (dropped > 0 or
#     errors > 1%) to each repetition and checks that there are 5.
# The points that do not pass are redone ONCE only, at the end of the queue.
# No analysis of the results: only gate and configuration.
#
# Usage (on the lab):
#   nohup setsid bash tools/replica-20260924.sh \
#     > harness/results/replica-20260924.log 2>&1 < /dev/null &
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../harness/load"
RES=../results
MAN="$RES/replica-20260924.tsv"

# The variables that docker-compose.yml and treclassi.sh read from the environment
# must come from .env and the defaults, as on 21 September (in that env.txt
# none was set in the shell).
unset BACKLOG BLOCK_CLASSES BUDGET_LOW BUDGET_WAIT CACHE_TTL CPUSET_APP \
      CPUSET_DB CPUSET_K6 CPUSET_OBS CPUSET_VARNISH DB_POOL_MAX DB_POOL_MIN \
      OBJECT_TTL TARGET THREADS VARNISH_H_SIZE VARNISH_L_SIZE VARNISH_SIZE \
      MODEL TOTAL_MB CORPUS AGENT_SESSION AGENT_SKEW MEASURE_FORCE

# name : AGENT_MUL : lambda : alpha : beta   (pre-registered order)
QUEUE="C12:2654435761:95:0.2947:0.1263
S12:3266489917:95:0.2947:0.1263
S36:3266489917:119:0.2353:0.3025
P0:2654435761:83:0.3373:0.0000
C36:2654435761:119:0.2353:0.3025"

# Preliminary checks: harness identical to the commit, no stack running.
git diff --quiet HEAD -- .. \
  || { echo "harness modified with respect to HEAD: stopping"; exit 1; }
[[ -z "$(docker ps -q)" ]] || { echo "containers already running: stopping"; exit 1; }
# The pre-registration must be in the commit that ends up in every env.txt.
git cat-file -e HEAD:docs/PREREG-replica-20260924.md 2>/dev/null \
  || { echo "pre-registration missing from the commit: stopping"; exit 1; }
echo "replica-20260924  commit $(git rev-parse --short HEAD)  start $(date -Is)"
[[ -f "$MAN" ]] || printf 'punto\trun\tesito\tinizio\n' > "$MAN"

FAILED=""

run_point() {
    local name="$1" mul="$2" lam="$3" a="$4" b="$5"
    local before dir pid start bad
    before=$(ls -d "$RES"/tre-* 2>/dev/null | sort | tail -1 || true)
    start=$(date -Is)
    printf '\n######## %s  AGENT_MUL=%s lambda=%s alpha=%s beta=%s  %s\n' \
        "$name" "$mul" "$lam" "$a" "$b" "$start"

    AGENT_MUL="$mul" AGENT_SCOPE=0.02 LAMBDA="$lam" REPS=5 GATE=0 \
        WARMUP=300 MEASURE_FORCE=620 POINTS="$a:$b" bash treclassi.sh < /dev/null &
    pid=$!

    # env.txt 30 seconds after the start
    sleep 30
    dir=$(ls -d "$RES"/tre-* | sort | tail -1)
    if [[ "$dir" == "$before" || ! -f "$dir/env.txt" ]]; then
        echo "env.txt not found: stopping"; kill "$pid" 2>/dev/null || true
        (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
    fi
    bad=0
    for kv in "AGENT_MUL=$mul" "AGENT_SCOPE=0.02" "LAMBDA=$lam" "REPS=5" "GATE=0" \
              "WARMUP=300" "MEASURE_FORCE=620" "POINTS=$a:$b"; do
        grep -qx "$kv" "$dir/env.txt" || { echo "  env.txt: $kv missing"; bad=1; }
    done
    for k in BUDGET_LOW BLOCK_CLASSES VARNISH_SIZE AGENT_SESSION AGENT_SKEW; do
        grep -q "^$k=" "$dir/env.txt" && { echo "  env.txt: $k set in the shell"; bad=1; }
    done
    if [[ "$bad" == 1 ]]; then
        echo "configuration different from the design: stopping"; kill "$pid" 2>/dev/null || true
        (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
    fi
    echo "  env.txt ok: $(basename "$dir")"

    wait "$pid" || echo "  treclassi.sh exited with code $?"

    # treclassi.sh gate, repetition by repetition, and number of repetitions
    local n g
    n=$(awk -F, 'NR>1' "$dir/points.csv" | wc -l)
    g=$(awk -F, 'NR>1 && ($12>0 || $13>0.01)' "$dir/points.csv" | wc -l)
    if [[ "$n" -eq 5 && "$g" -eq 0 ]]; then
        printf '%s\t%s\tok\t%s\n' "$name" "$(basename "$dir")" "$start" >> "$MAN"
        return 0
    fi
    echo "  GATE NOT PASSED: repetitions $n, outside gate $g"
    printf '%s\t%s\tgate(n=%s,fuori=%s)\t%s\n' "$name" "$(basename "$dir")" "$n" "$g" "$start" >> "$MAN"
    return 1
}

while IFS=: read -r name mul lam a b; do
    run_point "$name" "$mul" "$lam" "$a" "$b" || FAILED="$FAILED $name:$mul:$lam:$a:$b"
done <<< "$QUEUE"

# a single repetition per point, at the end of the queue, in the original order
for pt in $FAILED; do
    IFS=: read -r name mul lam a b <<< "$pt"
    run_point "$name-bis" "$mul" "$lam" "$a" "$b" || true
done

echo
echo "end $(date -Is)"
cat "$MAN"
