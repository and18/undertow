#!/usr/bin/env bash
#
# treclassi.sh - Costo e latenza per classe, a volume totale costante.
#
# Prima campagna del progetto in cui esistono tutte e tre le classi di
# cui parla la tesi: umana (Zipf), agentica (sessioni corte su capitoli
# contigui, una persona aspetta) ed esaustiva (scansione, nessuno
# aspetta).
#
# MEASURE e' derivato, non scelto: la classe esaustiva deve attraversare
# tutto il corpus almeno una volta, altrimenti il suo hit ratio e' un
# campione di una finestra e non una proprieta' del modello di accesso
# (decisions.md 28). A alpha basso questo costa molto tempo, ed e' il
# prezzo di una misura valida.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-110}"
# MODEL=zipf|agent|traversal isola una classe: e' la calibrazione che
# farebbe un controllore a costo esogeno.
MODEL="${MODEL:-mix}"
TOTAL_MB="${TOTAL_MB:-128}"
REPS="${REPS:-2}"
WARMUP="${WARMUP:-300}"
# GATE=0 registra i run con errori invece di scartarli: oltre la
# saturazione gli errori SONO il segnale, e il cancello butterebbe
# proprio i punti che dimostrano il collasso.
GATE="${GATE:-1}"
CORPUS="${CORPUS:-16954}"
POINTS="${POINTS:-0.00:0.05 0.10:0.05 0.20:0.05 0.30:0.05 0.40:0.05 0.25:0.02 0.25:0.10 0.25:0.20 0.00:0.05}"

STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="results/tre-$STAMP"; mkdir -p "$BASE"
CSV="$BASE/points.csv"
echo "alpha,beta,rep,measure,p99_zipf,p99_agent,p99_trav,h_zipf,h_agent,h_trav,origin_rps,dropped,fail,ts" > "$CSV"

if grep -q '^VARNISH_SIZE=' .env 2>/dev/null; then
    sed -i "s/^VARNISH_SIZE=.*/VARNISH_SIZE=${TOTAL_MB}m/" .env
else
    echo "VARNISH_SIZE=${TOTAL_MB}m" >> .env
fi
# app ricreata insieme a varnish: BUDGET_LOW e BUDGET_WAIT sono letti
# una sola volta all'avvio del processo.
docker compose up -d --force-recreate varnish app >/dev/null 2>&1; sleep 15
printf "    budget=%s wait=%s\n" "${BUDGET_LOW:-0}" "${BUDGET_WAIT:-0}"

cleanup() { docker compose down >/dev/null 2>&1; }
trap cleanup EXIT

