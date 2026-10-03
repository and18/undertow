/*
 * null-test.js - Is the generator the bottleneck?
 *
 * A single rate per invocation, driven by RATE. The sweep over the rates is
 * done by the calling script (null-test.sh).
 *
 * Why one rate at a time and not several scenarios in cascade: with
 * concatenated scenarios, dropped_iterations is a global counter and cannot
 * be attributed to the step that caused it. By separating the invocations,
 * every number belongs to a single rate, and between one step and the next
 * the queues really drain.
 *
 * PHASES
 *   ceiling   URL always in cache: the response comes out of Varnish without
 *             touching the application. The ceiling that emerges is that of
 *             the generator+cache system.
 *   app       /health, no DB access. Ceiling of the application.
 *
 * CRITERION
 *   dropped_iterations MUST be 0. With a constant-arrival-rate executor
 *   (open loop) k6 emits at a constant rate regardless of the responses;
 *   if it cannot keep up, it drops and counts. A non-zero value
 *   makes that measurement point useless.
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
      // Wide on purpose: if the VUs run out, k6 drops iterations for a
      // reason that has nothing to do with the real capacity of the generator.
      preAllocatedVUs: Math.min(Math.max(Math.ceil(RATE * 0.05), 20), 500),
      maxVUs: Math.min(Math.max(Math.ceil(RATE * 0.2), 50), 2000),
      gracefulStop: '10s',
    },
  },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'p(99.9)', 'max'],
  // No thresholds here: the verdict is issued by the script, which sees all
  // the steps. Thresholds would only make k6 exit with a non-zero code.
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