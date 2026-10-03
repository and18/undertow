#!/usr/bin/env python3
"""
honeypot_scope.py - The check that anchors the agentic generator to reality.

WHY NOW
  The AGENT_SCOPE sweep measures how the cost sensitivity changes as the
  width of a class's working set varies. That result holds as a description
  of the world only if we know WHERE, on that axis, the real agents sit.
  The honeypot is the only source that can tell us, and it is offline: it
  costs no lab time and runs in parallel with the sweep.

  It measures the four quantities that calibrate the generator, and nothing else:

    AGENT_SESSION = 3      <- pages per session
    AGENT_SCOPE   = 0.02   <- fraction of the site touched by a single client
    AGENT_SKEW    = 0.6    <- concentration of a client's requests
    3 contiguous chapters  <- contiguity of the requests in a session

WHAT IT CANNOT PROVE, and it must be written in the paper
  Nothing about cost: the honeypot has no comparable backend. Nothing
  causal. And no generalisation: it is one site, and moreover built to
  be visited. It serves to justify a calibration, not to support a claim.

PRIVACY
  IP addresses are never printed or written. They serve only as a
  grouping key and are replaced by a truncated hash.

Usage:
  python3 honeypot_scope.py --peek                 # shows the log fields
  python3 honeypot_scope.py /path/to/log [--pages 18720]
"""
import sys, os, json, gzip, glob, hashlib, argparse, re
from collections import defaultdict, Counter

ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default="data/hplogs")
ap.add_argument("--pages", type=int, default=18720, help="total pages of the site")
ap.add_argument("--peek", action="store_true")
ap.add_argument("--min-req", type=int, default=5, help="clients below this threshold ignored")
A = ap.parse_args()

def lines(path):
    files = sorted(glob.glob(os.path.join(path, "*"))) if os.path.isdir(path) else [path]
    for f in files:
        if os.path.isdir(f): continue
        op = gzip.open if f.endswith(".gz") else open
        try:
            with op(f, "rt", errors="replace") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if ln.startswith("{"):
                        try: yield json.loads(ln)
                        except Exception: pass
        except Exception as e:
            print(f"  (skipping {os.path.basename(f)}: {e})", file=sys.stderr)

if A.peek:
    for i, r in enumerate(lines(A.path)):
        print(json.dumps(r, indent=2)[:1500]); break
    else:
        print(f"no JSON row found in {A.path}")
    sys.exit()

def field(r, *names):
    for n in names:
        if n in r and r[n] not in ("", "-", None): return r[n]
    return None

anon = lambda s: hashlib.sha256(str(s).encode()).hexdigest()[:10]

def classify(ua):
    u = (ua or "").lower()
    if any(k in u for k in ("gptbot","claudebot","ccbot","google-extended","bytespider",
                            "meta-externalagent","applebot-extended")): return "training"
    if any(k in u for k in ("googlebot","bingbot","duckduckbot","baiduspider",
                            "yandexbot","applebot")):                    return "search"
    if any(k in u for k in ("chatgpt-user","claude-user","perplexity","oai-searchbot",
                            "claude-searchbot","gemini","copilot")):     return "agent"
    if any(k in u for k in ("bot","crawler","spider","scrapy","curl","wget",
                            "python-requests","httpx","go-http")):       return "other-bot"
    if any(k in u for k in ("mozilla","safari","chrome","firefox")):     return "browser"
    return "unknown"

def bookchap(p):
    """(book, chapter) from /book/33118-slug/chapter-008.html; None if it is not a chapter."""
    m = re.search(r"/book/(\d+)[^/]*/chapter-0*(\d+)", p or "")
    if m: return (m.group(1), int(m.group(2)))
    n = re.findall(r"(\d+)", p or "")
    return (None, int(n[-1])) if n else None

