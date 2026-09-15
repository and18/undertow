#!/usr/bin/env python3
"""
honeypot_deep.py - Analisi sistematica dei log dell'honeypot.

Sostituisce honeypot_events.py, che copriva otto domande scelte a mano.
Qui le sezioni seguono il ciclo di vita di una richiesta: chi arriva, su
che connessione, cosa chiede, cosa ottiene, quanto spreca, con che ritmo,
e quanto costa.

Ogni sezione dichiara cosa puo' invalidarla. Le sezioni che dipendono da
campi introdotti il 13 settembre (host, inm, ims) lo segnalano.

Uso:
  python3 honeypot_deep.py '/var/log/nginx/agentic.log*' [--split 2026-09-15]
                           [--pages 18720] [--json /tmp/deep.json]
"""

import argparse, glob, gzip, json, math, re, statistics, sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta

# --------------------------------------------------------------- tassonomia

OPS = [
    ("GPTBot",            r"GPTBot",                  "ai-training"),
    ("ChatGPT-User",      r"ChatGPT-User",            "ai-agent"),
    ("OAI-SearchBot",     r"OAI-SearchBot",           "ai-search"),
    ("ClaudeBot",         r"ClaudeBot|anthropic-ai",  "ai-training"),
    ("Claude-User",       r"Claude-User",             "ai-agent"),
    ("Claude-SearchBot",  r"Claude-SearchBot",        "ai-search"),
    ("PerplexityBot",     r"PerplexityBot",           "ai-search"),
    ("Perplexity-User",   r"Perplexity-User",         "ai-agent"),
    ("MistralAI-User",    r"MistralAI",               "ai-agent"),
    ("DuckAssistBot",     r"DuckAssistBot",           "ai-search"),
    ("Meta-External",     r"[Mm]eta-[Ee]xternal",     "ai-training"),
    ("Amazonbot",         r"Amazonbot",               "ai-training"),
    ("Bytespider",        r"Bytespider",              "ai-training"),
    ("CCBot",             r"CCBot",                   "ai-training"),
    ("Google-Extended",   r"Google-Extended",         "ai-training"),
    ("Google-CloudVertex", r"Google-CloudVertexBot",  "ai-training"),
    ("Applebot",          r"Applebot",                "ai-search"),
    ("GoogleOther",       r"GoogleOther",             "search"),
    ("Googlebot",         r"Googlebot",               "search"),
    ("Bingbot",           r"bingbot",                 "search"),
    ("YandexBot",         r"YandexBot",               "search"),
    ("AhrefsBot",         r"AhrefsBot",               "seo"),
    ("SemrushBot",        r"SemrushBot",              "seo"),
    ("SERanking",         r"SERanking",               "seo"),
    ("DotBot",            r"DotBot",                  "seo"),
    ("MJ12bot",           r"MJ12bot",                 "seo"),
    ("scanner",           r"l9explore|zgrab|Modat|feroxbuster|Infrawatch|"
                          r"masscan|Nuclei|FlowIQ|CensysInspect|Expanse", "scanner"),
    ("tooling",           r"UptimeRobot|Pingdom|StatusCake|curl/|Wget|"
                          r"python-requests|Go-http|okhttp|axios|node-fetch", "tooling"),
]
BROWSERISH = re.compile(r"Mozilla/5\.0", re.I)
AGENTIC = {"ChatGPT-User", "Claude-User", "Perplexity-User", "MistralAI-User"}


def classify(ua):
    for name, pat, cls in OPS:
        if re.search(pat, ua):
            return name, cls
    return ("browser-like", "unclassified") if BROWSERISH.search(ua) \
        else ("other", "unclassified")


def parse_ts(v):
    if v is None:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def gini(values):
    v = sorted(values)
    n = len(v)
    s = sum(v)
    if n == 0 or s == 0:
        return 0.0
    return (2 * sum(i * x for i, x in enumerate(v, 1))) / (n * s) - (n + 1) / n


def pct(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))]


def hdr(n, title):
    print(f"\n{'=' * 74}\n{n}. {title}\n{'=' * 74}")


