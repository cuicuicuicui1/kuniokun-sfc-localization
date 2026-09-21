"""How few slots does the glyph graph need, per window size?

Patches Encoder.colour with a randomized DSATUR (many restarts, best kept) and
runs the real build, so the window search reports what each window size costs.
"""
import sys, os, random
sys.path.insert(0, '.')
import cnbuild5 as cb

RESTARTS = int(os.environ.get('RESTARTS', '120'))
LIMIT = None      # taken from the encoder's own slot count
seen = {}

FORCE_MAIN = int(os.environ.get('FORCE_MAIN', '0'))
FORCE_LIST = int(os.environ.get('FORCE_LIST', '0'))

def colour_best(self, windows):
    global LIMIT
    LIMIT = int(os.environ.get('LIMIT', '0')) or len(self.load)
    freq, wcount, cw = {}, {}, {}
    wsets = list(windows)
    for wi, w in enumerate(wsets):
        for ch in w:
            freq[ch] = freq.get(ch, 0) + 1
            wcount[ch] = wcount.get(ch, 0) + 1
            cw.setdefault(ch, []).append(wi)
    pre = {ch: cb.FIXED_CODES[ch] - cb.FIXED0 for ch in cb.FIXED_CODES}
    best = None
    for seed in range(RESTARTS):
        rnd = random.Random(seed)
        slot = dict(pre); load = [0] * LIMIT
        for s in slot.values(): load[s] += 1
        satb = {ch: set() for ch in freq}
        for w in wsets:
            p = {slot[c] for c in w if c in slot}
            if not p: continue
            for c2 in w:
                if c2 in satb and c2 not in slot: satb[c2] |= p
        rem = set(freq) - set(slot); ok = True
        while rem:
            m = max(len(satb[c]) for c in rem)
            ch = rnd.choice([c for c in rem if len(satb[c]) == m])
            free = [s for s in range(LIMIT) if s not in satb[ch]]
            if not free: ok = False; break
            ml = min(load[s] for s in free)
            s = rnd.choice([x for x in free if load[x] == ml])
            slot[ch] = s; load[s] += 1; rem.discard(ch)
            for wi in cw[ch]:
                for c2 in wsets[wi]:
                    if c2 in rem: satb[c2].add(s)
        if ok:
            used = max(slot.values()) + 1
            if best is None or used < best[0]: best = (used, dict(slot), list(load))
    if best is None:
        raise ValueError('no colouring within %d slots' % LIMIT)
    used, slot, load = best
    self.slot.clear(); self.slot.update(slot)
    for i in range(len(load)): self.load[i] = load[i]
    n = len(wsets)
    key = max(len(w) for w in wsets)
    if FORCE_LIST and n != 0:
        pass
    if key not in seen or used < seen[key][0]:
        seen[key] = (used, n)
    print('  [exp] %d windows, widest %d -> %d slots' % (n, key, used))
    return used

cb.Encoder.colour = colour_best
cb.OUT_ROM = cb.BASE + '/exp_out.smc'
cb.OUT_IPS = cb.BASE + '/exp_out.ips'
try:
    cb.main()
except SystemExit as e:
    print('build stopped: %s' % e)
print('best slots per widest-window size:')
for k in sorted(seen):
    print('   widest %2d glyphs -> %d slots' % (k, seen[k][0]))
