#!/usr/bin/env python3
"""
generate.py - Generatore di contenuto per theslowshelf.org

Scarica testi di pubblico dominio da Project Gutenberg, li divide in capitoli
e produce un sito statico navigabile in profondita', con indici multipli e
sitemap.xml.

L'obiettivo strutturale non e' "avere pagine" ma avere una CODA LUNGA
navigabile: molte pagine raggiungibili solo seguendo link, con densita' di
collegamenti sufficiente a invitare un crawl profondo e ripetuto.

Nota: alcuni ISP residenziali sono bloccati da gutenberg.org. Se i download
falliscono in timeout, esegui lo script da un host con connessione datacenter
(la VM dell'honeypot va benissimo). Lo script prova comunque piu' mirror.

Uso:
    pip install requests
    python honeypot/content/generate.py --books 50

Cache in ./cache, output in ./site (entrambi da tenere fuori da git).
"""

import argparse
import html
import json
import random
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Serve la libreria requests:  pip install requests")


BASE_URL = "https://theslowshelf.org"
GUTENDEX = "https://gutendex.com/books"
USER_AGENT = "theslowshelf-builder/1.0 (+https://theslowshelf.org/about.html)"

# Mirror provati in cascata dopo l'URL fornito dal catalogo.
MIRRORS = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://gutenberg.pglaf.org/{path}/{id}/{id}-0.txt",
    "https://aleph.gutenberg.org/{path}/{id}/{id}-0.txt",
    "https://gutenberg.pglaf.org/{path}/{id}/{id}.txt",
    "https://aleph.gutenberg.org/{path}/{id}/{id}.txt",
]

# (timeout di connessione, timeout di lettura) in secondi.
TIMEOUT = (10, 30)

# Capitoli piu' corti di questa soglia vengono scartati: pagine povere di
# testo non sono utili ne' ai lettori ne' alla misurazione.
MIN_CHAPTER_CHARS = 1200
MAX_CHAPTERS_PER_BOOK = 60


# --------------------------------------------------------------------------
# Acquisizione
# --------------------------------------------------------------------------

def fetch_catalog(n_books, cache_dir):
    """Interroga Gutendex per ottenere i metadati dei libri piu' scaricati."""
    cache_file = cache_dir / "catalog.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if len(cached) >= n_books:
            print("catalogo: uso la cache")
            return cached[:n_books]

    books, page = [], 1
    while len(books) < n_books:
        print(f"catalogo: pagina {page}")
        r = requests.get(
            GUTENDEX,
            params={"languages": "en", "sort": "popular", "page": page},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
        for item in payload.get("results", []):
            text_url = None
            for key, url in item.get("formats", {}).items():
                if key.startswith("text/plain") and "zip" not in url:
                    text_url = url
                    break
            if not text_url:
                continue
            books.append({
                "id": item["id"],
                "title": item["title"].strip(),
                "authors": [a["name"] for a in item.get("authors", [])] or ["Unknown"],
                "subjects": item.get("subjects", [])[:6],
                "text_url": text_url,
            })
            if len(books) >= n_books:
                break
        if not payload.get("next"):
            break
        page += 1
        time.sleep(0.5)

    cache_file.write_text(json.dumps(books, indent=2), encoding="utf-8")
    return books


def _mirror_path(book_id):
    """I mirror organizzano i file una cartella per cifra: 1342 -> 1/3/4."""
    s = str(book_id)
    return "/".join(s[:-1]) if len(s) > 1 else "0"


def fetch_text(book, cache_dir):
    """Scarica il testo grezzo provando piu' mirror. Cache su disco."""
    cache_file = cache_dir / f"{book['id']}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8", errors="replace")

    print(f"  scarico {book['id']}: {book['title'][:50]}")
    urls = [book["text_url"]] + [
        m.format(id=book["id"], path=_mirror_path(book["id"])) for m in MIRRORS
    ]

    last_err = "nessun tentativo"
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            if r.status_code == 200 and len(r.content) > 5000:
                text = r.content.decode("utf-8", errors="replace")
                cache_file.write_text(text, encoding="utf-8")
                time.sleep(1.0)  # cortesia verso i server di Gutenberg
                return text
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = type(e).__name__

    raise RuntimeError(f"tutti i mirror falliti ({last_err})")


