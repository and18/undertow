#!/usr/bin/env bash
#
# mediator.sh - Intervento sul mediatore: la cache e' davvero il meccanismo?
#
# LA DOMANDA
#
# Lo sweep mostra che aumentando la frazione di traffico a bassa localita'
# il sistema attraversa un ginocchio. Ma correlazione non e' meccanismo:
# alpha guida ogni anello della catena per costruzione, quindi tutte le
# correlazioni lungo la catena sono vicine a 1 senza identificare nulla.
#
# L'unico modo per identificare la causa e' INTERVENIRE sul mediatore
# ipotizzato.
#
# PREVISIONE FALSIFICABILE
#
#   cache < working set   il ginocchio e' presente, e la sua posizione
#                         dipende dal rapporto cache/working-set
#
#   cache >= working set  il contributo della competizione in cache al
#                         ginocchio scompare o si riduce drasticamente,
#                         anche ad alpha = 1
#
# Formulazione deliberatamente cauta: "il contributo mediato dalla cache
# scompare" e non "il ginocchio deve sparire". Altri meccanismi
# indipendenti dalla cache — costo di generazione, churn di connessioni,
# burstiness — potrebbero produrne uno comunque. L'esperimento e'
# informativo in tutti e tre gli esiti possibili.
#
# MISURA PRIMARIA DEL CARICO ALL'ORIGINE
#
# Finora il carico all'origine era DEDOTTO da lambda*(1-hit). Qui viene
# anche MISURATO, come delta del contatore ut_requests_total diviso il
# tempo realmente trascorso. Il confronto fra i due e' la verifica
# quantitativa dell'anello centrale della catena: se coincidono, il
# passaggio cache -> origine e' chiuso; se non coincidono, esiste un
# percorso che il modello non vede.
#
# Il delta del contatore e' esatto; una media di campioni di rate() e'
# un'approssimazione. Si usa il primo come misura, il secondo solo come
# diagnostica del picco.
#
# TERMINOLOGIA
#
# alpha e' la frazione di traffico a BASSA LOCALITA', non ancora la
# frazione agentica: soltanto uno dei nove parametri di workload varia.
# Vedi docs/findings.md.
#
# WORKING SET
#
#   245 MB, 16.954 oggetti, ~10,6 KB medi in cache dopo compressione.
#
# Uso:
#   DRY=1 ./load/mediator.sh          verifica della logica, NON dati
#   ./load/mediator.sh                campagna completa
#   SIZES="128m 512m" REPS=3 ./load/mediator.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

# --- parametri sperimentali ----------------------------------------------

LAMBDA="${LAMBDA:-260}"

#   128m =  52% del working set   competizione forte
#   256m = 104% del working set   al limite
#   512m = 209% del working set   nessuna competizione
SIZES="${SIZES:-128m 256m 512m}"

# alpha=1.00 e' indispensabile: "nessun ginocchio a nessun alpha" non si
# testa fermandosi a 0.50.
ALPHAS="${ALPHAS:-0.00 0.15 0.30 0.50 1.00}"

REPS="${REPS:-3}"

# Minimo validato per la cache da 512 MB su questo workload. Con 300 s gli
# hit ratio a 128m e 512m risultano identici — si sta misurando il
# riempimento della cache, non il regime. Warm-up piu' corti non
# producono misure valide.
WARMUP="${WARMUP:-600}"

MEASURE="${MEASURE:-180}"
DRAIN="${DRAIN:-30}"
SEED="${SEED:-42}"

if [[ "${DRY:-0}" == "1" ]]; then
    # SOLO verifica della logica dello script. I numeri prodotti da un
    # dry run non sono dati sperimentali in nessuna circostanza.
    SIZES="128m 512m"; ALPHAS="0.00 0.50"; REPS=1
    WARMUP=120; MEASURE=45; DRAIN=10
fi

OUT="${OUT:-$HARNESS/results/mediator-$(date +%Y%m%d-%H%M%S)}"
CSV="$OUT/points.csv"
LOG="$OUT/mediator.log"

