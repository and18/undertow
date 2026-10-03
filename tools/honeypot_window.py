#!/usr/bin/env python3
"""
honeypot_window.py - Working set within a time window.

WHY
  honeypot_scope.py counts the distinct URLs per client over the whole
  observation period. For the cache that quantity is not what matters: an object survives
  only if revisited within the characteristic time T_C = capacity / miss
  rate, which on our testbed is ~143 s. What matters is how many distinct
  objects a client touches WITHIN a window of that order.

  The 40-day measurement overestimates the instantaneous working set. Since the
  sweep showed that the agentic marginal cost goes from -0.048 to +0.438
  as the width of the set varies, this is now the most
  important number the honeypot can provide.

WHAT IT DOES
  For each client and each sliding window of duration W, it counts the distinct
  URLs. It reports the distribution of the per-client maximum, which is the value
  the generator should reproduce.

WHAT IT CANNOT PROVE
  Nothing about cost. It is a calibration, and it holds for this site.

PRIVACY
  No IP is printed or written: only truncated hashes as a key.

Usage:  sudo python3 honeypot_window.py /var/log/nginx --pages 18720
"""
import sys, os, json, gzip, glob, hashlib, argparse
from collections import defaultdict, Counter, deque

ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default="/var/log/nginx")
ap.add_argument("--pages", type=int, default=18720)
ap.add_argument("--windows", default="143,600,3600",
                help="durations in seconds, comma-separated; 143 = T_C of the testbed")
ap.add_argument("--min-req", type=int, default=5)
A = ap.parse_args()
WINDOWS = [int(w) for w in A.windows.split(",")]

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

def epoch(ts):
    """2026-09-21T00:00:21+00:00 -> seconds, without external dependencies."""
    try:
        d, t = ts[:19].split("T")
        Y, M, D = (int(x) for x in d.split("-"))
        h, m, s = (int(x) for x in t.split(":"))
        days = (Y-1970)*365 + (Y-1969)//4 + sum((0,31,59,90,120,151,181,212,243,273,304,334)[:M-1]) + (D-1)
        if M > 2 and Y % 4 == 0: days += 1
        return days*86400 + h*3600 + m*60 + s
    except Exception:
        return None

anon = lambda s: hashlib.sha256(str(s).encode()).hexdigest()[:10]

ev = defaultdict(list)          # client -> [(t, url)]
cls = defaultdict(Counter)
total = 0
print(f"reading {A.path} ...", file=sys.stderr)
for r in lines(A.path):
    u, ip, ua, ts = r.get("u"), r.get("ip"), r.get("ua", ""), r.get("t")
    if not (u and ip and ts): continue
    e = epoch(ts)
    if e is None: continue
    c = anon(ip)
    ev[c].append((e, u)); cls[c][classify(ua)] += 1; total += 1

print(f"\n{'='*70}\n  WORKING SET IN WINDOW — what the cache really sees\n{'='*70}")
print(f"requests {total:,}   clients {len(ev):,}   site {A.pages:,} pages")
print(f"windows: {', '.join(str(w)+'s' for w in WINDOWS)}   (143 s = T_C of the testbed)\n")

def pct(v, q):
    if not v: return 0
    v = sorted(v); return v[min(len(v)-1, int(q*len(v)))]

CLS = ["agent", "training", "search", "other-bot", "browser", "unknown"]
for W in WINDOWS:
    peak = defaultdict(list)
    for c, e in ev.items():
        if len(e) < A.min_req: continue
        e.sort()
        dq, seen, best = deque(), Counter(), 0
        for t, u in e:
            dq.append((t, u)); seen[u] += 1
            while dq and dq[0][0] < t - W:
                _, ou = dq.popleft(); seen[ou] -= 1
                if seen[ou] == 0: del seen[ou]
            best = max(best, len(seen))
        peak[cls[c].most_common(1)[0][0]].append(best)
    print(f"--- window {W}s: distinct URLs at the peak, per client")
    print(f"{'class':12s} {'clients':>7s} {'median':>8s} {'mean':>8s} {'p90':>7s} {'max':>7s}"
          f" {'median scope':>14s} {'p90 scope':>10s}")
    for cl in CLS:
        P = peak.get(cl)
        if not P: continue
        print(f"{cl:12s} {len(P):7,d} {pct(P,.5):8d} {sum(P)/len(P):8.1f} {pct(P,.9):7d} "
              f"{max(P):7d} {pct(P,.5)/A.pages:14.5f} {pct(P,.9)/A.pages:10.5f}")
    print()

print(f"{'='*70}")
print("  To compare with the generator's AGENT_SCOPE: 0.02 = 339 bases = 1,017")
print("  nominal objects. The sweep measured the agentic marginal cost at")
print("  0.02 / 0.06 / 0.20, i.e. 1,017 / 3,052 / 10,172 objects against a")
print("  capacity of 5,274. The in-window peak says where the real agents fall.")
print(f"{'='*70}")