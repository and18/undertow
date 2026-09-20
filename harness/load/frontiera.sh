#!/usr/bin/env bash
#
# frontiera.sh - Il buco nella frontiera lavoro/latenza.
#
# LA DOMANDA
#
# La campagna del 19 settembre ha prodotto cinque punti al ginocchio
# (lambda=185, alpha=0,35, beta=0,10, cache 128 MB):
#
#     politica                 servite    p99 umano
#     A  nessuna               114.692      555,4 ms
#     D6 budget 6              111.384      212,3 ms
#     D4 budget 4              107.596      136,4 ms
#     B  blocco esaustiva       86.911       57,9 ms
#     C  blocco esaust+agent    84.067       57,8 ms
#
# C e' Pareto-dominata da B: stessa latenza, 2.844 richieste servite in
# meno. Quella dominanza e' gia' dimostrata e non richiede altro.
#
# Ma fra D4 (136 ms) e B (58 ms) non c'e' nessun punto. Non sappiamo se
# esista un budget con rinvio che raggiunga la latenza del blocco
# servendo piu' di 86.911 richieste, cioe' se il RINVIO DOMINI IL BLOCCO
# e non solo la sua variante piu' aggressiva.
#
# Questo script riempie il buco: budget 1, 2, 3. Gli altri punti sono
# gia' misurati allo stesso punto operativo e si riusano.
#
# ESITI
#   p99 <= 60 ms con servite > 86.911  ->  il rinvio domina il blocco
#   la curva passa sopra B ma non lo raggiunge in latenza
#                                      ->  i due meccanismi occupano
#                                          regioni diverse della frontiera
#   il rinvio resta sempre sotto B     ->  il blocco e' sulla frontiera
#
# FALSIFICA la tesi della dominanza: se a budget 1 il p99 umano non
# scende sotto ~90 ms, il rinvio non raggiunge il regime del blocco.
#
# LIMITE DA DICHIARARE: nella finestra di misura un 503 e un 403 contano
# entrambi come "non servita", perche' k6 non riprova (RETRY_MAX=0). Il
# vantaggio concettuale del rinvio - spostamento temporale invece di
# perdita - NON e' dimostrato da questi dati, e la frontiera regge senza
# bisogno di assumerlo.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

LAM="${LAM:-185}"
BUDGETS="${BUDGETS:-3 2 1}"

echo "lambda=$LAM  alpha=0.35  beta=0.10  cache=128MB  3 ripetizioni"
echo "budget: $BUDGETS   (4 e 6 gia' misurati il 19 settembre)"

for BU in $BUDGETS; do
  printf '\n######## budget %s ########  %s\n' "$BU" "$(date +%H:%M)"
  BLOCK_CLASSES="" BUDGET_LOW="$BU" BUDGET_WAIT=0 LAMBDA="$LAM" \
    REPS=3 GATE=0 WARMUP=300 MEASURE_FORCE=620 TOTAL_MB=128 \
    POINTS=0.35:0.10 bash treclassi.sh
done

echo
echo "================================================================"
echo "  Il riepilogo qui sopra NON stampa i rinvii, che sono il punto."
echo "  Estrarli dai JSON con:"
echo
echo "    cd ~/undertow/harness/results"
echo "    for d in \$(ls -td tre-*/ | head -3); do"
echo "      printf '%-26s ' \"\$d\""
echo "      f=\$(ls \$d/m-*.json | head -1)"
echo "      jq -r '[(.metrics.ut_ok_zipf.values.count//0),"
echo "              (.metrics.ut_ok_agent.values.count//0),"
echo "              (.metrics.ut_ok_traversal.values.count//0),"
echo "              (.metrics.ut_blk_traversal.values.count//0),"
echo "              (.metrics.ut_shed_traversal.values.count//0),"
echo "              ((.metrics.ut_lat_zipf.values[\"p(99)\"]//0)|round)]|@tsv' \$f"
echo "    done"
echo
echo "  Colonne: umano servito / agentico servito / esaustivo servito /"
echo "           esaustivo BLOCCATO (deve essere 0) / esaustivo RINVIATO /"
echo "           p99 umano."
echo
echo "  Il totale servito e' la somma delle prime tre. Confrontalo con"
echo "  86.911 a 57,9 ms, che e' il punto del blocco per identita'."