for pt in $POINTS; do
    A="${pt%%:*}"; B="${pt##*:}"
    # copertura del corpus per la classe esaustiva
    M=$(awk -v c="$CORPUS" -v l="$LAMBDA" -v a="$A" \
        'BEGIN{ if (a<=0) {print 620} else {m=c/(l*a); print (m<620)?620:int(m+1)} }')
    printf '\n\033[1m==> alpha=%s beta=%s  measure=%ss\033[0m  (%s)\n' "$A" "$B" "$M" "$(date +%H:%M)"

    rep=1; att=0
    while [[ $rep -le $REPS ]]; do
        att=$((att+1))
        [[ $att -gt $((REPS*2+2)) ]] && { echo "  troppi invalidi, passo oltre"; break; }
        printf '  rep %s (tent %s) ... ' "$rep" "$att"
        docker compose restart varnish >/dev/null 2>&1; sleep 8

        for ph in "$WARMUP:w" "$M:m"; do
            d="${ph%%:*}"; t="${ph##*:}"
            sk=0
            [[ "$t" == "m" ]] && sk=$(awk -v w="$WARMUP" -v l="$LAMBDA" -v a="$A" 'BEGIN{printf "%d", w*l*a}')
            docker compose --profile load run --rm -T -e MODEL="$MODEL" -e ALPHA="$A" -e BETA="$B" \
                -e RATE="$LAMBDA" -e DURATION="${d}s" -e TARGET=http://varnish:80 \
                -e TRAV_SKIP="$sk" -e OUTFILE="$t-a$A-b$B-$rep" \
                k6 run --quiet /scripts/workload.js < /dev/null > /dev/null 2>&1
            [[ "$t" == "w" ]] && rm -f "results/w-a$A-b$B-$rep.json"
        done

        f="results/m-a$A-b$B-$rep.json"
        [[ -f "$f" ]] || { echo "FALLITO"; sleep 15; continue; }
        j="$BASE/m-a$A-b$B-$rep.json"; mv "$f" "$j"

        dr=$(jq -r '.metrics.dropped_iterations.values.count // 0' "$j")
        fr=$(jq -r '.metrics.http_req_failed.values.rate // 0' "$j")
        if (( $(awk -v d="$dr" -v x="$fr" 'BEGIN{print (d>0 || x>0.01)?1:0}') )); then
            printf 'sospetto: scartate=%s errori=%.2f%% ' "$dr" "$(awk -v x="$fr" 'BEGIN{print x*100}')"
            if [[ "$GATE" == "1" ]]; then
                echo "— INVALIDO, rifaccio"
                mv "$j" "$BASE/invalid-a$A-b$B-$att.json"; sleep 15; continue
            fi
            echo "— registrato (GATE=0)"
        fi

        read -r pz pa pt_ hz ha ht orps <<<"$(jq -r --arg m "$M" '
          def n(x): (x // 0);
          def hr(h;t): (if (n(h)+n(t))>0 then ((n(h)/(n(h)+n(t)))*1000|round)/1000 else 0 end);
          [ ((n(.metrics.ut_lat_zipf.values["p(99)"])*10|round)/10),
            ((n(.metrics.ut_lat_agent.values["p(99)"])*10|round)/10),
            ((n(.metrics.ut_lat_traversal.values["p(99)"])*10|round)/10),
            hr(.metrics.ut_hit_zipf.values.count; .metrics.ut_miss_zipf.values.count),
            hr(.metrics.ut_hit_agent.values.count; .metrics.ut_miss_agent.values.count),
            hr(.metrics.ut_hit_traversal.values.count; .metrics.ut_miss_traversal.values.count),
            ((( n(.metrics.ut_miss_zipf.values.count)
              + n(.metrics.ut_miss_agent.values.count)
              + n(.metrics.ut_miss_traversal.values.count) ) / ($m|tonumber) * 100|round)/100)
          ] | @tsv' "$j")"

        echo "$A,$B,$rep,$M,$pz,$pa,$pt_,$hz,$ha,$ht,$orps,$dr,$fr,$(date -Is)" >> "$CSV"
        printf 'p99 umano=%s agente=%s  hit agente=%s  origine=%s\n' "$pz" "$pa" "$ha" "$orps"
        rep=$((rep+1)); sleep 15
    done
done

echo
echo "================================================================"
printf '%-6s %-6s %4s %9s %9s %9s %8s %8s %8s %9s\n' \
  "alpha" "beta" "n" "p99 uman" "p99 agen" "p99 trav" "h uman" "h agen" "h trav" "orig rps"
awk -F, 'NR>1 && $5!="" { k=$1" "$2; n[k]++
    for(i=5;i<=11;i++) s[k,i]+=$i }
  END { for (k in n) { c=n[k]; split(k,f," ")
    printf "%-6s %-6s %4d %9.1f %9.1f %9.1f %8.3f %8.3f %8.3f %9.2f\n", f[1], f[2], c,
      s[k,5]/c, s[k,6]/c, s[k,7]/c, s[k,8]/c, s[k,9]/c, s[k,10]/c, s[k,11]/c } }' "$CSV" | sort

echo
echo "  alpha=0.00 compare due volte, in testa e in coda: controllo di deriva."
echo "  La riga che conta: il p99 e l'hit ratio della classe agentica"
echo "  mentre cresce la quota esaustiva, a volume totale costante."
echo "Dati: $CSV"
