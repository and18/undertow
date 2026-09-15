#!/usr/bin/env bash
#
# costmap.sh - La mappa dei costi, e il test che puo' uccidere N1.
#
# IPOTESI SOTTO ESAME
#
# Il costo per richiesta di una classe non e' una proprieta' della classe:
# dipende dalla composizione del traffico. Se e' vero, un controllore di
# ammissione che usa costi calibrati in isolamento - cioe' tutti quelli
# pubblicati: DAGOR con priorita' dichiarate, Rajomon con prezzi per API,
# UCP con curve di utilita' isolate - usa un input falso.
#
# E l'errore si auto-conferma: se strozza la classe agentica perche' la
# crede cara, ne abbassa la quota, e a quota bassa quella classe E'
# davvero cara. La misura successiva gli da' ragione. Aggancio a un punto
# operativo peggiore con retroazione positiva.
#
# PRIMA DI COSTRUIRE QUALSIASI CONTROLLORE si misura la mappa e si calcola
# a tavolino la decisione che ciascuno prenderebbe. Se coincidono, l'idea
# muore in una notte invece che in due settimane.
#
# BLOCCO 1 - isolamento. Ogni classe da sola, ai volumi che ha nelle
#   miscele del blocco 2. E' la calibrazione del controllore statico.
#   Nota: non esiste un volume "giusto" a cui calibrare, ed e' parte del
#   problema.
#
# BLOCCO 2 - miscele. La stessa grandezza misurata in situ.
#   La differenza fra blocco 1 e blocco 2, allo stesso volume di classe,
#   E' l'errore del costo esogeno.
#
# BLOCCO 3 - la minaccia. Con TTL 60 s il beneficio di sistema del
#   traffico agentico quasi sparisce (R9: da -7,2% a -0,6%). Se non
#   esiste un punto operativo migliore, il controllore statico non sta
#   sbagliando niente di importante e N1 vale solo per contenuto che
#   cambia lentamente. Va saputo ORA, non dopo aver costruito.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift; env "$@" bash treclassi.sh
}

# --- blocco 1: isolamento -------------------------------------------------
# traversal: POINTS alpha=1.00 perche' MEASURE deve coprire il corpus
run "ISO traversal @22"  MODEL=traversal LAMBDA=22 REPS=2 POINTS="1.00:0.00"
run "ISO traversal @44"  MODEL=traversal LAMBDA=44 REPS=2 POINTS="1.00:0.00"
run "ISO agent @5"       MODEL=agent     LAMBDA=5  REPS=2 POINTS="0.00:1.00"
run "ISO agent @22"      MODEL=agent     LAMBDA=22 REPS=2 POINTS="0.00:1.00"
run "ISO zipf @44"       MODEL=zipf      LAMBDA=44 REPS=2 POINTS="0.00:0.00"
run "ISO zipf @88"       MODEL=zipf      LAMBDA=88 REPS=2 POINTS="0.00:0.00"

# --- blocco 2: miscele ----------------------------------------------------
run "MIX griglia" LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.20:0.05 0.20:0.20 0.30:0.05 0.30:0.20 0.40:0.05 0.40:0.20"

# --- blocco 3: la stessa griglia con scadenza realistica ------------------
run "MIX griglia TTL=60s" OBJECT_TTL=60 LAMBDA=110 REPS=2 GATE=0 \
    POINTS="0.25:0.02 0.25:0.10 0.25:0.20 0.25:0.30"

echo
echo "================================================================"
echo "  Costo per richiesta di una classe = 1 - hit ratio della classe."
echo "  ISO: quello che crede un controllore statico."
echo "  MIX: quello che e' vero in situ."
echo "  L'errore e' la differenza, allo stesso volume di classe."
echo "  Blocco 3: se a TTL 60 il carico all'origine non scende piu' al"
echo "  crescere di beta, non c'e' un punto operativo migliore da"
echo "  mancare, e N1 vale solo per contenuto lento."
