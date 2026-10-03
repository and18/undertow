#!/usr/bin/env python3
"""
analyze_honeypot.py - Characterisation of the observed automated traffic.

WHAT IT MEASURES, AND WHY

The current debate on automated traffic is organised around
IDENTITY: who is this client, did it declare itself, did it sign.
This script measures BEHAVIOUR instead, because it is
behaviour that determines the infrastructure cost.

The dimensions measured, in order of importance:

  connection reuse    requests per TCP connection. A client that opens
                      a new connection for every request imposes the
                      handshake cost every time and voids any edge
                      affinity. Not reported per individual operator
                      in any published source.

  duplication         requests / distinct URLs. A ratio of 2 means
                      that half of the load is work already done.

  waste               404s and requests to never-linked paths. Load that
                      does not even produce valid data.

  locality            fraction of requests concentrated on the URLs most
                      requested by that client. High = few pages heavily
                      visited (cacheable). Low = uniform scan.

  revalidation        304 against 200. A client that revalidates costs much
                      less than one that re-downloads.

  coverage            how many distinct URLs of the site it touched.

CAVEAT ON THE CONNECTION COUNT

nginx's $connection is a serial number PER WORKER: two workers may
assign the same number to different connections. The key used here is
(ip, connection), which reduces the collisions but does not eliminate them. The
number of distinct connections is therefore an UNDERESTIMATE, and
requests-per-connection an OVERESTIMATE. The direction of the
error is known: whoever shows 1.0 requests per connection really is at 1.0,
because no collision can lower that value.

Usage:
    python3 analyze_honeypot.py /var/log/nginx/agentic.log*
    python3 analyze_honeypot.py --exclude-ip 192.0.2.10 198.51.100.20 -- <file>
"""

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

# Classification by operator. Order matters: the first rule that
# matches wins, so specific rules precede generic ones.
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

# AI categories, for the aggregates.
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
                    # Rotated files may overlap: we deduplicate
                    # on the combination that identifies a request.
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
        # See the caveat at the top on the connection count.
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
    """Fraction of requests concentrated on the 1% most requested URLs.

    It is a direct measure of temporal locality, computable from the logs
    alone. Close to 1 = few pages heavily visited, hence cacheable.
    Close to the fraction itself (0.01) = uniform access, not cacheable.
    """
    if not url_counts:
        return 0.0
    counts = sorted(url_counts.values(), reverse=True)
    k = max(1, int(len(counts) * top_frac))
    return sum(counts[:k]) / sum(counts)


