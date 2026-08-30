#!/usr/bin/env bash
#
# split.sh - Il costo nascosto della scan-resistance.
#
# LA DOMANDA
#
# Zhang et al. (SoCC 2025) propongono politiche di sfratto che
# proteggono il contenuto popolare dalla scansione, e Cloudflare le sta
# adottando. Se in regime condiviso la classe esaustiva ottiene hit
# dalla cache riempita dal traffico umano, proteggere l'hot set le
# toglie quel passaggio gratuito e quel carico si riversa sull'origine.
#
# QUELLA PREMESSA E' DA VERIFICARE, NON E' UN DATO. La stima precedente
# (28%) veniva da misure invalidate il 26 agosto dall'offset casuale nel
# generatore. La prima cosa che questo script deve stabilire e' se
# hit_low in regime CONDIVISO e' diverso da zero. Se e' zero non c'e'
# niente da trasferire e la domanda cade.
#
# IL RIFERIMENTO
#
# r=shared manda entrambe le classi a varnish-h, che riceve tutta la
# cache: una sola cache condivisa. Le configurazioni partizionate
# mandano la classe bassa a varnish-l. In ogni caso il traffico passa
# dal router e la cache totale e' TOTAL_MB, quindi si confrontano due
# politiche e non due architetture.
#
# Fino al 30 agosto il router separava le classi anche in modalita'
# shared: il riferimento non esisteva e split-20260830-123521 e' nullo.
#
# PREVISIONE
#
#   il p99 della classe alta migliora al crescere di r
#   il carico totale all'origine PEGGIORA
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-220}"
ALPHA="${ALPHA:-0.25}"
TOTAL_MB="${TOTAL_MB:-128}"
FRACTIONS="${FRACTIONS:-shared 0.50 0.75 0.90 1.00}"
REPS="${REPS:-5}"
GATE="${GATE:-1}"     # 1 = scarta e ripete i run invalidi; 0 = li registra soltanto
WARMUP="${WARMUP:-180}"
MEASURE="${MEASURE:-180}"

STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="results/split-$STAMP"; mkdir -p "$BASE"
CSV="$BASE/points.csv"
echo "r,rep,p99_high,p99_low,hit_high,miss_high,hit_low,miss_low,origin_rps,dropped,fail_rate,ts" > "$CSV"

cleanup() { docker compose --profile split down >/dev/null 2>&1; }
trap cleanup EXIT