mkdir -p "$OUT"
# Il container k6 gira come utente non-root e scrive in /results.
chmod 777 "$HARNESS/results" 2>/dev/null || true

ORIG_SIZE=$(grep -E '^VARNISH_SIZE=' .env | cut -d= -f2 | tr -d ' ')
restore() { sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$ORIG_SIZE/" .env
            docker compose up -d --force-recreate varnish >/dev/null 2>&1; }
trap restore EXIT

log() { printf '\033[1m==>\033[0m %s\n' "$*" | tee -a "$LOG"; }

# --data-urlencode evita di codificare a mano le parentesi quadre, che e'
# gia' costato un run: %5B30s%5] invece di %5B30s%5D fallisce in silenzio
# restituendo sempre zero.
vmq() {
    curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '.data.result[0].value[1] // "0"'
}
vmq_sum() {
    curl -gs -G --data-urlencode "query=$1" \
        "http://localhost:8428/api/v1/query" \
        | jq -r '[.data.result[].value[1]|tonumber] | add // 0'
}

# --- schema CSV ------------------------------------------------------------
# Due schemi CSV diversi nello stesso progetto (sweep.sh e mediator.sh)
# sono un rischio latente: un'analisi scritta per uno e applicata
# all'altro legge le colonne sbagliate senza errori. Qui lo schema si
# verifica e, se non corrisponde, si esce invece di migrare in silenzio.

HEADER="cache,alpha,rep,lambda,completed,dropped,failed,p50,p95,p99,p999,hit_h,miss_h,hit_a,miss_a,inflight,app_cpu,db_cpu,origin_rps_mean,origin_rps_max,ts"

if [[ -e "$CSV" ]]; then
    found=$(head -n1 "$CSV" 2>/dev/null || true)
    if [[ "$found" != "$HEADER" ]]; then
        echo "ERRORE: schema CSV incompatibile in $CSV" >&2
        echo "atteso:  $HEADER" >&2
        echo "trovato: $found" >&2
        echo "Usa una directory OUT nuova invece di migrare un dataset." >&2
        exit 1
    fi
else
    echo "$HEADER" > "$CSV"
fi

{
  echo "MEDIATOR — $(date -Is)"
  echo "commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo "lambda=$LAMBDA sizes=$SIZES alphas=$ALPHAS reps=$REPS"
  echo "warmup=${WARMUP}s measure=${MEASURE}s drain=${DRAIN}s seed=$SEED"
  echo "dry_run=${DRY:-0}"
  echo "working set = 245 MB (16954 oggetti)"
  grep -E '^(THREADS|BACKLOG|DB_POOL|CPUSET_)' .env
} >> "$LOG"

# --- conteggio e stima -----------------------------------------------------
total=0
for s in $SIZES; do for a in $ALPHAS; do for r in $(seq 1 "$REPS"); do
    total=$((total+1)); done; done; done
log "$total misure, stima $(awk -v n="$total" -v w="$WARMUP" -v m="$MEASURE" \
    -v d="$DRAIN" 'BEGIN{printf "%.0f", n*(w+m+d+50)/60}') minuti"