# --------------------------------------------------------------------------
# Segmentazione
# --------------------------------------------------------------------------

START_RE = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)
END_RE = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", re.I)

CHAPTER_RE = re.compile(
    r"^\s*(CHAPTER|Chapter|BOOK|Book|PART|Part|LETTER|Letter|ACT|Act)\s+"
    r"([IVXLCDM]+|\d+|[A-Z][a-z]+)\.?\s*$",
    re.M,
)


def strip_boilerplate(text):
    """Rimuove le intestazioni legali di Project Gutenberg."""
    m = START_RE.search(text)
    if m:
        text = text[m.end():]
    m = END_RE.search(text)
    if m:
        text = text[:m.start()]
    return text.strip()


def split_chapters(text):
    """Divide il testo in capitoli. Senza marcatori, spezza a blocchi."""
    text = strip_boilerplate(text)
    matches = list(CHAPTER_RE.finditer(text))

    chunks = []
    if len(matches) >= 3:
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            title = " ".join(m.group(0).split())
            body = text[m.end():end].strip()
            if len(body) >= MIN_CHAPTER_CHARS:
                chunks.append((title, body))
    else:
        paragraphs = re.split(r"\n\s*\n", text)
        buf, n = [], 1
        for p in paragraphs:
            buf.append(p)
            if sum(len(x) for x in buf) > 9000:
                chunks.append((f"Section {n}", "\n\n".join(buf)))
                buf, n = [], n + 1
        if sum(len(x) for x in buf) >= MIN_CHAPTER_CHARS:
            chunks.append((f"Section {n}", "\n\n".join(buf)))

    return chunks[:MAX_CHAPTERS_PER_BOOK]