# ------------------------------------------------------------------ lettura

ap = argparse.ArgumentParser()
ap.add_argument("pattern")
ap.add_argument("--split", default=None,
                help="data di taglio per il confronto prima/dopo, es. 2026-09-15")
ap.add_argument("--pages", type=int, default=18720)
ap.add_argument("--json", default=None)
args = ap.parse_args()

files = sorted(glob.glob(args.pattern))
if not files:
    sys.exit(f"nessun file corrisponde a {args.pattern}")

R = []
bad = 0
for path in files:
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    R.append(json.loads(line))
                except Exception:
                    bad += 1
    except Exception as e:
        print(f"ATTENZIONE: {path} non leggibile ({e})", file=sys.stderr)

if not R:
    sys.exit("nessuna riga JSON trovata: controlla permessi e formato")

# arricchimento
for r in R:
    r["_t"] = parse_ts(r.get("t"))
    r["_op"], r["_cls"] = classify(str(r.get("ua") or "-"))
    r["_u"] = str(r.get("u") or "-").split("?")[0]
    try:
        r["_s"] = int(r.get("s") or 0)
    except Exception:
        r["_s"] = 0
    try:
        r["_b"] = int(r.get("b") or 0)
    except Exception:
        r["_b"] = 0
    try:
        r["_rt"] = float(r.get("rt") or 0)
    except Exception:
        r["_rt"] = 0.0

R.sort(key=lambda x: x["_t"] or datetime.min)
served = {r["_u"] for r in R if r["_s"] == 200}
days = sorted({r["_t"].date() for r in R if r["_t"]})

byop = defaultdict(list)
for r in R:
    byop[r["_op"]].append(r)
order = sorted(byop, key=lambda k: -len(byop[k]))

# ------------------------------------------------- 1. inventario e qualita'

hdr(1, "INVENTARIO E QUALITA' DEL DATO")
print(f"file letti            {len(files)}")
print(f"righe valide          {len(R)}   non parsate {bad}")
print(f"finestra              {days[0]} → {days[-1]}  ({len(days)} giorni)")
print(f"operatori distinti    {len(byop)}")

present = {k: sum(1 for r in R if k in r) for k in
           ("host", "inm", "ims", "conn", "conn_req", "sig_agent", "proto", "rt", "ref")}
print("\ncampi presenti (righe su totale):")
for k, v in present.items():
    flag = "" if v == len(R) else "   ← parziale, introdotto in corsa"
    print(f"  {k:10s} {v:8d} / {len(R)}{flag}")

protos = Counter(str(r.get("proto") or "-") for r in R)
print("\nversione di protocollo:")
for p, n in protos.most_common():
    print(f"  {p:12s} {n:8d}  {100*n/len(R):5.1f}%")
h2 = sum(n for p, n in protos.items() if "2" in p)
if h2 == 0:
    print("  ANOMALIA: zero HTTP/2 mentre nginx ha 'listen 443 ssl http2'.")
    print("  O nessun client lo negozia (implausibile), o $server_protocol non")
    print("  lo registra. Ogni conclusione sul riuso delle connessioni ne dipende.")

maxcr = defaultdict(int)
for r in R:
    try:
        maxcr[r["_op"]] = max(maxcr[r["_op"]], int(r.get("conn_req") or 0))
    except Exception:
        pass
tetti = [o for o, v in maxcr.items() if v in (1000, 100000)]
if tetti:
    print(f"\nTETTO DI MISURA: operatori fermi esattamente su keepalive_requests: "
          f"{', '.join(tetti)}")
    print("  Il riuso per questi e' un limite inferiore, non una misura.")

# ------------------------------------------------------- 2. composizione

hdr(2, "COMPOSIZIONE DEL TRAFFICO")
bycls = Counter(r["_cls"] for r in R)
for c, n in bycls.most_common():
    print(f"  {c:16s} {n:8d}  {100*n/len(R):5.1f}%")

print(f"\n{'operatore':20s} {'req':>8s} {'quota':>7s} {'MB':>8s} {'giorni':>7s} "
      f"{'picco/media':>12s} {'prima':>12s} {'ultima':>12s}")
