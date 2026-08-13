/*
 * null-test.js - Il generatore e' il collo di bottiglia?
 *
 * Un solo ritmo per invocazione, pilotato da RATE. Lo sweep sui ritmi lo
 * fa lo script chiamante (null-test.sh).
 *
 * Perche' un ritmo per volta e non piu' scenari in cascata: con scenari
 * concatenati, dropped_iterations e' un contatore globale e non si puo'
 * attribuire al gradino che l'ha causato. Separando le invocazioni, ogni
 * numero appartiene a un solo ritmo, e fra un gradino e l'altro le code
 * si svuotano davvero.
 *
 * FASI
 *   ceiling   URL sempre in cache: la risposta esce da Varnish senza
 *             toccare l'applicazione. Il tetto che emerge e' del sistema
 *             generatore+cache.
 *   app       /health, nessun accesso al DB. Tetto dell'applicazione.
 *
 * CRITERIO
 *   dropped_iterations DEVE essere 0. Con executor constant-arrival-rate
 *   (open loop) k6 emette a ritmo costante indipendentemente dalle
 *   risposte; se non ci riesce, scarta e conta. Un valore diverso da zero
 *   rende quel punto di misura inservibile.
 */

import http from 'k6/http';
import { check } from 'k6';

const TARGET = __ENV.TARGET || 'http://varnish:80';
const PHASE = __ENV.PHASE || 'ceiling';
const RATE = parseInt(__ENV.RATE || '1000');
const DURATION = __ENV.DURATION || '30s';

const URL = PHASE === 'app'
  ? `${TARGET}/health`
  : `${TARGET}/book/1342/ch/1`;

export const options = {
  scenarios: {
    step: {
      executor: 'constant-arrival-rate',
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      // Larghi di proposito: se i VU finiscono, k6 scarta iterazioni per
      // un motivo che non c'entra con la capacita' reale del generatore.
      preAllocatedVUs: Math.min(Math.max(Math.ceil(RATE * 0.05), 20), 500),
      maxVUs: Math.min(Math.max(Math.ceil(RATE * 0.2), 50), 2000),
      gracefulStop: '10s',
    },
  },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'p(99.9)', 'max'],
  // Nessuna soglia qui: il verdetto lo emette lo script, che vede tutti i
  // gradini. Le soglie farebbero solo uscire k6 con codice non zero.
};

export function setup() {
  for (let i = 0; i < 5; i++) http.get(URL);
}

export default function () {
  const res = http.get(URL, {
    headers: { 'User-Agent': 'undertow-null-test/1.0' },
  });
  check(res, { 'status 200': (r) => r.status === 200 });
}

export function handleSummary(data) {
  const out = {};
  out[`/results/${__ENV.OUTFILE || 'null-summary'}.json`] =
    JSON.stringify(data);
  return out;
}