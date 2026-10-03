#!/usr/bin/env python3
"""
patch-agentenv.py - Forwards ALL the agentic parameters to k6, not just AGENT_MUL.

On 20 September AGENT_MUL did not reach the container and the campaign was a
no-op. AGENT_SCOPE, AGENT_SESSION and AGENT_SKEW are still in that condition:
they were never varied because it was not possible to vary them. The
AGENT_SCOPE sweep cannot start until they are.

The defaults are READ from workload.js, not guessed, so that the behaviour
of the previous runs stays identical bit for bit.

Usage:  cd ~/undertow && python3 tools/patch-agentenv.py
"""
import re, sys, os

W, T = "harness/load/workload.js", "harness/load/treclassi.sh"
for p in (W, T):
    if not os.path.exists(p):
        sys.exit(f"{p} not found: run from the repo root (~/undertow)")

js = open(W).read()
VARS = ["AGENT_MUL", "AGENT_SCOPE", "AGENT_SESSION", "AGENT_SKEW"]
defaults = {}
for v in VARS:
    m = re.search(r"__ENV\." + v + r"\s*\|\|\s*'([^']*)'", js)
    if not m:
        sys.exit(f"default of {v} not found in {W}: not guessing")
    defaults[v] = m.group(1)
print("defaults read from workload.js:")
for v in VARS: print(f"  {v:15s} = {defaults[v]}")

s = open(T).read()
OLD = '                -e AGENT_MUL="${AGENT_MUL:-' + defaults["AGENT_MUL"] + '}" \\\n'
if "AGENT_SCOPE" in s:
    sys.exit("\nAGENT_SCOPE already forwarded: patch already applied")
if OLD not in s:
    sys.exit("\nANCHOR NOT FOUND, nothing written. Expected line:\n  " + OLD.rstrip())
NEW = "".join('                -e %s="${%s:-%s}" \\\n' % (v, v, defaults[v]) for v in VARS)
open(T, "w").write(s.replace(OLD, NEW, 1))
print(f"\n{T}: forwarded {len(VARS)} agentic parameters (before only AGENT_MUL)")
print("The defaults match those of workload.js: the previous runs stay reproducible.")
print("\nCheck after launch, 30 seconds:")
print("  grep -E 'AGENT_(MUL|SCOPE)' ~/undertow/harness/results/$(ls -t ~/undertow/harness/results | head -1)/env.txt")