def slugify(s, maxlen=60):
    s = re.sub(r"[^\w\s-]", "", s.lower())
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:maxlen] or "untitled"


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} &middot; The Slow Shelf</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<style>
body{{max-width:44rem;margin:0 auto;padding:2rem 1.25rem;
font:16px/1.7 Georgia,'Times New Roman',serif;color:#222;background:#fdfdfb}}
a{{color:#33507a}}
header{{border-bottom:1px solid #ddd;padding-bottom:.75rem;margin-bottom:2rem;
font-family:system-ui,sans-serif;font-size:.85rem}}
footer{{border-top:1px solid #ddd;margin-top:3rem;padding-top:1rem;
font-family:system-ui,sans-serif;font-size:.8rem;color:#666}}
h1{{font-size:1.6rem;line-height:1.3}}
h2{{font-size:1.15rem;margin-top:2rem}}
nav.pager{{display:flex;justify-content:space-between;margin:2.5rem 0;
font-family:system-ui,sans-serif;font-size:.9rem;gap:1rem}}
ul{{padding-left:1.25rem}} li{{margin:.35rem 0}}
p{{margin:1.1rem 0}}
.meta{{color:#666;font-size:.9rem;font-family:system-ui,sans-serif}}
</style>
</head>
<body>
<header><a href="/">The Slow Shelf</a> &middot;
<a href="/library.html">Library</a> &middot;
<a href="/authors.html">Authors</a> &middot;
<a href="/subjects.html">Subjects</a> &middot;
<a href="/about.html">About</a></header>
{body}
<footer>Public domain texts from
<a href="https://www.gutenberg.org">Project Gutenberg</a>.
This site is part of a public research project on automated web traffic &mdash;
see <a href="/about.html">about</a>.</footer>
</body>
</html>
"""


def write(out, relpath, title, desc, body):
    path = out / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        PAGE.format(
            title=html.escape(title),
            desc=html.escape(desc[:180]),
            canonical=f"{BASE_URL}/{relpath}",
            body=body,
        ),
        encoding="utf-8",
    )
    return relpath


def paragraphs_html(body):
    parts = re.split(r"\n\s*\n", body)
    return "\n".join(
        f"<p>{html.escape(' '.join(p.split()))}</p>"
        for p in parts if p.strip()
    )


# --------------------------------------------------------------------------
# Costruzione del sito
# --------------------------------------------------------------------------

def build(books, out, cache_dir, seed=42):
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    pages = []
    built = []
    failed = 0

    print("\nfase 1: download e segmentazione")
    for book in books:
        try:
            raw = fetch_text(book, cache_dir)
        except Exception as e:
            print(f"  ! salto {book['id']}: {e}")
            failed += 1
            continue

        chapters = split_chapters(raw)
        if len(chapters) < 2:
            print(f"  ! salto {book['id']}: segmentazione insufficiente")
            failed += 1
            continue

        bslug = f"{book['id']}-{slugify(book['title'])}"
        book["slug"] = bslug
        book["chapters"] = [
            {
                "n": i,
                "title": ctitle,
                "path": f"book/{bslug}/chapter-{i:03d}.html",
                "words": len(cbody.split()),
            }
            for i, (ctitle, cbody) in enumerate(chapters, 1)
        ]
        built.append(book)

    print(f"\nlibri utilizzabili: {len(built)}  (scartati: {failed})")
    if not built:
        raise SystemExit(
            "Nessun libro scaricato. Se sei su rete residenziale, gutenberg.org "
            "potrebbe bloccare il tuo ISP: esegui lo script dalla VM."
        )

    print("\nfase 2: generazione pagine")
    for book in built:
        raw = fetch_text(book, cache_dir)  # gia' in cache
        chapters = split_chapters(raw)
        author = ", ".join(book["authors"])

        for (ctitle, cbody), meta in zip(chapters, book["chapters"]):
            n = meta["n"]
            prev_ = book["chapters"][n - 2] if n > 1 else None
            next_ = book["chapters"][n] if n < len(book["chapters"]) else None

            pager = '<nav class="pager">'
            pager += (f'<a href="/{prev_["path"]}">&larr; {html.escape(prev_["title"])}</a>'
                      if prev_ else '<span></span>')
            pager += f'<a href="/book/{book["slug"]}/">Contents</a>'
            pager += (f'<a href="/{next_["path"]}">{html.escape(next_["title"])} &rarr;</a>'
                      if next_ else '<span></span>')
            pager += '</nav>'

            # Link laterali verso altri libri: aumentano la densita' del grafo
            # e creano percorsi che un crawler segue ma un umano quasi mai.
            others = [o for o in rng.sample(built, min(5, len(built)))
                      if o["slug"] != book["slug"]][:4]
            related = "".join(
                f'<li><a href="/book/{o["slug"]}/">{html.escape(o["title"])}</a> '
                f'<span class="meta">{html.escape(", ".join(o["authors"]))}</span></li>'
                for o in others
            )

            body = (
                f'<p class="meta"><a href="/book/{book["slug"]}/">'
                f'{html.escape(book["title"])}</a> &middot; {html.escape(author)}</p>'
                f'<h1>{html.escape(ctitle)}</h1>'
                f'{pager}'
                f'{paragraphs_html(cbody)}'
                f'{pager}'
                f'<h2>Elsewhere on the shelf</h2><ul>{related}</ul>'
            )
            pages.append(write(
                out, meta["path"],
                f"{ctitle} - {book['title']}",
                f"{ctitle} from {book['title']} by {author}.",
                body,
            ))

    # --- indice per libro ----------------------------------------------
    for book in built:
        author = ", ".join(book["authors"])
        toc = "".join(
            f'<li><a href="/{c["path"]}">{html.escape(c["title"])}</a> '
            f'<span class="meta">{c["words"]:,} words</span></li>'
            for c in book["chapters"]
        )
        subj = "".join(
            f'<li><a href="/subject/{slugify(s)}.html">{html.escape(s)}</a></li>'
            for s in book["subjects"]
        )
        body = (
            f'<h1>{html.escape(book["title"])}</h1>'
            f'<p class="meta">{html.escape(author)} &middot; '
            f'{len(book["chapters"])} chapters</p>'
            f'<h2>Contents</h2><ul>{toc}</ul>'
            + (f'<h2>Subjects</h2><ul>{subj}</ul>' if subj else '')
        )
        pages.append(write(
            out, f"book/{book['slug']}/index.html",
            book["title"],
            f"{book['title']} by {author}, in {len(book['chapters'])} chapters.",
            body,
        ))

    # --- indice per autore ---------------------------------------------
    by_author = {}
    for book in built:
        for a in book["authors"]:
            by_author.setdefault(a, []).append(book)

    for author, blist in by_author.items():
        items = "".join(
            f'<li><a href="/book/{b["slug"]}/">{html.escape(b["title"])}</a></li>'
            for b in blist
        )
        pages.append(write(
            out, f"author/{slugify(author)}.html",
            author,
            f"Works by {author} available on The Slow Shelf.",
            f'<h1>{html.escape(author)}</h1><ul>{items}</ul>',
        ))

    # --- indice per soggetto -------------------------------------------
    by_subject = {}
    for book in built:
        for s in book["subjects"]:
            by_subject.setdefault(s, []).append(book)

    for subject, blist in by_subject.items():
        items = "".join(
            f'<li><a href="/book/{b["slug"]}/">{html.escape(b["title"])}</a> '
            f'<span class="meta">{html.escape(", ".join(b["authors"]))}</span></li>'
            for b in blist
        )
        pages.append(write(
            out, f"subject/{slugify(subject)}.html",
            subject,
            f"Texts on {subject}.",
            f'<h1>{html.escape(subject)}</h1><ul>{items}</ul>',
        ))

    # --- indici principali ---------------------------------------------
    lib = "".join(
        f'<li><a href="/book/{b["slug"]}/">{html.escape(b["title"])}</a> '
        f'<span class="meta">{html.escape(", ".join(b["authors"]))} &middot; '
        f'{len(b["chapters"])} chapters</span></li>'
        for b in sorted(built, key=lambda x: x["title"])
    )
    pages.append(write(out, "library.html", "Library",
                       "All texts on The Slow Shelf.",
                       f'<h1>Library</h1><ul>{lib}</ul>'))

    auth = "".join(
        f'<li><a href="/author/{slugify(a)}.html">{html.escape(a)}</a> '
        f'<span class="meta">{len(b)} works</span></li>'
        for a, b in sorted(by_author.items())
    )
    pages.append(write(out, "authors.html", "Authors",
                       "Authors represented on The Slow Shelf.",
                       f'<h1>Authors</h1><ul>{auth}</ul>'))

    subj = "".join(
        f'<li><a href="/subject/{slugify(s)}.html">{html.escape(s)}</a> '
        f'<span class="meta">{len(b)} texts</span></li>'
        for s, b in sorted(by_subject.items())
    )
    pages.append(write(out, "subjects.html", "Subjects",
                       "Browse by subject.",
                       f'<h1>Subjects</h1><ul>{subj}</ul>'))

    total_ch = sum(len(b["chapters"]) for b in built)
    home = (
        '<h1>The Slow Shelf</h1>'
        '<p>A quiet archive of public domain literature, presented as plain '
        'readable pages. No trackers, no scripts, no advertising.</p>'
        f'<p class="meta">{len(built)} works &middot; {total_ch} chapters &middot; '
        f'{len(by_author)} authors</p>'
        '<h2>Browse</h2><ul>'
        '<li><a href="/library.html">All works</a></li>'
        '<li><a href="/authors.html">By author</a></li>'
        '<li><a href="/subjects.html">By subject</a></li>'
        '</ul>'
        '<h2>About this site</h2>'
        '<p>The Slow Shelf is also a measurement site for public research on '
        'automated and agentic web traffic. See <a href="/about.html">about</a> '
        'for details on what is recorded and why.</p>'
    )
    pages.append(write(out, "index.html", "The Slow Shelf",
                       "A quiet archive of public domain literature.", home))

    # --- sitemap --------------------------------------------------------
    today = time.strftime("%Y-%m-%d")
    entries = "\n".join(
        f"  <url><loc>{BASE_URL}/{p}</loc><lastmod>{today}</lastmod></url>"
        for p in sorted(set(pages))
    )
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n",
        encoding="utf-8",
    )

    return len(pages), len(built)


def main():
    repo_root = Path(__file__).resolve().parents[2]

    ap = argparse.ArgumentParser()
    ap.add_argument("--books", type=int, default=50)
    ap.add_argument("--out", default=str(repo_root / "site"))
    ap.add_argument("--cache", default=str(repo_root / "cache"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out = Path(args.out).resolve()
    cache = Path(args.cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)

    print(f"output: {out}\ncache:  {cache}\n")

    books = fetch_catalog(args.books, cache)
    print(f"catalogo: {len(books)} libri")
    n_pages, n_books = build(books, out, cache, args.seed)

    print(f"\nfatto: {n_pages} pagine da {n_books} libri in {out}")


if __name__ == "__main__":
    main()