for o in order[:24]:
    rows = byop[o]
    daily = Counter(r["_t"].date() for r in rows if r["_t"])
    vals = list(daily.values()) or [0]
    peak = max(vals) / (sum(vals) / len(vals)) if vals else 0
    mb = sum(r["_b"] for r in rows) / 1048576
    ts_ = [r["_t"] for r in rows if r["_t"]]
    print(f"{o:20s} {len(rows):8d} {100*len(rows)/len(R):6.1f}% {mb:8.1f} "
          f"{len(daily):7d} {peak:12.1f} "
          f"{min(ts_).strftime('%m-%d %H:%M') if ts_ else '-':>12s} "
          f"{max(ts_).strftime('%m-%d %H:%M') if ts_ else '-':>12s}")

# --------------------------------------------------------- 3. prima/dopo

if args.split:
    hdr(3, f"PRIMA E DOPO IL {args.split}")
    S = datetime.fromisoformat(args.split)
    pre = [r for r in R if r["_t"] and r["_t"] < S]
    post = [r for r in R if r["_t"] and r["_t"] >= S]
    dpre = len({r["_t"].date() for r in pre}) or 1
    dpost = len({r["_t"].date() for r in post}) or 1
    print(f"finestra prima: {dpre} giorni, {len(pre)} richieste")
    print(f"finestra dopo:  {dpost} giorni, {len(post)} richieste")
    if dpost < 3:
        print("\nATTENZIONE: meno di tre giorni dopo il taglio. Questa sezione")
        print("fissa la fotografia, non conclude. Rileggerla fra una settimana.")
    a = Counter(r["_op"] for r in pre)
    b = Counter(r["_op"] for r in post)
    ok_a = Counter(r["_op"] for r in pre if r["_s"] == 200)
    ok_b = Counter(r["_op"] for r in post if r["_s"] == 200)
    print(f"\n{'operatore':20s} {'req/g prima':>12s} {'req/g dopo':>11s} {'var':>9s} "
          f"{'200 prima':>10s} {'200 dopo':>9s}")
    for o in sorted(set(a) | set(b), key=lambda k: -(a[k] + b[k]))[:20]:
        r1, r2 = a[o] / dpre, b[o] / dpost
        p1 = 100 * ok_a[o] / a[o] if a[o] else 0
        p2 = 100 * ok_b[o] / b[o] if b[o] else 0
        ch = f"{(r2/r1-1)*100:+.0f}%" if r1 else "nuovo"
        print(f"{o:20s} {r1:12.0f} {r2:11.0f} {ch:>9s} {p1:9.1f}% {p2:8.1f}%")

# ------------------------------------------------------------ 4. identita'

hdr(4, "IDENTITA' E PROVENIENZA")
print(f"{'operatore':20s} {'firmate':>9s} {'% firm':>7s} {'IP':>7s} {'/24':>6s} "
      f"{'req/IP':>8s} {'conc.max':>9s}")
