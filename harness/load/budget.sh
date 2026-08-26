#!/usr/bin/env bash
#
# budget.sh - Un budget di risorse per classe protegge il traffico
#             interattivo senza penalizzare quello batch?
#
# LA DOMANDA
#
# Al ginocchio le due classi competono per gli stessi thread. La classe a
# bassa localita' ha volume alto e nessuno in attesa; quella ad alta
# localita' ha volume minore e una persona che aspetta. Oggi vince chi
# arriva prima, quindi la seconda aspetta dietro la prima.
#
# Il budget limita quante richieste a bassa localita' possono essere in
# elaborazione contemporaneamente. Le eccedenti attendono brevemente e,
# se lo slot non si libera, ricevono 503 con Retry-After: un rinvio, non
# un rifiuto. Il carico non viene perso, viene spostato nel tempo — cosa
# che un crawler batch puo' permettersi e un utente in attesa no.
#
# PREVISIONE ASIMMETRICA, ED E' IL PUNTO
#
#   la classe interattiva recupera molto
#   la classe batch perde poco
#
# perche' la classe batch non era limitata dai thread: era limitata dalla
# contesa che creava lei stessa. Se il conto torna, il conflitto e'
# apparente e non serve bloccare nessuno.
#
# CRITERIO, FISSATO PRIMA DEI DATI
#
#   riuscito   p99 della classe interattiva sotto 500 ms
#              E throughput completato della classe batch entro il 20%
#              del valore di riferimento
#
#   fallito    il throughput della classe batch cala in proporzione al
#              budget. In quel caso l'asimmetria non esiste e la tesi
#              va abbandonata.
#
# Il punto di lavoro e' alpha = 0.20, dove il p99 mediano e' 2681 ms e
# l'occupazione del pool 93%: appena oltre il ginocchio, dove c'e'
# qualcosa da recuperare.
#
# Uso:
#   DRY=1 ./load/budget.sh
#   ./load/budget.sh
#   ALPHA=0.25 BUDGETS="0 4 2" ./load/budget.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

LAMBDA="${LAMBDA:-260}"
ALPHA="${ALPHA:-0.20}"
# 0 = budget disattivato, riferimento. Gli altri valori sono slot
# concorrenti concessi alla classe a bassa localita', su THREADS totali.
BUDGETS="${BUDGETS:-0 6 4 3 2 1}"
BUDGET_WAIT="${BUDGET_WAIT:-0.5}"
REPS="${REPS:-5}"
# 180 s e' il warm-up validato per la cache da 128m; la dimensione della
# cache non varia in questo esperimento.
WARMUP="${WARMUP:-180}"
MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"

if [[ "${DRY:-0}" == "1" ]]; then
    BUDGETS="0 2"; REPS=1; WARMUP=60; MEASURE=45; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/budget-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/budget.log"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

restore() { sed -i 's/^BUDGET_LOW=.*/BUDGET_LOW=0/' .env 2>/dev/null
            docker compose up -d --force-recreate app >/dev/null 2>&1; }
trap restore EXIT

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }
vmq() { curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '.data.result[0].value[1] // "0"'; }

HEADER="budget,rep,alpha,lambda,p99_high,p99_low,p95_high,p95_low,ok_high,ok_low,shed_high,shed_low,hit_high,miss_high,hit_low,miss_low,inflight,app_cpu,db_cpu,ts"
if [[ -e "$CSV" ]]; then
    [[ "$(head -n1 "$CSV")" == "$HEADER" ]] || { echo "schema CSV incompatibile" >&2; exit 1; }
else
    echo "$HEADER" > "$CSV"
fi

{
  echo "BUDGET — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "alpha=$ALPHA lambda=$LAMBDA budgets=$BUDGETS wait=${BUDGET_WAIT}s reps=$REPS"
  grep -E '^(THREADS|BACKLOG|DB_POOL|VARNISH_SIZE|CPUSET_)' .env
} >> "$LOG"

total=0
for b in $BUDGETS; do for r in $(seq 1 "$REPS"); do total=$((total+1)); done; done
log "$total misure, stima $(( total * (WARMUP+MEASURE+DRAIN+50) / 60 )) minuti"

