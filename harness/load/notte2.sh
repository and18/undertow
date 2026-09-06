#!/usr/bin/env bash
#
# C — il passaggio gratuito, misurato pulito. TRAV_SKIP attivo e alpha
#     basso perché la traversata non si avvolga: la misura riprende da
#     dove il warm-up si è fermato invece di ripercorrerlo.
# A — il controllo. Stessa cosa senza classe umana e a pari ritmo della
#     classe esaustiva: qui il passaggio gratuito non può esistere, e
#     quello che resta è il pavimento di auto-hit. La differenza C - A
#     è il free ride vero.
# B — la validazione del metodo. Se dopo la correzione hit_bassa non
#     dipende più dal warm-up, l'artefatto è chiuso.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

run() { printf '\n\033[1m######## %s ########\033[0m %s\n' "$1" "$(date +%H:%M)"; shift; env "$@" bash split.sh; }

for MB in 32 64 128 256 384; do
  run "C  cache=${MB}m  con umani" LAMBDA=110 ALPHA=0.25 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

for MB in 32 64 128 256 384; do
  run "A  cache=${MB}m  solo esaustiva" LAMBDA=28 ALPHA=1.00 TOTAL_MB=$MB \
      FRACTIONS=shared REPS=3 WARMUP=300 MEASURE=180
done

for W in 120 300 600; do
  run "B  warmup=${W}s" LAMBDA=110 ALPHA=0.25 TOTAL_MB=128 \
      FRACTIONS=shared REPS=3 WARMUP=$W MEASURE=180
done

echo; echo "Riepilogo: guarda hit bassa in ogni blocco."