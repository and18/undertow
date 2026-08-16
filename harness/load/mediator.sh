#!/usr/bin/env bash
#
# mediator.sh - Intervento sul mediatore: la cache e' davvero il meccanismo?
#
# LA DOMANDA
#
# Lo sweep mostra che aumentando la frazione agentica il sistema
# attraversa un ginocchio. Ma correlazione non e' meccanismo: alpha
# guida ogni anello della catena per costruzione, quindi tutte le
# correlazioni lungo la catena sono vicine a 1 senza dimostrare nulla.
#
# L'unico modo per identificare la causa e' INTERVENIRE sul mediatore
# ipotizzato. Se il meccanismo e' la competizione per lo spazio in
# cache, allora dando alla cache capacita' sufficiente a contenere
# l'intero working set la competizione sparisce, e con essa il
# ginocchio — anche a alpha = 1.
#
# PREVISIONE FALSIFICABILE
#
#   cache < working set   ->  ginocchio presente, posizione ~ f(rapporto)
#   cache >= working set  ->  nessun ginocchio a nessun alpha
#
# Se il ginocchio persiste con cache abbondante, l'ipotesi e' FALSA e il
# meccanismo e' altrove (costo di generazione, pool di connessioni,
# interprete). Sarebbe un risultato, non un fallimento: indicherebbe
# dove guardare.
#
# Il working set misurato e' 245 MB (16.954 oggetti, ~10,6 KB medi in
# cache dopo compressione).
#
# Uso:
#   DRY=1 ./load/mediator.sh
#   ./load/mediator.sh                    ~4 ore
#   SIZES="128m 512m" ./load/mediator.sh  versione ridotta, ~2 ore
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

LAMBDA="${LAMBDA:-260}"
SIZES="${SIZES:-128m 256m 512m}"
ALPHAS="${ALPHAS:-0.00 0.15 0.30 0.50}"
REPS="${REPS:-5}"
WARMUP="${WARMUP:-300}"     # piu' lungo dello sweep: 512m richiede tempo
MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"

if [[ "${DRY:-0}" == "1" ]]; then
    SIZES="128m 512m"; ALPHAS="0.00 0.50"; REPS=1
    WARMUP=300; MEASURE=45; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/mediator-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/mediator.log"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

ORIG_SIZE=$(grep -E '^VARNISH_SIZE=' .env | cut -d= -f2 | tr -d ' ')
restore() { sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$ORIG_SIZE/" .env
            docker compose up -d --force-recreate varnish >/dev/null 2>&1; }
trap restore EXIT

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

if [[ ! -f "$CSV" ]]; then
    echo "cache,alpha,rep,lambda,completed,dropped,failed,p50,p95,p99,p999,hit_h,miss_h,hit_a,miss_a,inflight,app_cpu,db_cpu,origin_rps,ts" > "$CSV"
elif ! head -n 1 "$CSV" | grep -q 'origin_rps'; then
    tmp=$(mktemp)
    awk -F, 'BEGIN{OFS=","} NR==1 {print $0 ",origin_rps"} NR>1 {print $0 ","}' "$CSV" > "$tmp" && mv "$tmp" "$CSV"
fi

{
  echo "MEDIATOR — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "lambda=$LAMBDA sizes=$SIZES alphas=$ALPHAS reps=$REPS"
  echo "working set = 245 MB (16954 oggetti)"
  grep -E '^(THREADS|BACKLOG|DB_POOL|CPUSET_)' .env
} >> "$LOG"

# --- lista di lavori, mescolata ------------------------------------------
# La dimensione di cache NON si randomizza: cambiarla richiede il riavvio
# di Varnish, e alternarla continuamente moltiplicherebbe i transitori.
# Si randomizza alpha e ripetizione DENTRO ogni dimensione, che e' dove
# la deriva temporale potrebbe confondersi con l'effetto.
total=0
for s in $SIZES; do for a in $ALPHAS; do for r in $(seq 1 $REPS); do
    total=$((total+1)); done; done; done
log "$total misure, stima $(( total * (WARMUP+MEASURE+DRAIN+25) / 60 )) minuti"

