#!/usr/bin/env bash
# policy.sh - Le politiche di ammissione a confronto, al ginocchio.
#
#   A   nessuna politica                 il default del web
#   B   blocco della classe esaustiva    ammissione per identita'
#   C   blocco di esaustiva e agentica   default Cloudflare, 15 set 2026
#   D4  budget con rinvio, 4 slot        la nostra mitigazione
#   D6  budget con rinvio, 6 slot
#
# Il confronto che decide e' C contro D: C rifiuta la classe che costa
# meno servire, D rimanda quella che costa di piu'. Se D ottiene una
# latenza interattiva vicina a quella di C continuando a servire la
# classe agentica, il blocco per identita' paga un prezzo che non serve.
#
# Il blocco e' all'origine, non al bordo: una richiesta bloccata che
# trova l'oggetto in cache viene comunque servita da Varnish. Sul carico
# all'origine l'effetto e' identico, perche' un hit non raggiunge
# l'origine in nessun caso.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
LAM="${LAM:-185}"
echo "lambda=$LAM  alpha=0.35  beta=0.10  cache=128MB  3 ripetizioni"
for P in "A::0" "B:low:0" "C:low,agent:0" "D4::4" "D6::6"; do
  N="${P%%:*}"; R="${P#*:}"; B="${R%%:*}"; BU="${R##*:}"
  printf '\n######## politica %s  block=[%s] budget=%s ########  %s\n' \
      "$N" "$B" "$BU" "$(date +%H:%M)"
  BLOCK_CLASSES="$B" BUDGET_LOW="$BU" BUDGET_WAIT=0 LAMBDA="$LAM" \
    REPS=3 GATE=0 WARMUP=300 MEASURE_FORCE=620 TOTAL_MB=128 \
    POINTS=0.35:0.10 bash treclassi.sh
done
