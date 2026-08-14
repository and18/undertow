#!/usr/bin/env bash
#
# calibrate.sh - Calibrazione dell'harness, non presidiata.
#
# Risponde a una sola domanda: il carico e' I/O-BOUND?
#
# Un thread e' occupato mentre e' BLOCCATO, non mentre calcola. Se il
# lavoro sta in Postgres, i thread si accumulano in attesa e la CPU
# dell'applicazione resta bassa: allora il pool puo' saturarsi ed e' la
# risorsa vincolante, che e' la premessa dell'intero esperimento.
# Se invece la CPU sale e i thread restano vuoti, il vincolo e' il GIL
# di Python e il pool non si riempira' mai.
#
# Misura anche i costi per richiesta A CACHE FREDDA. Misurarli a cache
# calda restituisce la latenza di Varnish, non quella dell'applicazione:
# un errore gia' commesso una volta.
#
# Uso:
#   ./load/calibrate.sh
#   RATES="50 100 200 400" DURATION=45s ./load/calibrate.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

RATES="${RATES:-50 100 200 400 800}"
DURATION="${DURATION:-60s}"
GAP="${GAP:-15}"
SAMPLES="${SAMPLES:-20}"          # campioni di occupazione per gradino

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HARNESS/results/calibrate-$STAMP"
REPORT="$OUT/report.txt"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

THREADS_CFG=$(grep -E '^THREADS=' .env | cut -d= -f2 | tr -d ' ')

{
  echo "CALIBRAZIONE — $(date -Is)"
  echo "================================================================"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)  nproc=$(nproc)"
  grep -E '^(CPUSET_|THREADS|BACKLOG|DB_POOL|VARNISH_SIZE)' .env | sed 's/^/  /'
  echo
} > "$REPORT"

# --- 1. costi per richiesta a cache fredda -------------------------------
log "svuoto la cache"
docker compose restart varnish >/dev/null 2>&1
sleep 6

log "misuro i costi a cache fredda"
{
  echo "----------------------------------------------------------------"
  echo "COSTO PER RICHIESTA (cache fredda, un URL per volta)"
  echo "----------------------------------------------------------------"
} >> "$REPORT"

books=$(curl -s localhost:8080/library | jq -r '.[] | "\(.id) \(.n_chapters)"' | head -40)

ch_times=""
i=0
while read -r id nch; do
    [[ -z "$id" ]] && continue
    n=$(( (RANDOM % nch) + 1 ))
    t=$(curl -s -o /dev/null -w '%{time_total}' "localhost:8080/book/$id/ch/$n")
    ch_times="$ch_times $t"
    i=$((i+1)); [[ $i -ge 25 ]] && break
done <<< "$books"

srch_times=""
for w in $(awk '!/^#/{print $1}' profiles/search-terms.txt | head -12); do
    t=$(curl -s -o /dev/null -w '%{time_total}' "localhost:8080/search?q=$w")
    srch_times="$srch_times $t"
done

stat() {  # mediana e intervallo in ms
    tr ' ' '\n' <<< "$1" | grep -v '^$' | sort -g | awk '
      {v[NR]=$1*1000}
      END{ if(NR==0){print "n/a"; exit}
           m = (NR%2) ? v[(NR+1)/2] : (v[NR/2]+v[NR/2+1])/2
           printf "mediana %.1f ms   min %.1f   max %.1f   n=%d", m, v[1], v[NR], NR }'
}

CH_MED=$(tr ' ' '\n' <<< "$ch_times" | grep -v '^$' | sort -g | awk '{v[NR]=$1*1000} END{print (NR%2)?v[(NR+1)/2]:(v[NR/2]+v[NR/2+1])/2}')
SR_MED=$(tr ' ' '\n' <<< "$srch_times" | grep -v '^$' | sort -g | awk '{v[NR]=$1*1000} END{print (NR%2)?v[(NR+1)/2]:(v[NR/2]+v[NR/2+1])/2}')

{
  printf '  capitolo  %s\n' "$(stat "$ch_times")"
  printf '  ricerca   %s\n' "$(stat "$srch_times")"
  echo
  echo "  Legge di Little: per saturare N thread a lambda req/s serve"
  echo "  W = N/lambda. Con THREADS=$THREADS_CFG:"
  awk -v c="$CH_MED" -v s="$SR_MED" -v n="$THREADS_CFG" 'BEGIN{
    printf "    capitolo (W=%.0f ms): il pool satura a ~%.0f req/s all origine\n", c, n/(c/1000)
    printf "    ricerca  (W=%.0f ms): il pool satura a ~%.0f req/s all origine\n", s, n/(s/1000)
  }'
  echo
} >> "$REPORT"

