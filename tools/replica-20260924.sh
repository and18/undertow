#!/usr/bin/env bash
#
# replica-20260924.sh - campagna di replica nello stesso giorno.
# Disegno, previsioni e regole: docs/PREREG-replica-20260924.md (scritto e
# committato PRIMA del lancio). Non modifica l'harness: chiama treclassi.sh
# cinque volte, una per punto, con la stessa configurazione dello sweep del
# 21 settembre (GATE=0, WARMUP=300, MEASURE_FORCE=620, REPS=5).
#
# Per ogni punto:
#   - 30 s dopo l'avvio legge env.txt del run appena creato e si ferma se una
#     chiave del disegno non e' quella attesa;
#   - a fine punto applica il gate di treclassi.sh (scartate > 0 oppure
#     errori > 1%) a ogni ripetizione e controlla che siano 5.
# I punti che non passano si rifanno UNA sola volta, a fine coda.
# Nessuna analisi dei risultati: solo gate e configurazione.
#
# Uso (sul lab):
#   nohup setsid bash tools/replica-20260924.sh \
#     > harness/results/replica-20260924.log 2>&1 < /dev/null &
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../harness/load"
RES=../results
MAN="$RES/replica-20260924.tsv"

# Le variabili che docker-compose.yml e treclassi.sh leggono dall'ambiente
# devono venire da .env e dai default, come il 21 settembre (in quell'env.txt
# nessuna era impostata nella shell).
unset BACKLOG BLOCK_CLASSES BUDGET_LOW BUDGET_WAIT CACHE_TTL CPUSET_APP \
      CPUSET_DB CPUSET_K6 CPUSET_OBS CPUSET_VARNISH DB_POOL_MAX DB_POOL_MIN \
      OBJECT_TTL TARGET THREADS VARNISH_H_SIZE VARNISH_L_SIZE VARNISH_SIZE \
      MODEL TOTAL_MB CORPUS AGENT_SESSION AGENT_SKEW MEASURE_FORCE

# nome : AGENT_MUL : lambda : alpha : beta   (ordine pre-registrato)
QUEUE="C12:2654435761:95:0.2947:0.1263
S12:3266489917:95:0.2947:0.1263
S36:3266489917:119:0.2353:0.3025
P0:2654435761:83:0.3373:0.0000
C36:2654435761:119:0.2353:0.3025"

# Controlli preliminari: harness identico al commit, nessuno stack attivo.
git diff --quiet HEAD -- .. \
  || { echo "harness modificato rispetto a HEAD: mi fermo"; exit 1; }
[[ -z "$(docker ps -q)" ]] || { echo "container gia' attivi: mi fermo"; exit 1; }
# La pre-registrazione deve essere nel commit che finisce in ogni env.txt.
git cat-file -e HEAD:docs/PREREG-replica-20260924.md 2>/dev/null \
  || { echo "pre-registrazione assente dal commit: mi fermo"; exit 1; }
echo "replica-20260924  commit $(git rev-parse --short HEAD)  inizio $(date -Is)"
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

    # env.txt a 30 secondi dall'avvio
    sleep 30
    dir=$(ls -d "$RES"/tre-* | sort | tail -1)
    if [[ "$dir" == "$before" || ! -f "$dir/env.txt" ]]; then
        echo "env.txt non trovato: mi fermo"; kill "$pid" 2>/dev/null || true
        (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
    fi
    bad=0
    for kv in "AGENT_MUL=$mul" "AGENT_SCOPE=0.02" "LAMBDA=$lam" "REPS=5" "GATE=0" \
              "WARMUP=300" "MEASURE_FORCE=620" "POINTS=$a:$b"; do
        grep -qx "$kv" "$dir/env.txt" || { echo "  env.txt: manca $kv"; bad=1; }
    done
    for k in BUDGET_LOW BLOCK_CLASSES VARNISH_SIZE AGENT_SESSION AGENT_SKEW; do
        grep -q "^$k=" "$dir/env.txt" && { echo "  env.txt: $k impostata nella shell"; bad=1; }
    done
    if [[ "$bad" == 1 ]]; then
        echo "configurazione diversa dal disegno: mi fermo"; kill "$pid" 2>/dev/null || true
        (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
    fi
    echo "  env.txt ok: $(basename "$dir")"

    wait "$pid" || echo "  treclassi.sh uscito con codice $?"

    # gate di treclassi.sh, ripetizione per ripetizione, e numero di ripetizioni
    local n g
    n=$(awk -F, 'NR>1' "$dir/points.csv" | wc -l)
    g=$(awk -F, 'NR>1 && ($12>0 || $13>0.01)' "$dir/points.csv" | wc -l)
    if [[ "$n" -eq 5 && "$g" -eq 0 ]]; then
        printf '%s\t%s\tok\t%s\n' "$name" "$(basename "$dir")" "$start" >> "$MAN"
        return 0
    fi
    echo "  GATE NON PASSATO: ripetizioni $n, fuori gate $g"
    printf '%s\t%s\tgate(n=%s,fuori=%s)\t%s\n' "$name" "$(basename "$dir")" "$n" "$g" "$start" >> "$MAN"
    return 1
}

while IFS=: read -r name mul lam a b; do
    run_point "$name" "$mul" "$lam" "$a" "$b" || FAILED="$FAILED $name:$mul:$lam:$a:$b"
done <<< "$QUEUE"

# una sola ripetizione per punto, a fine coda, nell'ordine originale
for pt in $FAILED; do
    IFS=: read -r name mul lam a b <<< "$pt"
    run_point "$name-bis" "$mul" "$lam" "$a" "$b" || true
done

echo
echo "fine $(date -Is)"
cat "$MAN"
