"""Find text pointer tables using the 'string ends with F2 xx' structural signal."""
import struct, json
from collections import defaultdict
import kuniokun_map as M

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
N = len(d)

def scan_u16(minlen=6, maxlen=1200):
    cands = []
    for base in range(0, N - 2 * minlen):
        prev = -1; L = 0
        while L < maxlen:
            o = base + 2 * L
            if o + 2 > N: break
            v = d[o] | (d[o + 1] << 8)
            if v <= prev or v < 0x8000: break
            prev = v; L += 1
        if L >= minlen:
            cands.append((base, L))
    return cands

def boundary_score(base, L, bank, sample=80):
    """fraction of consecutive-pointer boundaries where byte before next ptr is F2."""
    vals = []
    for i in range(min(L, sample) + 1):
        o = base + 2 * i
        if o + 2 > N: break
        vals.append(d[o] | (d[o + 1] << 8))
    ok = 0; tot = 0
    for i in range(len(vals) - 1):
        nxt = bank * 0x8000 + (vals[i + 1] - 0x8000)
        if 0 <= nxt - 2 < N and d[nxt - 2] == 0xF2:
            ok += 1
        tot += 1
    return ok / tot if tot else 0.0

print('scanning ...')
raw = scan_u16()
print('raw', len(raw))

passed = []
for base, L in raw:
    best = (0.0, None)
    for bank in range(32):
        s = boundary_score(base, L, bank)
        if s > best[0]:
            best = (s, bank)
    if best[0] >= 0.6 and L >= 8:
        passed.append((base, L, best[1], best[0]))

# dedupe: drop candidates whose table byte-range overlaps a stronger candidate
passed.sort(key=lambda x: -(x[1] * x[3]))
kept = []
for c in passed:
    b, L = c[0], c[1]
    ov = False
    for k in kept:
        kb, kL = k[0], k[1]
        if b < kb + 2 * kL and kb < b + 2 * L:   # overlap
            ov = True; break
    if not ov:
        kept.append(c)

print('\nkept tables (%d):' % len(kept))
for base, L, bank, s in sorted(kept, key=lambda x: x[0]):
    vals = [d[base + 2 * i] | (d[base + 2 * i + 1] << 8) for i in range(min(L, 3))]
    tgt0 = bank * 0x8000 + (vals[0] - 0x8000)
    lastv = d[base + 2 * (L - 1)] | (d[base + 2 * (L - 1) + 1] << 8)
    tgtN = bank * 0x8000 + (lastv - 0x8000)
    print('  tbl=%06X len=%3d bank=%2d score=%.2f  targets %06X..%06X  first=%s' %
          (base, L, bank, s, tgt0, tgtN, ' '.join('%04X' % v for v in vals)))
