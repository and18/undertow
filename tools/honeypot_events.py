#!/usr/bin/env python3
"""
Event analysis on the honeypot: things never looked at so far.

  1. Break point of 15 September (Cloudflare default).
  2. Conditional requests, now measured and no longer deduced.
  3. www/apex separation: the redirect generates two rows per request.
  4. Canary: /canary.html is linked neither in sitemap nor anywhere. Whoever arrives
     there is guessing paths, and no header can mask it.
  5. Shape of the invented URLs: agents build addresses instead of
     following links. What shape do they have? .md? llms.txt? predictable slugs?
  6. Burstiness: distribution of the intervals between requests per
     operator. The load is an event, but of what shape?
  7. Daily cycle: do the automated operators have a day and a
     night, or do they arrive whenever?
  8. Service time per operator: do they request content of different
     cost? It serves to understand whether a "miss" costs the same for everyone.

Usage: python3 honeypot_events.py '/var/log/nginx/agentic.log*' --split 2026-09-15
"""
import argparse, glob, gzip, json, re, statistics, sys
from collections import defaultdict, Counter
from datetime import datetime

OPS = [("GPTBot", r"GPTBot"), ("ChatGPT-User", r"ChatGPT-User"),
       ("OAI-SearchBot", r"OAI-SearchBot"), ("ClaudeBot", r"ClaudeBot|anthropic-ai"),
       ("Claude-User", r"Claude-User"), ("Claude-SearchBot", r"Claude-SearchBot"),
       ("PerplexityBot", r"PerplexityBot"), ("Perplexity-User", r"Perplexity-User"),
       ("Meta", r"[Mm]eta-[Ee]xternal"), ("Amazonbot", r"Amazonbot"),
       ("Applebot", r"Applebot"), ("Bytespider", r"Bytespider"),
       ("Google-Extended", r"Google-Extended"), ("GoogleOther", r"GoogleOther"),
       ("Googlebot", r"Googlebot"), ("Bingbot", r"bingbot"),
       ("AhrefsBot", r"AhrefsBot"), ("SemrushBot", r"SemrushBot"),
       ("SERanking", r"SERanking"), ("DotBot", r"DotBot"), ("MJ12bot", r"MJ12bot"),
       ("YandexBot", r"YandexBot"),
       ("scanner", r"l9explore|zgrab|Modat|feroxbuster|Infrawatch|Nuclei")]

AGENTIC = {"ChatGPT-User", "Claude-User", "Perplexity-User"}


def op(ua):
    for n, p in OPS:
        if re.search(p, ua):
            return n
    return "browser-like" if re.search(r"Mozilla/5\.0", ua) else "other"


