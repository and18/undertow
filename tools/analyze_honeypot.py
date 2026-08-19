#!/usr/bin/env python3
"""
analyze_honeypot.py - Caratterizzazione del traffico automatico osservato.

COSA MISURA, E PERCHE'

Il dibattito corrente sul traffico automatico e' organizzato attorno
all'IDENTITA': chi e' questo client, si e' dichiarato, ha firmato.
Questo script misura invece il COMPORTAMENTO, perche' e' il
comportamento a determinare il costo infrastrutturale.

Le dimensioni misurate, in ordine di importanza:

  riuso connessione   richieste per connessione TCP. Un client che apre
                      una connessione nuova per ogni richiesta impone il
                      costo di handshake ogni volta e annulla ogni
                      affinita' di edge. Non risulta pubblicato per
                      singolo operatore in nessuna fonte.

  duplicazione        richieste / URL distinte. Un rapporto di 2 significa
                      che meta' del carico e' lavoro gia' fatto.

  spreco              404 e richieste a percorsi mai linkati. Carico che
                      non produce nemmeno dati validi.

  localita'           frazione di richieste concentrata sulle URL piu'
                      richieste da quel client. Alta = poche pagine molto
                      visitate (cacheable). Bassa = scansione uniforme.

  rivalidazione       304 contro 200. Un client che rivalida costa molto
                      meno di uno che riscarica.

  copertura           quante URL distinte del sito ha toccato.

CAVEAT SUL CONTEGGIO DELLE CONNESSIONI

$connection di nginx e' un numero seriale PER WORKER: due worker possono
assegnare lo stesso numero a connessioni diverse. La chiave usata qui e'
(ip, connection), il che riduce le collisioni ma non le elimina. Il
numero di connessioni distinte e' quindi una STIMA PER DIFETTO, e
richieste-per-connessione una stima PER ECCESSO. La direzione
dell'errore e' nota: chi risulta a 1,0 richieste per connessione lo e'
davvero, perche' nessuna collisione puo' abbassare quel valore.

Uso:
    python3 analyze_honeypot.py /var/log/nginx/agentic.log*
    python3 analyze_honeypot.py --exclude-ip 93.47.44.48 130.110.1.121 -- <file>
"""

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

# Classificazione per operatore. L'ordine conta: la prima regola che
# corrisponde vince, quindi le regole specifiche precedono quelle generiche.
OPERATORS = [
    ("GPTBot",        r"GPTBot"),
    ("OAI-SearchBot", r"OAI-SearchBot"),
    ("ChatGPT-User",  r"ChatGPT-User"),
    ("ClaudeBot",     r"ClaudeBot"),
    ("Claude-User",   r"Claude-User"),
    ("PerplexityBot", r"PerplexityBot"),
    ("Perplexity-User", r"Perplexity-User"),
    ("Google-Extended", r"Google-Extended"),
    ("Googlebot",     r"Googlebot"),
    ("Bingbot",       r"bingbot"),
    ("YandexBot",     r"YandexBot"),
    ("Meta",          r"meta-externalagent|facebookexternalhit"),
    ("Amazonbot",     r"Amazonbot"),
    ("Bytespider",    r"Bytespider"),
    ("CCBot",         r"CCBot"),
    ("AhrefsBot",     r"AhrefsBot"),
    ("SemrushBot",    r"SemrushBot"),
    ("Applebot",      r"Applebot"),
    ("MistralAI",     r"MistralAI"),
    ("DuckAssistBot", r"DuckAssistBot"),
    ("scanner",       r"zgrab|l9explore|l9tcpid|Modat|FlowIQ|masscan|Nuclei"),
    ("http-client",   r"^curl|^python|^Go-http|^okhttp|aiohttp|^Java|^Wget|libwww"),
]
OPERATORS = [(n, re.compile(p, re.I)) for n, p in OPERATORS]

# Categorie AI, per gli aggregati.
AI_TRAINING = {"GPTBot", "ClaudeBot", "CCBot", "Bytespider", "Amazonbot",
               "Google-Extended", "Applebot"}
