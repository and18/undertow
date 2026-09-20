#!/usr/bin/env python3
"""
patch-agent-sep.py - Separa l'insieme di lavoro agentico da quello umano.

IL CONFONDITORE
  workload.js mappa sia il rango Zipf umano sia il rango agentico con la
  STESSA permutazione moltiplicativa:

      permute(rank, N) = (rank * 2654435761 + SEED) % N

  La classe umana estrae il rango da Zipf(1), quindi i suoi oggetti caldi
  sono i ranghi 0..qualche centinaio. La classe agentica estrae il rango
  da Zipf(0,6) su [0, scope) con scope = 2% del corpus = 339.

  Le immagini coincidono: le basi di sessione agentiche SONO i 339
  oggetti piu' popolari per la classe umana. Un terzo delle richieste
  agentiche (le basi) cade sulla testa calda umana per costruzione; i due
  terzi restanti (base+1, base+2) sono capitoli contigui di popolarita'
  arbitraria.

  Questo gonfia l'hit ratio agentico e rende attaccabile il risultato
  centrale: un revisore dira' che abbiamo costruito un workload
  cache-friendly e scoperto che e' cache-friendly.

LA CORREZIONE
  Un moltiplicatore distinto per la classe agentica. Con AGENT_MUL
  diverso, permuteAgent([0, scope)) cade in una regione del corpus
  scorrelata dal rango di popolarita' umano: la sovrapposizione passa da
  "per costruzione" a "incidentale" (la coda Zipf umana visita comunque
  il 40% delle richieste fuori dai primi 339 ranghi, ma sparse su 16.615
  oggetti, quindi a ritmo per-oggetto trascurabile).

  Il default riproduce il moltiplicatore attuale, quindi tutti i run
  precedenti restano riproducibili. La separazione si attiva con
  AGENT_MUL=3266489917.

  Verifica di biiettivita': 16954 = 2 x 7^2 x 173. Il moltiplicatore deve
  essere coprimo. 3266489917 e' dispari, non divisibile per 7 (resto 5)
  ne' per 173 (resto 105). La mappa resta una permutazione.

Uso:  python3 tools/patch-agent-sep.py
"""
import sys

P = "harness/load/workload.js"

try:
    s = open(P).read()
except FileNotFoundError:
    sys.exit(f"{P} non trovato: esegui dalla radice del repo (~/undertow)")

if "AGENT_MUL" in s:
    sys.exit("AGENT_MUL gia' presente: patch gia' applicata, non la ripeto")

# ---- 1. la costante, accanto agli altri parametri agentici
A1 = "const AGENT_SKEW    = parseFloat(__ENV.AGENT_SKEW || '0.6');"
B1 = """const AGENT_SKEW    = parseFloat(__ENV.AGENT_SKEW || '0.6');

// Moltiplicatore della permutazione per la classe agentica. Il default
// e' lo stesso della classe umana, quindi riproduce i run fino al 19
// settembre 2026. Con un valore diverso l'insieme di lavoro agentico
// cade in una regione del corpus scorrelata dal rango di popolarita'
// umano, e la sovrapposizione fra le due classi passa da "per
// costruzione" a "incidentale".
//
// Deve essere dispari e coprimo con la dimensione del corpus
// (16954 = 2 x 7^2 x 173), altrimenti la mappa non e' una permutazione.
// Valore separato verificato: 3266489917.
const AGENT_MUL     = parseInt(__ENV.AGENT_MUL || '2654435761');"""

# ---- 2. la funzione
A2 = "function permute(rank, N) {"
B2 = """// Permutazione della sola classe agentica: vedi AGENT_MUL.
function permuteAgent(rank, N) {
  return (rank * AGENT_MUL + SEED) % N;
}

function permute(rank, N) {"""

# ---- 3. l'uso dentro agenticIndex
A3 = "    agSession = { base: permute(r, data.total), left: AGENT_SESSION, k: 0 };"
B3 = "    agSession = { base: permuteAgent(r, data.total), left: AGENT_SESSION, k: 0 };"

for old, new in ((A1, B1), (A2, B2), (A3, B3)):
    if old not in s:
        sys.exit("ANCORA NON TROVATA, niente scritto:\n  " + old[:80])
    s = s.replace(old, new, 1)

open(P, "w").write(s)
print("workload.js: AGENT_MUL aggiunto, 3 modifiche")
print()
print("Verifica che il default non cambi nulla:")
print("  AGENT_MUL non impostato  -> 2654435761, comportamento identico ai run precedenti")
print("  AGENT_MUL=3266489917     -> insieme di lavoro agentico separato")