#!/usr/bin/env python3
"""
patch-agentenv.py - Inoltra TUTTI i parametri agentici a k6, non solo AGENT_MUL.

Il 20 settembre AGENT_MUL non arrivava nel container e la campagna e' stata un
no-op. AGENT_SCOPE, AGENT_SESSION e AGENT_SKEW sono ancora in quella condizione:
non sono mai stati variati perche' non era possibile variarli. Lo sweep di
AGENT_SCOPE non puo' partire finche' non lo sono.

I default vengono LETTI da workload.js, non indovinati, cosi' il comportamento
dei run precedenti resta identico bit per bit.

Uso:  cd ~/undertow && python3 tools/patch-agentenv.py
"""
import re, sys, os

W, T = "harness/load/workload.js", "harness/load/treclassi.sh"
for p in (W, T):
    if not os.path.exists(p):
        sys.exit(f"{p} non trovato: esegui dalla radice del repo (~/undertow)")

js = open(W).read()
VARS = ["AGENT_MUL", "AGENT_SCOPE", "AGENT_SESSION", "AGENT_SKEW"]
defaults = {}
for v in VARS:
    m = re.search(r"__ENV\." + v + r"\s*\|\|\s*'([^']*)'", js)
    if not m:
        sys.exit(f"default di {v} non trovato in {W}: non tiro a indovinare")
    defaults[v] = m.group(1)
print("default letti da workload.js:")
for v in VARS: print(f"  {v:15s} = {defaults[v]}")

s = open(T).read()
OLD = '                -e AGENT_MUL="${AGENT_MUL:-' + defaults["AGENT_MUL"] + '}" \\\n'
if "AGENT_SCOPE" in s:
    sys.exit("\nAGENT_SCOPE gia' inoltrato: patch gia' applicata")
if OLD not in s:
    sys.exit("\nANCORA NON TROVATA, niente scritto. Riga attesa:\n  " + OLD.rstrip())
NEW = "".join('                -e %s="${%s:-%s}" \\\n' % (v, v, defaults[v]) for v in VARS)
open(T, "w").write(s.replace(OLD, NEW, 1))
print(f"\n{T}: inoltrati {len(VARS)} parametri agentici (prima solo AGENT_MUL)")
print("I default coincidono con quelli di workload.js: i run precedenti restano riproducibili.")
print("\nVerifica dopo il lancio, 30 secondi:")
print("  grep -E 'AGENT_(MUL|SCOPE)' ~/undertow/harness/results/$(ls -t ~/undertow/harness/results | head -1)/env.txt")
