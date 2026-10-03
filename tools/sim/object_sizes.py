#!/usr/bin/env python3
"""
object_sizes.py — bytes of the response of /book/<id>/ch/<n> for each chapter, rebuilt
from the lab texts (simulator, phase 1: docs/PREREG-simulatore-fase1.md, option (a)).

WHY
  The simulator's cache has byte capacity, like Varnish's `-s malloc,128m`, and the corpus
  is heavy-tailed: the size of each object is needed, which the repository does not have.

HOW
  Run locally, it launches itself on the lab (`ssh lab python3 - --remote`, source on
  stdin). On the lab:
    - imports ~/undertow/harness/app/load_corpus.py (psycopg2 replaced by an empty module,
      no __pycache__ written) and uses its split_chapters: same chapters as the database;
    - books as main() of load_corpus: catalog.json in order, text present, at least 2
      chapters; title[:300], authors joined with ", ", chapter title [:200],
      words = len(body.split());
    - link graph as main(): random.Random(42), rng.sample(all_ch, LINKS_PER_CHAPTER)
      for each chapter in order, discarding dst == src;
    - response of chapter() in app.py: {book_id, n, title, body, book, toc, related},
      serialised like Flask 3.0's jsonify outside debug (ensure_ascii, sort_keys,
      compact separators, trailing "\\n"). related: excerpt = body[:400] (left(c.body, 400));
      the ts_headline preview is NOT reproducible without PostgreSQL: estimated with the first 15
      words of the destination chapter. PostgreSQL 16.15, wparser_def.c, lines 2433-2445:
      with MaxFragments > 0 and no match it shows the first min_words words, default
      15 (line 2624). With a match the fragment reaches MaxWords = 30 plus the <b>
      tags: not modelled here, so the estimate is a lower bound (Amendment 1 of the
      pre-registration; until then 30 words).
    - prints only `book_id,n,bytes`. No text leaves the lab; nothing is written on the lab.
  Locally: checks that books and number of chapters coincide with data/corpus/books.csv
  and writes data/derived/chapter_sizes.csv, in the order of books.csv (that of locate()).

ASSUMPTION (declared)
  The lab database was loaded from the current texts of ~/undertow/cache with the
  current version of load_corpus.py (12 links, 54f5cf7). Not verifiable without querying
  the database, which stays off.

Usage:
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

    preview = {k: " ".join(v[1].split()[:15]) for k, v in chapters.items()}
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
        sys.exit(f"reconstruction different from books.csv: books not in common {len(miss)}, "
                 f"different number of chapters {len(diff)}, chapters {len(sizes)} "
                 f"against {sum(want.values())}")
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["book_id", "n", "bytes"])
        for r in books:
            for n in range(1, int(r["n_chapters"]) + 1):
                w.writerow([r["gutenberg_id"], n, sizes[(r["gutenberg_id"], n)]])
    print(f"{len(books)} books, {len(sizes)} chapters: they match books.csv")
    print(f"written {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", metavar="ROOT", help="(internal use) run on the lab")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "derived"
                                         / "chapter_sizes.csv"))
    a = ap.parse_args()
    if a.remote:
        remote(a.remote)
    else:
        local(a.out)
