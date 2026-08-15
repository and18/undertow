#!/usr/bin/env bash
#
# measure-model.sh - Misura i parametri del modello e deriva il punto
#                    operativo. Da eseguire PRIMA di qualsiasi sweep.
#
# PERCHE'
#
# Il carico che raggiunge l'origine e':
#
#     lambda_origin(a) = lambda_tot * [ (1-h_H) + a*(h_H - h_A) ]
#
# dove h_H e h_A sono gli hit ratio dei due profili e a la frazione
# agentica. Il ginocchio cade dove lambda_origin(a) raggiunge la
# capacita' C dell'origine:
#
#     a* = [ C/lambda_tot - (1-h_H) ] / (h_H - h_A)
#
# Se h_H, h_A e C si ASSUMONO invece di misurarli, si sceglie un punto
# operativo a caso. Con h_H=0.90, h_A=0.20, lambda=800 e C=620 il
# ginocchio cadrebbe ad a*=0.96: il sistema collasserebbe solo con
# traffico quasi interamente agentico — l'opposto della tesi, che parla
# di una frazione modesta.
#
# Misurando i tre parametri si puo' invece DERIVARE il lambda_tot che
# colloca il ginocchio dove serve, e soprattutto si ottiene una
# PREVISIONE contro cui confrontare la misura. Ginocchio previsto contro
# ginocchio osservato vale molto piu' di una curva empirica isolata.
#
# Uso:
#   ./load/measure-model.sh
#   ALPHA_TARGET=0.25 DURATION=300s ./load/measure-model.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

DURATION="${DURATION:-300s}"          # lungo: serve il regime stazionario
SETTLE="${SETTLE:-180}"               # si campiona solo dopo questo tempo
ALPHA_TARGET="${ALPHA_TARGET:-0.25}"  # dove si vuole il ginocchio
PROBE_RATE="${PROBE_RATE:-400}"       # ritmo per misurare h_H e h_A
CAP_RATES="${CAP_RATES:-100 200 300 400 500 600}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HARNESS/results/model-$STAMP"
REPORT="$OUT/report.txt"
mkdir -p "$OUT"; chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }
vmq() { curl -s "http://localhost:8428/api/v1/query?query=$1" \
        | jq -r '.data.result[0].value[1] // "0"'; }

THREADS=$(grep -E '^THREADS=' .env | cut -d= -f2 | tr -d ' ')
VSIZE=$(grep -E '^VARNISH_SIZE=' .env | cut -d= -f2 | tr -d ' ')

cold_cache() {
    # Ogni misura parte da cache fredda: senza, la storia di sfratto del
    # run precedente contamina il successivo.
    docker compose restart varnish >/dev/null 2>&1
    sleep 6
}

run_k6() {  # model, rate, outfile, [alpha]
    # Due fasi: la prima scalda la cache e viene SCARTATA, la seconda
    # misura. Senza questa separazione l'hit ratio includerebbe i miss
    # obbligatori del riempimento iniziale e risulterebbe molto piu'
    # basso del valore a regime — falsando h_H e con esso tutto il
    # modello che ne deriva.
    docker compose --profile load run --rm -T \
        -e MODEL="$1" -e RATE="$2" -e DURATION="${SETTLE}s" \
        -e ALPHA="${4:-0}" -e OUTFILE="warm-$3" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-warm-$3.log" 2>&1
    rm -f "$HARNESS/results/warm-$3.json"

    docker compose --profile load run --rm -T \
        -e MODEL="$1" -e RATE="$2" -e DURATION="$DURATION" \
        -e ALPHA="${4:-0}" -e OUTFILE="$3" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-$3.log" 2>&1
}

