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
import { sleep } from 'k6';

const TARGET   = __ENV.TARGET   || 'http://varnish:80';
const MODEL    = __ENV.MODEL    || 'mix';
const ALPHA    = parseFloat(__ENV.ALPHA || '0.5');
const RATE     = parseInt(__ENV.RATE || '800');
const DURATION = __ENV.DURATION || '300s';
const ENDPOINT = __ENV.ENDPOINT || 'chapter';
const SEED     = parseInt(__ENV.SEED || '42');

// Terza classe: agentica. Un agente che risponde a una persona in tempo
// reale non e' ne' un umano che naviga ne' un crawler che scandisce.
// Calibrata sull'honeypot (findings H6, H9): gli operatori agentici
// reali coprono il 2,1-6,1% del sito con Gini 0,38-0,42 e chiedono ogni
// URL 2,1-3,7 volte. Quindi: insieme ristretto di argomenti, popolarita'
// moderatamente concentrata, sessioni corte su capitoli contigui.
//
// BETA e' la quota agentica, ALPHA quella esaustiva, il resto e' Zipf.
// Il ritmo TOTALE resta costante, come per ALPHA.
const BETA          = parseFloat(__ENV.BETA || '0');
// 0,02 e non 0,05: la sessione espande ogni base in AGENT_SESSION
// capitoli contigui, quindi la copertura effettiva e' il triplo dello
// scope. A 0,05 il collaudo ha dato 11,6% contro il 2,1-6,1% misurato
// sugli operatori agentici reali (findings H6).
const AGENT_SCOPE   = parseFloat(__ENV.AGENT_SCOPE || '0.02');
const AGENT_SESSION = parseInt(__ENV.AGENT_SESSION || '3');
const AGENT_SKEW    = parseFloat(__ENV.AGENT_SKEW || '0.6');

// Moltiplicatore della permutazione per la classe agentica. Il default
// e' lo stesso della classe umana, quindi riproduce i run fino al 19
// settembre 2026. Con un valore diverso l'insieme di lavoro agentico
// cade in una regione del corpus scorrelata dal rango di popolarita'
// umano, e la sovrapposizione fra le due classi passa da "per
// costruzione" a "incidentale".
//
// Deve essere dispari e coprimo con la dimensione del corpus
// (16954 = 2 x 7^2 x 173), altrimenti la mappa non e' una permutazione.
// Valore separato verificato: 3266489917.
const AGENT_MUL     = parseInt(__ENV.AGENT_MUL || '2654435761');

if (ALPHA + BETA > 1.0000001) {
  throw new Error(`ALPHA(${ALPHA}) + BETA(${BETA}) supera 1`);
}

// Sfasamento della traversata, in iterazioni. Warm-up e misura sono due
// invocazioni k6 separate, quindi iterationInTest riparte da zero e la
// misura ripercorrerebbe la sequenza appena percorsa dal warm-up: ogni
// richiesta sarebbe una seconda visita a un oggetto inserito esattamente
// WARMUP secondi prima, e l'hit ratio misurato sarebbe la curva di
// sopravvivenza della cache invece del passaggio gratuito.
const TRAV_SKIP = parseInt(__ENV.TRAV_SKIP || '0');

const TERMS = (__ENV.TERMS ||
  'nurse,window,trial,servant,kiss,garden,letter,prayer,horse,silence'
).split(',');

// Metriche separate per classe: l'hit ratio va attribuito al profilo che
// lo ha generato, non solo aggregato.
const hitZipf  = new Counter('ut_hit_zipf');
const missZipf = new Counter('ut_miss_zipf');
const hitTrav  = new Counter('ut_hit_traversal');
const missTrav = new Counter('ut_miss_traversal');
const okZipf   = new Counter('ut_ok_zipf');
const okTrav   = new Counter('ut_ok_traversal');
const shedZipf = new Counter('ut_shed_zipf');
const shedTrav = new Counter('ut_shed_traversal');
// Il rinvio non e' una perdita se il client torna. Un crawler batch puo'
// permettersi di riprovare fra due secondi: nessuno sta aspettando. Nella
// campagna del 2026-08-28 il generatore non riprovava, quindi ogni 503
// appariva come lavoro perso e il budget sembrava costare il 12,6% del
// throughput batch. I ritenti si contano separatamente dai primi
// tentativi, altrimenti il carico offerto non sarebbe piu' confrontabile
// con il riferimento.
const retriedTrav   = new Counter('ut_retried_traversal');
const abandonedTrav = new Counter('ut_abandoned_traversal');

// RETRY_MAX=0 riproduce il comportamento precedente ed e' la
// configurazione di riferimento.
const RETRY_MAX = parseInt(__ENV.RETRY_MAX || '0');
const RETRY_CAP = parseFloat(__ENV.RETRY_CAP || '5');   // secondi
const latZipf  = new Trend('ut_lat_zipf', true);
const latTrav  = new Trend('ut_lat_traversal', true);
const hitAgent  = new Counter('ut_hit_agent');
const missAgent = new Counter('ut_miss_agent');
const okAgent   = new Counter('ut_ok_agent');
const shedAgent = new Counter('ut_shed_agent');
const latAgent  = new Trend('ut_lat_agent', true);
// Con BLOCK_CLASSES attivo una richiesta rifiutata torna 403, che oggi
// non incrementa ne' ok ne' miss: senza questi contatori l'hit ratio
// di una classe bloccata risulterebbe 1,000 perche' solo gli hit
// producono ancora un 200.
const blkZipf  = new Counter('ut_blk_zipf');
const blkAgent = new Counter('ut_blk_agent');
const blkTrav  = new Counter('ut_blk_traversal');

