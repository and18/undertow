#!/usr/bin/env python3
"""
patch-treclassi.py - Ripara due difetti in harness/load/treclassi.sh.

DIFETTO 1 (quello che ha bruciato il run del 20 settembre)
  L'invocazione di k6 inoltra solo MODEL, ALPHA, BETA, RATE, DURATION,
  TARGET, TRAV_SKIP, OUTFILE. Qualsiasi altra variabile impostata dal
  driver - AGENT_MUL fra queste - non arriva dentro il container e il
  workload usa il default. La campagna di separazione ha quindi
  rieseguito la configurazione del 14 settembre: 4 ore per un no-op.

  Correzione: si inoltra AGENT_MUL con default pari al valore attuale,
  quindi tutti i run precedenti restano bit-identici.

DIFETTO 2 (perche' il no-op e' rimasto invisibile per un giorno)
  Le directory dei risultati non registrano la propria configurazione:
  ne' lambda, ne' TOTAL_MB, ne' l'env. Non e' possibile sapere a
  posteriori con quali parametri un run e' stato fatto, ne' costruire
  un registry degli esperimenti.

  Correzione: un env.txt in ogni directory di run.

Idempotente: se una correzione e' gia' presente non la ripete. Se
un'ancora non si trova, non scrive nulla e lo dice.

Uso:  cd ~/undertow && python3 patch-treclassi.py
"""
import sys, os

P = "harness/load/treclassi.sh"
if not os.path.exists(P):
    sys.exit(f"{P} non trovato: esegui dalla radice del repo (~/undertow)")
s = open(P).read()
orig = s
done, skipped = [], []

# ---- 1. inoltro di AGENT_MUL a k6 -------------------------------------
A1 = '                -e TRAV_SKIP="$sk" -e OUTFILE="$t-a$A-b$B-$rep" \\\n'
B1 = ('                -e TRAV_SKIP="$sk" -e OUTFILE="$t-a$A-b$B-$rep" \\\n'
      '                -e AGENT_MUL="${AGENT_MUL:-2654435761}" \\\n')
if "AGENT_MUL" in s:
    skipped.append("1. AGENT_MUL gia' inoltrato")
elif A1 in s:
    s = s.replace(A1, B1, 1); done.append("1. AGENT_MUL inoltrato a k6")
else:
    sys.exit("ANCORA 1 NON TROVATA, niente scritto. Riga attesa:\n  " + A1.rstrip())

# ---- 2. dump dell'env nella directory di run --------------------------
# Si aggancia alla creazione di BASE, qualunque forma abbia.
if "env.txt" in s:
    skipped.append("2. env.txt gia' presente")
else:
    anchor = None
    for line in s.splitlines():
        t = line.strip()
        if t.startswith("mkdir") and "BASE" in t:
            anchor = line; break
    if anchor is None:
        skipped.append("2. NON APPLICATA: nessun 'mkdir ... $BASE' trovato. "
                       "Aggiungi a mano dopo la creazione della directory:\n"
                       '     env | sort > "$BASE/env.txt"')
    else:
        indent = anchor[:len(anchor) - len(anchor.lstrip())]
        s = s.replace(anchor, anchor + "\n" + indent +
                      '{ env | sort; echo "--- git $(git rev-parse --short HEAD 2>/dev/null)"; } '
                      '> "$BASE/env.txt" 2>/dev/null || true', 1)
        done.append("2. env.txt scritto in ogni directory di run")

if s == orig:
    print("nessuna modifica necessaria")
else:
    open(P, "w").write(s)

for d in done:    print("FATTO   ", d)
for k in skipped: print("SALTATO ", k)

print("""
--------------------------------------------------------------------
VERIFICA, 2 minuti, PRIMA di lanciare qualunque campagna lunga.

Che la mappatura separata sia matematicamente diversa e' gia' provato
offline: le 339 basi agentiche si sovrappongono al 100% con la testa
calda umana sotto il default e al 2,1% sotto 3266489917; la massa di
traffico umano che cade su quelle basi passa dal 62,1% al 10,6%.
Resta da provare che la variabile arrivi davvero dentro k6.

  cd ~/undertow/harness
  docker compose restart varnish && sleep 3
  docker compose --profile load run --rm -T \\
    -e ALPHA=0 -e BETA=1 -e RATE=40 -e DURATION=45s \\
    -e TARGET=http://varnish:80 -e AGENT_MUL=3266489917 \\
    k6 run --quiet /scripts/workload.js >/dev/null 2>&1
  docker compose logs --no-log-prefix --since 60s app \\
    | grep -oE '/book/[0-9]+/ch/[0-9]+' | sort -u > /tmp/urls-separato.txt

  docker compose restart varnish && sleep 3
  docker compose --profile load run --rm -T \\
    -e ALPHA=0 -e BETA=1 -e RATE=40 -e DURATION=45s \\
    -e TARGET=http://varnish:80 \\
    k6 run --quiet /scripts/workload.js >/dev/null 2>&1
  docker compose logs --no-log-prefix --since 60s app \\
    | grep -oE '/book/[0-9]+/ch/[0-9]+' | sort -u > /tmp/urls-default.txt

  wc -l /tmp/urls-*.txt
  comm -12 /tmp/urls-default.txt /tmp/urls-separato.txt | wc -l

ESITO
  sovrapposizione vicina a ZERO  -> la variabile arriva, si puo' lanciare
  gli insiemi COINCIDONO         -> non arriva ancora, non lanciare nulla

Se il secondo comando non produce URL, l'app non sta loggando le
richieste: in quel caso mandami l'output di
  docker compose logs --tail 20 app
e trovo un'altra strada, senza lanciare la campagna al buio.
--------------------------------------------------------------------""")