hit_ratio() {  # file json, prefisso metrica
    jq -r --arg p "$2" '
        ((.metrics["ut_hit_"+$p].values.count // 0) as $h |
         (.metrics["ut_miss_"+$p].values.count // 0) as $m |
         if ($h+$m) > 0 then ($h/($h+$m)*1000|round/1000) else 0 end)' "$1"
}

{
  echo "MISURA DEI PARAMETRI DEL MODELLO — $(date -Is)"
  echo "================================================================"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "THREADS=$THREADS  VARNISH_SIZE=$VSIZE  durata=$DURATION"
  echo "nproc=$(nproc)"
  echo
  lscpu -e=CPU,CORE,MAXMHZ 2>/dev/null | head -20 | sed 's/^/  /'
  echo
} > "$REPORT"

# --- 1. h_H : hit ratio del profilo umano puro ---------------------------
log "misuro h_H (Zipf puro) a $PROBE_RATE req/s"
cold_cache
run_k6 zipf "$PROBE_RATE" "zipf"
mv "$HARNESS/results/zipf.json" "$OUT/" 2>/dev/null
H_H=$(hit_ratio "$OUT/zipf.json" zipf)

# --- 2. h_A : hit ratio del profilo agentico puro ------------------------
log "misuro h_A (traversal puro) a $PROBE_RATE req/s"
cold_cache
run_k6 traversal "$PROBE_RATE" "trav"
mv "$HARNESS/results/trav.json" "$OUT/" 2>/dev/null
H_A=$(hit_ratio "$OUT/trav.json" traversal)

{
  echo "----------------------------------------------------------------"
  echo "PARAMETRI MISURATI"
  echo "----------------------------------------------------------------"
  printf '  h_H  hit ratio profilo umano      %.3f\n' "$H_H"
  printf '  h_A  hit ratio profilo agentico   %.3f\n' "$H_A"
  printf '  divario                           %.3f\n' \
         "$(awk -v a="$H_H" -v b="$H_A" 'BEGIN{print a-b}')"
  echo
} >> "$REPORT"

# --- 3. C : capacita' dell'origine ---------------------------------------
log "misuro C (capacita' origine) con traversal a ritmi crescenti"
{
  echo "----------------------------------------------------------------"
  echo "CAPACITA' DELL'ORIGINE"
  echo "----------------------------------------------------------------"
  printf '%-8s %10s %9s %9s %9s %10s\n' \
         rate 'origine' 'uso pool' 'app CPU%' 'db CPU%' 'p99 ms'
} >> "$REPORT"

C=""
for rate in $CAP_RATES; do
    printf '    %s req/s ... ' "$rate"
    cold_cache
    sleep 30
    docker compose --profile load run --rm -T \
        -e MODEL=traversal -e RATE="$rate" -e DURATION=120s \
        -e OUTFILE="cap-$rate" -e ENDPOINT=chapter \
        k6 run --quiet /scripts/workload.js < /dev/null \
        > "$OUT/k6-cap-$rate.log" 2>&1 &
    kp=$!

    sleep 60
    inf=0; acpu=0; dcpu=0
    for s in $(seq 1 15); do
        i=$(vmq 'ut_requests_inflight')
        read -r a d <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' \
            | awk '/ut-app /{gsub(/%/,"",$2); x=$2} /ut-db /{gsub(/%/,"",$2); y=$2} END{print x+0, y+0}')"
        inf=$(awk -v s="$inf" -v v="$i" 'BEGIN{print s+v}')
        acpu=$(awk -v m="$acpu" -v v="$a" 'BEGIN{print (v>m)?v:m}')
        dcpu=$(awk -v m="$dcpu" -v v="$d" 'BEGIN{print (v>m)?v:m}')
        sleep 1
    done
    inf=$(awk -v s="$inf" 'BEGIN{printf "%.1f", s/15}')
    util=$(awk -v i="$inf" -v n="$THREADS" 'BEGIN{printf "%.0f", 100*i/n}')
    wait $kp 2>/dev/null

    f="$HARNESS/results/cap-$rate.json"
    [[ -f "$f" ]] && mv "$f" "$OUT/" && f="$OUT/cap-$rate.json"
    p99=$(jq -r '(.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10' "$f" 2>/dev/null || echo 0)
    ha=$(hit_ratio "$f" traversal 2>/dev/null || echo 0)
    orig=$(awk -v r="$rate" -v h="$ha" 'BEGIN{printf "%.0f", r*(1-h)}')

    printf '%-8s %10s %8s%% %9s %9s %10s\n' \
           "$rate" "$orig" "$util" "$acpu" "$dcpu" "$p99" >> "$REPORT"
    echo "origine=$orig uso=${util}% appcpu=$acpu"

    # C = ritmo all'origine oltre cui il pool supera il 90%
    if [[ -z "$C" ]] && awk -v u="$util" 'BEGIN{exit !(u>=90)}'; then
        C="$orig"
    fi
    sleep 10
done

[[ -z "$C" ]] && C=$(awk -v r="$(echo $CAP_RATES | awk '{print $NF}')" 'BEGIN{print r}')

# --- 4. punto operativo derivato ------------------------------------------
{
  echo
  echo "----------------------------------------------------------------"
  echo "PUNTO OPERATIVO DERIVATO"
  echo "----------------------------------------------------------------"
  awk -v hH="$H_H" -v hA="$H_A" -v C="$C" -v at="$ALPHA_TARGET" -v n="$THREADS" '
  BEGIN {
    d = hH - hA
    printf "  C   capacita origine misurata       %.0f req/s\n", C
    printf "  a*  frazione agentica bersaglio     %.2f\n\n", at
    if (d <= 0.01) {
      print "  ERRORE: h_H e h_A sono quasi uguali."
      print "  I due modelli di accesso non producono hit ratio distinti."
      print "  Senza divario, la composizione non puo generare il fenomeno."
      print "  Verificare la dimensione della cache rispetto al corpus."
      exit
    }
    lt = C / ((1-hH) + at*d)
    printf "  lambda_tot derivato               %.0f req/s\n", lt
    printf "\n  Previsione del modello:\n"
    printf "    a=0.00  origine %.0f req/s   uso pool %.0f%%\n", lt*(1-hH), 100*lt*(1-hH)/C
    printf "    a=%.2f  origine %.0f req/s   uso pool %.0f%%  <- ginocchio previsto\n", at, lt*((1-hH)+at*d), 100*lt*((1-hH)+at*d)/C
    printf "    a=1.00  origine %.0f req/s   uso pool %.0f%%\n", lt*(1-hA), 100*lt*(1-hA)/C
    printf "\n  Sweep consigliato: alpha da 0 a %.2f a passi di 0.05,\n", (at*2>1?1:at*2)
    printf "  a lambda_tot=%.0f fisso, almeno 5 ripetizioni per punto\n", lt
    printf "  (10 nei tre punti intorno ad alpha=%.2f).\n", at
  }' >> "$REPORT"

  echo
  echo "CONTROLLI PRIMA DI PROCEDERE"
  echo
  echo "  1. app CPU% al ginocchio deve stare sotto il 50%. Il tetto del"
  echo "     GIL osservato e' ~80%: oltre, il ginocchio sarebbe in parte"
  echo "     artefatto dell interprete e non della coda."
  echo "  2. Se le frequenze in lscpu differiscono fra core, i cpuset"
  echo "     assegnano componenti a tipi di core diversi. Riassegnare"
  echo "     tenendo ogni componente su un solo tipo."
  echo "  3. Il divario h_H - h_A deve superare 0.3, altrimenti la"
  echo "     composizione ha troppa poca leva sul carico all origine."
  echo
  echo "Dettagli in: $OUT"
} >> "$REPORT"

echo; cat "$REPORT"; echo
log "rapporto: $REPORT"