"""
cache.py — LRU a capienza in byte: riproduzione di harness/varnish/default.vcl.tpl con
`-s malloc,128m` (docs/PREREG-simulatore-fase1.md, «Cache»).

  - chiave = indice di capitolo (URL, nessuna normalizzazione, nessun Vary);
  - miss: inserimento in testa, sfratto dalla coda finche' c'e' spazio;
  - hit: l'oggetto passa in testa (LRU esatto; Varnish usa lru_interval = 2 s);
  - footprint = byte del corpo + H;
  - TTL: scadenza assoluta, controllata al momento della richiesta (86 400 s: nella fase 1
    non scade mai dentro una ripetizione).
"""
from collections import OrderedDict

CAPACITY = 134_217_728   # 128 MiB
TTL = 86_400


class LRU:
    def __init__(self, sizes, h, capacity=CAPACITY, ttl=TTL):
        self.sizes, self.h, self.capacity, self.ttl = sizes, h, capacity, ttl
        self.d = OrderedDict()               # idx -> scadenza
        self.used = 0

    def get(self, idx, now):
        """True se hit. Un miss inserisce l'oggetto."""
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
