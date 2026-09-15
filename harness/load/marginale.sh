#!/usr/bin/env bash
#
# marginale.sh - Il costo marginale, misurato invece che dedotto.
#
# Ogni campagna finora ha tenuto il volume TOTALE costante, quindi far
# crescere beta SOSTITUIVA traffico umano con traffico agentico. Da li'
# si ricava un effetto di sostituzione, non il costo marginale.
#
# Qui umano e esaustivo restano fissi in valore ASSOLUTO (55 e 28 req/s)
# e si aggiungono agenti. La pendenza d(origine)/d(richieste agentiche)
# E' il costo marginale: la grandezza di cui un controllore ha bisogno e
# che nessuna calibrazione in isolamento produce.
#
# PREVISIONE REGISTRATA PRIMA DELLA MISURA
#   Se il marginale vale ~0,05 (stima indiretta dai dati del 9-11 set),
#   il carico all'origine sale di ~1,8 req/s da 0 a 36 agenti/s.
#   Se invece vale quanto il costo medio a quota bassa (0,27), sale di
#   ~9,7. I due scenari sono distinguibili a occhio.
#
# La calibrazione isolata della classe agentica dava 0,102 a 5 req/s e
# 0,002 a 22 req/s: se il marginale e' piatto intorno a 0,05, allora
# nessuna delle due calibrazioni isolate lo approssima, e la scelta del
# volume di calibrazione decide l'errore.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## agenti=%s req/s  lambda=%s ########\033[0m  %s\n' \
        "$1" "$2" "$(date +%H:%M)"
    LAMBDA="$2" REPS=2 GATE=0 WARMUP=300 POINTS="$3:$4" bash treclassi.sh
}

#   agenti  lambda  alpha    beta     (umano sempre 55, esaustivo sempre 28)
run  0      83      0.3373   0.0000
run  6      89      0.3146   0.0674
run  12     95      0.2947   0.1263
run  24     107     0.2617   0.2243
run  36     119     0.2353   0.3025

echo
echo "================================================================"
echo "  Costo marginale = variazione di orig rps / variazione di"
echo "  richieste agentiche al secondo. Umano e esaustivo sono fissi,"
echo "  quindi la pendenza e' attribuibile alla sola classe agentica."
echo "  Controllo: h uman e h trav devono restare quasi piatti. Se si"
echo "  muovono molto, la classe agentica sta alterando anche gli altri"
echo "  e il marginale include un effetto incrociato da dichiarare."