AI_SEARCH = {"OAI-SearchBot", "PerplexityBot", "DuckAssistBot"}
AI_AGENT = {"ChatGPT-User", "Claude-User", "Perplexity-User", "MistralAI"}
SEARCH = {"Googlebot", "Bingbot", "YandexBot"}
SEO = {"AhrefsBot", "SemrushBot"}


def classify(ua):
    if not ua:
        return "no-ua"
    for name, rx in OPERATORS:
        if rx.search(ua):
            return name
    if re.search(r"Chrome|Firefox|Safari|Edge|Gecko", ua, re.I):
        return "browser-like"
    return "other"


def openlog(path):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace")
    return open(path, "r", errors="replace")


def parse(paths, exclude_ips):
    seen = set()
    rows = []
    bad = 0
    for p in paths:
        try:
            with openlog(p) as f:
                for line in f:
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        bad += 1
                        continue
                    if r.get("ip") in exclude_ips:
                        continue
                    # I file ruotati possono sovrapporsi: si deduplica
                    # sulla combinazione che identifica una richiesta.
                    key = (r.get("t"), r.get("ip"), r.get("conn"),
                           r.get("conn_req"), r.get("u"))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(r)
        except OSError as e:
            print(f"  ! {p}: {e}", file=sys.stderr)
    rows.sort(key=lambda r: r.get("t", ""))
    return rows, bad


class Stats:
    __slots__ = ("n", "urls", "conns", "ips", "status", "bytes", "proto",
                 "enc", "signed", "hours", "uas", "url_counts", "times",
                 "chapter_hits")

    def __init__(self):
        self.n = 0
        self.urls = set()
        self.conns = set()
        self.ips = set()
        self.status = Counter()
        self.bytes = 0
        self.proto = Counter()
        self.enc = 0
        self.signed = 0
        self.hours = Counter()
        self.uas = Counter()
        self.url_counts = Counter()
        self.times = []
        self.chapter_hits = 0


CHAPTER = re.compile(r"/book/[^/]+/chapter-")


def collect(rows):
    by = defaultdict(Stats)
    for r in rows:
        k = classify(r.get("ua", ""))
        s = by[k]
        s.n += 1
        u = r.get("u", "")
        s.urls.add(u)
        s.url_counts[u] += 1
        if CHAPTER.search(u):
            s.chapter_hits += 1
        ip = r.get("ip", "")
        s.ips.add(ip)
        # Vedi il caveat in testa sul conteggio delle connessioni.
        s.conns.add((ip, r.get("conn", "")))
        s.status[r.get("s", 0)] += 1
        s.bytes += r.get("b", 0) or 0
        s.proto[r.get("proto", "?")] += 1
        if r.get("enc"):
            s.enc += 1
        if r.get("sig_agent") or r.get("sig_input"):
            s.signed += 1
        t = r.get("t", "")
        if len(t) >= 13:
            s.hours[t[11:13]] += 1
        s.uas[(r.get("ua") or "")[:110]] += 1
        try:
            s.times.append(datetime.fromisoformat(t).timestamp())
        except (ValueError, TypeError):
            pass
    return by


def locality(url_counts, top_frac=0.01):
    """Frazione di richieste concentrata sull'1% di URL piu' richieste.

    E' una misura diretta della localita' temporale, calcolabile dai soli
    log. Vicino a 1 = poche pagine molto visitate, quindi cacheable.
    Vicino alla frazione stessa (0,01) = accesso uniforme, non cacheable.
    """
    if not url_counts:
        return 0.0
    counts = sorted(url_counts.values(), reverse=True)
    k = max(1, int(len(counts) * top_frac))
    return sum(counts[:k]) / sum(counts)


def gini(url_counts):
    """Disuguaglianza della distribuzione degli accessi. 0 = uniforme."""
    v = sorted(url_counts.values())
    n = len(v)
    if n < 2:
        return 0.0
    tot = sum(v)
    if tot == 0:
        return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * tot) - (n + 1) / n


