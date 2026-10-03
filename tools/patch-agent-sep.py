#!/usr/bin/env python3
"""
patch-agent-sep.py - Separates the agentic working set from the human one.

THE CONFOUNDER
  workload.js maps both the human Zipf rank and the agentic rank with the
  SAME multiplicative permutation:

      permute(rank, N) = (rank * 2654435761 + SEED) % N

  The human class draws the rank from Zipf(1), so its hot objects
  are the ranks 0..a few hundred. The agentic class draws the rank
  from Zipf(0.6) over [0, scope) with scope = 2% of the corpus = 339.

  The images coincide: the agentic session bases ARE the 339
  most popular objects for the human class. A third of the agentic
  requests (the bases) falls on the human hot head by construction; the two
  remaining thirds (base+1, base+2) are contiguous chapters of
  arbitrary popularity.

  This inflates the agentic hit ratio and makes the central result
  attackable: a reviewer will say we built a cache-friendly workload
  and discovered that it is cache-friendly.

THE FIX
  A distinct multiplier for the agentic class. With a different
  AGENT_MUL, permuteAgent([0, scope)) falls in a region of the corpus
  uncorrelated with the human popularity rank: the overlap goes from
  "by construction" to "incidental" (the human Zipf tail still visits
  40% of the requests outside the first 339 ranks, but spread over 16,615
  objects, hence at a negligible per-object rate).

  The default reproduces the current multiplier, so all the
  previous runs stay reproducible. The separation is activated with
  AGENT_MUL=3266489917.

  Bijectivity check: 16954 = 2 x 7^2 x 173. The multiplier must be
  coprime. 3266489917 is odd, not divisible by 7 (remainder 5)
  nor by 173 (remainder 105). The map stays a permutation.

Usage:  python3 tools/patch-agent-sep.py
"""
import sys

P = "harness/load/workload.js"

try:
    s = open(P).read()
except FileNotFoundError:
    sys.exit(f"{P} not found: run from the repo root (~/undertow)")

if "AGENT_MUL" in s:
    sys.exit("AGENT_MUL already present: patch already applied, not repeating")

# ---- 1. the constant, next to the other agentic parameters
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

# ---- 2. the function
A2 = "function permute(rank, N) {"
B2 = """// Permutazione della sola classe agentica: vedi AGENT_MUL.
function permuteAgent(rank, N) {
  return (rank * AGENT_MUL + SEED) % N;
}

function permute(rank, N) {"""

# ---- 3. the use inside agenticIndex
A3 = "    agSession = { base: permute(r, data.total), left: AGENT_SESSION, k: 0 };"
B3 = "    agSession = { base: permuteAgent(r, data.total), left: AGENT_SESSION, k: 0 };"

for old, new in ((A1, B1), (A2, B2), (A3, B3)):
    if old not in s:
        sys.exit("ANCHOR NOT FOUND, nothing written:\n  " + old[:80])
    s = s.replace(old, new, 1)

open(P, "w").write(s)
print("workload.js: AGENT_MUL added, 3 changes")
print()
print("Check that the default changes nothing:")
print("  AGENT_MUL not set        -> 2654435761, behaviour identical to the previous runs")
print("  AGENT_MUL=3266489917     -> agentic working set separated")