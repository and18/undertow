#!/usr/bin/env python3
"""
Analisi di eventi sull'honeypot: cose mai guardate finora.

  1. Punto di rottura del 15 settembre (default Cloudflare).
  2. Richieste condizionali, ora misurate e non piu' dedotte.
  3. Separazione www/apex: il redirect genera due righe per richiesta.
  4. Canary: /canary.html non e' linkato ne' in sitemap. Chi ci arriva
     sta indovinando percorsi, e non c'e' header che possa mascherarlo.
  5. Forma degli URL inventati: gli agenti costruiscono indirizzi invece
     di seguire link. Che forma hanno? .md? llms.txt? slug prevedibili?
  6. Impulsivita': distribuzione degli intervalli fra richieste per
     operatore. Il carico e' un evento, ma di che forma?
  7. Ciclo giornaliero: gli operatori automatici hanno un giorno e una
     notte, o arrivano quando capita?
  8. Tempo di servizio per operatore: chiedono contenuti di costo
     diverso? Serve a capire se un "miss" costa uguale per tutti.

Uso: python3 honeypot_events.py '/var/log/nginx/agentic.log*' --split 2026-09-15
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

print(f"righe: {len(rows)}\n")

has_host = any("host" in r for r in rows)
has_inm = any("inm" in r for r in rows)
print(f"campo host presente: {has_host}   campo inm presente: {has_inm}")
print("(assenti nei log anteriori al 13 settembre: l'analisi che li usa")
print(" vale solo da quella data in poi)\n")

# --- 1. punto di rottura -------------------------------------------------
print("=== 1. PRIMA E DOPO IL", a.split, "===")
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
print(f"{'operatore':20s} {'req/g prima':>12s} {'req/g dopo':>11s} {'var':>8s} "
      f"{'200 pre':>8s} {'200 post':>9s}")
for n in sorted(set(pre) | set(post), key=lambda x: -(pre[x]["req"] + post[x]["req"]))[:18]:
    a1, a2 = pre[n]["req"] / npre, post[n]["req"] / npost
    p1 = 100 * pre[n]["s200"] / pre[n]["req"] if pre[n]["req"] else 0
    p2 = 100 * post[n]["s200"] / post[n]["req"] if post[n]["req"] else 0
    ch = f"{(a2/a1-1)*100:+.0f}%" if a1 else "nuovo"
    print(f"{n:20s} {a1:12.0f} {a2:11.0f} {ch:>8s} {p1:7.1f}% {p2:8.1f}%")
print(f"\ngiorni: {npre} prima, {npost} dopo")

# --- 2. richieste condizionali ------------------------------------------
if has_inm:
    print("\n=== 2. RICHIESTE CONDIZIONALI (misurate, non dedotte) ===")
    c = Counter()
    for r in rows:
        if r.get("inm") or r.get("ims"):
            c[op(str(r.get("ua", "")))] += 1
    tot = sum(1 for r in rows if "inm" in r)
    print(f"su {tot} righe con il campo: {sum(c.values())} condizionali")
    for n, v in c.most_common(10):
        print(f"  {n:20s} {v}")
    if not c:
        print("  NESSUNA. Ora e' una misura diretta, non un'inferenza dal codice.")

# --- 3. www contro apex --------------------------------------------------
if has_host:
    print("\n=== 3. HOST: quanto traffico e' solo redirect ===")
    h = Counter(str(r.get("host", "-")) for r in rows if "host" in r)
    for k, v in h.most_common(5):
        print(f"  {k:30s} {v}")

# --- 4. canary -----------------------------------------------------------
print("\n=== 4. CANARY: chi trova un URL non linkato e non in sitemap ===")
c = Counter(op(str(r.get("ua", ""))) for r in rows if "/canary" in str(r.get("u", "")))
print("  nessuno" if not c else "")
for n, v in c.most_common():
    print(f"  {n:20s} {v}")

# --- 5. forma degli URL inventati ---------------------------------------
print("\n=== 5. COSA INVENTANO GLI AGENTI ===")
served = {str(r.get("u", "")).split("?")[0] for r in rows if r.get("s") == 200}
for name in sorted(AGENTIC):
    bogus = Counter(str(r.get("u", "")).split("?")[0] for r in rows
                    if op(str(r.get("ua", ""))) == name
                    and str(r.get("u", "")).split("?")[0] not in served)
    if not bogus:
        continue
    print(f"\n{name}: {sum(bogus.values())} richieste a {len(bogus)} URL inesistenti")
    pat = Counter()
    for u in bogus:
        pat[".md" if u.endswith(".md") else
            "llms.txt" if "llms" in u else
            ".json/.xml" if re.search(r"\.(json|xml)$", u) else
            "/api|/v1" if re.search(r"/(api|v1|mcp)", u) else
            "slug con trattini" if re.search(r"/[a-z0-9]+(-[a-z0-9]+){2,}", u) else
            "estensione" if re.search(r"\.[a-z]{2,4}$", u) else "altro"] += 1
    for k, v in pat.most_common():
        print(f"   {k:22s} {v:5d}  ({100*v/len(bogus):.0f}% degli URL)")
    for u, v in bogus.most_common(6):
        print(f"     {v:4d}  {u[:76]}")

# --- 6. impulsivita' -----------------------------------------------------
print("\n=== 6. INTERVALLI FRA RICHIESTE (impulsivita') ===")
byop = defaultdict(list)
for r in rows:
    t = ts(r.get("t"))
    if t:
        byop[op(str(r.get("ua", "")))].append(t)
print(f"{'operatore':20s} {'n':>7s} {'mediana s':>10s} {'p90 s':>9s} {'<1s':>7s} {'>1h':>7s}")
for n, v in sorted(byop.items(), key=lambda kv: -len(kv[1]))[:14]:
    if len(v) < 20:
        continue
    v.sort()
    g = [(v[i + 1] - v[i]).total_seconds() for i in range(len(v) - 1)]
    g.sort()
    print(f"{n:20s} {len(v):7d} {statistics.median(g):10.2f} "
          f"{g[int(.9*len(g))]:9.1f} {100*sum(1 for x in g if x<1)/len(g):6.0f}% "
          f"{100*sum(1 for x in g if x>3600)/len(g):6.0f}%")

# --- 7. ciclo giornaliero -----------------------------------------------
print("\n=== 7. ORA DEL GIORNO (UTC), quota per operatore ===")
print(f"{'operatore':20s} " + "".join(f"{h:02d} " for h in range(0, 24, 2)))
for n, v in sorted(byop.items(), key=lambda kv: -len(kv[1]))[:12]:
    if len(v) < 100:
        continue
    hh = Counter(t.hour // 2 for t in v)
    m = max(hh.values()) or 1
    print(f"{n:20s} " + "".join(f"{'#' if hh[h]>0.66*m else '+' if hh[h]>0.33*m else '.' if hh[h] else ' ':>2s} "
                                for h in range(12)))

# --- 8. tempo di servizio -----------------------------------------------
print("\n=== 8. TEMPO DI SERVIZIO: i miss costano uguale per tutti? ===")
rt = defaultdict(list)
for r in rows:
    try:
        if r.get("s") == 200:
            rt[op(str(r.get("ua", "")))].append(float(r.get("rt", 0)))
    except Exception:
        pass
print(f"{'operatore':20s} {'n':>7s} {'mediana ms':>11s} {'p99 ms':>9s}")
for n, v in sorted(rt.items(), key=lambda kv: -len(kv[1]))[:14]:
    if len(v) < 50:
        continue
    v.sort()
    print(f"{n:20s} {len(v):7d} {1000*statistics.median(v):11.1f} {1000*v[int(.99*len(v))]:9.1f}")