# --- ciclo principale ------------------------------------------------------
i=0
for size in $SIZES; do
    log "cache = $size  ($(awk -v s="${size%m}" 'BEGIN{printf "%.0f", 100*s/245}')% del working set)"
    sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=$size/" .env
    docker compose up -d --force-recreate varnish >/dev/null 2>&1
    sleep 10

    # La dimensione di cache NON si randomizza: cambiarla richiede il
    # riavvio di Varnish. Si randomizzano alpha e ripetizione DENTRO ogni
    # dimensione, che e' dove la deriva temporale della macchina potrebbe
    # confondersi con l'effetto studiato.
    jobs=()
    for a in $ALPHAS; do for r in $(seq 1 "$REPS"); do jobs+=("$a:$r"); done; done
    mapfile -t jobs < <(printf '%s\n' "${jobs[@]}" | shuf --random-source=<(yes "$SEED"))

    for job in "${jobs[@]}"; do
        a="${job%:*}"; rep="${job#*:}"; i=$((i+1))
        if grep -q "^$size,$a,$rep," "$CSV" 2>/dev/null; then
            echo "  [$i/$total] $size alpha=$a rep=$rep  gia fatto"; continue
        fi

        printf '  [%2d/%2d] %s alpha=%s rep=%s ... ' "$i" "$total" "$size" "$a" "$rep"
        tag="${size}-a${a}-r${rep}"
        max_orps=0

        # Cache fredda prima di OGNI punto: con l'ordine randomizzato,
        # ereditare la cache del punto precedente sarebbe fatale.
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

        # Baseline dopo l'avvio del generatore: prendendola prima, il
        # denominatore includerebbe l'avvio del container e la finestra
        # risulterebbe piu' lunga del periodo in cui il carico e' fluito.
        sleep 2
        origin_before=$(vmq_sum 'sum(ut_requests_total{endpoint="chapter"})')
        t_before=$(date +%s.%N)

        # Campionamento diagnostico per l'intera finestra. Da qui NON esce
        # la misura del carico all'origine — quella viene dal delta del
        # contatore — ma solo occupazione del pool, CPU e picco di rate.
        sleep 15
        inf=0; ac=0; dc=0; ns=0
        while kill -0 "$kp" 2>/dev/null; do
            v=$(vmq 'ut_requests_inflight')
            orps=$(vmq_sum 'sum(rate(ut_requests_total[30s]))')
            awk -v x="$max_orps" -v y="$orps" 'BEGIN{exit !(y>x)}' && max_orps="$orps"
            read -r x y <<<"$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null \
                | awk '/ut-app /{gsub(/%/,"",$2); p=$2} /ut-db /{gsub(/%/,"",$2); q=$2} END{print p+0, q+0}')"
            inf=$(awk -v s="$inf" -v v="$v" 'BEGIN{print s+v}')
            ac=$(awk -v m="$ac" -v v="$x" 'BEGIN{print (v>m)?v:m}')
            dc=$(awk -v m="$dc" -v v="$y" 'BEGIN{print (v>m)?v:m}')
            ns=$((ns+1)); sleep 3
        done
        wait "$kp" 2>/dev/null

        origin_after=$(vmq_sum 'sum(ut_requests_total{endpoint="chapter"})')
        t_after=$(date +%s.%N)

        inf=$(awk -v s="$inf" -v n="$ns" 'BEGIN{printf "%.2f", (n>0)?s/n:0}')

        # Delta diviso il tempo REALMENTE trascorso, non la durata
        # nominale: fra il campione iniziale e l'uscita di k6 ci sono
        # l'avvio del container e il gracefulStop, quindi dividere per
        # MEASURE sovrastimerebbe.
        mean_orps=$(awk -v b="$origin_before" -v a="$origin_after" \
                        -v t0="$t_before" -v t1="$t_after" 'BEGIN{
            d = a - b; el = t1 - t0
            if (d < 0) { print "NA"; exit }        # contatore azzerato: app riavviata
            printf "%.1f", (el > 0) ? d/el : 0 }')
        [[ "$mean_orps" == "NA" ]] && log "ATTENZIONE: contatore azzerato durante $tag"

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
            echo "$size,$a,$rep,$LAMBDA,$comp,$drop,$fail,$p50,$p95,$p99,$p999,$hh,$mh,$ha,$ma,$inf,$ac,$dc,$mean_orps,$max_orps,$(date -Is)" >> "$CSV"
            printf 'p99=%s  pool=%s  orig=%s req/s\n' "$p99" "$inf" "$mean_orps"
        else
            # 11 campi vuoti fra lambda e inflight: completed, dropped,
            # failed, p50, p95, p99, p999, hit_h, miss_h, hit_a, miss_a.
            echo "$size,$a,$rep,$LAMBDA,,,,,,,,,,,,$inf,$ac,$dc,$mean_orps,$max_orps,$(date -Is)" >> "$CSV"
            echo "FALLITO — vedi $OUT/k6-$tag.log"
        fi
        sleep "$DRAIN"
    done