# --- 2. verifica I/O-bound su una scala di ritmi -------------------------
for endpoint in chapter search; do
  log "verifica I/O-bound: endpoint $endpoint"
  {
    echo "----------------------------------------------------------------"
    echo "ENDPOINT $endpoint"
    echo "----------------------------------------------------------------"
    printf '%-7s %9s %8s %9s %9s %8s %9s %8s\n' \
           rate inflight 'uso%' 'app CPU%' 'db CPU%' 'db conn' 'p99 ms' 'hit%'
  } >> "$REPORT"

  for rate in $RATES; do
    printf '    %s @ %s ... ' "$endpoint" "$rate"
    tag="$endpoint-$rate"

    docker compose --profile load run --rm -T \
      -e ENDPOINT="$endpoint" -e RATE="$rate" -e DURATION="$DURATION" \
      -e OUTFILE="p-$tag" \
      k6 run --quiet /scripts/probe-origin.js < /dev/null > "$OUT/k6-$tag.log" 2>&1 &
    k6pid=$!

    sleep 20   # regime stazionario prima di campionare

    inf_sum=0; cpu_max=0; dbcpu_max=0; dbc_max=0
    for s in $(seq 1 $SAMPLES); do
      inf=$(vmq 'ut_requests_inflight')
      dbc=$(vmq 'ut_db_pool_busy')
      read -r acpu dcpu <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' \
              | awk '/ut-app /{gsub(/%/,"",$2); a=$2} /ut-db /{gsub(/%/,"",$2); d=$2} END{print a+0, d+0}')"
      inf_sum=$(awk -v a="$inf_sum" -v b="$inf" 'BEGIN{print a+b}')
      cpu_max=$(awk -v a="$cpu_max" -v b="$acpu" 'BEGIN{print (b>a)?b:a}')
      dbcpu_max=$(awk -v a="$dbcpu_max" -v b="$dcpu" 'BEGIN{print (b>a)?b:a}')
      dbc_max=$(awk -v a="$dbc_max" -v b="$dbc" 'BEGIN{print (b>a)?b:a}')
      sleep 1
    done
    inf_avg=$(awk -v s="$inf_sum" -v n="$SAMPLES" 'BEGIN{printf "%.1f", s/n}')
    util=$(awk -v i="$inf_avg" -v n="$THREADS_CFG" 'BEGIN{printf "%.0f", 100*i/n}')

    wait $k6pid 2>/dev/null

    f="$HARNESS/results/p-$tag.json"
    if [[ -f "$f" ]]; then
      mv "$f" "$OUT/"; f="$OUT/p-$tag.json"
      read -r p99 h m <<<"$(jq -r '[
          ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
          (.metrics.ut_cache_hit.values.count // 0),
          (.metrics.ut_cache_miss.values.count // 0)] | @tsv' "$f")"
      hitpc=$(awk -v h="$h" -v m="$m" 'BEGIN{t=h+m; printf "%.0f", (t>0)?100*h/t:0}')
    else
      p99="?"; hitpc="?"
    fi

    printf '%-7s %9s %8s %9s %9s %8s %9s %8s\n' \
           "$rate" "$inf_avg" "$util" "$cpu_max" "$dbcpu_max" "$dbc_max" "$p99" "$hitpc" >> "$REPORT"
    echo "inflight=$inf_avg (${util}%) appcpu=$cpu_max"
    sleep "$GAP"
  done
  echo >> "$REPORT"
done

# --- 3. verdetto ----------------------------------------------------------
{
  echo "================================================================"
  echo "COME LEGGERE"
  echo "================================================================"
  echo
  echo "  inflight   thread occupati in media. E' la metrica centrale."
  echo "  uso%       inflight / THREADS. Il ginocchio va cercato dove"
  echo "             questo si avvicina al 100%."
  echo "  app CPU%   100% = un core. Se si ferma attorno a 80-100 mentre"
  echo "             inflight resta basso, il vincolo e' il GIL e NON il"
  echo "             pool: il carico non e' I/O-bound e gli sweep non"
  echo "             possono funzionare cosi'."
  echo "  db CPU%    se alta mentre app CPU e' bassa, il lavoro sta nel"
  echo "             database: e' la condizione voluta."
  echo "  hit%       percentuale servita dalla cache. Con capitoli"
  echo "             casuali su cache piccola deve essere bassa."
  echo
  echo "CONDIZIONE DA VERIFICARE"
  echo
  echo "  A un ritmo raggiungibile, 'uso%' deve superare il 70% mentre"
  echo "  'app CPU%' resta sotto il 60%. Se questo accade, l'harness e'"
  echo "  pronto: si fissa il ritmo operativo appena sopra quel punto e"
  echo "  gli sweep sulla composizione del traffico possono partire."
  echo
  echo "  Se non accade su nessun ritmo, la leva successiva e' ridurre"
  echo "  shared_buffers di Postgres, per costringerlo a leggere da disco"
  echo "  e produrre blocco reale invece di lavoro in memoria."
  echo
  echo "Dettagli in: $OUT"
} >> "$REPORT"

echo; cat "$REPORT"; echo
log "rapporto: $REPORT"