for o in order[:20]:
    rows = byop[o]
    sig = sum(1 for r in rows if str(r.get("sig_agent") or "").strip() not in ("", "-"))
    ips = {str(r.get("ip")) for r in rows}
    nets = {".".join(str(r.get("ip")).split(".")[:3]) for r in rows}
    # concorrenza: massimo numero di connessioni distinte viste in 10 s
    buckets = defaultdict(set)
    for r in rows:
        if r["_t"]:
            buckets[int(r["_t"].timestamp() // 10)].add((r.get("ip"), r.get("conn")))
    conc = max((len(v) for v in buckets.values()), default=0)
    print(f"{o:20s} {sig:9d} {100*sig/len(rows):6.1f}% {len(ips):7d} {len(nets):6d} "
          f"{len(rows)/max(len(ips),1):8.1f} {conc:9d}")
print("\nconc.max = connessioni distinte aperte dallo stesso operatore in 10 s.")
print("E' la pressione istantanea, che il totale giornaliero non mostra.")

# --------------------------------------------------------- 5. connessioni

hdr(5, "RIUSO DELLE CONNESSIONI")
print(f"{'operatore':20s} {'conn':>8s} {'req/conn':>9s} {'max su 1':>9s} "
      f"{'mediana':>8s} {'p90':>6s}")
for o in order[:20]:
    rows = byop[o]
    per = Counter()
    for r in rows:
        per[(r.get("ip"), r.get("conn"))] += 1
    v = sorted(per.values())
    if not v:
        continue
    print(f"{o:20s} {len(per):8d} {len(rows)/len(per):9.1f} {max(v):9d} "
          f"{statistics.median(v):8.1f} {pct(v, .9):6d}")
print("\nCaveat: nginx $connection e' un seriale per worker, quindi la chiave")
print("(ip, conn) sottostima le connessioni distinte e sovrastima il riuso.")

# ------------------------------------------------------------- 6. cache

hdr(6, "COMPORTAMENTO VERSO LA CACHE")
cond = [r for r in R if str(r.get("inm") or "").strip() not in ("", "-")
        or str(r.get("ims") or "").strip() not in ("", "-")]
n304 = [r for r in R if r["_s"] == 304]
withfield = present["inm"]
print(f"righe con il campo inm/ims:  {withfield}")
print(f"richieste condizionali:      {len(cond)}"
      f"  ({100*len(cond)/max(withfield,1):.4f}% di quelle misurabili)")
print(f"risposte 304:                {len(n304)}  ({100*len(n304)/len(R):.4f}%)")
if withfield == 0:
    print("  Il campo non esiste nei log letti: 'nessuno rivalida' resta")
    print("  un'inferenza dal codice di risposta, non una misura.")
c = Counter(r["_op"] for r in cond)
for o, n in c.most_common(8):
    print(f"    condizionali  {o:20s} {n}")
c = Counter(r["_op"] for r in n304)
for o, n in c.most_common(8):
    print(f"    304           {o:20s} {n}")

print("\nIntervallo di ritorno sullo stesso URL (chi ignora max-age=86400):")
print(f"{'operatore':20s} {'URL ripetuti':>13s} {'mediana h':>10s} {'<24h':>7s}")
for o in order[:16]:
    gaps = []
    seen = defaultdict(list)
    for r in byop[o]:
        if r["_t"]:
            seen[r["_u"]].append(r["_t"])
    rep = 0
    for u, ts_ in seen.items():
        if len(ts_) > 1:
            rep += 1
            ts_.sort()
            gaps += [(ts_[i+1] - ts_[i]).total_seconds() / 3600
                     for i in range(len(ts_) - 1)]
    if not gaps:
        continue
    gaps.sort()
    print(f"{o:20s} {rep:13d} {statistics.median(gaps):10.1f} "
          f"{100*sum(1 for g in gaps if g < 24)/len(gaps):6.0f}%")

# -------------------------------------------------------------- 7. spreco

hdr(7, "SPRECO: QUANTO TRAFFICO NON SERVE A NIENTE")
print(f"{'operatore':20s} {'200':>7s} {'301':>7s} {'404':>7s} {'altro':>7s} "
      f"{'utile':>7s} {'MB persi':>9s}")
for o in order[:20]:
    rows = byop[o]
    c = Counter(r["_s"] for r in rows)
    n = len(rows)
    util = 100 * c[200] / n
    lost = sum(r["_b"] for r in rows if r["_s"] != 200) / 1048576
    altro = n - c[200] - c[301] - c[404]
    print(f"{o:20s} {100*c[200]/n:6.1f}% {100*c[301]/n:6.1f}% "
          f"{100*c[404]/n:6.1f}% {100*altro/n:6.1f}% {util:6.1f}% {lost:9.2f}")
if present["host"]:
    print("\nHost richiesto (il redirect www genera due righe per richiesta utile):")
    for h, n in Counter(str(r.get("host") or "-") for r in R
                        if "host" in r).most_common(5):
        print(f"  {h:32s} {n:8d}")

# ------------------------------------------------------- 8. strategia

hdr(8, "STRATEGIA DI CRAWLING")
print(f"{'operatore':20s} {'URL':>7s} {'reali':>7s} {'inventati':>10s} "
      f"{'copertura':>10s} {'gini':>6s} {'req/URL':>8s} {'profondita':>11s}")
for o in order[:20]:
    rows = byop[o]
    urls = Counter(r["_u"] for r in rows)
    real = [u for u in urls if u in served]
    bogus = [u for u in urls if u not in served]
    depth = statistics.median([u.count("/") for u in urls]) if urls else 0
    print(f"{o:20s} {len(urls):7d} {len(real):7d} {len(bogus):10d} "
          f"{100*len(real)/args.pages:9.2f}% {gini(list(urls.values())):6.3f} "
          f"{len(rows)/max(len(urls),1):8.2f} {depth:11.0f}")

print("\nOrdine di visita (correlazione fra ordine temporale e ordine")
print("alfabetico degli URL: ~1 = segue la sitemap, ~0 = ordine proprio):")
for o in order[:14]:
    seq = [r["_u"] for r in byop[o] if r["_s"] == 200]
    if len(seq) < 100:
        continue
    uniq, seen = [], set()
    for u in seq:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    if len(uniq) < 50:
        continue
    rank = {u: i for i, u in enumerate(sorted(uniq))}
    asc = sum(1 for i in range(len(uniq) - 1)
              if rank[uniq[i+1]] > rank[uniq[i]])
    print(f"  {o:20s} {asc/(len(uniq)-1):.3f}   ({len(uniq)} URL distinti)")

# --------------------------------------------------------- 9. agentici

hdr(9, "COMPORTAMENTO AGENTICO")
canary = [r for r in R if "canary" in r["_u"]]
print(f"/canary.html - non linkato, non in sitemap: {len(canary)} richieste")
for o, n in Counter(r["_op"] for r in canary).most_common():
    print(f"  {o:20s} {n}")
if not canary:
    print("  nessuno. Nessun client ha indovinato quel percorso.")

for o in [x for x in order if x in AGENTIC]:
    rows = byop[o]
    urls = Counter(r["_u"] for r in rows)
    bogus = {u: v for u, v in urls.items() if u not in served}
    print(f"\n{o}: {len(rows)} richieste, {len(urls)} URL distinti, "
          f"{len(bogus)} inesistenti ({100*len(bogus)/max(len(urls),1):.0f}%)")
    if bogus:
        pat = Counter()
        for u in bogus:
            pat[".md"          if u.endswith(".md") else
                "llms.txt"     if "llms" in u.lower() else
                "json/xml"     if re.search(r"\.(json|xml)$", u) else
                "api/mcp"      if re.search(r"/(api|v1|mcp|\.well-known)", u) else
                "slug lungo"   if re.search(r"/[a-z0-9]+(-[a-z0-9]+){2,}", u) else
                "altra estens." if re.search(r"\.[a-z]{2,4}$", u) else
                "senza estens."] += 1
        for k, v in pat.most_common():
            print(f"    {k:18s} {v:5d}  {100*v/len(bogus):4.0f}%")
        for u, v in sorted(bogus.items(), key=lambda kv: -kv[1])[:6]:
            print(f"      {v:4d}  {u[:74]}")
    # sessioni: raffiche separate da piu' di 5 minuti
    ts_ = sorted(r["_t"] for r in rows if r["_t"])
    if len(ts_) > 5:
        sess, cur = [], 1
        for i in range(len(ts_) - 1):
            if (ts_[i+1] - ts_[i]).total_seconds() > 300:
                sess.append(cur); cur = 1
            else:
                cur += 1
        sess.append(cur)
        print(f"    sessioni: {len(sess)}, mediana {statistics.median(sess):.0f} "
              f"richieste, massima {max(sess)}")

# ------------------------------------------------------ 10. impulsivita'

hdr(10, "RITMO E IMPULSIVITA'")
print(f"{'operatore':20s} {'mediana s':>10s} {'p90 s':>8s} {'<1s':>6s} "
      f"{'>1h':>6s} {'dispers.':>9s}")
for o in order[:18]:
    ts_ = sorted(r["_t"] for r in byop[o] if r["_t"])
    if len(ts_) < 30:
        continue
    g = sorted((ts_[i+1] - ts_[i]).total_seconds() for i in range(len(ts_) - 1))
    permin = Counter(int(t.timestamp() // 60) for t in ts_)
    vals = list(permin.values())
    disp = (statistics.pvariance(vals) / statistics.mean(vals)) if len(vals) > 1 \
        and statistics.mean(vals) > 0 else 0
    print(f"{o:20s} {statistics.median(g):10.2f} {pct(g,.9):8.1f} "
          f"{100*sum(1 for x in g if x<1)/len(g):5.0f}% "
          f"{100*sum(1 for x in g if x>3600)/len(g):5.0f}% {disp:9.1f}")
print("\ndispers. = varianza/media delle richieste al minuto. 1 = arrivi casuali")
print("(Poisson). Valori alti = raffiche. Il dimensionamento sulla media")
print("e' sbagliato di tanto quanto questo numero e' sopra 1.")

print("\nOra del giorno UTC (# > 66% del picco, + > 33%, . resto):")
print(f"{'operatore':20s} " + "".join(f"{h:>2d}" for h in range(0, 24, 2)))
for o in order[:14]:
    ts_ = [r["_t"] for r in byop[o] if r["_t"]]
    if len(ts_) < 200:
        continue
    hh = Counter(t.hour // 2 for t in ts_)
    m = max(hh.values()) or 1
    print(f"{o:20s} " + "".join(
        f"{'#' if hh[h] > .66*m else '+' if hh[h] > .33*m else '.' if hh[h] else ' ':>2s}"
        for h in range(12)))

# --------------------------------------------------------------- 11. costo

hdr(11, "COSTO: I MISS NON COSTANO UGUALE")
print(f"{'operatore':20s} {'n':>7s} {'KB med':>8s} {'KB p99':>9s} "
      f"{'ms med':>8s} {'ms p99':>8s}")
for o in order[:18]:
    rows = [r for r in byop[o] if r["_s"] == 200]
    if len(rows) < 30:
        continue
    b = sorted(r["_b"] for r in rows)
    t = sorted(r["_rt"] for r in rows)
    print(f"{o:20s} {len(rows):7d} {statistics.median(b)/1024:8.1f} "
          f"{pct(b,.99)/1024:9.1f} {1000*statistics.median(t):8.1f} "
          f"{1000*pct(t,.99):8.1f}")
print("\nSe la taglia mediana varia molto fra operatori su contenuto statico,")
print("allora classi diverse chiedono oggetti di costo diverso. Sul banco")
print("prova questo significa che contare i miss non equivale a contare il")
print("lavoro, ed e' il limite principale della metrica origin rps.")

# --------------------------------------------------- 12. sovrapposizione

hdr(12, "SOVRAPPOSIZIONE FRA OPERATORI")
sets = {o: {r["_u"] for r in byop[o] if r["_s"] == 200} for o in order[:10]}
sets = {o: s for o, s in sets.items() if len(s) > 200}
names = list(sets)
print("Jaccard sugli URL serviti con 200 (1 = stesse pagine, 0 = disgiunti):")
print(f"{'':18s}" + "".join(f"{n[:8]:>9s}" for n in names))
for a_ in names:
    row = ""
    for b_ in names:
        u = len(sets[a_] | sets[b_])
        row += f"{len(sets[a_] & sets[b_])/u:9.2f}" if u else f"{'-':>9s}"
    print(f"{a_[:18]:18s}{row}")
print("\nSovrapposizione alta = gli operatori si riscaldano la cache a vicenda.")
print("E' l'analogo di campo dell'esternalita' misurata sul banco prova.")

# ------------------------------------------------------------------- json

if args.json:
    out = {"generated": datetime.now().isoformat(), "files": len(files),
           "rows": len(R), "days": len(days),
           "first": str(days[0]), "last": str(days[-1]),
           "operators": {o: len(byop[o]) for o in order}}
    with open(args.json, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\nriepilogo in {args.json}")