for r in $FRACTIONS; do
    if [[ "$r" == "shared" ]]; then
        h=$TOTAL_MB; l=1; low_backend=varnish-h
    else
        h=$(awk -v t="$TOTAL_MB" -v r="$r" 'BEGIN{printf "%.0f", t*r}')
        l=$(awk -v t="$TOTAL_MB" -v r="$r" 'BEGIN{printf "%.0f", (t*(1-r)>1)?t*(1-r):1}')
        low_backend=varnish-l
    fi
    printf '\n\033[1m==> r=%s  alta=%sm  bassa=%sm  classe bassa -> %s\033[0m  (%s)\n' \
        "$r" "$h" "$l" "$low_backend" "$(date +%H:%M)"

    sed "s/__LOW_BACKEND__/$low_backend/" nginx/router.conf.tpl > nginx/router.active.conf

    # La forma precedente (sed -i || echo) non aggiungeva mai la chiave
    # mancante, perche' sed esce con 0 anche se non trova il pattern.
    for kv in "VARNISH_H_SIZE=${h}m" "VARNISH_L_SIZE=${l}m"; do
        k="${kv%%=*}"
        if grep -q "^$k=" .env 2>/dev/null; then
            sed -i "s|^$k=.*|$kv|" .env
        else
            echo "$kv" >> .env
        fi
    done

    docker compose --profile split up -d --force-recreate varnish-h varnish-l router >/dev/null 2>&1
    sleep 12

    for c in varnish-h varnish-l; do
        want=$([[ $c == varnish-h ]] && echo "$h" || echo "$l")
        got=$(docker compose --profile split exec -T $c varnishstat -n /var/lib/varnish/ut -1 -f SMA.s0.g_space 2>/dev/null | awk '{print int($2/1048576)}')
        printf '     %s: spazio=%sMB atteso=%sMB\n' "$c" "$got" "$want"
    done

    rep=1; attempts=0
    while [[ $rep -le $REPS ]]; do
        attempts=$((attempts+1))
        if [[ $attempts -gt $((REPS*2+2)) ]]; then
            echo "  troppi run invalidi su r=$r, passo oltre"; break
        fi
        printf '  rep %s (tentativo %s) ... ' "$rep" "$attempts"
        # Il router riparte insieme alle cache: nginx tiene 64 connessioni
        # keepalive per upstream e se Varnish riparte senza di lui quelle
        # restano appese. E' il sospetto principale per la deriva del 30
        # agosto (0 invalidi nel primo blocco, 5 su 8 nel quarto, stessa
        # identica configurazione).
        docker compose --profile split restart varnish-h varnish-l router >/dev/null 2>&1; sleep 10

        for phase in "$WARMUP:w" "$MEASURE:m"; do
            docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA="$ALPHA" \
                -e RATE="$LAMBDA" -e DURATION="${phase%%:*}s" -e TARGET=http://router:80 \
                -e OUTFILE="${phase##*:}-r$r-$rep" \
                k6 run --quiet /scripts/workload.js < /dev/null > /dev/null 2>&1
            [[ "${phase##*:}" == "w" ]] && rm -f "results/w-r$r-$rep.json"
        done

        f="results/m-r$r-$rep.json"
        if [[ ! -f "$f" ]]; then echo "FALLITO"; sleep 20; continue; fi
        j="$BASE/m-r$r-$rep.json"; mv "$f" "$j"

        # Cancello di validita'. http_req_failed e' una metrica Rate: ha
        # .rate, non .count — con .count il controllo passava sempre.
        dropped=$(jq -r '.metrics.dropped_iterations.values.count // 0' "$j")
        fail_rate=$(jq -r '.metrics.http_req_failed.values.rate // 0' "$j")
        if (( $(awk -v d="$dropped" -v x="$fail_rate" 'BEGIN{print (d>0 || x>0.01)?1:0}') )); then
            printf 'sospetto: scartate=%s errori=%s%% ' "$dropped" \
                "$(awk -v x="$fail_rate" 'BEGIN{printf "%.2f", x*100}')"
            docker compose --profile split logs --tail 150 router varnish-h app \
                > "$BASE/diag-r$r-a$attempts.log" 2>&1
            if [[ "$GATE" == "1" ]]; then
                echo "— INVALIDO, rifaccio"
                mv "$j" "$BASE/invalid-r$r-a$attempts.json"
                sleep 20; continue
            fi
            echo "— registrato (GATE=0)"
        fi

        # hit_low per differenza: k6 omette dal riepilogo le metriche
        # personalizzate senza campioni, quindi "assente" e "zero" sono
        # indistinguibili se la si legge direttamente.
        read -r ph pl hh mh hl ml <<<"$(jq -r '[
            ((.metrics.ut_lat_zipf.values["p(99)"]//0)*10|round/10),
            ((.metrics.ut_lat_traversal.values["p(99)"]//0)*10|round/10),
            (.metrics.ut_hit_zipf.values.count//0),
            (.metrics.ut_miss_zipf.values.count//0),
            (.metrics.ut_hit_traversal.values.count //
              ((.metrics.ut_ok_traversal.values.count//0) - (.metrics.ut_miss_traversal.values.count//0))),
            (.metrics.ut_miss_traversal.values.count//0)
          ]|@tsv' "$j")"

        # Carico all'origine sulla sola fase di misura: lambda*(1-h),
        # ricavato dai miss di entrambe le classi.
        #
        # La versione precedente leggeva il contatore di VictoriaMetrics
        # fra t0 e t1, cioe' su warmup e misura insieme: la fase a cache
        # fredda gonfiava il valore in modo diverso per ogni r, un bias
        # correlato alla variabile indipendente. In piu' l'osservabilita'
        # non e' fra le dipendenze del profilo split, quindi la query
        # tornava vuota e il valore era 0,0 senza segnalare nulla.
        orps=$(awk -v mh="$mh" -v ml="$ml" -v d="$MEASURE" 'BEGIN{printf "%.2f", (mh+ml)/d}')

        echo "$r,$rep,$ph,$pl,$hh,$mh,$hl,$ml,$orps,$dropped,$fail_rate,$(date -Is)" >> "$CSV"
        printf 'p99 alta=%s  hit bassa=%s  origine=%s req/s\n' "$ph" "$hl" "$orps"
        rep=$((rep+1)); sleep 20
    done
done

echo
echo "================================================================"
printf '%-8s %5s %10s %10s %10s %10s %10s\n' "r" "n" "p99 alta" "p99 bassa" "hit alta" "hit bassa" "orig rps"
awk -F, 'NR>1 && $3!="" { r=$1; n[r]++; v[r,n[r]]=$3; w[r,n[r]]=$4
    hh[r]+=$5; mh[r]+=$6; hl[r]+=$7; ml[r]+=$8; o[r]+=$9 }
  END { for (r in n) { c=n[r]
    for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) {
      if(v[r,j]+0<v[r,i]+0){t=v[r,i];v[r,i]=v[r,j];v[r,j]=t}
      if(w[r,j]+0<w[r,i]+0){t=w[r,i];w[r,i]=w[r,j];w[r,j]=t} }
    printf "%-8s %5d %10.1f %10.1f %10.3f %10.3f %10.1f\n", r, c,
      (c%2)?v[r,(c+1)/2]:(v[r,c/2]+v[r,c/2+1])/2,
      (c%2)?w[r,(c+1)/2]:(w[r,c/2]+w[r,c/2+1])/2,
      (hh[r]+mh[r]>0)?hh[r]/(hh[r]+mh[r]):0,
      (hl[r]+ml[r]>0)?hl[r]/(hl[r]+ml[r]):0, o[r]/c } }' "$CSV" | sort

echo
echo "  r = frazione di cache riservata alla classe ad alta localita'."
echo "  shared = riferimento, UNA cache per entrambe le classi."
echo
echo "  PRECONDIZIONE: se hit bassa e' 0 anche su shared, il"
echo "  partizionamento non toglie nulla e la domanda non ha oggetto."
echo
echo "  PARADOSSO CONFERMATO se al crescere di r il p99 alta migliora"
echo "  MA orig rps peggiora rispetto a shared."
echo
echo "Dati: $CSV"