#!/usr/bin/env bash
#
# verifiche.sh - Le tre prove che possono chiudere la direzione.
#
# A  TTL. Il costo endogeno della classe agentica poggia sulla residenza
#    di un insieme piccolo. Con una scadenza realistica quella residenza
#    sparisce e l'effetto con lei. Previsione registrata prima della
#    misura: crollo fra TTL 30 e 120 s, con la classe agentica che perde
#    molto piu' di quella umana (intervallo di ritorno ~45 s contro
#    frazioni di secondo).
#
# B  Endogeneita' su un intervallo piu' fitto. Se il costo unitario della
#    classe agentica dipende dalla sua stessa quota, la curva deve essere
#    monotona e non un artefatto di due punti.
#
# C  Secondo collo di bottiglia. Finora satura sempre la CPU di
#    PostgreSQL. Stringendo il pool di connessioni sotto il pool di
#    thread, la risorsa che satura cambia natura: si esaurisce per posti,
#    non per calcolo. Se il ginocchio resta allo stesso rho, la
#    generalita' e' dimostrata; se scende, abbiamo trovato la variabile
#    mancante (la variabilita' del tempo di servizio).
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() { printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"; shift; env "$@" bash treclassi.sh; }

for T in 0 300 120 60 30; do
  run "A  TTL=${T}s" OBJECT_TTL=$T LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.25:0.02 0.25:0.20"
done

run "B  endogeneita' della classe agentica" LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.02 0.25:0.05 0.25:0.10 0.25:0.15 0.25:0.20 0.25:0.30"

for P in 4 12; do
  run "C  pool DB=${P}" DB_POOL_MAX=$P LAMBDA=160 REPS=2 GATE=0 \
      POINTS="0.00:0.05 0.30:0.05 0.40:0.05"
done

echo
echo "================================================================"
echo "  A: se hit agente crolla fra TTL 120 e 30, l'effetto e' un"
echo "     artefatto del contenuto immutabile e la direzione e' chiusa."
echo "  B: la curva deve essere monotona su sei punti, non due."
echo "  C: se il ginocchio resta a rho 0,89-0,97 con pool 4, la soglia"
echo "     e' una proprieta' delle code e non del nostro database."
