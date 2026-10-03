#!/usr/bin/env bash
#
# split.sh - The hidden cost of scan-resistance.
#
# THE QUESTION
#
# Zhang et al. (SoCC 2025) propose eviction policies that
# protect popular content from scans, and Cloudflare is adopting them.
# If in the shared regime the exhaustive class gets hits from the cache
# filled by human traffic, protecting the hot set takes that free ride
# away from it and that load spills onto the origin.
#
# THAT PREMISE IS TO BE CHECKED, IT IS NOT A DATUM. The previous estimate
# (28%) came from measurements invalidated on 26 August by the random
# offset in the generator. The first thing this script must establish is
# whether hit_low in the SHARED regime is different from zero. If it is
# zero there is nothing to transfer and the question falls.
#
# THE REFERENCE
#
# r=shared sends both classes to varnish-h, which receives the whole
# cache: a single shared cache. The partitioned configurations
# send the low class to varnish-l. In every case the traffic goes
# through the router and the total cache is TOTAL_MB, so two
# policies are compared and not two architectures.
#
# Until 30 August the router separated the classes even in shared
# mode: the reference did not exist and split-20260830-123521 is null.
#
# PREDICTION
#
#   the high class's p99 improves as r grows
#   the total origin load WORSENS
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

LAMBDA="${LAMBDA:-220}"
ALPHA="${ALPHA:-0.25}"
TOTAL_MB="${TOTAL_MB:-128}"
FRACTIONS="${FRACTIONS:-shared 0.50 0.75 0.90 1.00}"
REPS="${REPS:-5}"
GATE="${GATE:-1}"     # 1 = discard and repeat invalid runs; 0 = only record them
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
    printf '\n\033[1m==> r=%s  high=%sm  low=%sm  low class -> %s\033[0m  (%s)\n' \
        "$r" "$h" "$l" "$low_backend" "$(date +%H:%M)"

    sed "s/__LOW_BACKEND__/$low_backend/" nginx/router.conf.tpl > nginx/router.active.conf

    # The previous form (sed -i || echo) never added the missing key,
    # because sed exits with 0 even if it does not find the pattern.
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
        printf '     %s: space=%sMB expected=%sMB\n' "$c" "$got" "$want"
    done

    rep=1; attempts=0
    while [[ $rep -le $REPS ]]; do
        attempts=$((attempts+1))
        if [[ $attempts -gt $((REPS*2+2)) ]]; then
            echo "  too many invalid runs on r=$r, moving on"; break
        fi
        printf '  rep %s (attempt %s) ... ' "$rep" "$attempts"
        # The router restarts together with the caches: nginx keeps 64
        # keepalive connections per upstream and if Varnish restarts without
        # it those stay hanging. It is the main suspect for the 30
        # August drift (0 invalid in the first block, 5 out of 8 in the
        # fourth, exact same configuration).
        docker compose --profile split restart varnish-h varnish-l router >/dev/null 2>&1; sleep 10

        for phase in "$WARMUP:w" "$MEASURE:m"; do
            dur="${phase%%:*}"; tag="${phase##*:}"
            skip=0
            [[ "$tag" == "m" ]] && skip=$(awk -v w="$WARMUP" -v l="$LAMBDA" -v a="$ALPHA" \
                'BEGIN{printf "%d", w*l*a}')
            # Override for the 7 September experiment: isolates the effect
            # of the window of ranks traversed from the warm-up effect.
            [[ "$tag" == "m" && -n "${TRAV_SKIP_FORCE:-}" ]] && skip="$TRAV_SKIP_FORCE"
            docker compose --profile load run --rm -T -e MODEL=mix -e ALPHA="$ALPHA" \
                -e RATE="$LAMBDA" -e DURATION="${dur}s" -e TARGET=http://router:80 \
                -e TRAV_SKIP="$skip" -e OUTFILE="$tag-r$r-$rep" \
                k6 run --quiet /scripts/workload.js < /dev/null > /dev/null 2>&1
            [[ "$tag" == "w" ]] && rm -f "results/w-r$r-$rep.json"
        done

        f="results/m-r$r-$rep.json"
        if [[ ! -f "$f" ]]; then echo "FAILED"; sleep 20; continue; fi
        j="$BASE/m-r$r-$rep.json"; mv "$f" "$j"

        # Validity gate. http_req_failed is a Rate metric: it has
        # .rate, not .count — with .count the check always passed.
        dropped=$(jq -r '.metrics.dropped_iterations.values.count // 0' "$j")
        fail_rate=$(jq -r '.metrics.http_req_failed.values.rate // 0' "$j")
        if (( $(awk -v d="$dropped" -v x="$fail_rate" 'BEGIN{print (d>0 || x>0.01)?1:0}') )); then
            printf 'suspect: dropped=%s errors=%s%% ' "$dropped" \
                "$(awk -v x="$fail_rate" 'BEGIN{printf "%.2f", x*100}')"
            docker compose --profile split logs --tail 150 router varnish-h app \
                > "$BASE/diag-r$r-a$attempts.log" 2>&1
            if [[ "$GATE" == "1" ]]; then
                echo "— INVALID, redoing"
                mv "$j" "$BASE/invalid-r$r-a$attempts.json"
                sleep 20; continue
            fi
            echo "— recorded (GATE=0)"
        fi

        # hit_low by difference: k6 omits custom metrics without samples
        # from the summary, so "absent" and "zero" are indistinguishable
        # if it is read directly.
        read -r ph pl hh mh hl ml <<<"$(jq -r '[
            ((.metrics.ut_lat_zipf.values["p(99)"]//0)*10|round/10),
            ((.metrics.ut_lat_traversal.values["p(99)"]//0)*10|round/10),
            (.metrics.ut_hit_zipf.values.count//0),
            (.metrics.ut_miss_zipf.values.count//0),
            (.metrics.ut_hit_traversal.values.count //
              ((.metrics.ut_ok_traversal.values.count//0) - (.metrics.ut_miss_traversal.values.count//0))),
            (.metrics.ut_miss_traversal.values.count//0)
          ]|@tsv' "$j")"

        # Origin load over the measurement phase only: lambda*(1-h),
        # derived from the misses of both classes.
        #
        # The previous version read the VictoriaMetrics counter
        # between t0 and t1, that is over warmup and measurement together: the
        # cold-cache phase inflated the value differently for each r, a bias
        # correlated with the independent variable. Moreover observability
        # is not among the dependencies of the split profile, so the query
        # returned empty and the value was 0.0 without signalling anything.
        orps=$(awk -v mh="$mh" -v ml="$ml" -v d="$MEASURE" 'BEGIN{printf "%.2f", (mh+ml)/d}')

        echo "$r,$rep,$ph,$pl,$hh,$mh,$hl,$ml,$orps,$dropped,$fail_rate,$(date -Is)" >> "$CSV"
        printf 'p99 high=%s  low hit=%s  origin=%s req/s\n' "$ph" "$hl" "$orps"
        rep=$((rep+1)); sleep 20
    done
done

echo
echo "================================================================"
printf '%-8s %5s %10s %10s %10s %10s %10s\n' "r" "n" "p99 high" "p99 low" "hit high" "hit low" "orig rps"
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
echo "  r = fraction of the cache reserved for the high-locality class."
echo "  shared = reference, ONE cache for both classes."
echo
echo "  PRECONDITION: if low hit is 0 even on shared, the"
echo "  partitioning takes nothing away and the question is moot."
echo
echo "  PARADOX CONFIRMED if as r grows the p99 high improves"
echo "  BUT orig rps worsens relative to shared."
echo
echo "Data: $CSV"