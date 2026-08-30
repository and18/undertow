#!/usr/bin/env bash
#
# poolfix.sh - Il pool applicativo puo' essere troppo grande?
#
# L'IPOTESI, contraria alla pratica comune
#
# Un pool di thread piu' grande della capacita' del backend non aumenta
# il throughput. Aumenta soltanto quanto lavoro puo' accumularsi davanti
# a una risorsa satura, e quindi rende il sistema SENSIBILE alla
# composizione del traffico. Un pool piu' piccolo lo rende immune,
# perche' rifiuta a monte invece di accodare.
#
# Se regge: contro il traffico esaustivo non serve piu' capacita'
# applicativa, ne serve meno.
#
# IL DISEGNO
#
# lambda FISSO, varia SOLO il numero di thread. E' la correzione al run
# del 2026-08-28, dove lambda seguiva N e i due effetti non erano
# separabili — quello che sembrava immunita' del pool piccolo poteva
# essere solo carico piu' basso.
#
# alpha arriva a 0,80 perche' oltre 0,40 il carico all'origine supera la
# capacita' per qualunque pool: e' li' che si vede se il pool piccolo
# regge dove il grande crolla.
#
# CONTROLLO DI DERIVA
#
# Fra un pool e l'altro si rimisura lo stesso punto fisso. Il 2026-08-28
# il database e' derivato del 31% in otto ore, il che rende i confronti
# fra l'inizio e la fine della campagna privi di senso. Lo script si
# ferma invece di produrre dati non comparabili.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-220}"
THREADS_LIST="${THREADS_LIST:-3 4 6 8 12 16}"
ALPHAS="${ALPHAS:-0.10 0.25 0.40 0.60 0.80}"
REPS="${REPS:-5}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="results/poolfix-$STAMP"
mkdir -p "$BASE"
SUM="$BASE/summary.txt"

restore() { sed -i 's/^THREADS=.*/THREADS=8/' .env
            docker compose up -d --force-recreate app >/dev/null 2>&1; }
trap restore EXIT

# Punto fisso: THREADS=8, alpha=0.25, il ginocchio noto.
checkpoint() {
    sed -i 's/^THREADS=.*/THREADS=8/' .env
    docker compose up -d --force-recreate app >/dev/null 2>&1; sleep 12
    docker compose restart varnish >/dev/null 2>&1; sleep 8
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE="$LAMBDA" -e DURATION=120s -e OUTFILE=cpw \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    rm -f results/cpw.json
    docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA=0.25 \
        -e RATE="$LAMBDA" -e DURATION=120s -e OUTFILE=cp \
        k6 run --quiet /scripts/workload.js < /dev/null >/dev/null 2>&1
    local v
    v=$(jq -r '(.metrics.ut_lat_zipf.values["p(99)"] // 0)|round' results/cp.json 2>/dev/null || echo 0)
    mv results/cp.json "$BASE/cp-$(date +%H%M).json" 2>/dev/null
    echo "$v"
}

REF=$(checkpoint)
echo "riferimento: p99 = ${REF} ms" | tee -a "$SUM"
[[ "$REF" -lt 100 ]] && { echo "riferimento implausibile, mi fermo" | tee -a "$SUM"; exit 1; }

for t in $THREADS_LIST; do
    printf '\n\033[1m==> THREADS=%s  lambda=%s\033[0m  (%s)\n' "$t" "$LAMBDA" "$(date +%H:%M)" | tee -a "$SUM"
    sed -i "s/^THREADS=.*/THREADS=$t/" .env
    docker compose up -d --force-recreate app >/dev/null 2>&1
    sleep 12
    OUT="$BASE/t$t" LAMBDA="$LAMBDA" ALPHAS="$ALPHAS" REPS="$REPS" \
        bash load/sweep.sh 2>&1 | tail -20 | tee -a "$SUM"

    now=$(checkpoint)
    pct=$(awk -v a="$REF" -v b="$now" 'BEGIN{printf "%.0f", 100*(b-a)/a}')
    echo "   deriva dopo t=$t: ${now} ms contro ${REF} ms (${pct}%)" | tee -a "$SUM"
    awk -v p="$pct" 'BEGIN{exit !(p<-30 || p>30)}' && {
        echo "DERIVA OLTRE IL 30% — mi fermo" | tee -a "$SUM"; break; }
done

# --- tabella finale ------------------------------------------------------
# Le richieste completate per classe sono il numero che decide se il pool
# piccolo e' una cura o un collo di bottiglia spostato.
{
  echo
  echo "================================================================"
  echo "RISULTATO — p99 interattivo e throughput, per pool e composizione"
  echo "================================================================"
  printf '%-8s %-7s %11s %11s %11s %9s\n' \
         "THREADS" "alpha" "p99 alta" "ok alta" "ok bassa" "hit"
  for d in "$BASE"/t*/points.csv; do
    [[ -f "$d" ]] || continue
    t=$(basename "$(dirname "$d")" | tr -d 't')
    awk -F, -v t="$t" 'NR>1 && $11!="" {
        a=$1; n[a]++; v[a,n[a]]=$11
        okh[a]+=$5; okl[a]+=$0*0
        hh[a]+=$14; mh[a]+=$15; ha[a]+=$16; ma[a]+=$17
        comp[a]+=$5 }
      END { for (a in n) {
        c=n[a]
        for(i=1;i<=c;i++) for(j=i+1;j<=c;j++)
          if(v[a,j]+0<v[a,i]+0){x=v[a,i];v[a,i]=v[a,j];v[a,j]=x}
        m=(c%2)?v[a,(c+1)/2]:(v[a,c/2]+v[a,c/2+1])/2
        tot=hh[a]+mh[a]+ha[a]+ma[a]
        printf "%-8s %-7s %11.1f %11.0f %11.0f %9.3f\n",
               t, a, m, (hh[a]+mh[a])/c, (ha[a]+ma[a])/c,
               (tot>0)?(hh[a]+ha[a])/tot:0 } }' "$d"
  done | sort -n -k1,1 -k2,2
  echo
  echo "COME LEGGERE"
  echo
  echo "  p99 alta   latenza della classe interattiva. Se resta bassa"
  echo "             sui pool piccoli anche ad alpha alto, l ipotesi"
  echo "             regge."
  echo "  ok alta    richieste interattive servite. NON deve crollare:"
  echo "             se cala col pool, il pool piccolo non e una cura"
  echo "             ma un collo di bottiglia spostato."
  echo "  ok bassa   richieste della classe esaustiva servite."
  echo
  echo "  IPOTESI CONFERMATA se esiste un pool piccolo con p99 alta"
  echo "  bassa a ogni alpha E ok alta confrontabile con i pool grandi."
  echo "  Significa che il pool grande non produce throughput, produce"
  echo "  solo coda."
  echo
  echo "  IPOTESI FALSIFICATA se il ginocchio compare a ogni pool,"
  echo "  oppure se il pool piccolo lo evita solo perche serve meno"
  echo "  richieste."
} | tee -a "$SUM"

echo; echo "dati in $BASE"
