#!/usr/bin/env bash
#
# replica-own-20260928.sh - rilancio dei 5 punti della replica con la
# traversata esaustiva in uno scenario proprio (TRAV_MODE=scen).
# Copia di tools/replica-20260924.sh: stesso ordine, stessi REPS, WARMUP,
# MEASURE_FORCE e GATE; cambia solo TRAV_MODE=scen.
# Disegno, previsioni e criteri: docs/PREREG-lab-trav-own-20260928.md (scritto
# e committato PRIMA del lancio). Non modifica l'harness: chiama treclassi.sh
# cinque volte, una per punto.
#
# Controllo in piu': dopo la prima ripetizione del primo punto, i conteggi per
# classe di k6 (hit + miss) devono coincidere con i rate configurati entro il
# 2% (esaustiva alpha*lambda, agentica beta*lambda, umana il resto, per 620 s);
# altrimenti lo script si ferma.
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
#   nohup setsid bash tools/replica-own-20260928.sh \
#     > harness/results/replica-own-20260928.log 2>&1 < /dev/null &
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../harness/load"
RES=../results
MAN="$RES/replica-own-20260928.tsv"

# Le variabili che docker-compose.yml e treclassi.sh leggono dall'ambiente
# devono venire da .env e dai default, come il 21 settembre (in quell'env.txt
# nessuna era impostata nella shell).
unset BACKLOG BLOCK_CLASSES BUDGET_LOW BUDGET_WAIT CACHE_TTL CPUSET_APP \
      CPUSET_DB CPUSET_K6 CPUSET_OBS CPUSET_VARNISH DB_POOL_MAX DB_POOL_MIN \
      OBJECT_TTL TARGET THREADS VARNISH_H_SIZE VARNISH_L_SIZE VARNISH_SIZE \
      MODEL TOTAL_MB CORPUS AGENT_SESSION AGENT_SKEW MEASURE_FORCE TRAV_MODE

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
git cat-file -e HEAD:docs/PREREG-lab-trav-own-20260928.md 2>/dev/null \
  || { echo "pre-registrazione assente dal commit: mi fermo"; exit 1; }
echo "replica-own-20260928  commit $(git rev-parse --short HEAD)  inizio $(date -Is)"
[[ -f "$MAN" ]] || printf 'punto\trun\tesito\tinizio\n' > "$MAN"

FAILED=""
FIRST=1

# Conteggi per classe della prima ripetizione contro i rate configurati (2%).
check_counts() {
    local j="$1" lam="$2" a="$3" b="$4"
    jq -r --arg l "$lam" --arg a "$a" --arg b "$b" '
      def n(x): (x // 0);
      def c(k): n(.metrics["ut_hit_" + k].values.count) + n(.metrics["ut_miss_" + k].values.count);
      ($l|tonumber) as $l | ($a|tonumber) as $a | ($b|tonumber) as $b |
      [ ["esaustiva", c("traversal"), $a*$l*620],
        ["agentica",  c("agent"),     $b*$l*620],
        ["umana",     c("zipf"),      (1-$a-$b)*$l*620] ]
      | map(. + [ (if .[2] > 0 then ((.[1] - .[2]) / .[2]) else 0 end) ])
      | .[] | @tsv' "$j" | awk -F'\t' '
        { printf "  conteggi %-9s k6 %6d  attesi %9.1f  scarto %+6.2f%%\n", $1, $2, $3, 100*$4
          if ($4 > 0.02 || $4 < -0.02) bad=1 }
        END { exit bad }'
}

run_point() {
    local name="$1" mul="$2" lam="$3" a="$4" b="$5"
    local before dir pid start bad
    before=$(ls -d "$RES"/tre-* 2>/dev/null | sort | tail -1 || true)
    start=$(date -Is)
    printf '\n######## %s  AGENT_MUL=%s lambda=%s alpha=%s beta=%s  %s\n' \
        "$name" "$mul" "$lam" "$a" "$b" "$start"

    TRAV_MODE=scen AGENT_MUL="$mul" AGENT_SCOPE=0.02 LAMBDA="$lam" REPS=5 GATE=0 \
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
    for kv in "TRAV_MODE=scen" "AGENT_MUL=$mul" "AGENT_SCOPE=0.02" "LAMBDA=$lam" "REPS=5" "GATE=0" \
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

    # solo il primo punto: conteggi per classe della prima ripetizione
    if [[ "$FIRST" == 1 ]]; then
        FIRST=0
        local j="$dir/m-a$a-b$b-1.json" waited=0
        while [[ ! -f "$j" ]]; do
            kill -0 "$pid" 2>/dev/null || { echo "treclassi.sh terminato senza la ripetizione 1: mi fermo"; exit 1; }
            sleep 20; waited=$((waited + 20))
            [[ "$waited" -gt 2400 ]] && { echo "ripetizione 1 assente dopo 40 min: mi fermo"
                kill "$pid" 2>/dev/null || true
                (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1; }
        done
        sleep 5
        if ! check_counts "$j" "$lam" "$a" "$b"; then
            echo "conteggi per classe fuori dal 2%: mi fermo"; kill "$pid" 2>/dev/null || true
            (cd .. && docker compose --profile load down --remove-orphans >/dev/null 2>&1); exit 1
        fi
        echo "  conteggi per classe ok (entro 2%)"
    fi

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
