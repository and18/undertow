#!/usr/bin/env bash
#
# null-test.sh - Esegue il test nullo completo e produce un rapporto compatto.
#
# Per ogni fase (ceiling, app) e per ogni ritmo:
#   - avvia un campionatore di CPU sui container
#   - lancia k6 a quel ritmo
#   - estrae dal sommario JSON le metriche che contano
#   - registra il picco di CPU per container durante quel gradino
#
# Il rapporto finale sta in una pagina: e' quello da leggere e condividere.
# I log completi di k6 restano nei file, non a schermo, perche' k6 emette
# una riga di WARN per ogni richiesta fallita e a 8000 req/s sono decine
# di migliaia di righe inutili.
#
# Uso:
#   ./load/null-test.sh
#   RATES="500 1000 2000" DURATION=20s ./load/null-test.sh
#
set -uo pipefail

HARNESS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HARNESS"

RATES="${RATES:-500 1000 2000 4000 8000 16000}"
PHASES="${PHASES:-ceiling app}"
DURATION="${DURATION:-30s}"
GAP="${GAP:-10}"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$HARNESS/results/null-test-$STAMP"
REPORT="$OUT/report.txt"

mkdir -p "$OUT"
chmod 777 "$HARNESS/results" 2>/dev/null || true

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }

# --- campionatore di CPU -------------------------------------------------
# Campiona ogni 2s in CSV. Il container di k6 ha nome generato da
# "docker compose run", quindi si normalizza a "k6".

sampler_start() {
    local f="$1"
    : > "$f"
    (
        while true; do
            docker stats --no-stream --format '{{.Name}},{{.CPUPerc}}' 2>/dev/null \
              | sed 's/^undertow-k6-run-[a-f0-9]*/k6/' >> "$f"
            sleep 2
        done
    ) >/dev/null 2>&1 &
    echo $!
}

sampler_peak() {
    # Picco di CPU per container, formato "nome=NN".
    awk -F, '{gsub(/%/,"",$2); if ($2+0 > m[$1]) m[$1]=$2+0}
             END {for (c in m) printf "%s=%.0f ", c, m[c]}' "$1"
}

annotate() {
    curl -s -X POST http://localhost:3000/api/annotations \
        -H 'Content-Type: application/json' \
        -u admin:undertow \
        -d "{\"time\":$(date +%s000),\"tags\":[\"undertow\",\"$1\"],\"text\":\"$2\"}" \
        > /dev/null 2>&1 || true
}

# --- verifica preliminare -------------------------------------------------
log "verifico che lo stack risponda"
if ! docker compose ps --status running --format '{{.Service}}' | grep -q varnish; then
    echo "ERRORE: lo stack non e' attivo. Lancia:  docker compose up -d" >&2
    exit 1
fi

{
    echo "TEST NULLO — $(date -Is)"
    echo "================================================================"
    echo
    echo "Configurazione:"
    grep -E '^(CPUSET_|THREADS|BACKLOG|DB_POOL|VARNISH_SIZE)' .env | sed 's/^/  /'
    echo "  RATES=$RATES"
    echo "  DURATION=$DURATION"
    echo "  commit=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
    echo "  nproc=$(nproc)"
    echo
} > "$REPORT"

# --- sweep ----------------------------------------------------------------
for phase in $PHASES; do
    log "fase: $phase"
    {
        echo "----------------------------------------------------------------"
        echo "FASE $phase"
        echo "----------------------------------------------------------------"
        printf '%-8s %9s %9s %9s %8s  %s\n' \
               rate dropped reqs 'p99(ms)' 'fail%' 'picco CPU %'
    } >> "$REPORT"

    for rate in $RATES; do
        printf '    ritmo %s ... ' "$rate"
        tag="$phase-$rate"
        cpuf="$OUT/cpu-$tag.csv"
        k6log="$OUT/k6-$tag.log"

        annotate "$phase-$rate" "Inizio gradino $rate req/s"

        pid=$(sampler_start "$cpuf")

        docker compose --profile load run --rm -T -T \
            -e PHASE="$phase" -e RATE="$rate" -e DURATION="$DURATION" \
            -e OUTFILE="s-$tag" \
            k6 run --quiet /scripts/null-test.js > "$k6log" 2>&1

        kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null

        sum="$HARNESS/results/s-$tag.json"
        if [[ -f "$sum" ]]; then
            mv "$sum" "$OUT/"
            sum="$OUT/s-$tag.json"
            read -r dropped reqs p99 failed <<<"$(jq -r '
                [ (.metrics.dropped_iterations.values.count // 0),
                  (.metrics.http_reqs.values.count // 0),
                  ((.metrics.http_req_duration.values["p(99)"] // 0)*10|round/10),
                  ((.metrics.http_req_failed.values.rate // 0)*1000|round/10)
                ] | @tsv' "$sum")"
        else
            dropped="?"; reqs="?"; p99="?"; failed="?"
        fi

        peak="$(sampler_peak "$cpuf")"
        printf '%-8s %9s %9s %9s %8s  %s\n' \
               "$rate" "$dropped" "$reqs" "$p99" "$failed" "$peak" >> "$REPORT"

        if [[ "$dropped" == "0" ]]; then echo "ok"; else echo "scartate: $dropped"; fi

        annotate "$phase-$rate" "Fine gradino $rate req/s"
        sleep "$GAP"
    done
    echo >> "$REPORT"
done

# --- verdetto -------------------------------------------------------------
{
    echo "================================================================"
    echo "VERDETTO"
    echo "================================================================"
    for phase in $PHASES; do
        best=""
        for rate in $RATES; do
            f="$OUT/s-$phase-$rate.json"
            # dropped==0 e' necessario ma non sufficiente: un gradino con
            # p99 di 17 secondi e il 3% di fallimenti descrive un sistema
            # gia' rotto, anche se il generatore ha retto il ritmo.
            ok=$(jq -r '
                if ((.metrics.dropped_iterations.values.count // 0) == 0)
                   and ((.metrics.http_req_failed.values.rate // 0) < 0.001)
                   and ((.metrics.http_req_duration.values["p(99)"] // 9999) < 200)
                then "1" else "0" end' "$f" 2>/dev/null || echo 0)
            if [[ "$ok" == "1" ]]; then best="$rate"; else break; fi
        done
        if [[ -n "$best" ]]; then
            echo "  $phase: tetto pulito a $best req/s"
        else
            echo "  $phase: nessun ritmo pulito — il generatore e' il limite"
        fi
    done
    echo
    echo "Regola operativa: gli sweep girano a un DECIMO del tetto della"
    echo "fase ceiling. E' quel margine che permette di affermare che il"
    echo "generatore non ha mai influito sulla misura."
    echo
    echo "Da controllare a mano nella colonna picco CPU:"
    echo "  varnish  deve restare sotto il 60% del suo budget di core."
    echo "           Se satura, la cache diventa il collo di bottiglia e"
    echo "           si misurerebbe lei invece dell'application server."
    echo "  k6       se supera il 90%, il tetto e' il generatore."
    echo "  app      se satura la CPU prima che il pool di thread si"
    echo "           riempia, il limite e' il GIL e non il pool."
    echo
    echo "Log completi e sommari JSON in: $OUT"
} >> "$REPORT"

echo
cat "$REPORT"
echo
log "rapporto: $REPORT"