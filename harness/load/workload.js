/*
 * workload.js - Generatore di workload a composizione variabile.
 *
 * MODELLI DI ACCESSO
 *
 * Il cache hit ratio NON deve essere una proprieta' osservata per caso
 * durante lo sweep: deve DISCENDERE dal modello di accesso. Con
 * campionamento uniforme casuale l'hit ratio dipende dalla durata del
 * test invece che dal pattern (48.000 richieste su 16.954 capitoli
 * significano tre visite per pagina; a ritmo basso quasi tutte uniche).
 * Nella calibrazione questo effetto ha prodotto da solo un hit ratio da
 * 21% a 76%.
 *
 *   zipf        Profilo umano. Rango estratto da Zipf(1), poi mappato su
 *               un capitolo tramite permutazione deterministica.
 *               Alta localita' temporale: poche pagine molto richieste.
 *
 *   traversal   Profilo agentico. Discesa in profondita': si sceglie un
 *               libro e se ne percorrono i capitoli in sequenza, poi si
 *               passa al successivo. Localita' quasi nulla, ogni pagina
 *               vista una volta sola. E' il modello usato da Zhang et
 *               al. (SoCC 2025) per il traffico AI, adottato qui per
 *               comparabilita' diretta.
 *
 *   mix         Miscela: ogni iterazione e' traversal con probabilita'
 *               ALPHA, zipf altrimenti. ALPHA e' la frazione agentica,
 *               unica variabile indipendente dello sweep.
 *
 * IL RITMO TOTALE RESTA COSTANTE al variare di ALPHA. Se il volume
 * crescesse con la frazione agentica, un eventuale ginocchio
 * dimostrerebbe soltanto che piu' carico satura un sistema.
 *
 * ENDPOINT
 *   chapter   cacheable      replica ed estensione del lavoro esistente
 *   search    non cacheable  caso non ancora studiato
 *
 * USO
 *   -e MODEL=zipf -e RATE=800 -e DURATION=300s
 *   -e MODEL=mix -e ALPHA=0.25 -e RATE=800
 */

import http from 'k6/http';
import exec from 'k6/execution';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const TARGET   = __ENV.TARGET   || 'http://varnish:80';
const MODEL    = __ENV.MODEL    || 'mix';
const ALPHA    = parseFloat(__ENV.ALPHA || '0.5');
const RATE     = parseInt(__ENV.RATE || '800');
const DURATION = __ENV.DURATION || '300s';
const ENDPOINT = __ENV.ENDPOINT || 'chapter';
const SEED     = parseInt(__ENV.SEED || '42');

const TERMS = (__ENV.TERMS ||
  'nurse,window,trial,servant,kiss,garden,letter,prayer,horse,silence'
).split(',');

// Metriche separate per classe: l'hit ratio va attribuito al profilo che
// lo ha generato, non solo aggregato.
const hitZipf  = new Counter('ut_hit_zipf');
const missZipf = new Counter('ut_miss_zipf');
const hitTrav  = new Counter('ut_hit_traversal');
const missTrav = new Counter('ut_miss_traversal');
const latZipf  = new Trend('ut_lat_zipf', true);
const latTrav  = new Trend('ut_lat_traversal', true);

export const options = {
  scenarios: {
    load: {
      executor: 'constant-arrival-rate',   // open loop, obbligatorio
      rate: RATE,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.min(Math.max(Math.ceil(RATE * 0.2), 50), 1500),
      maxVUs: Math.min(Math.max(RATE * 2, 200), 6000),
      gracefulStop: '20s',
    },
  },
  discardResponseBodies: true,
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'p(99.9)', 'max'],
  // Il riuso delle connessioni e' un fattore di ablazione: si controlla a
  // livello di campagna (NO_REUSE=1), non per singola richiesta, perche'
  // k6 non permette di variarlo per iterazione.
  noConnectionReuse: __ENV.NO_REUSE === '1',
};

// -------------------------------------------------------------------------
// Struttura del corpus
//
// Si evita di materializzare i 16.954 capitoli: k6 copia i dati di setup
// in OGNI VU, e con centinaia di VU sarebbero centinaia di MB. Si tiene
// solo il vettore cumulativo per libro (495 numeri) e si risale
// all'indice globale con una ricerca binaria.
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
  return {
    ids: ids, cum: cum, total: total,
    // Offset casuale per run, condiviso da tutti i VU. Senza, warm-up e
    // misura percorrono la stessa permutazione a partire da zero e la
    // misura trova in cache esattamente cio' che il warm-up ha caricato.
    // Con l'offset, la finestra di misura visita una porzione diversa
    // dello spazio mentre la cache contiene la precedente — che e' anche
    // il comportamento di un crawler che prosegue la scansione.
    offset: Math.floor(Math.random() * 1e9),
  };
}

