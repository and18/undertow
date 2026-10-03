"""
policies.py — replacement policies of phase 2 (docs/PREREG-simulatore-fase2.md, with
amendment 1), all with byte capacity, footprint = body bytes + H.

Common interface (as cache.LRU of phase 1):
    get(idx, now) -> True if hit; a miss tries to insert the object
    idx in cache  -> presence;  len(cache) -> objects;  cache.used -> bytes occupied

TTL: phase 2 uses TTL 86,400 s and each repetition lasts 920 s, so no object expires.
Here the TTL is not modelled; `get` checks that `now` stays below the TTL (assertion).

  SIEVE      Zhang, Yang, Yue, Vigfusson, Rashmi, NSDI '24, Algorithm 1.
  S3FIFO     Yang, Zhang, Qiu, Yue, Rashmi, SOSP '23, Algorithm 1 (amendment 1, point 1).
  WTinyLFU   Einziger, Friedman, Manes, ACM TOS 2017 (W-TinyLFU, reset) + Einziger, Eytan,
             Friedman, Manes, ACM TOS 2022, Algorithms 1 and 4 (Aggregated Victims;
             amendment 1, points 2 and 3).
"""
from collections import OrderedDict

from cache import CAPACITY, LRU, TTL  # noqa: F401  (LRU: the reference policy, unchanged)


def _check(now):
    assert now < TTL, "phase 2 does not model expiry: now must stay below the TTL"


# ------------------------------------------------------------------------------ SIEVE
class _Node:
    __slots__ = ("key", "visited", "newer", "older")

    def __init__(self, key):
        self.key, self.visited, self.newer, self.older = key, 0, None, None


class SIEVE:
    """A queue: head = newest, tail = oldest. `newer` is the paper's `prev`."""

    def __init__(self, sizes, h, capacity=CAPACITY):
        self.sizes, self.h, self.capacity = sizes, h, capacity
        self.nodes = {}
        self.head = self.tail = self.hand = None
        self.used = 0

    def __contains__(self, idx):
        return idx in self.nodes

    def __len__(self):
        return len(self.nodes)

    def _fp(self, idx):
        return self.sizes[idx] + self.h

    def _unlink(self, o):
        if o.newer is not None:
            o.newer.older = o.older
        else:
            self.head = o.older
        if o.older is not None:
            o.older.newer = o.newer
        else:
            self.tail = o.newer

    def _evict(self):
        o = self.hand if self.hand is not None else self.tail      # lines 5-7
        while o.visited:                                           # lines 8-12
            o.visited = 0
            o = o.newer
            if o is None:
                o = self.tail
        self.hand = o.newer                                        # line 13
        self._unlink(o)                                            # line 14
        del self.nodes[o.key]
        self.used -= self._fp(o.key)

    def get(self, idx, now):
        _check(now)
        o = self.nodes.get(idx)
        if o is not None:                                          # lines 1-2
            o.visited = 1
            return True
        fp = self._fp(idx)
        if fp > self.capacity:
            return False
        while self.used + fp > self.capacity:                      # by bytes: until it fits
            self._evict()
        o = _Node(idx)                                             # lines 15-16
        o.older = self.head
        if self.head is not None:
            self.head.newer = o
        self.head = o
        if self.tail is None:
            self.tail = o
        self.nodes[idx] = o
        self.used += fp
        return False


# ----------------------------------------------------------------------------- S3-FIFO
class S3FIFO:
    """OrderedDict: first element = tail (oldest), last = head."""

    def __init__(self, sizes, h, capacity=CAPACITY):
        self.sizes, self.h, self.capacity = sizes, h, capacity
        self.S, self.M, self.G = OrderedDict(), OrderedDict(), OrderedDict()
        self.freq = {}
        self.size_s = self.size_m = 0
        self.guard = 0          # times evictM finds nothing and falls back to evictS

    @property
    def used(self):
        return self.size_s + self.size_m

    def __contains__(self, idx):
        return idx in self.S or idx in self.M

    def __len__(self):
        return len(self.S) + len(self.M)

    def _fp(self, idx):
        return self.sizes[idx] + self.h

    def _to_ghost(self, t):
        self.G[t] = None
        while len(self.G) > len(self.M):        # G: as many keys as objects in M
            self.G.popitem(last=False)

    def _evict_s(self):                                            # lines 19-30
        evicted = False
        while not evicted and self.S:
            t, _ = self.S.popitem(last=False)
            fp = self._fp(t)
            self.size_s -= fp
            if self.freq[t] > 1:
                self.M[t] = None
                self.size_m += fp
                self.freq[t] = 0                # «access bits are cleared during the move»
                if self.size_m > 0.9 * self.capacity:
                    self._evict_m()
            else:
                del self.freq[t]
                self._to_ghost(t)
                evicted = True
        return evicted

    def _evict_m(self):                                            # lines 31-40
        evicted = False
        while not evicted and self.M:
            t = next(iter(self.M))
            if self.freq[t] > 0:
                self.M.move_to_end(t)
                self.freq[t] -= 1
            else:
                del self.M[t]
                del self.freq[t]
                self.size_m -= self._fp(t)
                evicted = True
        return evicted

    def _evict(self):                                              # lines 14-18
        if self.size_s >= 0.1 * self.capacity:
            self._evict_s()
        elif not self._evict_m():
            self.guard += 1
            self._evict_s()

    def get(self, idx, now):
        _check(now)
        if idx in self.S or idx in self.M:                         # lines 2-3
            self.freq[idx] = min(self.freq[idx] + 1, 3)
            return True
        fp = self._fp(idx)                                         # lines 5-13
        if fp > self.capacity:
            return False
        while self.used + fp > self.capacity:
            self._evict()
        if idx in self.G:
            del self.G[idx]
            self.M[idx] = None
            self.size_m += fp
        else:
            self.S[idx] = None
            self.size_s += fp
        self.freq[idx] = 0
        return False