def gini(url_counts):
    """Inequality of the access distribution. 0 = uniform."""
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
    """Intervals between successive requests: median and burstiness."""
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
    # Dispersion index: 1 for a Poisson process, much greater
    # for bursty arrivals.
    return med, (var / mean) if mean > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--exclude-ip", nargs="*", default=[],
                    help="IPs to exclude: own traffic, health checks")
    ap.add_argument("--min-requests", type=int, default=20)
    ap.add_argument("--site-pages", type=int, default=18720)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    excl = set(args.exclude_ip)
    rows, bad = parse(args.logs, excl)
    if not rows:
        sys.exit("no valid row found")

    by = collect(rows)
    total = len(rows)

    print("=" * 96)
    print("CHARACTERISATION OF THE AUTOMATED TRAFFIC")
    print("=" * 96)
    print(f"window     {rows[0].get('t')}  ->  {rows[-1].get('t')}")
    print(f"requests   {total:,}   unparsable rows: {bad}")
    if excl:
        print(f"excluded   {', '.join(sorted(excl))}")

    # --- volume per day ----------------------------------------------------
    days = Counter(r.get("t", "")[:10] for r in rows)
    print("\nVOLUME PER DAY")
    for d in sorted(days):
        print(f"  {d}  {days[d]:>8,}")

    # --- main table --------------------------------------------------------
    print("\n" + "=" * 96)
    print("BEHAVIOUR PER OPERATOR")
    print("=" * 96)
    print(f"{'operator':<16}{'req':>9}{'url':>8}{'req/url':>8}"
          f"{'req/conn':>9}{'IP':>5}{'404%':>7}{'304%':>7}"
          f"{'local':>7}{'gini':>6}{'signed':>6}")
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
        sig = "yes" if s.signed else "-"
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

    # --- detail ------------------------------------------------------------
    print("\n" + "=" * 96)
    print("DETAIL")
    print("=" * 96)
    for name, s in ordered:
        if s.n < args.min_requests:
            continue
        d = export[name]
        print(f"\n{name}   {s.n:,} requests, {s.bytes/1e6:.1f} MB")
        print(f"  connections {d['connections']:,} over {d['ips']} IPs"
              f"   ->  {d['req_per_conn']} requests per connection")
        print(f"  site coverage {d['coverage_pct']}%"
              f"   chapters {d['chapter_pct']}% of the requests")
        print(f"  median interval {d['median_gap_s']}s"
              f"   burstiness {d['burstiness_index']}"
              f"   gzip offered {d['gzip_offered_pct']}%")
        print(f"  protocolli {dict(s.proto)}")
        print(f"  statuses {dict(s.status.most_common(5))}")
        if s.signed:
            print(f"  *** Web Bot Auth: {s.signed:,} signed requests")
        top_ua = s.uas.most_common(1)[0]
        print(f"  ua  {top_ua[0]}")

    # --- aggregates per category ------------------------------------------
    print("\n" + "=" * 96)
    print("AGGREGATES")
    print("=" * 96)
    for label, members in [("AI training", AI_TRAINING),
                           ("AI search", AI_SEARCH),
                           ("AI agent (retrieval)", AI_AGENT),
                           ("traditional engines", SEARCH),
                           ("SEO", SEO)]:
        n = sum(by[m].n for m in members if m in by)
        conns = sum(len(by[m].conns) for m in members if m in by)
        urls = sum(len(by[m].urls) for m in members if m in by)
        if n == 0:
            print(f"  {label:<22} absent")
            continue
        print(f"  {label:<22}{n:>9,} requests "
              f"({100*n/total:>5.1f}%)  "
              f"req/conn {n/conns if conns else 0:>6.1f}  "
              f"req/url {n/urls if urls else 0:>5.2f}")

    # --- signers -----------------------------------------------------------
    print("\nWEB BOT AUTH — who signs")
    signers = [(k, v.signed, v.n) for k, v in by.items() if v.signed]
    if signers:
        for k, sg, n in sorted(signers, key=lambda x: -x[1]):
            rpc = by[k].n / len(by[k].conns) if by[k].conns else 0
            print(f"  {k:<16}{sg:>8,} signed out of {n:,}"
                  f"   ({rpc:.1f} requests per connection)")
        print("\n  Verifiable identity does not predict cost: compare")
        print("  the requests per connection of the signers with those of the")
        print("  non-signers in the main table.")
    else:
        print("  no operator signs")

    # --- never-linked paths -----------------------------------------------
    print("\nWASTE — most requested nonexistent paths")
    miss = Counter(r.get("u", "") for r in rows if r.get("s") == 404)
    for u, c in miss.most_common(15):
        print(f"  {c:>6}  {u[:80]}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"window": [rows[0].get("t"), rows[-1].get("t")],
                       "total": total, "by_operator": export}, f, indent=2)
        print(f"\nJSON: {args.json_out}")

    print("\n" + "=" * 96)
    print("HOW TO READ")
    print("=" * 96)
    print("  req/conn   requests per TCP connection. Values close to 1")
    print("             mean a new connection for every request:")
    print("             repeated handshake cost and no edge")
    print("             affinity. Overestimate (see the caveat in the source).")
    print("  req/url    1.0 = no duplication. 2.0 = every page")
    print("             downloaded twice, half of the load is waste.")
    print("  local      fraction of requests on the 1% most visited URLs.")
    print("             High = cacheable. Close to 0.01 = uniform scan.")
    print("  gini       inequality of the accesses. 0 = perfectly")
    print("             uniform, hence the worst case for a cache.")
    print("  404%       requests to nonexistent paths: whoever guesses")
    print("             instead of following the links.")
    print("  304%       revalidations. A client that revalidates costs much")
    print("             less than one that re-downloads every time.")


if __name__ == "__main__":
    main()