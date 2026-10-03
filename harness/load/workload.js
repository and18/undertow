/*
 * workload.js - Workload generator with variable composition.
 *
 * ACCESS MODELS
 *
 * The cache hit ratio must NOT be a property observed by chance
 * during the sweep: it must DERIVE from the access model. With
 * uniform random sampling the hit ratio depends on the duration of the
 * test instead of the pattern (48,000 requests over 16,954 chapters
 * mean three visits per page; at a low rate almost all unique).
 * In the calibration this effect alone produced a hit ratio from
 * 21% to 76%.
 *
 *   zipf        Human profile. Rank drawn from Zipf(1), then mapped onto
 *               a chapter through a deterministic permutation.
 *               High temporal locality: few pages requested a lot.
 *
 *   traversal   Agentic profile. Depth-first descent: a book is chosen
 *               and its chapters are walked in sequence, then the next
 *               one. Almost no locality, every page seen only once. It is
 *               the model used by Zhang et al. (SoCC 2025) for AI
 *               traffic, adopted here for direct comparability.
 *
 *   mix         Mixture: each iteration is traversal with probability
 *               ALPHA, zipf otherwise. ALPHA is the agentic fraction,
 *               the sweep's only independent variable.
 *
 * THE TOTAL RATE STAYS CONSTANT as ALPHA varies. If the volume
 * grew with the agentic fraction, any knee would only
 * show that more load saturates a system.
 *
 * ENDPOINT
 *   chapter   cacheable      replication and extension of existing work
 *   search    not cacheable  case not yet studied
 *
 * USAGE
 *   -e MODEL=zipf -e RATE=800 -e DURATION=300s
 *   -e MODEL=mix -e ALPHA=0.25 -e RATE=800
 */

import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { sleep } from 'k6';

const TARGET   = __ENV.TARGET   || 'http://varnish:80';
const MODEL    = __ENV.MODEL    || 'mix';
const ALPHA    = parseFloat(__ENV.ALPHA || '0.5');
const RATE     = parseInt(__ENV.RATE || '800');
const DURATION = __ENV.DURATION || '300s';
const ENDPOINT = __ENV.ENDPOINT || 'chapter';
const SEED     = parseInt(__ENV.SEED || '42');

// Third class: agentic. An agent answering a person in real
// time is neither a human browsing nor a crawler scanning.
// Calibrated on the honeypot (findings H6, H9): real agentic operators
// cover 2.1-6.1% of the site with Gini 0.38-0.42 and request each
// URL 2.1-3.7 times. Hence: a narrow set of topics, moderately
// concentrated popularity, short sessions over contiguous chapters.
//
// BETA is the agentic share, ALPHA the exhaustive one, the rest is Zipf.
// The TOTAL rate stays constant, as for ALPHA.
const BETA          = parseFloat(__ENV.BETA || '0');
// 0.02 and not 0.05: the session expands each base into AGENT_SESSION
// contiguous chapters, so the effective coverage is three times the
// scope. At 0.05 the trial gave 11.6% against the 2.1-6.1% measured
// on real agentic operators (findings H6).
const AGENT_SCOPE   = parseFloat(__ENV.AGENT_SCOPE || '0.02');
const AGENT_SESSION = parseInt(__ENV.AGENT_SESSION || '3');
const AGENT_SKEW    = parseFloat(__ENV.AGENT_SKEW || '0.6');

// Multiplier of the permutation for the agentic class. The default
// is the same as the human class, so it reproduces the runs up to 19
// September 2026. With a different value the agentic working set
// falls in a region of the corpus uncorrelated with the human
// popularity rank, and the overlap between the two classes goes from "by
// construction" to "incidental".
//
// It must be odd and coprime with the corpus size
// (16954 = 2 x 7^2 x 173), otherwise the map is not a permutation.
// Verified separate value: 3266489917.
const AGENT_MUL     = parseInt(__ENV.AGENT_MUL || '2654435761');

if (ALPHA + BETA > 1.0000001) {
  throw new Error(`ALPHA(${ALPHA}) + BETA(${BETA}) exceeds 1`);
}

// Offset of the traversal, in iterations. Warm-up and measurement are two
// separate k6 invocations, so iterationInTest restarts from zero and the
// measurement would retrace the sequence just walked by the warm-up: every
// request would be a second visit to an object inserted exactly
// WARMUP seconds earlier, and the measured hit ratio would be the cache's
// survival curve instead of the free ride.
const TRAV_SKIP = parseInt(__ENV.TRAV_SKIP || '0');

const TERMS = (__ENV.TERMS ||
  'nurse,window,trial,servant,kiss,garden,letter,prayer,horse,silence'
).split(',');