# --------------------------------------------------------------------------- W-TinyLFU
_M64 = (1 << 64) - 1


def _mix(x):
    """splitmix64: deterministic hash."""
    x = (x + 0x9E3779B97F4A7C15) & _M64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _M64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _M64
    return x ^ (x >> 31)


class CountMin:
    """4 rows x 32,768, seeds 1..4, cap W/C = 10, reset: after W increments all the
    counters and the sample counter are halved (TinyLFU §3.3: «we divide it and all
    other counters in the approximation sketch by 2»)."""

    def __init__(self, sample, cap=10, width=32768, seeds=(1, 2, 3, 4)):
        self.sample, self.cap, self.width, self.seeds = sample, cap, width, seeds
        self.rows = [[0] * width for _ in seeds]
        self.count = 0
        self.resets = 0

    def _cols(self, x):
        if not isinstance(x, int):              # test keys (letters): deterministic integer
            x = int.from_bytes(str(x).encode(), "little")
        return [_mix(x * 0x100000001B3 + s) % self.width for s in self.seeds]

    def add(self, x):
        for row, c in zip(self.rows, self._cols(x)):
            if row[c] < self.cap:
                row[c] += 1
        self.count += 1
        if self.count >= self.sample:
            for row in self.rows:
                for i, v in enumerate(row):
                    if v:
                        row[i] = v >> 1
            self.count >>= 1
            self.resets += 1

    def estimate(self, x):
        return min(row[c] for row, c in zip(self.rows, self._cols(x)))


class WTinyLFU:
    """LRU window 1% + SLRU main 99% (protected 80%, probation 20%), size-aware
    TinyLFU admission «Aggregated Victims». OrderedDict: first = LRU, last = MRU."""

    def __init__(self, sizes, h, capacity=CAPACITY, sample=10 * 5263):
        self.sizes, self.h, self.capacity = sizes, h, capacity
        self.win_cap = capacity // 100
        self.main_cap = capacity - self.win_cap
        self.prot_cap = self.main_cap * 8 // 10
        self.win, self.prob, self.prot = OrderedDict(), OrderedDict(), OrderedDict()
        self.size_w = self.size_prob = self.size_prot = 0
        self.sketch = CountMin(sample)
        self.rejected = 0

    @property
    def used(self):
        return self.size_w + self.size_prob + self.size_prot

    def __contains__(self, idx):
        return idx in self.win or idx in self.prob or idx in self.prot

    def __len__(self):
        return len(self.win) + len(self.prob) + len(self.prot)

    def _fp(self, idx):
        return self.sizes[idx] + self.h

    def _to_protected(self, x):
        """x (already removed from where it was) at the head of protected; the excess goes back to probation."""
        fp = self._fp(x)
        self.prot[x] = None
        self.size_prot += fp
        while self.size_prot > self.prot_cap:
            y, _ = self.prot.popitem(last=False)
            fy = self._fp(y)
            self.size_prot -= fy
            self.prob[y] = None
            self.size_prob += fy

    def _promote(self, v):
        """As an access in the SLRU: probation -> head of protected; protected -> head."""
        if v in self.prob:
            del self.prob[v]
            self.size_prob -= self._fp(v)
            self._to_protected(v)
        elif v in self.prot:
            self.prot.move_to_end(v)

    def _victims(self):
        """Eviction order of the main: tail of probation, then tail of protected."""
        yield from self.prob
        yield from self.prot

    def _evict_or_admit(self, c):                                  # Algorithm 4 (AV)
        fp = self._fp(c)
        need = self.size_prob + self.size_prot + fp - self.main_cap
        victims, vsize, vfreq = [], 0, 0
        fc = self.sketch.estimate(c)
        if need > 0:
            for v in self._victims():                              # lines 3-7
                victims.append(v)
                vsize += self._fp(v)
                vfreq += self.sketch.estimate(v)
                if fc < vfreq:
                    break                                          # early pruning
                if vsize >= need:
                    break
        if fc >= vfreq and vsize >= need:                          # lines 8-11
            for v in victims:
                if v in self.prob:
                    del self.prob[v]
                    self.size_prob -= self._fp(v)
                else:
                    del self.prot[v]
                    self.size_prot -= self._fp(v)
            self.prob[c] = None
            self.size_prob += fp
        else:                                                      # lines 12-15
            for v in victims:
                self._promote(v)
            self.rejected += 1

    def get(self, idx, now):
        _check(now)
        self.sketch.add(idx)                     # every request increments the sketch
        if idx in self.win:
            self.win.move_to_end(idx)
            return True
        if idx in self.prob:
            self._promote(idx)
            return True
        if idx in self.prot:
            self.prot.move_to_end(idx)
            return True
        fp = self._fp(idx)                                         # Algorithm 1
        if fp > self.capacity:
            return False
        candidates = []
        if fp > self.win_cap:
            candidates.append(idx)
        else:
            self.win[idx] = None
            self.size_w += fp
            while self.size_w > self.win_cap:
                c, _ = self.win.popitem(last=False)
                self.size_w -= self._fp(c)
                candidates.append(c)
        for c in candidates:
            self._evict_or_admit(c)
        return False


POLICIES = {"LRU": LRU, "SIEVE": SIEVE, "S3FIFO": S3FIFO, "WTinyLFU": WTinyLFU}
