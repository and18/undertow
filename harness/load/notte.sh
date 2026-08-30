#!/usr/bin/env bash
#
# notte.sh - Campagna lunga non presidiata.
#
# FASE 1 (F5, priorita'). Sweep in lambda su due sole configurazioni.
#
#   Il 30 agosto la protezione e' costata +10,2% di carico all'origine
#   senza dare latenza, perche' a rho=0,67 la latenza e' piatta. Ma se
#   sposta +10% sull'origine, il sistema protetto deve saturare a un
#   lambda piu' basso. Con capacita' 90 req/s e ginocchio a rho=0,89:
#
#     condiviso  h=0,4535 -> ginocchio previsto a lambda = 146
#     protetto   h=0,4015 -> ginocchio previsto a lambda = 134
#
#   Se il protetto rompe prima, la scan-resistance provoca il collasso
#   che dovrebbe prevenire. Se rompono insieme, il costo esiste ma non
#   ha conseguenze operative: risultato negativo, comunque pubblicabile.
#
# FASE 2 (F4). Curva completa in r a lambda fisso, solo se resta tempo.
#   shared compare due volte: controllo di deriva.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

HOURS="${HOURS:-9}"
DEADLINE=$(( $(date +%s) + $(awk -v h="$HOURS" 'BEGIN{printf "%d", h*3600}') ))
LAMBDAS="${LAMBDAS:-110 125 135 145 155}"

STAMP="$(date +%Y%m%d-%H%M%S)"
IDX="../results/notte-$STAMP.csv"
echo "fase,lambda,dir" > "$IDX"

run() {   # run <fase> <lambda> <frazioni> <gate> <reps>
    printf '\n\033[1m######## %s  lambda=%s  r={%s} ########\033[0m  %s\n' \
        "$1" "$2" "$3" "$(date +%H:%M)"
    LAMBDA="$2" ALPHA=0.50 TOTAL_MB=128 FRACTIONS="$3" REPS="$5" GATE="$4" bash split.sh
    echo "$1,$2,$(basename "$(ls -td ../results/split-*/ | head -1)")" >> "$IDX"
}

for L in $LAMBDAS; do
    if [[ $(date +%s) -gt $DEADLINE ]]; then echo "tempo scaduto, fase 1 interrotta"; break; fi
    run F5 "$L" "shared 1.00" 0 3
done

if [[ $(date +%s) -lt $((DEADLINE - 10800)) ]]; then
    run F4 110 "shared 0.50 0.75 0.90 1.00 shared" 1 3
else
    echo "fase 2 saltata: non resta abbastanza tempo"
fi

echo; echo "==================== RIEPILOGO ===================="
printf '%-4s %-7s %-8s %4s %9s %9s %10s %9s\n' \
    "fase" "lambda" "r" "n" "p99 alta" "hit alta" "hit bassa" "orig rps"
tail -n +2 "$IDX" | while IFS=, read -r fase lam dir; do
    [[ -f "../results/$dir/points.csv" ]] || continue
    awk -F, -v f="$fase" -v l="$lam" 'NR>1 && $3!="" {
        r=$1; n[r]++; p[r]+=$3; hh[r]+=$5; mh[r]+=$6; hl[r]+=$7; ml[r]+=$8; o[r]+=$9 }
      END { for (r in n) printf "%-4s %-7s %-8s %4d %9.1f %9.3f %10.3f %9.2f\n",
        f, l, r, n[r], p[r]/n[r], hh[r]/(hh[r]+mh[r]),
        (hl[r]+ml[r]>0)?hl[r]/(hl[r]+ml[r]):0, o[r]/n[r] }' "../results/$dir/points.csv"
done
echo "Indice: $IDX"