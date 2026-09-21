"""Experiment: how few slots does the glyph graph really need?

Runs the real build with a randomized DSATUR (many restarts, best kept) and
prints the slot count it achieves.  Writes to temp output paths only.
"""
import sys, os, random
sys.path.insert(0, '.')
import cnbuild5 as cb

RESTARTS = int(os.environ.get('RESTARTS', '400'))
LIMIT = int(os.environ.get('LIMIT', '34'))     # slots the budget allows

def colour_best(self, windows):
    freq, wcount, cw = {}, {}, {}
    wsets = list(windows)
    for wi, w in enumerate(wsets):
        for ch in w:
            freq[ch] = freq.get(ch, 0) + 1
            wcount[ch] = wcount.get(ch, 0) + 1
            cw.setdefault(ch, []).append(wi)
    pre_fixed = {}
    for ch in cb.FIXED_CODES:
        pre_fixed[ch] = cb.FIXED_CODES[ch] - cb.FIXED0
    best = None
    for seed in range(RESTARTS):
        rnd = random.Random(seed)
        slot = dict(pre_fixed)
        load = [0] * LIMIT
        for s in slot.values():
            load[s] += 1
        satb = {ch: set() for ch in freq}
        for w in wsets:
            pre = {slot[c] for c in w if c in slot}
            if not pre:
                continue
            for c2 in w:
                if c2 in satb and c2 not in slot:
                    satb[c2] |= pre
        remaining = set(freq) - set(slot)
        ok = True
        while remaining:
            m = max(len(satb[c]) for c in remaining)
            cands = [c for c in remaining if len(satb[c]) == m]
            ch = rnd.choice(cands)
            free = [s for s in range(LIMIT) if s not in satb[ch]]
            if not free:
                ok = False
                break
            ml = min(load[s] for s in free)
            s = rnd.choice([x for x in free if load[x] == ml])
            slot[ch] = s
            load[s] += 1
            remaining.discard(ch)
            for wi in cw[ch]:
                for c2 in wsets[wi]:
                    if c2 in remaining:
                        satb[c2].add(s)
        if not ok:
            continue
        used = max(slot.values()) + 1
        if best is None or used < best[0]:
            best = (used, dict(slot), list(load))
    if best is None:
        raise ValueError('no colouring found within %d slots' % LIMIT)
    used, slot, load = best
    self.slot.clear(); self.slot.update(slot)
    for i in range(len(load)):
        self.load[i] = load[i]
    print('  [exp] best colouring uses %d slots' % used)
    return used

cb.Encoder.colour = colour_best
cb.OUT_ROM = cb.BASE + '/exp_out.smc'
cb.OUT_IPS = cb.BASE + '/exp_out.ips'
cb.main()
