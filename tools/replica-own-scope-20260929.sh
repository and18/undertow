#!/usr/bin/env bash
#
# replica-own-scope-20260929.sh - rerun of scopes 0.06 and 0.20 of A1
# (S12 and S36 for each) with the exhaustive traversal in a scenario of its own
# (TRAV_MODE=scen). Copy of tools/replica-own-20260928.sh: same REPS,
# WARMUP, MEASURE_FORCE, GATE and checks; the points and AGENT_SCOPE change.
# Design, predictions and criteria: docs/PREREG-lab-trav-own-scope-20260929.md
# (written and committed BEFORE the launch). It does not modify the harness: it calls
# treclassi.sh four times, once per point.
#
# Extra check: after the first repetition of the first point, the per-class
# counts of k6 (hit + miss) must match the configured rates within
# 2% (exhaustive alpha*lambda, agentic beta*lambda, human the rest, for 620 s);
# otherwise the script stops.
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
#   nohup setsid bash tools/replica-own-scope-20260929.sh \
#     > harness/results/replica-own-scope-20260929.log 2>&1 < /dev/null &
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../harness/load"
RES=../results
MAN="$RES/replica-own-scope-20260929.tsv"

# The variables that docker-compose.yml and treclassi.sh read from the environment
# must come from .env and the defaults, as on 21 September (in that env.txt
# none was set in the shell).
unset BACKLOG BLOCK_CLASSES BUDGET_LOW BUDGET_WAIT CACHE_TTL CPUSET_APP \
      CPUSET_DB CPUSET_K6 CPUSET_OBS CPUSET_VARNISH DB_POOL_MAX DB_POOL_MIN \
      OBJECT_TTL TARGET THREADS VARNISH_H_SIZE VARNISH_L_SIZE VARNISH_SIZE \
      MODEL TOTAL_MB CORPUS AGENT_SESSION AGENT_SKEW MEASURE_FORCE TRAV_MODE

# name : AGENT_MUL : lambda : alpha : beta : AGENT_SCOPE   (pre-registered order)
QUEUE="S12_006:3266489917:95:0.2947:0.1263:0.06
S36_006:3266489917:119:0.2353:0.3025:0.06
S12_020:3266489917:95:0.2947:0.1263:0.20
S36_020:3266489917:119:0.2353:0.3025:0.20"

# Preliminary checks: harness identical to the commit, no stack running.
git diff --quiet HEAD -- .. \
  || { echo "harness modified with respect to HEAD: stopping"; exit 1; }
[[ -z "$(docker ps -q)" ]] || { echo "containers already running: stopping"; exit 1; }
# The pre-registration must be in the commit that ends up in every env.txt.
git cat-file -e HEAD:docs/PREREG-lab-trav-own-scope-20260929.md 2>/dev/null \
  || { echo "pre-registration missing from the commit: stopping"; exit 1; }
echo "replica-own-scope-20260929  commit $(git rev-parse --short HEAD)  start $(date -Is)"
[[ -f "$MAN" ]] || printf 'punto\trun\tesito\tinizio\n' > "$MAN"

FAILED=""
FIRST=1

# Per-class counts of the first repetition against the configured rates (2%).
check_counts() {
    local j="$1" lam="$2" a="$3" b="$4"
    jq -r --arg l "$lam" --arg a "$a" --arg b "$b" '
      def n(x): (x // 0);
      def c(k): n(.metrics["ut_hit_" + k].values.count) + n(.metrics["ut_miss_" + k].values.count);
      ($l|tonumber) as $l | ($a|tonumber) as $a | ($b|tonumber) as $b |
      [ ["exhaustive", c("traversal"), $a*$l*620],
        ["agentic",    c("agent"),     $b*$l*620],
        ["human",      c("zipf"),      (1-$a-$b)*$l*620] ]
      | map(. + [ (if .[2] > 0 then ((.[1] - .[2]) / .[2]) else 0 end) ])
      | .[] | @tsv' "$j" | awk -F'\t' '
        { printf "  counts %-10s k6 %6d  expected %9.1f  deviation %+6.2f%%\n", $1, $2, $3, 100*$4
          if ($4 > 0.02 || $4 < -0.02) bad=1 }
        END { exit bad }'
}

run_point() {
    local name="$1" mul="$2" lam="$3" a="$4" b="$5" sc="$6"
    local before dir pid start bad
    before=$(ls -d "$RES"/tre-* 2>/dev/null | sort | tail -1 || true)
    start=$(date -Is)
    printf '\n######## %s  AGENT_MUL=%s lambda=%s alpha=%s beta=%s scope=%s  %s\n' \
        "$name" "$mul" "$lam" "$a" "$b" "$sc" "$start"

    TRAV_MODE=scen AGENT_MUL="$mul" AGENT_SCOPE="$sc" LAMBDA="$lam" REPS=5 GATE=0 \
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
    for kv in "TRAV_MODE=scen" "AGENT_MUL=$mul" "AGENT_SCOPE=$sc" "LAMBDA=$lam" "REPS=5" "GATE=0" \
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

    # first point only: per-class counts of the first repetition
    if [[ "$FIRST" == 1 ]]; then
        FIRST=0
        local j="$dir/m-a$a-b$b-1.json" waited=0
        while [[ ! -f "$j" ]]; do
            kill -0 "$pid" 2>/dev/null || { echo "treclassi.sh ended without repetition 1: stopping"; exit 1; }
            sleep 20; waited=$((waited + 20))
            [[ "$waited" -gt 2400 ]] && { echo "repetition 1 missing after 40 min: stopping"
                kill "$pid" 2>/dev/null || true
                (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1; }
        done
        sleep 5
        if ! check_counts "$j" "$lam" "$a" "$b"; then
            echo "per-class counts outside 2%: stopping"; kill "$pid" 2>/dev/null || true
            (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
        fi
        echo "  per-class counts ok (within 2%)"
    fi

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

while IFS=: read -r name mul lam a b sc; do
    run_point "$name" "$mul" "$lam" "$a" "$b" "$sc" || FAILED="$FAILED $name:$mul:$lam:$a:$b:$sc"
done <<< "$QUEUE"

# a single repetition per point, at the end of the queue, in the original order
for pt in $FAILED; do
    IFS=: read -r name mul lam a b sc <<< "$pt"
    run_point "$name-bis" "$mul" "$lam" "$a" "$b" "$sc" || true
done

echo
echo "end $(date -Is)"
cat "$MAN"
