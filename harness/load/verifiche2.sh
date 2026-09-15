#!/usr/bin/env bash
#
# verifiche2.sh - I due controlli che mancano prima di scrivere.
#
# D  DURATA. Minaccia diretta a N1. L'hit ratio della classe agentica
#    cresce finche' il suo insieme di lavoro non e' residente. A beta=0,02
#    quella classe emette 1364 richieste in 620 s su ~1000 URL distinti:
#    passa sul proprio insieme 1,4 volte. A beta=0,30 ne emette 20460:
#    ci passa 20 volte. Quindi "il costo dipende dalla quota" potrebbe
#    essere "il costo dipende da quante richieste hai gia' fatto".
#
#    Test: quota FISSA, durata variabile. Se a beta=0,02 l'hit ratio sale
#    da 0,73 verso 0,97 allungando la misura, l'endogeneita' e' un
#    artefatto della finestra e N1 muore. Se si ferma intorno a 0,75,
#    l'effetto e' reale.
#
#    Il punto di controllo a beta=0,30 e' gia' saturo per costruzione e
#    non deve muoversi: se si muove, il problema e' altrove.
#
# M  MEDIATORE. R2 e' l'unica affermazione causale del lavoro e risale al
#    16 agosto, con il generatore che usava l'offset casuale ritirato il
#    26. Va rifatta sotto il protocollo corrente e con tre classi.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift; env "$@" bash treclassi.sh
}

for M in 620 1860 3720; do
  run "D  durata=${M}s  beta=0.02" MEASURE_FORCE=$M LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.25:0.02"
done
run "D  controllo  durata=1860s  beta=0.30" MEASURE_FORCE=1860 LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.30"

for C in 64 128 256 512; do
  run "M  cache=${C}m" TOTAL_MB=$C LAMBDA=110 REPS=2 GATE=0 \
      POINTS="0.00:0.05 0.30:0.05"
done

echo
echo "================================================================"
echo "  D: se h agente a beta=0,02 sale con la durata, N1 e' un"
echo "     artefatto della finestra di misura. Il controllo a beta=0,30"
echo "     deve restare fermo."
echo "  M: il ginocchio deve spostarsi o sparire al crescere della cache."
echo "     E' la sola prova causale del lavoro e va rifatta pulita."