// Separate metrics per class: the hit ratio must be attributed to the
// profile that generated it, not only aggregated.
const hitZipf  = new Counter('ut_hit_zipf');
const missZipf = new Counter('ut_miss_zipf');
const hitTrav  = new Counter('ut_hit_traversal');
const missTrav = new Counter('ut_miss_traversal');
const okZipf   = new Counter('ut_ok_zipf');
const okTrav   = new Counter('ut_ok_traversal');
const shedZipf = new Counter('ut_shed_zipf');
const shedTrav = new Counter('ut_shed_traversal');
// Deferral is not a loss if the client comes back. A batch crawler can
// afford to retry after two seconds: nobody is waiting. In the
// 2026-08-28 campaign the generator did not retry, so every 503
// appeared as lost work and the budget seemed to cost 12.6% of the
// batch throughput. Retries are counted separately from first
// attempts, otherwise the offered load would no longer be comparable
// with the reference.
const retriedTrav   = new Counter('ut_retried_traversal');
const abandonedTrav = new Counter('ut_abandoned_traversal');

// RETRY_MAX=0 reproduces the previous behaviour and is the
// reference configuration.
const RETRY_MAX = parseInt(__ENV.RETRY_MAX || '0');
const RETRY_CAP = parseFloat(__ENV.RETRY_CAP || '5');   // secondi
const latZipf  = new Trend('ut_lat_zipf', true);
const latTrav  = new Trend('ut_lat_traversal', true);
const hitAgent  = new Counter('ut_hit_agent');
const missAgent = new Counter('ut_miss_agent');
const okAgent   = new Counter('ut_ok_agent');
const shedAgent = new Counter('ut_shed_agent');
const latAgent  = new Trend('ut_lat_agent', true);
// With BLOCK_CLASSES active a rejected request returns 403, which today
// increments neither ok nor miss: without these counters the hit ratio
// of a blocked class would come out as 1.000 because only hits
// still produce a 200.
const blkZipf  = new Counter('ut_blk_zipf');
const blkAgent = new Counter('ut_blk_agent');
const blkTrav  = new Counter('ut_blk_traversal');

// Session state, per VU. In k6 module variables are local to the
// VU, so each VU carries its own session forward between iterations.
let agSession = null;

// Zipf(AGENT_SKEW) over a subset of the corpus, by inverse
// transform. For s<1, CDF(r) = (r/N)^(1-s), so r = N*u^(1/(1-s)).
// With s=0.6 the exponent is 2.5. Session base = that rank mapped
// to a chapter; the following ones are contiguous, i.e. the same book.
function agenticIndex(data) {
  if (agSession === null || agSession.left <= 0) {
    const scope = Math.max(1, Math.floor(data.total * AGENT_SCOPE));
    const r = Math.min(scope - 1,
      Math.floor(scope * Math.pow(Math.random(), 1 / (1 - AGENT_SKEW))));
    agSession = { base: permuteAgent(r, data.total), left: AGENT_SESSION, k: 0 };
  }
  agSession.left--;
  return (agSession.base + agSession.k++) % data.total;
}

// TRAV_MODE: how the exhaustive class chooses the chapter.
//
//   glob (default, TRAV_MODE absent)  like all the runs up to 28 September
//        2026: a single scenario; the traversal index is iterationInTest
//        of that scenario, which counts the iterations of ALL the classes. The
//        same chapter comes back every N total iterations, i.e. every N/RATE
//        seconds: at equal ALPHA*RATE the exhaustive path depends on RATE
//        (simulator phase 2b, docs/PREREG-simulatore-fase2b.md).
//   scen the exhaustive class is a scenario of its own at rate ALPHA*RATE: its
//        iterationInTest counts only the exhaustive requests, so the same
//        chapter comes back every N/(ALPHA*RATE) seconds whatever RATE is. Human and
//        agentic sit in the "load" scenario at rate (1-ALPHA)*RATE, with
//        agentic at probability BETA/(1-ALPHA). The exhaustive arrivals become
//        regular instead of drawn at random. docs/PREREG-lab-trav-own-20260928.md.
//
// constant-arrival-rate wants an integer rate: in scen the rates are expressed
// per 10,000 s (rounding error < 1e-5 req/s).
const TRAV_MODE = __ENV.TRAV_MODE || 'glob';
if (TRAV_MODE !== 'glob' && TRAV_MODE !== 'scen') {
  throw new Error(`TRAV_MODE=${TRAV_MODE}: allowed values glob, scen`);
}
const SCEN = TRAV_MODE === 'scen' && MODEL === 'mix' && ALPHA > 0;
if (TRAV_MODE === 'scen' && !SCEN) {
  throw new Error('TRAV_MODE=scen requires MODEL=mix and ALPHA > 0');
}
const SCEN_UNIT = 10000;
const RATE_TRAV = Math.round(ALPHA * RATE * SCEN_UNIT);
const RATE_REST = Math.round((1 - ALPHA) * RATE * SCEN_UNIT);