def median(xs):
    if not xs:
        return 0.0
    v = sorted(xs)
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def gap_stats(times):
    """Intervalli fra richieste successive: mediana e burstiness."""
    if len(times) < 3:
        return 0.0, 0.0
    gaps = [b - a for a, b in zip(times, times[1:]) if b >= a]
    if not gaps:
        return 0.0, 0.0
    med = median(gaps)
    mean = sum(gaps) / len(gaps)
    if mean <= 0:
        return med, 0.0
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    # Indice di dispersione: 1 per un processo di Poisson, molto maggiore
    # per arrivi a raffica.
    return med, (var / mean) if mean > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--exclude-ip", nargs="*", default=[],
                    help="IP da escludere: traffico proprio, health check")
    ap.add_argument("--min-requests", type=int, default=20)
    ap.add_argument("--site-pages", type=int, default=18720)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    excl = set(args.exclude_ip)
    rows, bad = parse(args.logs, excl)
    if not rows:
        sys.exit("nessuna riga valida trovata")

    by = collect(rows)
    total = len(rows)

    print("=" * 96)
    print("CARATTERIZZAZIONE DEL TRAFFICO AUTOMATICO")
    print("=" * 96)
    print(f"finestra   {rows[0].get('t')}  ->  {rows[-1].get('t')}")
    print(f"richieste  {total:,}   righe non parsabili: {bad}")
    if excl:
        print(f"esclusi    {', '.join(sorted(excl))}")

    # --- volume per giorno -------------------------------------------------
    days = Counter(r.get("t", "")[:10] for r in rows)
    print("\nVOLUME PER GIORNO")
    for d in sorted(days):
        print(f"  {d}  {days[d]:>8,}")

    # --- tabella principale ------------------------------------------------
    print("\n" + "=" * 96)
    print("COMPORTAMENTO PER OPERATORE")
    print("=" * 96)
    print(f"{'operatore':<16}{'req':>9}{'url':>8}{'req/url':>8}"
          f"{'req/conn':>9}{'IP':>5}{'404%':>7}{'304%':>7}"
          f"{'local':>7}{'gini':>6}{'firma':>6}")
    print("-" * 96)

    ordered = sorted(by.items(), key=lambda kv: -kv[1].n)
    export = {}
    for name, s in ordered:
        if s.n < args.min_requests:
            continue
        nurl = len(s.urls)
        rpu = s.n / nurl if nurl else 0
        rpc = s.n / len(s.conns) if s.conns else 0
        e404 = 100 * s.status.get(404, 0) / s.n
        e304 = 100 * s.status.get(304, 0) / s.n
        loc = locality(s.url_counts)
        g = gini(s.url_counts)
        sig = "si" if s.signed else "-"
        print(f"{name:<16}{s.n:>9,}{nurl:>8,}{rpu:>8.2f}{rpc:>9.1f}"
              f"{len(s.ips):>5}{e404:>7.1f}{e304:>7.1f}"
              f"{loc:>7.3f}{g:>6.2f}{sig:>6}")
        med_gap, disp = gap_stats(s.times)
        export[name] = {
            "requests": s.n, "unique_urls": nurl,
            "req_per_url": round(rpu, 3),
            "req_per_conn": round(rpc, 2),
            "connections": len(s.conns), "ips": len(s.ips),
            "pct_404": round(e404, 2), "pct_304": round(e304, 2),
            "locality_top1pct": round(loc, 4),
            "gini": round(g, 3),
            "signed_requests": s.signed,
            "bytes": s.bytes,
            "gzip_offered_pct": round(100 * s.enc / s.n, 1),
            "coverage_pct": round(100 * nurl / args.site_pages, 2),
            "chapter_pct": round(100 * s.chapter_hits / s.n, 1),
            "median_gap_s": round(med_gap, 3),
            "burstiness_index": round(disp, 2),
            "protocols": dict(s.proto),
            "hours": dict(sorted(s.hours.items())),
        }

    # --- dettaglio ---------------------------------------------------------
    print("\n" + "=" * 96)
    print("DETTAGLIO")
    print("=" * 96)
    for name, s in ordered:
        if s.n < args.min_requests:
            continue
        d = export[name]
        print(f"\n{name}   {s.n:,} richieste, {s.bytes/1e6:.1f} MB")
        print(f"  connessioni {d['connections']:,} su {d['ips']} IP"
              f"   ->  {d['req_per_conn']} richieste per connessione")
        print(f"  copertura del sito {d['coverage_pct']}%"
              f"   capitoli {d['chapter_pct']}% delle richieste")
        print(f"  intervallo mediano {d['median_gap_s']}s"
              f"   burstiness {d['burstiness_index']}"
              f"   gzip offerto {d['gzip_offered_pct']}%")
        print(f"  protocolli {dict(s.proto)}")
        print(f"  stati {dict(s.status.most_common(5))}")
        if s.signed:
            print(f"  *** Web Bot Auth: {s.signed:,} richieste firmate")
        top_ua = s.uas.most_common(1)[0]
        print(f"  ua  {top_ua[0]}")

    # --- aggregati per categoria ------------------------------------------
    print("\n" + "=" * 96)
    print("AGGREGATI")
    print("=" * 96)
    for label, members in [("AI training", AI_TRAINING),
                           ("AI search", AI_SEARCH),
                           ("AI agent (retrieval)", AI_AGENT),
                           ("motori tradizionali", SEARCH),
                           ("SEO", SEO)]:
        n = sum(by[m].n for m in members if m in by)
        conns = sum(len(by[m].conns) for m in members if m in by)
        urls = sum(len(by[m].urls) for m in members if m in by)
        if n == 0:
            print(f"  {label:<22} assente")
            continue
        print(f"  {label:<22}{n:>9,} richieste "
              f"({100*n/total:>5.1f}%)  "
              f"req/conn {n/conns if conns else 0:>6.1f}  "
              f"req/url {n/urls if urls else 0:>5.2f}")

    # --- firmatari ---------------------------------------------------------
    print("\nWEB BOT AUTH — chi firma")
    signers = [(k, v.signed, v.n) for k, v in by.items() if v.signed]
    if signers:
        for k, sg, n in sorted(signers, key=lambda x: -x[1]):
            rpc = by[k].n / len(by[k].conns) if by[k].conns else 0
            print(f"  {k:<16}{sg:>8,} firmate su {n:,}"
                  f"   ({rpc:.1f} richieste per connessione)")
        print("\n  L'identita' verificabile non predice il costo: confrontare")
        print("  le richieste per connessione dei firmatari con quelle dei")
        print("  non firmatari nella tabella principale.")
    else:
        print("  nessun operatore firma")

    # --- percorsi mai linkati ---------------------------------------------
    print("\nSPRECO — percorsi inesistenti piu' richiesti")
    miss = Counter(r.get("u", "") for r in rows if r.get("s") == 404)
    for u, c in miss.most_common(15):
        print(f"  {c:>6}  {u[:80]}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"window": [rows[0].get("t"), rows[-1].get("t")],
                       "total": total, "by_operator": export}, f, indent=2)
        print(f"\nJSON: {args.json_out}")

    print("\n" + "=" * 96)
    print("COME LEGGERE")
    print("=" * 96)
    print("  req/conn   richieste per connessione TCP. Valori vicini a 1")
    print("             significano una connessione nuova per ogni richiesta:")
    print("             costo di handshake ripetuto e nessuna affinita' di")
    print("             edge. Stima per eccesso (vedi caveat nel sorgente).")
    print("  req/url    1,0 = nessuna duplicazione. 2,0 = ogni pagina")
    print("             scaricata due volte, meta' del carico e' spreco.")
    print("  local      frazione di richieste sull'1% di URL piu' visitate.")
    print("             Alta = cacheable. Vicina a 0,01 = scansione uniforme.")
    print("  gini       disuguaglianza degli accessi. 0 = perfettamente")
    print("             uniforme, quindi il caso peggiore per una cache.")
    print("  404%       richieste a percorsi inesistenti: chi indovina")
    print("             invece di seguire i link.")
    print("  304%       rivalidazioni. Un client che rivalida costa molto")
    print("             meno di uno che riscarica ogni volta.")


if __name__ == "__main__":
    main()