def ts(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


ap = argparse.ArgumentParser()
ap.add_argument("pattern")
ap.add_argument("--split", default="2026-09-15")
a = ap.parse_args()
SPLIT = datetime.fromisoformat(a.split)

rows = []
for f in sorted(glob.glob(a.pattern)):
    o = gzip.open(f, "rt", errors="replace") if f.endswith(".gz") else open(f, errors="replace")
    with o as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass

print(f"rows: {len(rows)}\n")

has_host = any("host" in r for r in rows)
has_inm = any("inm" in r for r in rows)
print(f"host field present: {has_host}   inm field present: {has_inm}")
print("(absent in the logs before 13 September: the analysis that uses them")
print(" holds only from that date onwards)\n")

# --- 1. break point ------------------------------------------------------
print("=== 1. BEFORE AND AFTER", a.split, "===")
pre, post = defaultdict(Counter), defaultdict(Counter)
pre_d, post_d = set(), set()
for r in rows:
    t = ts(r.get("t"))
    if not t:
        continue
    n = op(str(r.get("ua", "")))
    d = (post, post_d) if t >= SPLIT else (pre, pre_d)
    d[0][n]["req"] += 1
    d[0][n][f"s{r.get('s')}"] += 1
    d[1].add(t.date())
npre, npost = max(len(pre_d), 1), max(len(post_d), 1)
print(f"{'operator':20s} {'req/d before':>12s} {'req/d after':>11s} {'change':>8s} "
      f"{'200 pre':>8s} {'200 post':>9s}")
for n in sorted(set(pre) | set(post), key=lambda x: -(pre[x]["req"] + post[x]["req"]))[:18]:
    a1, a2 = pre[n]["req"] / npre, post[n]["req"] / npost
    p1 = 100 * pre[n]["s200"] / pre[n]["req"] if pre[n]["req"] else 0
    p2 = 100 * post[n]["s200"] / post[n]["req"] if post[n]["req"] else 0
    ch = f"{(a2/a1-1)*100:+.0f}%" if a1 else "new"
    print(f"{n:20s} {a1:12.0f} {a2:11.0f} {ch:>8s} {p1:7.1f}% {p2:8.1f}%")
print(f"\ndays: {npre} before, {npost} after")

# --- 2. conditional requests --------------------------------------------
if has_inm:
    print("\n=== 2. CONDITIONAL REQUESTS (measured, not deduced) ===")
    c = Counter()
    for r in rows:
        if r.get("inm") or r.get("ims"):
            c[op(str(r.get("ua", "")))] += 1
    tot = sum(1 for r in rows if "inm" in r)
    print(f"out of {tot} rows with the field: {sum(c.values())} conditional")
    for n, v in c.most_common(10):
        print(f"  {n:20s} {v}")
    if not c:
        print("  NONE. It is now a direct measurement, not an inference from the code.")

# --- 3. www against apex -------------------------------------------------
if has_host:
    print("\n=== 3. HOST: how much traffic is only redirect ===")
    h = Counter(str(r.get("host", "-")) for r in rows if "host" in r)
    for k, v in h.most_common(5):
        print(f"  {k:30s} {v}")

# --- 4. canary -----------------------------------------------------------
print("\n=== 4. CANARY: who finds a URL that is neither linked nor in the sitemap ===")
c = Counter(op(str(r.get("ua", ""))) for r in rows if "/canary" in str(r.get("u", "")))
print("  nobody" if not c else "")
for n, v in c.most_common():
    print(f"  {n:20s} {v}")

# --- 5. shape of the invented URLs --------------------------------------
print("\n=== 5. WHAT THE AGENTS INVENT ===")
served = {str(r.get("u", "")).split("?")[0] for r in rows if r.get("s") == 200}
for name in sorted(AGENTIC):
    bogus = Counter(str(r.get("u", "")).split("?")[0] for r in rows
                    if op(str(r.get("ua", ""))) == name
                    and str(r.get("u", "")).split("?")[0] not in served)
    if not bogus:
        continue
    print(f"\n{name}: {sum(bogus.values())} requests to {len(bogus)} nonexistent URLs")
    pat = Counter()
    for u in bogus:
        pat[".md" if u.endswith(".md") else
            "llms.txt" if "llms" in u else
            ".json/.xml" if re.search(r"\.(json|xml)$", u) else
            "/api|/v1" if re.search(r"/(api|v1|mcp)", u) else
            "hyphenated slug" if re.search(r"/[a-z0-9]+(-[a-z0-9]+){2,}", u) else
            "extension" if re.search(r"\.[a-z]{2,4}$", u) else "other"] += 1
    for k, v in pat.most_common():
        print(f"   {k:22s} {v:5d}  ({100*v/len(bogus):.0f}% of the URLs)")
    for u, v in bogus.most_common(6):
        print(f"     {v:4d}  {u[:76]}")

# --- 6. burstiness -------------------------------------------------------
print("\n=== 6. INTERVALS BETWEEN REQUESTS (burstiness) ===")
byop = defaultdict(list)
for r in rows:
    t = ts(r.get("t"))
    if t:
        byop[op(str(r.get("ua", "")))].append(t)
print(f"{'operator':20s} {'n':>7s} {'median s':>10s} {'p90 s':>9s} {'<1s':>7s} {'>1h':>7s}")
for n, v in sorted(byop.items(), key=lambda kv: -len(kv[1]))[:14]:
    if len(v) < 20:
        continue
    v.sort()
    g = [(v[i + 1] - v[i]).total_seconds() for i in range(len(v) - 1)]
    g.sort()
    print(f"{n:20s} {len(v):7d} {statistics.median(g):10.2f} "
          f"{g[int(.9*len(g))]:9.1f} {100*sum(1 for x in g if x<1)/len(g):6.0f}% "
          f"{100*sum(1 for x in g if x>3600)/len(g):6.0f}%")

# --- 7. daily cycle -----------------------------------------------------
print("\n=== 7. HOUR OF THE DAY (UTC), share per operator ===")
print(f"{'operator':20s} " + "".join(f"{h:02d} " for h in range(0, 24, 2)))
for n, v in sorted(byop.items(), key=lambda kv: -len(kv[1]))[:12]:
    if len(v) < 100:
        continue
    hh = Counter(t.hour // 2 for t in v)
    m = max(hh.values()) or 1
    print(f"{n:20s} " + "".join(f"{'#' if hh[h]>0.66*m else '+' if hh[h]>0.33*m else '.' if hh[h] else ' ':>2s} "
                                for h in range(12)))

# --- 8. service time ----------------------------------------------------
print("\n=== 8. SERVICE TIME: do misses cost the same for everyone? ===")
rt = defaultdict(list)
for r in rows:
    try:
        if r.get("s") == 200:
            rt[op(str(r.get("ua", "")))].append(float(r.get("rt", 0)))
    except Exception:
        pass
print(f"{'operator':20s} {'n':>7s} {'median ms':>11s} {'p99 ms':>9s}")
for n, v in sorted(rt.items(), key=lambda kv: -len(kv[1]))[:14]:
    if len(v) < 50:
        continue
    v.sort()
    print(f"{n:20s} {len(v):7d} {1000*statistics.median(v):11.1f} {1000*v[int(.99*len(v))]:9.1f}")
