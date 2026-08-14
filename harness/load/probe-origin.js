/*
 * probe-origin.js - Carico che raggiunge davvero l'origine.
 *
 * A differenza di null-test.js, che martella un URL fisso e quindi
 * misura la cache, questo campiona capitoli distinti da tutto il corpus.
 * Con una cache molto piu' piccola del working set, la maggior parte
 * delle richieste va in miss e arriva all'application server.
 *
 * Serve a verificare la precondizione degli sweep: il carico deve essere
 * I/O-bound, cioe' i thread devono risultare OCCUPATI (bloccati in attesa
 * di Postgres) mentre la CPU dell'applicazione resta bassa. Se invece la
 * CPU sale e i thread restano vuoti, il vincolo e' il GIL e il pool non
 * potra' mai saturarsi.
 *
 * ENDPOINT
 *   chapter   capitoli casuali, cacheable ma nella coda lunga
 *   search    ricerca full-text, non cacheable
 *
 *   docker compose --profile load run --rm -T \
 *     -e ENDPOINT=chapter -e RATE=200 -e DURATION=60s k6 run /scripts/probe-origin.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const TARGET = __ENV.TARGET || 'http://varnish:80';
const ENDPOINT = __ENV.ENDPOINT || 'chapter';
const RATE = parseInt(__ENV.RATE || '200');
const DURATION = __ENV.DURATION || '60s';

// Termini selezionati da tools/pick_terms.py per costo omogeneo.
const TERMS = (__ENV.TERMS ||
  'nurse,window,trial,servant,kiss,garden,letter,prayer,horse,silence'
).split(',');

const hits = new Counter('ut_cache_hit');
const miss = new Counter('ut_cache_miss');

export const options = {
  scenarios: {
    probe: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.min(Math.max(Math.ceil(RATE * 0.3), 50), 1000),
      maxVUs: Math.min(Math.max(RATE * 2, 200), 4000),
      gracefulStop: '15s',
    },
  },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
};

// Il corpus: 495 libri, fino a 60 capitoli ciascuno. Gli id non sono
// contigui, quindi si campiona dalla lista reale raccolta in setup.
export function setup() {
  const res = http.get(`${TARGET}/library`);
  const books = JSON.parse(res.body).map(b => ({ id: b.id, n: b.n_chapters }));
  return { books: books };
}

export default function (data) {
  let url;
  if (ENDPOINT === 'search') {
    url = `${TARGET}/search?q=${TERMS[Math.floor(Math.random() * TERMS.length)]}`;
  } else {
    const b = data.books[Math.floor(Math.random() * data.books.length)];
    const n = 1 + Math.floor(Math.random() * b.n);
    url = `${TARGET}/book/${b.id}/ch/${n}`;
  }

  const res = http.get(url, { headers: { 'User-Agent': 'undertow-probe/1.0' } });
  check(res, { 'status 200': (r) => r.status === 200 });
  if (res.headers['X-Cache'] === 'HIT') hits.add(1); else miss.add(1);
}

export function handleSummary(data) {
  const out = {};
  out[`/results/${__ENV.OUTFILE || 'probe'}.json`] = JSON.stringify(data);
  return out;
}