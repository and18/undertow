"""
load_corpus.py - Loads the Gutenberg corpus into PostgreSQL.

Reuses the same texts already downloaded for the honeypot (cache/
directory), so that the same corpus feeds both the public site and
the controlled experiment.

It also builds a link graph between chapters, with a fixed seed: it is the
graph that the agentic profile traverses depth-first. Deterministic,
so the same corpus produces the same graph on any machine.

    python load_corpus.py --corpus /corpus
"""

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

import psycopg2

MIN_CHAPTER_CHARS = 1200
MAX_CHAPTERS_PER_BOOK = 60
# Twelve outgoing links per chapter, not four. It is the number of related
# items a real CMS page shows, and it determines the page generation
# cost: with four, the chapter costs ~12 ms and the thread pool could
# never saturate under the ceiling imposed by the GIL.
LINKS_PER_CHAPTER = 12

START_RE = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)
END_RE = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)
CHAPTER_RE = re.compile(
    r"^\s*(CHAPTER|Chapter|BOOK|Book|PART|Part|LETTER|Letter|ACT|Act)\s+"
    r"([IVXLCDM]+|\d+|[A-Z][a-z]+)\.?\s*$", re.M)

DDL = """
DROP TABLE IF EXISTS links, chapters, books CASCADE;

CREATE TABLE books (
    id          integer PRIMARY KEY,
    title       text NOT NULL,
    author      text NOT NULL,
    n_chapters  integer NOT NULL
);

CREATE TABLE chapters (
    book_id  integer NOT NULL REFERENCES books(id),
    n        integer NOT NULL,
    title    text NOT NULL,
    words    integer NOT NULL,
    body     text NOT NULL,
    tsv      tsvector,
    PRIMARY KEY (book_id, n)
);

CREATE TABLE links (
    src_book  integer NOT NULL,
    src_n     integer NOT NULL,
    dst_book  integer NOT NULL,
    dst_n     integer NOT NULL,
    PRIMARY KEY (src_book, src_n, dst_book, dst_n)
);

CREATE INDEX chapters_tsv_idx ON chapters USING gin(tsv);
CREATE INDEX links_src_idx ON links (src_book, src_n);
"""


def strip_boilerplate(text):
    m = START_RE.search(text)
    if m:
        text = text[m.end():]
    m = END_RE.search(text)
    if m:
        text = text[:m.start()]
    return text.strip()


def split_chapters(text):
    text = strip_boilerplate(text)
    matches = list(CHAPTER_RE.finditer(text))
    chunks = []
    if len(matches) >= 3:
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end].strip()
            if len(body) >= MIN_CHAPTER_CHARS:
                chunks.append((" ".join(m.group(0).split()), body))
    else:
        paras, buf, n = re.split(r"\n\s*\n", text), [], 1
        for p in paras:
            buf.append(p)
            if sum(len(x) for x in buf) > 9000:
                chunks.append((f"Section {n}", "\n\n".join(buf)))
                buf, n = [], n + 1
        if sum(len(x) for x in buf) >= MIN_CHAPTER_CHARS:
            chunks.append((f"Section {n}", "\n\n".join(buf)))
    return chunks[:MAX_CHAPTERS_PER_BOOK]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="/corpus")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    corpus = Path(args.corpus)
    catalog_file = corpus / "catalog.json"
    if not catalog_file.exists():
        sys.exit(f"catalog.json not found in {corpus}")

    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    conn = psycopg2.connect(
        host=os.environ.get("PGHOST", "db"),
        dbname=os.environ.get("PGDATABASE", "undertow"),
        user=os.environ.get("PGUSER", "undertow"),
        password=os.environ["PGPASSWORD"],
    )
    cur = conn.cursor()
    print("creating the schema")
    cur.execute(DDL)
    conn.commit()

    loaded = []
    for meta in catalog:
        f = corpus / f"{meta['id']}.txt"
        if not f.exists():
            continue
        chapters = split_chapters(f.read_text(encoding="utf-8", errors="replace"))
        if len(chapters) < 2:
            continue

        author = ", ".join(meta.get("authors") or ["Unknown"])
        cur.execute(
            "INSERT INTO books (id, title, author, n_chapters)"
            " VALUES (%s,%s,%s,%s)",
            (meta["id"], meta["title"][:300], author[:200], len(chapters)))

        for i, (title, body) in enumerate(chapters, 1):
            cur.execute(
                "INSERT INTO chapters (book_id, n, title, words, body, tsv)"
                " VALUES (%s,%s,%s,%s,%s, to_tsvector('english', %s))",
                (meta["id"], i, title[:200], len(body.split()), body, body))

        loaded.append((meta["id"], len(chapters)))
        print(f"  {meta['id']}: {len(chapters)} chapters")

    conn.commit()

    # Link graph, deterministic: it is the path that the agentic profile
    # traverses depth-first.
    print("building the link graph")
    rng = random.Random(args.seed)
    all_ch = [(b, n) for b, cnt in loaded for n in range(1, cnt + 1)]
    rows = []
    for src in all_ch:
        for dst in rng.sample(all_ch, LINKS_PER_CHAPTER):
            if dst != src:
                rows.append((src[0], src[1], dst[0], dst[1]))

    cur.executemany(
        "INSERT INTO links VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
    conn.commit()

    cur.execute("ANALYZE")
    conn.commit()

    print(f"\ndone: {len(loaded)} books, {len(all_ch)} chapters, "
          f"{len(rows)} links")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()