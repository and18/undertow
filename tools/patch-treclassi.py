#!/usr/bin/env python3
"""
patch-treclassi.py - Repairs two defects in harness/load/treclassi.sh.

DEFECT 1 (the one that burned the run of 20 September)
  The k6 invocation forwards only MODEL, ALPHA, BETA, RATE, DURATION,
  TARGET, TRAV_SKIP, OUTFILE. Any other variable set by the
  driver - AGENT_MUL among them - does not reach the container and the
  workload uses the default. The separation campaign therefore
  reran the configuration of 14 September: 4 hours for a no-op.

  Fix: AGENT_MUL is forwarded with a default equal to the current value,
  so all the previous runs stay bit-identical.

DEFECT 2 (why the no-op stayed invisible for a day)
  The results directories do not record their own configuration:
  neither lambda, nor TOTAL_MB, nor the env. It is not possible to know
  afterwards with which parameters a run was made, nor to build
  a registry of the experiments.

  Fix: an env.txt in every run directory.

Idempotent: if a fix is already present it does not repeat it. If
an anchor is not found, it writes nothing and says so.

"""
import sys, os

P = "harness/load/treclassi.sh"
if not os.path.exists(P):
    sys.exit(f"{P} not found: run from the repo root (~/undertow)")
s = open(P).read()
orig = s
done, skipped = [], []

# ---- 1. forwarding AGENT_MUL to k6 ------------------------------------
A1 = '                -e TRAV_SKIP="$sk" -e OUTFILE="$t-a$A-b$B-$rep" \\\n'
B1 = ('                -e TRAV_SKIP="$sk" -e OUTFILE="$t-a$A-b$B-$rep" \\\n'
      '                -e AGENT_MUL="${AGENT_MUL:-2654435761}" \\\n')
if "AGENT_MUL" in s:
    skipped.append("1. AGENT_MUL already forwarded")
elif A1 in s:
    s = s.replace(A1, B1, 1); done.append("1. AGENT_MUL forwarded to k6")
else:
    sys.exit("ANCHOR 1 NOT FOUND, nothing written. Expected line:\n  " + A1.rstrip())

# ---- 2. env dump in the run directory ---------------------------------
# It hooks onto the creation of BASE, whatever form it takes.
if "env.txt" in s:
    skipped.append("2. env.txt already present")
else:
    anchor = None
    for line in s.splitlines():
        t = line.strip()
        if t.startswith("mkdir") and "BASE" in t:
            anchor = line; break
    if anchor is None:
        skipped.append("2. NOT APPLIED: no 'mkdir ... $BASE' found. "
                       "Add by hand after the creation of the directory:\n"
                       '     env | sort > "$BASE/env.txt"')
    else:
        indent = anchor[:len(anchor) - len(anchor.lstrip())]
        s = s.replace(anchor, anchor + "\n" + indent +
                      '{ env | sort; echo "--- git $(git rev-parse --short HEAD 2>/dev/null)"; } '
                      '> "$BASE/env.txt" 2>/dev/null || true', 1)
        done.append("2. env.txt written in every run directory")

if s == orig:
    print("no change needed")
else:
    open(P, "w").write(s)

for d in done:    print("DONE    ", d)
for k in skipped: print("SKIPPED ", k)

print("""
--------------------------------------------------------------------
VERIFICATION, 2 minutes, BEFORE launching any long campaign.

That the separate mapping is mathematically different is already proven
offline: the 339 agentic bases overlap 100% with the human hot head under the
default and 2.1% under 3266489917; the mass of human
traffic falling on those bases goes from 62.1% to 10.6%.
It remains to be proven that the variable really arrives inside k6.

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

OUTCOME
  overlap close to ZERO  -> the variable arrives, one can launch
  the sets COINCIDE      -> it still does not arrive, launch nothing

If the second command produces no URLs, the app is not logging the
requests: in that case send me the output of
  docker compose logs --tail 20 app
and I will find another way, without launching the campaign blind.
--------------------------------------------------------------------""")