function arrival(rate, timeUnit, perSecond, exec) {
  const s = {
    executor: 'constant-arrival-rate',     // open loop, mandatory
    rate: rate,
    timeUnit: timeUnit,
    duration: DURATION,
    preAllocatedVUs: Math.min(Math.max(Math.ceil(perSecond * 2), 200), 4000),
    maxVUs: Math.min(Math.max(perSecond * 20, 2000), 20000),
    gracefulStop: '20s',
  };
  if (exec) s.exec = exec;
  return s;
}

export const options = {
  scenarios: SCEN ? {
    load: arrival(RATE_REST, `${SCEN_UNIT}s`, RATE_REST / SCEN_UNIT),
    trav: arrival(RATE_TRAV, `${SCEN_UNIT}s`, RATE_TRAV / SCEN_UNIT, 'trav'),
  } : {
    load: arrival(RATE, '1s', RATE),
  },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'p(99.9)', 'max'],
  // Connection reuse is an ablation factor: it is controlled at
  // campaign level (NO_REUSE=1), not per request, because
  // k6 does not allow varying it per iteration.
  noConnectionReuse: __ENV.NO_REUSE === '1',
};

// -------------------------------------------------------------------------
// Corpus structure
//
// We avoid materialising the 16,954 chapters: k6 copies the setup data
// into EVERY VU, and with hundreds of VUs that would be hundreds of MB. We keep
// only the cumulative vector per book (495 numbers) and recover
// the global index with a binary search.
// -------------------------------------------------------------------------

export function setup() {
  const res = http.get(`${TARGET}/library`, { responseType: 'text' });
  const books = JSON.parse(res.body);

  const ids = [], cum = [];
  let total = 0;
  for (const b of books) {
    ids.push(b.id);
    total += b.n_chapters;
    cum.push(total);
  }
  const g = (a, b) => { while (b) { [a, b] = [b, a % b]; } return a; };
  if (g(TRAV_MUL % total, total) !== 1) {
    throw new Error(`TRAV_MUL not coprime with ${total}: the traversal does not cover the corpus`);
  }
  return {
    ids: ids, cum: cum, total: total,
    // Deterministic offset, from the experiment seed.
    // A random offset makes the hit ratio of the low-locality class
    // non-reproducible between otherwise identical runs.
    offset: (SEED * 7919) % total,
  };
}

function locate(data, idx) {
  // global chapter index -> (book, chapter number)
  let lo = 0, hi = data.cum.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (data.cum[mid] <= idx) lo = mid + 1; else hi = mid;
  }
  const base = lo > 0 ? data.cum[lo - 1] : 0;
  return { book: data.ids[lo], n: idx - base + 1 };
}

// Deterministic multiplicative permutation: maps the popularity rank
// onto a chapter index without storing a table.
// The multiplier is prime, so the map is bijective on [0, N).
// Permutation of the agentic class only: see AGENT_MUL.
function permuteAgent(rank, N) {
  return (rank * AGENT_MUL + SEED) % N;
}

function permute(rank, N) {
  return (rank * 2654435761 + SEED) % N;
}

// Multiplier distinct from that of permute(). With the same one, the
// argument of the traversal IS the popularity rank: the scanner walks the
// corpus in decreasing popularity order, and hit_low depends on which
// window of ranks the measurement traverses — that is, on TRAV_SKIP, that is on WARMUP.
// Signature of 6 September, block B: 0.254 / 0.267 / 0.159 at warm-up 120/300/600
// with an otherwise identical configuration.
const TRAV_MUL = 2246822519;

function permuteTrav(i, N) {
  return ((i % N) * (TRAV_MUL % N) + SEED * 7919) % N;
}

// Zipf(1) by inverse transform. For alpha=1 the CDF of rank r is
// H_r/H_N, and H_r ~ ln(r), hence r ~ N^u with u uniform in [0,1].
// No table to precompute.
function zipfRank(N) {
  return Math.min(Math.floor(Math.pow(N, Math.random())), N - 1);
}

