/*
 * null-test.js - Il generatore e' il collo di bottiglia?
 *
 * Nessun risultato successivo e' difendibile senza questa verifica: se
 * k6 satura prima del sistema sotto test, la curva che si misura e' la
 * saturazione del generatore, non quella del bersaglio.
 *
 * DUE FASI
 *
 *   A  ceiling   Martella un URL gia' in cache. La risposta esce da
 *                Varnish senza toccare l'applicazione, quindi il tetto
 *                che emerge e' quello di k6.
 *
 *   B  app       Colpisce /health, che non tocca il database. Misura il
 *                tetto dell'applicazione senza il DB di mezzo.
 *
 * CRITERIO
 *
 *   dropped_iterations DEVE essere 0.
 *
 *   Con executor constant-arrival-rate, k6 tenta di emettere richieste a
 *   ritmo costante indipendentemente dalle risposte (open loop). Se non
 *   ci riesce — VU esauriti, CPU satura — scarta le iterazioni e le
 *   conta. Un valore diverso da zero significa che quel punto di misura
 *   e' inservibile.
 *
 *   E' l'opposto di un generatore closed-loop, che semplicemente
 *   rallenterebbe insieme al bersaglio e riporterebbe latenze
 *   ottimistiche proprio nell'istante del collasso (coordinated
 *   omission, Tene).
 *
 * USO
 *
 *   docker compose --profile load run --rm \
 *     -e PHASE=ceiling k6 run /scripts/null-test.js
 *
 *   docker compose --profile load run --rm \
 *     -e PHASE=app k6 run /scripts/null-test.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const TARGET = __ENV.TARGET || 'http://varnish:80';
const PHASE = __ENV.PHASE || 'ceiling';

// Scala dei ritmi da provare. Ogni gradino dura 30s con 10s di pausa,
// cosi' che le code si svuotino fra un gradino e l'altro e un gradino
// non contamini il successivo.
const RATES = (__ENV.RATES || '100,500,1000,2000,5000,10000')
  .split(',').map(Number);

const STEP_DURATION = __ENV.STEP_DURATION || '30s';
const GAP = 10;

const cacheHits = new Counter('ut_cache_hits');
const cacheMiss = new Counter('ut_cache_miss');
const ttfb = new Trend('ut_ttfb', true);

// --- costruzione degli scenari -------------------------------------------
// Uno scenario per gradino, avviati in sequenza con startTime crescente.
// preAllocatedVUs va dimensionato con larghezza: se i VU finiscono, k6
// scarta iterazioni e il test fallisce per un motivo che non c'entra con
// la capacita' reale del generatore.

const scenarios = {};
let offset = 0;
for (const rate of RATES) {
  const dur = parseInt(STEP_DURATION) || 30;
  scenarios[`r${rate}`] = {
    executor: 'constant-arrival-rate',
    rate: rate,
    timeUnit: '1s',
    duration: STEP_DURATION,
    preAllocatedVUs: Math.min(Math.max(rate * 2, 100), 6000),
    maxVUs: Math.min(Math.max(rate * 4, 200), 12000),
    startTime: `${offset}s`,
    tags: { rate: String(rate) },
    gracefulStop: '5s',
  };
  offset += dur + GAP;
}

export const options = {
  scenarios: scenarios,
  // Corpi scartati: nel test nullo interessa solo il ritmo sostenibile,
  // e tenerli darebbe al generatore un lavoro che nella misura vera
  // non e' quello sotto esame.
  discardResponseBodies: true,
  thresholds: {
    // Soglia informativa: non fa fallire il run, serve a rendere
    // esplicito il criterio nel sommario.
    dropped_iterations: ['count==0'],
    http_req_failed: ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'p(99.9)', 'max'],
};

// --- URL bersaglio --------------------------------------------------------
// Fase A: un solo URL, sempre lo stesso, quindi sempre in cache dopo la
// prima richiesta. Fase B: /health, che non tocca il DB.

const URL = PHASE === 'app'
  ? `${TARGET}/health`
  : `${TARGET}/book/1342/ch/1`;

export function setup() {
  // Scalda la cache prima di iniziare, altrimenti il primo gradino
  // misurerebbe anche i miss iniziali.
  for (let i = 0; i < 5; i++) http.get(URL);
  return { url: URL, phase: PHASE };
}

export default function () {
  const res = http.get(URL, {
    headers: { 'User-Agent': 'undertow-null-test/1.0' },
  });

  check(res, { 'status 200': (r) => r.status === 200 });
  ttfb.add(res.timings.waiting);

  const xc = res.headers['X-Cache'];
  if (xc === 'HIT') cacheHits.add(1);
  else if (xc === 'MISS') cacheMiss.add(1);
}

export function handleSummary(data) {
  const dropped = (data.metrics.dropped_iterations &&
                   data.metrics.dropped_iterations.values.count) || 0;
  const reqs = (data.metrics.http_reqs &&
                data.metrics.http_reqs.values.count) || 0;
  const p99 = (data.metrics.http_req_duration &&
               data.metrics.http_req_duration.values['p(99)']) || 0;

  const verdict = dropped === 0
    ? 'PASS  il generatore ha retto tutti i gradini'
    : `FAIL  ${dropped} iterazioni scartate: il generatore e' il limite`;

  const txt = [
    '',
    '='.repeat(64),
    `TEST NULLO — fase: ${PHASE}`,
    '='.repeat(64),
    `richieste emesse    ${reqs}`,
    `iterazioni scartate ${dropped}`,
    `p99 complessivo     ${p99.toFixed(1)} ms`,
    '',
    verdict,
    '',
    'Nota: il p99 aggregato su tutti i gradini non e\' significativo di',
    'per se\'. Il dato che conta e\' dove le iterazioni scartate passano',
    'da zero a diverso da zero: quello e\' il soffitto del generatore.',
    '='.repeat(64),
    '',
  ].join('\n');

  return {
    'stdout': txt,
    '/results/null-test-summary.json': JSON.stringify(data, null, 2),
  };
}