// Stato di sessione, per VU. In k6 le variabili di modulo sono locali al
// VU, quindi ogni VU porta avanti la propria sessione fra iterazioni.
let agSession = null;

// Zipf(AGENT_SKEW) su un sottoinsieme del corpus, per trasformata
// inversa. Per s<1 vale CDF(r) = (r/N)^(1-s), quindi r = N*u^(1/(1-s)).
// Con s=0,6 l'esponente e' 2,5. Base della sessione = quel rango mappato
// a un capitolo; i successivi sono contigui, cioe' lo stesso libro.
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

// TRAV_MODE: come la classe esaustiva sceglie il capitolo.
//
//   glob (default, TRAV_MODE assente)  come tutti i run fino al 28 settembre
//        2026: un solo scenario; l'indice della traversata e' iterationInTest
//        di quello scenario, che conta le iterazioni di TUTTE le classi. Lo
//        stesso capitolo torna ogni N iterazioni totali, cioe' ogni N/RATE
//        secondi: a parita' di ALPHA*RATE il percorso esaustivo dipende da RATE
//        (fase 2b del simulatore, docs/PREREG-simulatore-fase2b.md).
//   scen l'esaustiva e' uno scenario proprio a rate ALPHA*RATE: il suo
//        iterationInTest conta solo le richieste esaustive, quindi lo stesso
//        capitolo torna ogni N/(ALPHA*RATE) secondi qualunque sia RATE. Umana e
//        agentica stanno nello scenario "load" a rate (1-ALPHA)*RATE, con
//        agentica a probabilita' BETA/(1-ALPHA). Gli arrivi esaustivi diventano
//        regolari invece che estratti a caso. docs/PREREG-lab-trav-own-20260928.md.
//
// constant-arrival-rate vuole un rate intero: in scen i rate sono espressi
// per 10 000 s (scarto di arrotondamento < 1e-5 req/s).
const TRAV_MODE = __ENV.TRAV_MODE || 'glob';
if (TRAV_MODE !== 'glob' && TRAV_MODE !== 'scen') {
  throw new Error(`TRAV_MODE=${TRAV_MODE}: valori ammessi glob, scen`);
}
const SCEN = TRAV_MODE === 'scen' && MODEL === 'mix' && ALPHA > 0;
if (TRAV_MODE === 'scen' && !SCEN) {
  throw new Error('TRAV_MODE=scen richiede MODEL=mix e ALPHA > 0');
}
const SCEN_UNIT = 10000;
const RATE_TRAV = Math.round(ALPHA * RATE * SCEN_UNIT);
const RATE_REST = Math.round((1 - ALPHA) * RATE * SCEN_UNIT);

function arrival(rate, timeUnit, perSecond, exec) {
  const s = {
    executor: 'constant-arrival-rate',     // open loop, obbligatorio
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
  const g = (a, b) => { while (b) { [a, b] = [b, a % b]; } return a; };
  if (g(TRAV_MUL % total, total) !== 1) {
    throw new Error(`TRAV_MUL non coprimo con ${total}: la traversata non copre il corpus`);
  }
  return {
    ids: ids, cum: cum, total: total,
    // Offset deterministico, dal seed dell'esperimento.
    // Un offset casuale rende l'hit ratio della classe a bassa localita'
    // non riproducibile tra run altrimenti identici.
    offset: (SEED * 7919) % total,
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
// Permutazione della sola classe agentica: vedi AGENT_MUL.
function permuteAgent(rank, N) {
  return (rank * AGENT_MUL + SEED) % N;
}

function permute(rank, N) {
  return (rank * 2654435761 + SEED) % N;
}

// Moltiplicatore distinto da quello di permute(). Con lo stesso, l'argomento
// della traversata E' il rango di popolarita': lo scanner percorre il corpus
// in ordine di popolarita' decrescente, e hit_bassa dipende da quale finestra
// di ranghi la misura attraversa — cioe' da TRAV_SKIP, cioe' da WARMUP.
// Firma del 6 settembre, blocco B: 0,254 / 0,267 / 0,159 a warm-up 120/300/600
// con configurazione altrimenti identica.
const TRAV_MUL = 2246822519;

function permuteTrav(i, N) {
  return ((i % N) * (TRAV_MUL % N) + SEED * 7919) % N;
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
  return permuteTrav(data.offset + TRAV_SKIP + exec.scenario.iterationInTest, data.total);
}

// -------------------------------------------------------------------------

export default function (data) {
  // Un solo sorteggio per la ripartizione a tre vie: due sorteggi
  // indipendenti introdurrebbero correlazione fra le classi.
  // Con TRAV_MODE=scen questo scenario porta solo umana e agentica.
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

// Scenario "trav" di TRAV_MODE=scen: ogni iterazione e' una richiesta
// esaustiva; traversalIndex legge l'iterationInTest di questo scenario.
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

  // Solo la classe batch riprova, e solo sul 503 del budget.
  let attempts = 0;
  while (agentic && res.status === 503 && attempts < RETRY_MAX) {
    shedTrav.add(1);
    // Retry-After in secondi; il server invia 2. Il limite superiore
    // evita che un valore anomalo blocchi il VU.
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
    // La classe agentica non riprova: c'e' una persona che aspetta.
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
      // Ancora rinviata dopo l'ultimo tentativo: questa e' persa davvero.
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