clients   = defaultdict(lambda: {"urls": Counter(), "cls": Counter(), "n": 0})
signed    = defaultdict(Counter)
conns     = defaultdict(list)
conn_meta = {}
total = skipped = 0
tmin = tmax = None

print(f"reading {A.path} ...", file=sys.stderr)
for r in lines(A.path):
    total += 1
    path = field(r, "u", "request_uri", "uri", "path", "request", "url")
    ip   = field(r, "ip", "remote_addr", "client_ip", "addr")
    ua   = field(r, "ua", "http_user_agent", "user_agent", "agent") or ""
    cid  = field(r, "conn", "connection", "conn_id", "connection_id", "tcp_conn")
    cnum = field(r, "conn_req", "connection_requests", "req_num")
    ts   = field(r, "t", "time_iso8601", "time", "timestamp", "@timestamp")
    sig  = field(r, "sig_agent") or field(r, "sig_input")
    if not path or not ip: skipped += 1; continue
    if isinstance(path, str) and " " in path:           # "GET /x HTTP/1.1"
        parts = path.split()
        path = parts[1] if len(parts) > 2 else path
    if ts:
        tmin = ts if tmin is None or ts < tmin else tmin
        tmax = ts if tmax is None or ts > tmax else tmax
    c = anon(ip)
    clients[c]["urls"][path] += 1
    clients[c]["cls"][classify(ua)] += 1
    clients[c]["n"] += 1
    signed[classify(ua)][bool(sig)] += 1
    if cid is not None:
        k = (c, str(cid))
        conns[k].append((int(cnum) if str(cnum).isdigit() else len(conns[k]), path))
        conn_meta[k] = classify(ua)

print(f"\n{'='*66}\n  HONEYPOT - calibration of the agentic generator\n{'='*66}")
print(f"requests read        : {total:,}   (discarded {skipped:,})")
print(f"period               : {tmin} -> {tmax}")
print(f"distinct clients     : {len(clients):,}")
print(f"distinct connections : {len(conns):,}" if conns else
      "connections          : field absent, section 1 will be skipped")
print(f"site pages           : {A.pages:,}")

def pct(v, q):
    if not v: return 0
    v = sorted(v); i = min(len(v)-1, int(q*len(v)))
    return v[i]

CLS = ["agent", "training", "search", "other-bot", "browser", "unknown"]

# ---- 1. AGENT_SESSION -------------------------------------------------
if conns:
    print(f"\n--- 1. PAGES PER SESSION  (calibrates AGENT_SESSION, current value 3)")
    print(f"{'class':12s} {'sessions':>9s} {'median':>8s} {'mean':>7s} {'p75':>5s} {'p90':>5s} {'p99':>6s}")
    per = defaultdict(list)
    for k, v in conns.items(): per[conn_meta[k]].append(len(v))
    for cl in CLS:
        L = per.get(cl)
        if not L: continue
        print(f"{cl:12s} {len(L):9,d} {pct(L,.5):8d} {sum(L)/len(L):7.1f} "
              f"{pct(L,.75):5d} {pct(L,.90):5d} {pct(L,.99):6d}")

# ---- 2. AGENT_SCOPE ---------------------------------------------------
print(f"\n--- 2. WIDTH OF THE WORKING SET  (calibrates AGENT_SCOPE, current 0.0200)")
print("    fraction of the site touched by a single client, over clients with"
      f" at least {A.min_req} requests")
print(f"{'class':12s} {'clients':>7s} {'median':>9s} {'mean':>9s} {'p90':>9s} {'max':>9s}")
scopes = defaultdict(list)
for c, d in clients.items():
    if d["n"] < A.min_req: continue
    scopes[d["cls"].most_common(1)[0][0]].append(len(d["urls"]) / A.pages)
for cl in CLS:
    S = scopes.get(cl)
    if not S: continue
    print(f"{cl:12s} {len(S):7,d} {pct(S,.5):9.4f} {sum(S)/len(S):9.4f} "
          f"{pct(S,.90):9.4f} {max(S):9.4f}")