// Traversal state.
//
// Real crawlers do NOT revisit. On the honeypot GPTBot, AhrefsBot and
// Amazonbot all show req/url = 1.00 and gini = 0.00 over about 19,000
// pages: perfectly uniform access, every page once only.
//
// The previous per-VU cursor did revisit, because independent VUs
// overlap: at lambda=260 with alpha=0.5 the ratio came out at about
// 1.4, so 28% of the agentic requests were repetitions that the
// cache could serve. This INFLATES h_A and underestimates the cost.
//
// iterationInTest is a global monotonic counter across all the VUs of the
// scenario. Mapped with a multiplicative permutation (multiplier
// coprime with the corpus size, verified) it produces distinct
// indices as long as the number of iterations stays below that
// size. Beyond, it wraps around: the expected req/url ratio is
//
//     max(1, alpha * RATE * duration / total)
//
// and must be reported for every point, because it is a scale limit of the
// testbed and not a property of the model.
function traversalIndex(data) {
  return permuteTrav(data.offset + TRAV_SKIP + exec.scenario.iterationInTest, data.total);
}

// -------------------------------------------------------------------------

export default function (data) {
  // A single draw for the three-way split: two independent draws
  // would introduce correlation between the classes.
  // With TRAV_MODE=scen this scenario carries only human and agentic.
  const u = Math.random();
  const cls = MODEL === 'traversal' ? 'trav'
            : MODEL === 'agent'     ? 'agent'
            : MODEL === 'zipf'      ? 'zipf'
            : SCEN                  ? (u < BETA / (1 - ALPHA) ? 'agent' : 'zipf')
            : u < ALPHA             ? 'trav'
            : u < ALPHA + BETA      ? 'agent'
            :                         'zipf';
  request(data, cls);
}

// "trav" scenario of TRAV_MODE=scen: every iteration is an exhaustive
// request; traversalIndex reads the iterationInTest of this scenario.
export function trav(data) {
  request(data, 'trav');
}

function request(data, cls) {
  const agentic = cls === 'trav';

  let url;
  if (ENDPOINT === 'search') {
    url = `${TARGET}/search?q=${TERMS[Math.floor(Math.random() * TERMS.length)]}`;
  } else {
    const idx = cls === 'trav'  ? traversalIndex(data)
              : cls === 'agent' ? agenticIndex(data)
              :                   permute(zipfRank(data.total), data.total);
    const loc = locate(data, idx);
    url = `${TARGET}/book/${loc.book}/ch/${loc.n}`;
  }

  const UA = { trav: 'undertow-lowloc/1.0',
               agent: 'undertow-agent/1.0',
               zipf: 'undertow-highloc/1.0' };
  const headers = { 'User-Agent': UA[cls] };
  if (cls !== 'trav') headers['Accept-Language'] = 'en-GB,en;q=0.9';

  let res = http.get(url, {
    headers: headers,
    tags: { profile: cls },
  });

  // Only the batch class retries, and only on the budget's 503.
  let attempts = 0;
  while (agentic && res.status === 503 && attempts < RETRY_MAX) {
    shedTrav.add(1);
    // Retry-After in seconds; the server sends 2. The upper limit
    // prevents an anomalous value from blocking the VU.
    const ra = Math.min(parseFloat(res.headers['Retry-After'] || '2'), RETRY_CAP);
    sleep(ra);
    attempts++;
    retriedTrav.add(1);
    res = http.get(url, {
      headers: headers,
      tags: { profile: 'agent', retry: 'true' },
    });
  }

  check(res, { 'status 200': (r) => r.status === 200 });

  const hit = res.headers['X-Cache'] === 'HIT';
  if (cls === 'agent') {
    // The agentic class does not retry: there is a person waiting.
    if (res.status === 403) blkAgent.add(1);
    if (res.status === 503) shedAgent.add(1);
    else if (res.status === 200) {
      okAgent.add(1);
      if (hit) hitAgent.add(1); else missAgent.add(1);
    }
    latAgent.add(res.timings.duration);
  } else if (agentic) {
    if (res.status === 403) {
      blkTrav.add(1);
    } else if (res.status === 503) {
      // Still deferred after the last attempt: this one is truly lost.
      if (attempts >= RETRY_MAX) abandonedTrav.add(1);
      if (RETRY_MAX === 0) shedTrav.add(1);
    } else if (res.status === 200) {
      okTrav.add(1);
      if (hit) hitTrav.add(1); else missTrav.add(1);
    }
    latTrav.add(res.timings.duration);
  } else {
    if (res.status === 403) blkZipf.add(1);
    else if (res.status === 503) shedZipf.add(1);
    else if (res.status === 200) {
      okZipf.add(1);
      if (hit) hitZipf.add(1); else missZipf.add(1);
    }
    latZipf.add(res.timings.duration);
  }
}

export function handleSummary(data) {
  const out = {};
  out[`/results/${__ENV.OUTFILE || 'workload'}.json`] = JSON.stringify(data);
  return out;
}