i=0
for size in $SIZES; do
    log "cache = $size  ($(awk -v s="${size%m}" 'BEGIN{printf "%.0f", 100*s/245}')% del working set)"
    sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$size/" .env
    docker compose up -d --force-recreate varnish >/dev/null 2>&1
    sleep 10

    jobs=()
    for a in $ALPHAS; do for r in $(seq 1 $REPS); do jobs+=("$a:$r"); done; done
    mapfile -t jobs < <(printf '%s\n' "${jobs[@]}" | shuf --random-source=<(yes "$SEED"))

    for job in "${jobs[@]}"; do
        a="${job%:*}"; rep="${job#*:}"; i=$((i+1))
        grep -q "^$size,$a,$rep," "$CSV" 2>/dev/null && { echo "  [$i/$total] $size a=$a r=$rep gia fatto"; continue; }

        printf '  [%2d/%2d] %s alpha=%s rep=%s ... ' "$i" "$total" "$size" "$a" "$rep"
        tag="${size}-a${a}-r${rep}"
        max_orps=0

        docker compose restart varnish >/dev/null 2>&1
        sleep 8

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${WARMUP}s" \
            -e ENDPOINT=chapter -e OUTFILE="w-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-w-$tag.log" 2>&1
        rm -f "$HARNESS/results/w-$tag.json"

        docker compose --profile load run --rm -T \
            -e MODEL=mix -e ALPHA="$a" -e RATE="$LAMBDA" -e DURATION="${MEASURE}s" \
            -e ENDPOINT=chapter -e OUTFILE="m-$tag" \
            k6 run --quiet /scripts/workload.js < /dev/null \
            > "$OUT/k6-$tag.log" 2>&1 &
        kp=$!

        sleep 20
        inf=0; ac=0; dc=0; ns=0
        while kill -0 $kp 2>/dev/null && [[ $ns -lt 40 ]]; do
            v=$(vmq 'ut_requests_inflight')
            orps=$(curl -s "http://localhost:8428/api/v1/query?query=sum(rate(ut_requests_total%5B30s%5D))" \
                   | jq -r '[.data.result[].value[1]|tonumber]|add // 0')
            if awk -v a="$max_orps" -v b="$orps" 'BEGIN { exit !(b > a) }'; then
                max_orps="$orps"
            fi
            read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
                | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
            inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
            ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
            dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
            ns=$((ns+1)); sleep 3
        done
        wait $kp 2>/dev/null
        inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

        f="$HARNESS/results/m-$tag.json"
        if [[ -f "$f" ]]; then
            mv "$f" "$OUT/"; f="$OUT/m-$tag.json"
            read -r comp drop fail p50 p95 p99 p999 hh mh ha ma <<<"$(jq -r '[
                (.metrics.http_reqs.values.count // 0),
                (.metrics.dropped_iterations.values.count // 0),
                ((.metrics.http_req_failed.values.rate // 0)*10000|round/10000),
                ((.metrics.http_req_duration.values.med // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(95)"] // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
                ((.metrics.http_req_duration.values["p(99.9)"] // 0)*10|round/10),
                (.metrics.ut_hit_zipf.values.count // 0),
                (.metrics.ut_miss_zipf.values.count // 0),
                (.metrics.ut_hit_traversal.values.count // 0),
                (.metrics.ut_miss_traversal.values.count // 0)] | @tsv' "$f")"
            echo "$size,$a,$rep,$LAMBDA,$comp,$drop,$fail,$p50,$p95,$p99,$p999,$hh,$mh,$ha,$ma,$inf,$ac,$dc,$max_orps,$(date -Is)" >> "$CSV"
            printf 'p99=%s inflight=%s origin_rps=%s\n' "$p99" "$inf" "$max_orps"
        else
            echo "$size,$a,$rep,$LAMBDA,,,,,,,,,,,,$inf,$ac,$dc,$max_orps,$(date -Is)" >> "$CSV"
            echo "FALLITO"
        fi
        sleep "$DRAIN"
    done
done

# --- verdetto -------------------------------------------------------------
{
  echo
  echo "================================================================"
  echo "RISULTATO — p99 mediana per (cache, alpha)"
  echo "================================================================"
  awk -F, 'NR>1 && $10!="" {
      key=$1" "$2; n[key]++; v[key,n[key]]=$10
      hit[key]+=$12+$14; mis[key]+=$13+$15; orps[key]+=$19
  }
  END {
    printf "%-8s %-7s %5s %11s %10s %10s\n", "cache", "alpha", "n", "p99 med", "hit", "orig rps"
    for (k in n) {
      c=n[k]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) if(v[k,j]+0<v[k,i]+0){t=v[k,i];v[k,i]=v[k,j];v[k,j]=t}
      m=(c%2)?v[k,(c+1)/2]:(v[k,c/2]+v[k,c/2+1])/2
      split(k,p," ")
      printf "%-8s %-7s %5d %11.1f %10.3f %10.1f\n", p[1], p[2], c, m, (hit[k]+mis[k]>0)?hit[k]/(hit[k]+mis[k]):0, orps[k]/c
    }
  }' "$CSV" | (read -r h; echo "$h"; sort -k1,1 -k2,2)

  echo
  echo "COME LEGGERE"
  echo
  echo "  Il working set e' 245 MB. Quindi:"
  echo "    128m = 52%   competizione forte"
  echo "    256m = 104%  competizione al limite"
  echo "    512m = 209%  nessuna competizione"
  echo
  echo "  IPOTESI CONFERMATA se a 512m il p99 resta piatto per ogni"
  echo "  alpha, incluso 0.50. Significa che il ginocchio non e' una"
  echo "  proprieta' del traffico agentico in se', ma dell'interazione"
  echo "  fra traffico agentico e una cache troppo piccola per il"
  echo "  working set. E' identificazione causale per intervento, non"
  echo "  correlazione."
  echo
  echo "  IPOTESI FALSIFICATA se il ginocchio persiste a 512m. Il"
  echo "  meccanismo sarebbe allora il costo di generazione della"
  echo "  pagina, non la competizione in cache: da indagare con le"
  echo "  ablazioni e con il cambio di collo di bottiglia."
  echo
  echo "  ATTESO INOLTRE: a 256m un comportamento intermedio, con il"
  echo "  ginocchio spostato verso alpha piu' alti. Se la posizione si"
  echo "  muove col rapporto cache/working-set nella direzione prevista"
  echo "  dal modello, la relazione e' quantitativa e non solo"
  echo "  qualitativa."
  echo
  echo "Dati: $CSV"
} | tee -a "$LOG"