#!/usr/bin/env bash
#
# split.sh - Il costo nascosto della scan-resistance.
#
# LA DOMANDA
#
# Zhang et al. (SoCC 2025) propongono politiche di sfratto che
# proteggono il contenuto popolare dalla scansione, e Cloudflare le sta
# adottando. Ma la classe esaustiva ottiene hit dalla cache riempita dal
# traffico umano: sui dati ARM il 28% delle sue richieste a alpha basso.
# Proteggere l'hot set le toglie quel passaggio gratuito, e tutto quel
# carico va all'origine.
#
# Qui la protezione e' portata all'estremo: due cache separate, con
# frazione riservata r alla classe ad alta localita'. r=1.0 e'
# scan-resistance perfetta.
#
# PREVISIONE
#
#   il p99 interattivo migliora al crescere di r
#   il carico totale all'origine PEGGIORA
#
# Se esiste un r che li migliora entrambi, il compromesso non c'e' e la
# proposta di Zhang e' corretta senza costi nascosti — risultato
# altrettanto pubblicabile.
#
# RIFERIMENTO EQUO
#
# r=shared instrada entrambe le classi alla stessa istanza, ma sempre
# attraverso nginx: si confrontano due politiche, non due architetture.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-220}"
ALPHA="${ALPHA:-0.25}"
TOTAL_MB="${TOTAL_MB:-128}"
FRACTIONS="${FRACTIONS:-shared 0.50 0.75 0.90 1.00}"
REPS="${REPS:-5}"
WARMUP="${WARMUP:-180}"
MEASURE="${MEASURE:-180}"

STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="results/split-$STAMP"; mkdir -p "$BASE"
CSV="$BASE/points.csv"
echo "r,rep,p99_high,p99_low,hit_high,miss_high,hit_low,miss_low,origin_rps,ts" > "$CSV"

cleanup() { docker compose --profile split down >/dev/null 2>&1; }
trap cleanup EXIT

for r in $FRACTIONS; do
    if [[ "$r" == "shared" ]]; then
        h=$TOTAL_MB; l=$TOTAL_MB      # stessa istanza logica, tutta la cache
    else
        h=$(awk -v t="$TOTAL_MB" -v r="$r" 'BEGIN{printf "%.0f", t*r}')
        l=$(awk -v t="$TOTAL_MB" -v r="$r" 'BEGIN{printf "%.0f", (t*(1-r)>1)?t*(1-r):1}')
    fi
    printf '\n\033[1m==> r=%s  alta=%sm  bassa=%sm\033[0m  (%s)\n' "$r" "$h" "$l" "$(date +%H:%M)"

    sed -i "s/^VARNISH_H_SIZE=.*/VARNISH_H_SIZE=${h}m/" .env 2>/dev/null || echo "VARNISH_H_SIZE=${h}m" >> .env
    sed -i "s/^VARNISH_L_SIZE=.*/VARNISH_L_SIZE=${l}m/" .env 2>/dev/null || echo "VARNISH_L_SIZE=${l}m" >> .env
    docker compose --profile split up -d --force-recreate varnish-h varnish-l router >/dev/null 2>&1
    sleep 12

    for rep in $(seq 1 "$REPS"); do
        printf '  rep %s ... ' "$rep"
        docker compose --profile split restart varnish-h varnish-l >/dev/null 2>&1; sleep 8

        b=$(curl -gs -G --data-urlencode 'query=sum(ut_requests_total{endpoint="chapter"})' \
            http://localhost:8428/api/v1/query | jq -r '[.data.result[].value[1]|tonumber]|add // 0')
        t0=$(date +%s.%N)

        for phase in "$WARMUP:w" "$MEASURE:m"; do
            docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA="$ALPHA" \
                -e RATE="$LAMBDA" -e DURATION="${phase%%:*}s" -e TARGET=http://router:80 \
                -e OUTFILE="${phase##*:}-r$r-$rep" \
                k6 run --quiet /scripts/workload.js < /dev/null > /dev/null 2>&1
            [[ "${phase##*:}" == "w" ]] && rm -f "results/w-r$r-$rep.json"
        done

        a=$(curl -gs -G --data-urlencode 'query=sum(ut_requests_total{endpoint="chapter"})' \
            http://localhost:8428/api/v1/query | jq -r '[.data.result[].value[1]|tonumber]|add // 0')
        t1=$(date +%s.%N)
        orps=$(awk -v b="$b" -v a="$a" -v x="$t0" -v y="$t1" 'BEGIN{d=a-b; e=y-x; printf "%.1f", (e>0&&d>=0)?d/e:0}')

        f="results/m-r$r-$rep.json"
        if [[ -f "$f" ]]; then
            mv "$f" "$BASE/"
            read -r ph pl hh mh hl ml <<<"$(jq -r '[
                ((.metrics.ut_lat_zipf.values["p(99)"]//0)*10|round/10),
                ((.metrics.ut_lat_traversal.values["p(99)"]//0)*10|round/10),
                (.metrics.ut_hit_zipf.values.count//0),(.metrics.ut_miss_zipf.values.count//0),
                (.metrics.ut_hit_traversal.values.count//0),(.metrics.ut_miss_traversal.values.count//0)
              ]|@tsv' "$BASE/m-r$r-$rep.json")"
            echo "$r,$rep,$ph,$pl,$hh,$mh,$hl,$ml,$orps,$(date -Is)" >> "$CSV"
            printf 'p99 alta=%s  origine=%s req/s\n' "$ph" "$orps"
        else
            echo "FALLITO"
        fi
        sleep 20
    done
done

echo
echo "================================================================"
printf '%-8s %5s %11s %11s %11s %11s\n' "r" "n" "p99 alta" "p99 bassa" "hit alta" "orig rps"
awk -F, 'NR>1 && $3!="" { r=$1; n[r]++; v[r,n[r]]=$3; w[r,n[r]]=$4
    hh[r]+=$5; mh[r]+=$6; o[r]+=$9 }
  END { for (r in n) { c=n[r]
    for(i=1;i<=c;i++) for(j=i+1;j<=c;j++) {
      if(v[r,j]+0<v[r,i]+0){t=v[r,i];v[r,i]=v[r,j];v[r,j]=t}
      if(w[r,j]+0<w[r,i]+0){t=w[r,i];w[r,i]=w[r,j];w[r,j]=t} }
    printf "%-8s %5d %11.1f %11.1f %11.3f %11.1f\n", r, c,
      (c%2)?v[r,(c+1)/2]:(v[r,c/2]+v[r,c/2+1])/2,
      (c%2)?w[r,(c+1)/2]:(w[r,c/2]+w[r,c/2+1])/2,
      hh[r]/(hh[r]+mh[r]), o[r]/c } }' "$CSV" | sort

echo
echo "  r = frazione di cache riservata alla classe ad alta localita'."
echo "  shared = riferimento, cache condivisa attraverso lo stesso router."
echo
echo "  PARADOSSO CONFERMATO se al crescere di r il p99 alta migliora"
echo "  MA orig rps peggiora rispetto a shared. La protezione della"
echo "  cache sposta il costo sull'origine invece di eliminarlo."
echo
echo "  ASSENTE se esiste un r che migliora entrambi: allora la"
echo "  proposta di Zhang non ha costi nascosti."
echo
echo "Dati: $CSV"