#!/usr/bin/env python3
"""
Analisi esaustiva dei log honeypot. Produce le misure di campo che
calibrano i parametri delle classi del banco prova (decisions.md §2).

Uso:  python3 honeypot_full.py '/var/log/nginx/agentic.log*' --pages 18720 --out /tmp/hp
"""
import argparse, glob, gzip, json, math, re, sys
from collections import defaultdict, Counter
from datetime import datetime

CANDIDATES = {
    "ts":     ["time_iso8601", "timestamp", "time_local", "time", "ts", "t"],
    "ua":     ["http_user_agent", "user_agent", "ua", "agent"],
    "uri":    ["request_uri", "uri", "path", "request", "u"],
    "status": ["status", "code", "s"],
    "ip":     ["remote_addr", "client_ip", "ip"],
    "conn":   ["connection", "conn", "connection_id"],
    "connreq":["connection_requests", "conn_requests", "connection_req", "conn_req"],
    "bytes":  ["body_bytes_sent", "bytes_sent", "bytes", "b"],
    "proto":  ["server_protocol", "protocol", "http_version"],
    "sigagent":["http_signature_agent", "signature_agent", "sig_agent"],
    "rtime":  ["request_time", "rt"],
    "siginput":["http_signature_input", "signature_input", "sig_input"],
    "inm":    ["http_if_none_match", "if_none_match"],
    "ims":    ["http_if_modified_since", "if_modified_since"],
    "ref":    ["http_referer", "referer"],
}

OPERATORS = [
    ("GPTBot",            r"GPTBot",                        "ai-training"),
    ("ChatGPT-User",      r"ChatGPT-User",                  "ai-agent"),
    ("OAI-SearchBot",     r"OAI-SearchBot",                 "ai-search"),
    ("ClaudeBot",         r"ClaudeBot|anthropic-ai",        "ai-training"),
    ("Claude-User",       r"Claude-User",                   "ai-agent"),
    ("Claude-SearchBot",  r"Claude-SearchBot",              "ai-search"),
    ("PerplexityBot",     r"PerplexityBot",                 "ai-search"),
    ("Perplexity-User",   r"Perplexity-User",               "ai-agent"),
    ("Meta-ExternalAgent",r"[Mm]eta-[Ee]xternal",           "ai-training"),
    ("Amazonbot",         r"Amazonbot",                     "ai-training"),
    ("Bytespider",        r"Bytespider",                    "ai-training"),
    ("Applebot",          r"Applebot",                      "ai-search"),
    ("Google-Extended",   r"Google-Extended",               "ai-training"),
    ("GoogleOther",       r"GoogleOther",                   "search"),
    ("Google-CloudVertex",r"Google-CloudVertexBot",         "ai-training"),
    ("Googlebot",         r"Googlebot",                     "search"),
    ("Bingbot",           r"bingbot",                       "search"),
    ("YandexBot",         r"YandexBot",                     "search"),
    ("AhrefsBot",         r"AhrefsBot",                     "seo"),
    ("SemrushBot",        r"SemrushBot",                    "seo"),
    ("SERanking",         r"SERanking",                     "seo"),
    ("DotBot",            r"DotBot",                        "seo"),
    ("MJ12bot",           r"MJ12bot",                       "seo"),
    ("scanner",           r"l9explore|zgrab|Modat|feroxbuster|Infrawatch|masscan|Nuclei|FlowIQ", "scanner"),
    ("monitor",           r"UptimeRobot|Pingdom|StatusCake|curl|wget|python-requests|Go-http", "tooling"),
]
BROWSERISH = re.compile(r"Mozilla/5\.0", re.I)
COMPATIBLE = re.compile(r"compatible;|bot|crawler|spider|http", re.I)


def detect(sample):
    m = {}
    for key, names in CANDIDATES.items():
        m[key] = next((n for n in names if n in sample), None)
    return m


def openf(p):
    return gzip.open(p, "rt", errors="replace") if p.endswith(".gz") else open(p, errors="replace")


def parse_ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return datetime.utcfromtimestamp(v)
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S+00:00", "%d/%b/%Y:%H:%M:%S %z"):
        try:
            return datetime.strptime(v.strip("[]"), f).replace(tzinfo=None)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def classify(ua):
    for name, pat, cls in OPERATORS:
        if re.search(pat, ua):
            return name, cls
    if BROWSERISH.search(ua) and not COMPATIBLE.search(ua):
        return "browser-like", "unclassified"
    return "other", "unclassified"


def gini(counts):
    v = sorted(counts)
    n = len(v)
    if n == 0 or sum(v) == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(v, 1):
        cum += i * x
    return (2 * cum) / (n * sum(v)) - (n + 1) / n


