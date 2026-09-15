#!/usr/bin/env bash
#
# marginale2.sh - Barre d'errore sull'agente, e lo stesso disegno per il
# crawler. L'affermazione da sostenere non e' un numero sull'agente: e'
# che la calibrazione isolata sbaglia in modo ASIMMETRICO fra le due
# classi, misurata con metodologia identica.
#
# A  agente: 5 ripetizioni sui punti dove la pendenza cambia segno.
#    Il primo run (14 set) ha dato marginale +0,047 / +0,023 / -0,014 /
#    -0,070 con 2 ripetizioni e dispersione 0,1-0,5 req/s sul carico
#    all'origine: il segno dell'ultimo tratto e' a 2 sigma.
#
# B  crawler: umano e agente FISSI in valore assoluto (55 e 12 req/s),
#    crawler da 0 a 42. PREVISIONE REGISTRATA: marginale vicino a 1,0 e
#    leggermente sopra, perche' il crawler consuma residenza e peggiora
#    anche gli altri. Se esce ~1,0 piatto mentre l'agente e' decrescente
#    e negativo, l'asimmetria e' dimostrata.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift
    LAMBDA="$1" REPS="$4" GATE=0 WARMUP=300 POINTS="$2:$3" bash treclassi.sh
}

# A - agente, umano 55 + crawler 28 fissi, 5 ripetizioni
run "A agenti=0"   83  0.3373 0.0000 5
run "A agenti=12"  95  0.2947 0.1263 5
run "A agenti=24" 107  0.2617 0.2243 5
run "A agenti=36" 119  0.2353 0.3025 5

# B - crawler, umano 55 + agente 12 fissi
run "B crawler=0"   67  0.0000 0.1791 3
run "B crawler=14"  81  0.1728 0.1481 3
run "B crawler=28"  95  0.2947 0.1263 3
run "B crawler=42" 109  0.3853 0.1101 3

echo
echo "================================================================"
echo "  A: pendenza del carico all'origine contro richieste agentiche,"
echo "     con 5 ripetizioni per avere una dispersione."
echo "  B: stessa pendenza per il crawler. Controllo: h uman deve"
echo "     restare piatto in entrambi i blocchi."