done

# --- riepilogo -------------------------------------------------------------
{
  echo
  echo "================================================================"
  echo "RISULTATO"
  echo "================================================================"
  awk -F, 'NR>1 && $10!="" {
      k=$1" "$2; n[k]++; v[k,n[k]]=$10
      hit[k]+=$12+$14; mis[k]+=$13+$15
      if ($19 != "NA") { orps[k]+=$19; on[k]++ }
      lam[k]+=$4
  }
  END {
    printf "%-7s %-6s %4s %10s %8s %11s %11s %8s\n",
           "cache","alpha","n","p99 med","hit","orig prev","orig oss","scarto"
    for (k in n) {
      c=n[k]
      for(i=1;i<=c;i++) for(j=i+1;j<=c;j++)
        if(v[k,j]+0<v[k,i]+0){t=v[k,i];v[k,i]=v[k,j];v[k,j]=t}
      m=(c%2)?v[k,(c+1)/2]:(v[k,c/2]+v[k,c/2+1])/2
      h=(hit[k]+mis[k]>0)?hit[k]/(hit[k]+mis[k]):0
      pred=(lam[k]/c)*(1-h)
      obs=(on[k]>0)?orps[k]/on[k]:0
      dev=(pred>0)?100*(obs-pred)/pred:0
      split(k,p," ")
      printf "%-7s %-6s %4d %10.1f %8.3f %11.1f %11.1f %7.1f%%\n",
             p[1],p[2],c,m,h,pred,obs,dev
    }
  }' "$CSV" | (read -r hdr; echo "$hdr"; sort -k1,1 -k2,2)

  echo
  echo "COME LEGGERE"
  echo
  echo "  Working set nominale 245 MB:"
  echo "    128m =  52%   sotto il working set, competizione forte"
  echo "    256m = 104%   appena sopra"
  echo "    512m = 209%   margine ampio, nessuna competizione attesa"
  echo
  echo "  VERIFICA DELL'ANELLO CENTRALE"
  echo "    orig prev = lambda x (1 - hit),  dedotto"
  echo "    orig oss  = delta di ut_requests_total / tempo,  misurato"
  echo "    Uno scarto piccolo chiude quantitativamente il passaggio"
  echo "    cache -> origine. Uno scarto grande indica un percorso che"
  echo "    il modello non vede, ed e' un risultato a sua volta."
  echo
  echo "  ESITO DEL MEDIATORE — tre livelli, non due"
  echo
  echo "  SUPPORTATO"
  echo "    Con cache >= working set la dipendenza di p99 da alpha"
  echo "    scompare, mentre sotto il working set il ginocchio c'e'."
  echo "    La competizione in cache e' il meccanismo, dimostrato per"
  echo "    intervento e non per correlazione."
  echo
  echo "  PARZIALMENTE SUPPORTATO"
  echo "    Il ginocchio si sposta molto con la cache ma non sparisce."
  echo "    La cache e' un mediatore importante ma non unico: restano"
  echo "    costo di generazione, churn di connessioni, burstiness."
  echo
  echo "  NON SUPPORTATO COME MECCANISMO PRINCIPALE"
  echo "    Il ginocchio resta sostanzialmente dov'e' anche con cache"
  echo "    abbondante. Il meccanismo dominante e' altrove: la prossima"
  echo "    cosa da guardare e' il costo di generazione della pagina."
  echo
  echo "  NOTA. alpha e' la frazione di traffico a bassa localita', non"
  echo "  una frazione agentica calibrata empiricamente."
  echo
  echo "Dati: $CSV"
} | tee -a "$LOG"