i=0
for budget in $BUDGETS; do
    if [[ "$budget" == "0" ]]; then
        log "budget disattivato (riferimento)"
    else
        log "budget = $budget slot concorrenti per la classe a bassa localita'"
    fi

    # Il budget si applica all'avvio del processo: cambiarlo richiede di
    # ricreare il container dell'applicazione.
    grep -q '^BUDGET_LOW=' .env && sed -i "s/^BUDGET_LOW=.*/BUDGET_LOW=$budget/" .env \
        || echo "BUDGET_LOW=$budget" >> .env
    grep -q '^BUDGET_WAIT=' .env && sed -i "s/^BUDGET_WAIT=.*/BUDGET_WAIT=$BUDGET_WAIT/" .env \
        || echo "BUDGET_WAIT=$BUDGET_WAIT" >> .env
    docker compose up -d --force-recreate app >/dev/null 2>&1
    sleep 12

    # Le ripetizioni si mescolano dentro ogni valore di budget: e' li'
    # che la deriva temporale della macchina potrebbe confondersi con
    # l'effetto. Il budget stesso non si randomizza perche' cambiarlo
    # richiede il riavvio dell'applicazione.
    mapfile -t reps < <(seq 1 "$REPS" | shuf --random-source=<(yes "$SEED"))

    for rep in "${reps[@]}"; do
        i=$((i+1))
        grep -q "^$budget,$rep," "$CSV" 2>/dev/null && { echo "  [$i/$total] gia fatto"; continue; }

        printf '  [%2d/%2d] budget=%-2s rep=%s ... ' "$i" "$total" "$budget" "$rep"
        tag="b${budget}-r${rep}"

        docker compose restart varnish >/dev/null 2>&1
        sleep 8

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$ALPHA" -e RATE="$LAMBDA" -e DURATION="${WARMUP}s" -e SEED="$SEED" \
            -e ENDPOINT=chapter -e OUTFILE="w-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-w-$tag.log" 2>&1
        rm -f "$HARNESS/results/w-$tag.json"

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$ALPHA" -e RATE="$LAMBDA" -e DURATION="${MEASURE}s" -e SEED="$SEED" \
            -e ENDPOINT=chapter -e OUTFILE="m-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-$tag.log" 2>&1 &
        kp=$!

        sleep 15
        inf=0; ac=0; dc=0; ns=0
        while kill -0 "$kp" 2>/dev/null; do
            v=$(vmq 'ut_requests_inflight')
            read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
                | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
            inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
            ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
            dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
            ns=$((ns+1)); sleep 3
        done
        wait "$kp" 2>/dev/null
        inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

        f="$HARNESS/results/m-$tag.json"
        if [[ -f "$f" ]]; then
            mv "$f" "$OUT/"; f="$OUT/m-$tag.json"
            read -r p99h p99l p95h p95l okh okl shh shl hh mh hl ml <<<"$(jq -r '[
                ((.metrics.ut_lat_zipf.values["p(99)"] // 0)*10|round/10),
                ((.metrics.ut_lat_traversal.values["p(99)"] // 0)*10|round/10),
                ((.metrics.ut_lat_zipf.values["p(95)"] // 0)*10|round/10),
                ((.metrics.ut_lat_traversal.values["p(95)"] // 0)*10|round/10),
                (.metrics.ut_ok_zipf.values.count // 0),
                (.metrics.ut_ok_traversal.values.count // 0),
                (.metrics.ut_shed_zipf.values.count // 0),
                (.metrics.ut_shed_traversal.values.count // 0),
                (.metrics.ut_hit_zipf.values.count // 0),
                (.metrics.ut_miss_zipf.values.count // 0),
                (.metrics.ut_hit_traversal.values.count // 0),
                (.metrics.ut_miss_traversal.values.count // 0)] | @tsv' "$f")"
            echo "$budget,$rep,$ALPHA,$LAMBDA,$p99h,$p99l,$p95h,$p95l,$okh,$okl,$shh,$shl,$hh,$mh,$hl,$ml,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
            printf 'p99 alta=%s bassa=%s   ok bassa=%s   rinviate=%s\n' "$p99h" "$p99l" "$okl" "$shl"
        else
            echo "$budget,$rep,$ALPHA,$LAMBDA,,,,,,,,,,,,$inf,$ac,$dc,$(date -Is)" >> "$CSV"
            echo "FALLITO — vedi $OUT/k6-$tag.log"
        fi
        sleep "$DRAIN"
    done
done

# --- riepilogo -------------------------------------------------------------
{
  echo
  echo "================================================================"
  echo "RISULTATO — mediane per budget"
  echo "================================================================"
  awk -F, 'NR>1 && $5!="" {
      b=$1; n[b]++
      ph[b,n[b]]=$5; pl[b,n[b]]=$6
      okl[b]+=$10; shl[b]+=$12; okh[b]+=$9
  }
  function med(k, c,   i,j,t,arr) { return 0 }
  END {
    printf "%-8s %5s %11s %11s %12s %12s %10s\n",
           "budget","n","p99 alta","p99 bassa","ok bassa","rinviate","% rinvio"
    for (b in n) {
      c=n[b]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) {
        if(ph[b,j]+0<ph[b,i]+0){t=ph[b,i];ph[b,i]=ph[b,j];ph[b,j]=t}
        if(pl[b,j]+0<pl[b,i]+0){t=pl[b,i];pl[b,i]=pl[b,j];pl[b,j]=t}
      }
      mh=(c%2)?ph[b,(c+1)/2]:(ph[b,c/2]+ph[b,c/2+1])/2
      ml=(c%2)?pl[b,(c+1)/2]:(pl[b,c/2]+pl[b,c/2+1])/2
      tot=okl[b]+shl[b]
      printf "%-8s %5d %11.1f %11.1f %12.0f %12.0f %9.1f%%\n",
             (b==0?"off":b), c, mh, ml, okl[b]/c, shl[b]/c,
             (tot>0)?100*shl[b]/tot:0
    }
  }' "$CSV" | (read -r hdr; echo "$hdr"; sort -k1,1)

  echo
  echo "COME LEGGERE"
  echo
  echo "  p99 alta     latenza della classe interattiva, quella con una"
  echo "               persona in attesa. E' il numero che deve scendere."
  echo "  ok bassa     richieste della classe batch completate con 200."
  echo "               E' il numero che NON deve crollare."
  echo "  rinviate     richieste della classe batch che hanno ricevuto"
  echo "               503 con Retry-After. Non sono perse: sono spostate."
  echo
  echo "  RIUSCITO se esiste un budget con p99 alta sotto 500 ms e ok"
  echo "  bassa entro il 20% del riferimento. Significa che proteggere"
  echo "  il traffico interattivo costa poco a quello batch, e quindi"
  echo "  che il conflitto e' apparente."
  echo
  echo "  FALLITO se ok bassa cala in proporzione al budget. L'asimmetria"
  echo "  non esiste, la classe batch era davvero limitata dai thread, e"
  echo "  la tesi va abbandonata."
  echo
  echo "  DA GUARDARE ANCHE: se p99 bassa sale molto mentre ok bassa"
  echo "  resta alta, il crawler viene servito piu' lentamente ma"
  echo "  completamente — che e' esattamente il comportamento voluto."
  echo
  echo "Dati: $CSV"
} | tee -a "$LOG"