def pct(v, q):
    if not v:
        return 0.0
    z = sorted(v)
    return round(z[min(len(z) - 1, int(q * len(z)))], 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--pages", type=int, default=18720)
    ap.add_argument("--out", default="/tmp/hp")
    a = ap.parse_args()

    files = sorted(glob.glob(a.pattern))
    if not files:
        sys.exit(f"nessun file per {a.pattern}")

    with openf(files[0]) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                F = detect(json.loads(line))
                break
        else:
            sys.exit("nessuna riga JSON trovata")

    print("campi rilevati:", {k: v for k, v in F.items() if v})
    missing = [k for k in ("ua", "uri", "status") if not F[k]]
    if missing:
        sys.exit(f"campi essenziali mancanti: {missing} — adatta CANDIDATES")

    op = defaultdict(lambda: {
        "req": 0, "urls": Counter(), "conns": set(), "connreq_max": 0,
        "status": Counter(), "bytes": 0, "ips": set(), "nets": set(),
        "proto": Counter(), "daily": Counter(), "cond": 0, "signed": 0,
        "first": None, "last": None, "cls": None, "ref": 0, "rt": [],
    })
    total = bad = 0
    site_urls = Counter()
    served = set()   # URL che almeno una volta hanno dato 200

    for path in files:
        with openf(path) as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    bad += 1
                    continue
                total += 1
                ua = str(r.get(F["ua"]) or "-")
                name, cls = classify(ua)
                d = op[name]
                d["cls"] = cls
                d["req"] += 1
                uri = str(r.get(F["uri"]) or "-").split("?")[0]
                d["urls"][uri] += 1
                site_urls[uri] += 1
                st = str(r.get(F["status"]) or "0")
                d["status"][st] += 1
                if st == "200":
                    served.add(uri)
                if F["conn"]:
                    d["conns"].add((r.get(F["ip"]), r.get(F["conn"])))
                if F["connreq"]:
                    try:
                        d["connreq_max"] = max(d["connreq_max"], int(r.get(F["connreq"]) or 0))
                    except Exception:
                        pass
                if F["bytes"]:
                    try:
                        d["bytes"] += int(r.get(F["bytes"]) or 0)
                    except Exception:
                        pass
                if F["ip"] and r.get(F["ip"]):
                    ip = str(r[F["ip"]])
                    d["ips"].add(ip)
                    d["nets"].add(".".join(ip.split(".")[:3]))
                if F["proto"]:
                    d["proto"][str(r.get(F["proto"]) or "-")] += 1
                if (F["inm"] and r.get(F["inm"]) not in (None, "-", "")) or \
                   (F["ims"] and r.get(F["ims"]) not in (None, "-", "")):
                    d["cond"] += 1
                if F["sigagent"] and r.get(F["sigagent"]) not in (None, "-", ""):
                    d["signed"] += 1
                if F["ref"] and r.get(F["ref"]) not in (None, "-", ""):
                    d["ref"] += 1
                if F["rtime"]:
                    try:
                        d["rt"].append(float(r.get(F["rtime"]) or 0))
                    except Exception:
                        pass
                t = parse_ts(r.get(F["ts"])) if F["ts"] else None
                if t:
                    d["daily"][t.strftime("%Y-%m-%d")] += 1
                    d["first"] = t if d["first"] is None else min(d["first"], t)
                    d["last"] = t if d["last"] is None else max(d["last"], t)

    known200 = served
    rows = []
    for name, d in sorted(op.items(), key=lambda kv: -kv[1]["req"]):
        uniq = len(d["urls"])
        conns = len(d["conns"]) or None
        daily = list(d["daily"].values())
        rows.append({
            "operator": name, "class": d["cls"], "requests": d["req"],
            "unique_urls": uniq,
            "req_per_url": round(d["req"] / uniq, 3) if uniq else 0,
            "connections": conns or 0,
            "req_per_conn": round(d["req"] / conns, 1) if conns else None,
            "max_req_one_conn": d["connreq_max"],
            "coverage_pct": round(100 * len([u for u in d["urls"] if u in served]) / a.pages, 2),
            "bogus_urls": len([u for u in d["urls"] if u not in served]),
            "gini": round(gini(list(d["urls"].values())), 3),
            "ips": len(d["ips"]), "slash24": len(d["nets"]),
            "http2_pct": round(100 * sum(v for k, v in d["proto"].items() if "2" in k) / d["req"], 1) if d["req"] else 0,
            "pct_200": round(100 * d["status"]["200"] / d["req"], 1),
            "pct_404": round(100 * d["status"]["404"] / d["req"], 1),
            "n_304": d["status"]["304"],
            "conditional_req": d["cond"],
            "signed_req": d["signed"],
            "referer_pct": round(100 * d["ref"] / d["req"], 1),
            "MB": round(d["bytes"] / 1048576, 1),
            "rt_p50": pct(d["rt"], 0.50), "rt_p95": pct(d["rt"], 0.95),
            "active_days": len(daily),
            "peak_day": max(daily) if daily else 0,
            "peak_over_mean": round(max(daily) / (sum(daily) / len(daily)), 1) if daily else 0,
            "first_seen": d["first"].strftime("%Y-%m-%d %H:%M") if d["first"] else "-",
            "last_seen": d["last"].strftime("%Y-%m-%d %H:%M") if d["last"] else "-",
        })

    hdr = ["operator", "class", "requests", "unique_urls", "req_per_url", "req_per_conn",
           "max_req_one_conn", "coverage_pct", "gini", "ips", "slash24", "http2_pct",
           "pct_200", "pct_404", "n_304", "conditional_req", "signed_req",
           "bogus_urls", "peak_over_mean", "active_days", "MB"]
    w = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in hdr}
    print("\n=== OPERATORI ===")
    print("  ".join(h.ljust(w[h]) for h in hdr))
    for r in rows:
        print("  ".join(str(r[h]).ljust(w[h]) for h in hdr))

    print("\n=== CODICI DI RISPOSTA PER OPERATORE ===")
    for name, d in sorted(op.items(), key=lambda kv: -kv[1]["req"]):
        parts = "  ".join(f"{k}:{100*v/d['req']:.1f}%" for k, v in d["status"].most_common(7))
        print(f"{name:20s} {parts}")

    print("\n=== SINTESI ===")
    tot304 = sum(r["n_304"] for r in rows)
    totcond = sum(r["conditional_req"] for r in rows)
    print(f"richieste totali      {total}   righe non parsate {bad}")
    print(f"URL distinti visti    {len(site_urls)} su {a.pages} pagine ({100*len(site_urls)/a.pages:.1f}%)")
    print(f"304 totali            {tot304}  ({100*tot304/total:.4f}%)")
    print(f"richieste condizionali {totcond} ({100*totcond/total:.4f}%)")
    bycls = Counter()
    for r in rows:
        bycls[r["class"]] += r["requests"]
    for c, n in bycls.most_common():
        print(f"  {c:16s} {n:8d}  {100*n/total:5.1f}%")

    print("\n=== CICLO DI VITA: richieste al giorno per classe ===")
    days = sorted({d for x in op.values() for d in x["daily"]})
    classes = [c for c, _ in bycls.most_common()]
    print("data        " + "".join(c[:11].rjust(13) for c in classes))
    for day in days:
        cells = []
        for c in classes:
            n = sum(x["daily"][day] for x in op.values() if x["cls"] == c)
            cells.append(str(n).rjust(13))
        print(day + "".join(cells))

    print("\n=== H8: decomposizione del traffico non classificato ===")
    for name in ("browser-like", "other"):
        if name not in op:
            continue
        d = op[name]
        uniq = len(d["urls"]) or 1
        conns = len(d["conns"]) or 1
        never200 = sum(v for u, v in d["urls"].items() if u not in known200)
        print(f"\n{name}: {d['req']} richieste, {uniq} URL distinti")
        print(f"  rapporto di duplicazione   {d['req']/uniq:.2f}   (>1.5 = ricrawl sistematico)")
        print(f"  richieste per connessione  {d['req']/conns:.1f}")
        print(f"  404                        {100*d['status']['404']/d['req']:.1f}%")
        print(f"  con referer                {100*d['ref']/d['req']:.1f}%   (basso = non naviga)")
        print(f"  URL mai serviti a nessuno  {never200}   (indovina invece di seguire link)")
        print("  top 8 URL:")
        for u, n in d["urls"].most_common(8):
            print(f"    {n:6d}  {u[:80]}")

    with open(a.out + ".json", "w") as f:
        json.dump({"generated": datetime.utcnow().isoformat(),
                   "total_requests": total, "site_pages": a.pages,
                   "operators": rows}, f, indent=1)
    with open(a.out + ".csv", "w") as f:
        f.write(",".join(hdr) + "\n")
        for r in rows:
            f.write(",".join(str(r[h]) for h in hdr) + "\n")
    print(f"\nscritti {a.out}.json e {a.out}.csv")


if __name__ == "__main__":
    main()
