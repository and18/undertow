/*
 * probe-origin.js - Load that really reaches the origin.
 *
 * Unlike null-test.js, which hammers a fixed URL and therefore
 * measures the cache, this samples distinct chapters from the whole corpus.
 * With a cache much smaller than the working set, most of the
 * requests miss and reach the application server.
 *
 * It serves to check the precondition of the sweeps: the load must be
 * I/O-bound, that is the threads must show up as BUSY (blocked waiting
 * for Postgres) while the application CPU stays low. If instead the
 * CPU rises and the threads stay empty, the constraint is the GIL and the pool
 * will never be able to saturate.
 *
 * ENDPOINT
 *   chapter   random chapters, cacheable but in the long tail
 *   search    full-text search, not cacheable
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

// Terms selected by tools/pick_terms.py for homogeneous cost.
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

// The corpus: 495 books, up to 60 chapters each. The ids are not
// contiguous, so we sample from the real list collected in setup.
export function setup() {
  const res = http.get(`${TARGET}/library`, { responseType: 'text' });
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