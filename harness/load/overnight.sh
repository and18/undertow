#!/usr/bin/env bash
#
# overnight.sh - Quattro campagne in sequenza, con controllo di deriva.
#
# COSA CHIUDE, IN ORDINE DI IMPORTANZA
#
#   1. RETRY   il costo del budget e' lavoro perso o solo lavoro
#              posticipato? Se la classe batch che rispetta Retry-After
#              recupera il throughput, il conflitto fra classi e'
#              apparente e la mitigazione non costa nulla.
#
#   2. POOL    la relazione dipende dalla dimensione del pool? Il
#              confine di stabilita' e' stato osservato a THREADS=8 in
#              tutte e cinque le campagne precedenti. Se a 4 e 12 il
#              ginocchio resta alla stessa occupazione, la
#              normalizzazione e' dimostrata e non assunta.
#
#   3. F2      rimisura degli hit ratio per classe con l'offset
#              deterministico. I valori precedenti sono ritrattati
#              (findings.md, 2026-08-26) e con essi la decomposizione
#              bidirezionale.
#
#   4. BAND    la banda di instabilita' esiste su questa macchina? Su
#              x86 la dispersione al ginocchio era oltre il 300%, su ARM
#              il 4%. Venti ripetizioni su passo fine dicono se il
#              fenomeno e' reale o era variabilita' della piattaforma.
#
# CONTROLLO DI DERIVA
#
# Fra una campagna e l'altra si rimisura lo stesso punto fisso. Se il p99
# di riferimento cambia oltre il 30%, la macchina non e' piu' quella di
# prima e le campagne successive non sono confrontabili: lo script si
# ferma invece di produrre dati non comparabili. E' successo il
# 2026-08-18, quando PostgreSQL si e' scaldato durante una campagna e il
# ginocchio e' sparito.
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

# Punto fisso di controllo: alpha 0.25, lambda 220, budget spento.
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
log "riferimento iniziale: p99 alta = ${REF} ms"
[[ "$REF" -lt 100 ]] && { echo "riferimento implausibile, mi fermo" | tee -a "$LOG"; exit 1; }

drift_ok() {
    local now pct
    now=$(checkpoint)
    pct=$(awk -v a="$REF" -v b="$now" 'BEGIN{printf "%.0f", 100*(b-a)/a}')
    log "controllo deriva: ${now} ms contro ${REF} ms  (${pct}%)"
    awk -v p="$pct" 'BEGIN{exit !(p<-30 || p>30)}' && {
        echo "DERIVA OLTRE IL 30% — campagne successive non confrontabili" | tee -a "$LOG"
        return 1; }
    return 0
}

# --- 1. RETRY ------------------------------------------------------------
log "1/4  RETRY — il budget costa lavoro o solo tempo?"
OUT="$BASE/retry" LAMBDA=220 ALPHA=0.25 BUDGETS="0 5 4" REPS=5 \
    RETRY_MAX=3 MEASURE=300 bash load/budget.sh >> "$LOG" 2>&1
restore_env

drift_ok || exit 1

# --- 2. POOL -------------------------------------------------------------
# Il ritmo si scala con la dimensione del pool per tenere costante
# l'occupazione attesa: e' il senso della normalizzazione.
log "2/4  POOL — il confine dipende dalla dimensione del pool?"
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
log "3/4  F2 — hit ratio per classe, con offset deterministico"
OUT="$BASE/f2" LAMBDA=220 ALPHAS="0.00 0.10 0.20 0.30 0.40 0.50" \
    REPS=3 bash load/sweep.sh >> "$LOG" 2>&1

drift_ok || exit 1

# --- 4. BAND -------------------------------------------------------------
log "4/4  BAND — la transizione e' bimodale o solo ripida?"
OUT="$BASE/band" LAMBDA=220 ALPHAS="0.22 0.24 0.26 0.28" \
    REPS=20 bash load/sweep.sh >> "$LOG" 2>&1

log "tutte le campagne completate"
echo "risultati in $BASE" | tee -a "$LOG"
ls -d "$BASE"/*/ | tee -a "$LOG"