print("\n    >>> the value to compare with AGENT_SCOPE=0.0200 is the median"
      " of the 'agent' row")

# ---- 3. AGENT_SKEW ----------------------------------------------------
print(f"\n--- 3. CONCENTRATION  (calibrates AGENT_SKEW, current 0.6)")
print("    share of a client's requests that falls on the 10% most visited URLs")
print(f"{'class':12s} {'clients':>7s} {'median':>9s} {'mean':>9s}")
conc = defaultdict(list)
for c, d in clients.items():
    if d["n"] < max(10, A.min_req): continue
    cnt = sorted(d["urls"].values(), reverse=True)
    k = max(1, len(cnt)//10)
    conc[d["cls"].most_common(1)[0][0]].append(sum(cnt[:k]) / sum(cnt))
for cl in CLS:
    C = conc.get(cl)
    if not C: continue
    print(f"{cl:12s} {len(C):7,d} {pct(C,.5):9.3f} {sum(C)/len(C):9.3f}")
print("    reference: uniform = 0.10   Zipf(0.6) over 339 = ~0.30   Zipf(1) = ~0.55")

# ---- 4. contiguity ----------------------------------------------------
if conns:
    print(f"\n--- 4. CONTIGUITY  (calibrates the 'contiguous chapters' model)")
    print("    share of consecutive requests with an adjacent page number")
    print(f"{'class':12s} {'sessions':>9s} {'contiguous':>10s} {'repeated':>9s}")
    adj = defaultdict(lambda: [0, 0, 0])
    for k, v in conns.items():
        if len(v) < 2: continue
        seq = [bookchap(p) for _, p in sorted(v)]
        a = r = t = 0
        for x, y in zip(seq, seq[1:]):
            if x is None or y is None: continue
            t += 1
            if x[0] == y[0]:                      # same book
                if abs(y[1]-x[1]) == 1: a += 1
                if y[1] == x[1]:        r += 1
        if t:
            s = adj[conn_meta[k]]; s[0] += a; s[1] += r; s[2] += t
    for cl in CLS:
        s = adj.get(cl)
        if not s or not s[2]: continue
        print(f"{cl:12s} {s[2]:9,d} {s[0]/s[2]:9.3f} {s[1]/s[2]:9.3f}")

# ---- 5. composition ---------------------------------------------------
print(f"\n--- 5. TRAFFIC COMPOSITION")
tot = Counter()
for d in clients.values():
    for cl, n in d["cls"].items(): tot[cl] += n
S = sum(tot.values()) or 1
for cl in CLS:
    if tot.get(cl): print(f"{cl:12s} {tot[cl]:10,d} requests  {100*tot[cl]/S:5.1f}%")

print(f"\n--- 6. SIGNED REQUESTS  (Web Bot Auth, fields sig_agent / sig_input)")
tt = sum(sum(c.values()) for c in signed.values())
if tt:
    print(f"{'class':12s} {'signed':>10s} {'total':>10s} {'share':>7s}")
    for cl in CLS:
        c = signed.get(cl)
        if not c: continue
        n = sum(c.values())
        print(f"{cl:12s} {c[True]:10,d} {n:10,d} {100*c[True]/n:6.2f}%")
    tot_s = sum(c[True] for c in signed.values())
    print(f"{'TOTAL':12s} {tot_s:10,d} {tt:10,d} {100*tot_s/tt:6.2f}%")
    print("    real data on the adoption of webbotauth: useful in Related Work,")
    print("    it supports no claim on cost")

print(f"\n{'='*66}")
print("  This output justifies or refutes the generator's parameters.")
print("  If the median scope for the 'agent' class is far from 0.0200,")
print("  it must be said in the paper, and the scope sweep becomes even more useful")
print("  because it covers the interval in which the true value falls.")
print(f"{'='*66}")