"""
cache.py — LRU with byte capacity: reproduction of harness/varnish/default.vcl.tpl with
`-s malloc,128m` (docs/PREREG-simulatore-fase1.md, «Cache»).

  - key = chapter index (URL, no normalisation, no Vary);
  - miss: insertion at the head, eviction from the tail until there is room;
  - hit: the object moves to the head (exact LRU; Varnish uses lru_interval = 2 s);
  - footprint = body bytes + H;
  - TTL: absolute expiry, checked at request time (86,400 s: in phase 1 it
    never expires within a repetition).
"""
from collections import OrderedDict

CAPACITY = 134_217_728   # 128 MiB
TTL = 86_400


class LRU:
    def __init__(self, sizes, h, capacity=CAPACITY, ttl=TTL):
        self.sizes, self.h, self.capacity, self.ttl = sizes, h, capacity, ttl
        self.d = OrderedDict()               # idx -> expiry
        self.used = 0

    def get(self, idx, now):
        """True if hit. A miss inserts the object."""
        exp = self.d.get(idx)
        if exp is not None:
            if now < exp:
                self.d.move_to_end(idx)
                return True
            del self.d[idx]
            self.used -= self.sizes[idx] + self.h
        fp = self.sizes[idx] + self.h
        if fp > self.capacity:
            return False
        while self.used + fp > self.capacity:
            old, _ = self.d.popitem(last=False)
            self.used -= self.sizes[old] + self.h
        self.d[idx] = now + self.ttl
        self.used += fp
        return False

    def __len__(self):
        return len(self.d)
