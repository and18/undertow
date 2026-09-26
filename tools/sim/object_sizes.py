#!/usr/bin/env python3
"""
object_sizes.py — byte della risposta di /book/<id>/ch/<n> per ogni capitolo, ricostruiti
dai testi del lab (simulatore, fase 1: docs/PREREG-simulatore-fase1.md, opzione (a)).

PERCHE'
  La cache del simulatore ha capienza in byte, come `-s malloc,128m` di Varnish, e il corpus
  e' a coda pesante: serve la dimensione di ogni oggetto, che il repository non ha.

COME
  Eseguito in locale, lancia se stesso sul lab (`ssh lab python3 - --remote`, sorgente su
  stdin). Sul lab:
    - importa ~/undertow/harness/app/load_corpus.py (psycopg2 sostituito da un modulo vuoto,
      nessun __pycache__ scritto) e ne usa split_chapters: stessi capitoli del database;
    - libri come main() di load_corpus: catalog.json in ordine, testo presente, almeno 2
      capitoli; titolo[:300], autori uniti con ", ", titolo di capitolo [:200],
      words = len(body.split());
    - grafo dei link come main(): random.Random(42), rng.sample(all_ch, LINKS_PER_CHAPTER)
      per ogni capitolo in ordine, scartando dst == src;
    - risposta di chapter() in app.py: {book_id, n, title, body, book, toc, related},
      serializzata come jsonify di Flask 3.0 fuori da debug (ensure_ascii, sort_keys,
      separatori compatti, "\\n" finale). related: excerpt = body[:400] (left(c.body, 400));
      preview di ts_headline NON riproducibile senza PostgreSQL: stimata con le prime 30
      parole del capitolo di destinazione (MaxWords=30).
    - stampa solo `book_id,n,bytes`. Nessun testo esce dal lab; nulla viene scritto sul lab.
  In locale: controlla che libri e numero di capitoli coincidano con data/corpus/books.csv
  e scrive data/derived/chapter_sizes.csv, nell'ordine di books.csv (quello di locate()).

IPOTESI (dichiarata)
  Il database del lab e' stato caricato dai testi attuali di ~/undertow/cache con la
  versione attuale di load_corpus.py (12 link, 54f5cf7). Non verificabile senza interrogare
  il database, che resta spento.

Uso:
    python3 tools/sim/object_sizes.py
"""
import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path


def remote(root):
    import importlib.util
    import random
    import types

    sys.dont_write_bytecode = True
    sys.modules["psycopg2"] = types.ModuleType("psycopg2")
    spec = importlib.util.spec_from_file_location(
        "load_corpus", f"{root}/harness/app/load_corpus.py")
    lc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lc)

    corpus = Path(root) / "cache"
    catalog = json.loads((corpus / "catalog.json").read_text(encoding="utf-8"))
    books, chapters = [], {}
    for meta in catalog:
        f = corpus / f"{meta['id']}.txt"
        if not f.exists():
            continue
        ch = lc.split_chapters(f.read_text(encoding="utf-8", errors="replace"))
        if len(ch) < 2:
            continue
        b = {"id": meta["id"], "title": meta["title"][:300],
             "author": ", ".join(meta.get("authors") or ["Unknown"])[:200],
             "n_chapters": len(ch)}
        books.append(b)
        for i, (title, body) in enumerate(ch, 1):
            chapters[(b["id"], i)] = (title[:200], body, len(body.split()))

    rng = random.Random(42)
    all_ch = [(b["id"], n) for b in books for n in range(1, b["n_chapters"] + 1)]
    links = {}
    for src in all_ch:
        links[src] = [d for d in rng.sample(all_ch, lc.LINKS_PER_CHAPTER) if d != src]

    preview = {k: " ".join(v[1].split()[:30]) for k, v in chapters.items()}
    book_by_id = {b["id"]: b for b in books}
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(["book_id", "n", "bytes"])
    for b in books:
        toc = [{"n": n, "title": chapters[(b["id"], n)][0], "words": chapters[(b["id"], n)][2]}
               for n in range(1, b["n_chapters"] + 1)]
        for n in range(1, b["n_chapters"] + 1):
            title, body, _ = chapters[(b["id"], n)]
            related = []
            for db, dn in links[(b["id"], n)]:
                dt, dbody, _ = chapters[(db, dn)]
                related.append({"book_id": db, "n": dn, "title": dt,
                                "book_title": book_by_id[db]["title"],
                                "excerpt": dbody[:400], "preview": preview[(db, dn)]})
            row = {"book_id": b["id"], "n": n, "title": title, "body": body,
                   "book": b, "toc": toc, "related": related}
            s = json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
            out.writerow([b["id"], n, len(s.encode("ascii"))])


def local(out):
    root = Path(__file__).resolve().parents[2]
    src = Path(__file__).read_bytes()
    res = subprocess.run(["ssh", "lab", "python3 - --remote ~/undertow"],
                         input=src, capture_output=True, check=True)
    rows = list(csv.DictReader(io.StringIO(res.stdout.decode())))
    sizes = {(r["book_id"], int(r["n"])): int(r["bytes"]) for r in rows}
    with open(root / "data" / "corpus" / "books.csv", newline="") as f:
        books = list(csv.DictReader(f))
    lab_n = {}
    for (b, n) in sizes:
        lab_n[b] = max(lab_n.get(b, 0), n)
    want = {r["gutenberg_id"]: int(r["n_chapters"]) for r in books}
    if lab_n != want or len(sizes) != sum(want.values()):
        miss = set(want) ^ set(lab_n)
        diff = [b for b in set(want) & set(lab_n) if want[b] != lab_n[b]]
        sys.exit(f"ricostruzione diversa da books.csv: libri non comuni {len(miss)}, "
                 f"numero di capitoli diverso {len(diff)}, capitoli {len(sizes)} "
                 f"contro {sum(want.values())}")
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["book_id", "n", "bytes"])
        for r in books:
            for n in range(1, int(r["n_chapters"]) + 1):
                w.writerow([r["gutenberg_id"], n, sizes[(r["gutenberg_id"], n)]])
    print(f"{len(books)} libri, {len(sizes)} capitoli: coincidono con books.csv")
    print(f"scritto {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", metavar="ROOT", help="(uso interno) esecuzione sul lab")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "derived"
                                         / "chapter_sizes.csv"))
    a = ap.parse_args()
    if a.remote:
        remote(a.remote)
    else:
        local(a.out)
