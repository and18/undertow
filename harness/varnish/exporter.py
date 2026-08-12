"""
exporter.py - Espone le statistiche di Varnish in formato Prometheus.

Sostituisce un exporter di terze parti: varnishstat -j fornisce gia'
tutti i contatori, e la conversione e' banale. Meno dipendenze esterne
significa meno cose che possono rompersi o sparire fra due anni, il che
conta in un lavoro che deve restare riproducibile.
"""

import json
import re
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

VARNISH_N = "/var/lib/varnish/ut"
SAFE = re.compile(r"[^a-zA-Z0-9_]")


def collect():
    out = subprocess.run(
        ["varnishstat", "-n", VARNISH_N, "-j"],
        capture_output=True, text=True, timeout=5,
    )
    if out.returncode != 0:
        return f"# varnishstat failed: {out.stderr.strip()[:200]}\n"

    data = json.loads(out.stdout)
    counters = data.get("counters", data)

    lines = []
    for name, c in counters.items():
        if not isinstance(c, dict) or "value" not in c:
            continue
        metric = "varnish_" + SAFE.sub("_", name).lower()
        kind = "counter" if c.get("flag") == "c" else "gauge"
        desc = (c.get("description", "") or "").replace("\\", " ")[:120]
        lines.append(f"# HELP {metric} {desc}")
        lines.append(f"# TYPE {metric} {kind}")
        lines.append(f"{metric} {c['value']}")
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = collect().encode()
        except Exception as e:
            body = f"# error: {e}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9131), Handler).serve_forever()