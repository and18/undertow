#!/usr/bin/env bash
#
# scopesweep.sh - L'ultimo esperimento: la sensibilita' del costo di una classe
# in funzione di dove sta il suo insieme di lavoro rispetto alla capienza.
#
# IPOTESI (registrata prima del run)
#   La sensibilita' del costo per richiesta di una classe alla composizione del
#   traffico non dipende dal fatto che la classe abbia localita', ma dal
#   rapporto fra il suo insieme di lavoro e la capienza della cache.
#
# PREVISIONE (forma, non soglia)
#   Misurando la sensibilita' S(scope) = escursione del miss ratio agentico fra
#   quota 13% e quota 30%, la relazione S contro (insieme di lavoro / capienza)
#   deve essere NON MONOTONA: bassa quando l'insieme e' molto sotto la capienza,
#   massima nell'intorno della capienza, di nuovo bassa quando e' molto sopra.
#
# FALSIFICAZIONE
#   S monotona in scope, oppure S statisticamente indistinguibile fra i tre
#   punti. Il criterio e' un test sulla forma, non una soglia scelta a mano:
#   serve S(centrale) maggiore di S(basso) E di S(alto), ciascuno con
#   separazione di almeno 2 errori standard combinati.
#
# SE E' NEGATIVO
#   Il meccanismo del confine di residenza cade. Resta la caratterizzazione
#   empirica (4,09x contro 1,02x e 1,03x) senza spiegazione meccanicistica:
#   livello 2, pubblicabile, piu' debole.
#
# PREREQUISITI, entrambi obbligatori
#   1. capacity.sh eseguito: la capienza reale e' nota
#   2. patch-agentenv.py applicato: AGENT_SCOPE arriva dentro k6
#
# Uso:  SCOPE_LOW=... SCOPE_HIGH=... bash scopesweep.sh
#   I due valori si ricavano dalla tabella stampata da capacity.sh:
#   SCOPE_LOW  -> insieme ~0,1x la capienza
#   SCOPE_HIGH -> insieme ~10x la capienza
#   Il punto centrale (scope 0,02) NON si rilancia: e' gia' misurato ieri.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

: "${SCOPE_LOW:?manca SCOPE_LOW - prendilo dalla tabella di capacity.sh}"
: "${SCOPE_HIGH:?manca SCOPE_HIGH - prendilo dalla tabella di capacity.sh}"
REPS="${REPS:-5}"

echo "sweep AGENT_SCOPE: $SCOPE_LOW e $SCOPE_HIGH   ($REPS ripetizioni)"
echo "punto centrale 0.02 gia' misurato il 21 settembre, non rilanciato"
echo "mappatura separata attiva in tutti i punti (AGENT_MUL=3266489917)"
echo

for SC in "$SCOPE_LOW" "$SCOPE_HIGH"; do
  for PT in "95:0.2947:0.1263" "119:0.2353:0.3025"; do
    LAM="${PT%%:*}"; REST="${PT#*:}"; A="${REST%%:*}"; B="${REST##*:}"
    printf '\n######## scope=%s  quota=%s  lambda=%s ########  %s\n' \
      "$SC" "$B" "$LAM" "$(date +%H:%M)"
    AGENT_MUL=3266489917 AGENT_SCOPE="$SC" \
      LAMBDA="$LAM" REPS="$REPS" GATE=0 WARMUP=300 MEASURE_FORCE=620 \
      POINTS="$A:$B" bash treclassi.sh
  done
done

echo
echo "================================================================"
echo "  Confronto da fare: per ciascuno scope, escursione del miss"
echo "  ratio agentico fra quota 13% e quota 30%."
echo "  Riferimento gia' misurato a scope 0,02: 0,180 -> 0,044 = 4,09x"
echo
echo "  Estrarre con:"
echo "    cd ~/undertow/harness/results"
echo "    for d in \$(ls -td tre-* | head -4); do"
echo "      printf '%-26s scope=%-8s ' \"\$d\" \\"
echo "        \"\$(grep -oP 'AGENT_SCOPE=\\K.*' \$d/env.txt)\""
echo "      tail -n +2 \$d/points.csv | awk -F, '{s+=\$9; n++} END {printf \"h_agent=%.3f\\n\", s/n}'"
echo "    done"