function locate(data, idx) {
  // indice globale di capitolo -> (libro, numero di capitolo)
  let lo = 0, hi = data.cum.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (data.cum[mid] <= idx) lo = mid + 1; else hi = mid;
  }
  const base = lo > 0 ? data.cum[lo - 1] : 0;
  return { book: data.ids[lo], n: idx - base + 1 };
}

// Permutazione moltiplicativa deterministica: mappa il rango di
// popolarita' su un indice di capitolo senza memorizzare una tabella.
// Il moltiplicatore e' primo, quindi la mappa e' biiettiva su [0, N).
function permute(rank, N) {
  return (rank * 2654435761 + SEED) % N;
}

// Zipf(1) per trasformata inversa. Per alpha=1 la CDF del rango r vale
// H_r/H_N, e H_r ~ ln(r), da cui r ~ N^u con u uniforme in [0,1].
// Nessuna tabella da precalcolare.
function zipfRank(N) {
  return Math.min(Math.floor(Math.pow(N, Math.random())), N - 1);
}

// Stato di attraversamento.
//
// I crawler reali NON rivisitano. Sull'honeypot GPTBot, AhrefsBot e
// Amazonbot mostrano tutti req/url = 1,00 e gini = 0,00 su circa 19.000
// pagine: accesso perfettamente uniforme, ogni pagina una volta sola.
//
// Il cursore per-VU precedente rivisitava, perche' VU indipendenti si
// sovrappongono: a lambda=260 con alpha=0,5 il rapporto risultava circa
// 1,4, quindi il 28% delle richieste agentiche erano ripetizioni che la
// cache poteva servire. Questo GONFIA h_A e sottostima il costo.
//
// iterationInTest e' un contatore globale monotono su tutti i VU dello
// scenario. Mappato con una permutazione moltiplicativa (moltiplicatore
// coprimo con la dimensione del corpus, verificato) produce indici
// distinti finche' il numero di iterazioni resta sotto quella
// dimensione. Oltre, riavvolge: il rapporto req/url atteso e'
//
//     max(1, alpha * RATE * durata / total)
//
// e va riportato per ogni punto, perche' e' un limite di scala del
// testbed e non una proprieta' del modello.
function traversalIndex(data) {
  return permute(data.offset + exec.scenario.iterationInTest, data.total);
}

// -------------------------------------------------------------------------

export default function (data) {
  const agentic = MODEL === 'traversal' ||
                  (MODEL === 'mix' && Math.random() < ALPHA);

  let url;
  if (ENDPOINT === 'search') {
    url = `${TARGET}/search?q=${TERMS[Math.floor(Math.random() * TERMS.length)]}`;
  } else {
    const idx = agentic
      ? traversalIndex(data)
      : permute(zipfRank(data.total), data.total);
    const loc = locate(data, idx);
    url = `${TARGET}/book/${loc.book}/ch/${loc.n}`;
  }

  // Il transpiler di k6 non supporta lo spread negli oggetti: gli header
  // si costruiscono per assegnazione.
  const headers = {
    'User-Agent': agentic ? 'undertow-lowloc/1.0' : 'undertow-highloc/1.0',
  };
  // Il profilo umano negozia contenuto e lingua, quello agentico no.
  // Parametro secondario, registrato ma non variato in questa fase.
  if (!agentic) headers['Accept-Language'] = 'en-GB,en;q=0.9';

  const res = http.get(url, {
    headers: headers,
    tags: { profile: agentic ? 'agent' : 'human' },
  });

  check(res, { 'status 200': (r) => r.status === 200 });

  const hit = res.headers['X-Cache'] === 'HIT';
  if (agentic) {
    if (hit) hitTrav.add(1); else missTrav.add(1);
    latTrav.add(res.timings.duration);
  } else {
    if (hit) hitZipf.add(1); else missZipf.add(1);
    latZipf.add(res.timings.duration);
  }
}

export function handleSummary(data) {
  const out = {};
  out[`/results/${__ENV.OUTFILE || 'workload'}.json`] = JSON.stringify(data);
  return out;
}