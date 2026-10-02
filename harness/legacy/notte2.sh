#!/usr/bin/env bash
#
# Campagna del 3 settembre. Rimisura tutto quello che dipendeva dal
# passaggio gratuito, dopo la correzione di TRAV_SKIP.
#
# Il bug: warm-up e misura sono due invocazioni k6 separate, quindi
# iterationInTest ripartiva da zero e la classe esaustiva rivisitava
# esattamente gli oggetti inseriti WARMUP secondi prima. hit_bassa
# misurava la curva di sopravvivenza della cache, non il free ride.
# Firma: a 128 MB vale 0,163 con warm-up 180 s e 0,089 con 300 s.
#
# Con TRAV_SKIP la misura riprende la traversata dove il warm-up l'ha
# lasciata, quindi la classe esaustiva non incontra i propri inserimenti
# e tutto ciò che trova in cache ce l'ha messo la classe umana.
#
# alpha=0.25 e non 0.50: a 0.50 la traversata si avvolge sul corpus
# (26.400 richieste su 16.954 oggetti) e i ripassaggi tornano da un'altra
# porta. A 0.25 sono 13.200, sotto la dimensione del corpus.
#
# smoke  la correzione funziona? deve dare hit bassa ~ 0
# C      il passaggio gratuito vero, contro il rapporto cache/corpus
# A      controllo senza classe umana: nessuno riempie la cache per lo
#        scanner, quindi hit bassa deve restare ~ 0. NON è un termine da
#        sottrarre a C: senza la classe umana il tasso di inserimento è
#        quasi dimezzato e la cache si comporta diversamente.
# D      il costo del partizionamento rimisurato pulito (era O8b)
# B      hit bassa non deve più dipendere dal warm-up
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() {
    printf '\n\033[1m######## %s ########\033[0m  %s\n' "$1" "$(date +%H:%M)"
    shift
    env "$@" bash split.sh
}

run "smoke  solo esaustiva, 128m" LAMBDA=28 ALPHA=1.00 TOTAL_MB=128 \
    FRACTIONS=shared REPS=1 WARMUP=300 MEASURE=180

for MB in 32 64 128 256 384; do
  run "C  cache=${MB}m  con classe umana" LAMBDA=110 ALPHA=0.25 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

for MB in 32 64 128 256 384; do
  run "A  cache=${MB}m  solo esaustiva" LAMBDA=28 ALPHA=1.00 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

run "D  costo del partizionamento, generatore corretto" LAMBDA=110 ALPHA=0.25 \
    TOTAL_MB=128 FRACTIONS="shared 0.75 1.00 shared" REPS=3 WARMUP=300 MEASURE=180

for W in 120 300 600; do
  run "B  warmup=${W}s" LAMBDA=110 ALPHA=0.25 TOTAL_MB=128 \
      FRACTIONS=shared REPS=3 WARMUP=$W MEASURE=180
done

echo
echo "================================================================"
echo "  smoke e A: hit bassa deve essere ~ 0. Se non lo è, TRAV_SKIP non"
echo "  funziona e tutto il resto della notte è da buttare."
echo "  C: il passaggio gratuito. Cresce col rapporto cache/corpus?"
echo "  D: shared due volte come controllo di deriva, devono coincidere."
echo "  B: le tre righe devono dare lo stesso hit bassa."